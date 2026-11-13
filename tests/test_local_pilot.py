"""Pilot windows, estimators, safeguards and archived reexecution parameters."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

import numpy as np
import pandas as pd
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_analysis import execute
from local_export import build_bundle
from local_provenance import attach_provenance, result_digest


def parameters(kind="continuous", **changes):
    value = {"kind": kind, "direction": "decrease", "target": 9 if kind == "continuous" else 3,
             "before_start": "2026-01-01", "before_end": "2026-01-10",
             "after_start": "2026-02-01", "after_end": "2026-02-10",
             "independence_confirmed": True, "comparability_confirmed": True,
             "indicator": "Tempo" if kind == "continuous" else "Refugo",
             "definition": "Mesma definição operacional e população nas duas janelas fictícias.",
             "unit": "min" if kind == "continuous" else "%", "comparability_notes": "Caso fictício: revisar mix, medição e outras mudanças.",
             "action_id": "acao-ficticia", "action_label": "Testar procedimento de setup"}
    return dict(value, **changes)


def continuous(before=(10, 11, 12, 13), after=(7, 8, 9, 10)):
    return pd.DataFrame({"Data": ["2026-01-02"]*len(before) + ["2026-02-02"]*len(after), "Valor": [*before, *after]})


def run(frame=None, config=None):
    return execute(continuous() if frame is None else frame, {"data": "Data", "medida": "Valor"}, "piloto", parameters=parameters() if config is None else config)


def test_welch_difference_and_confidence_match_scipy():
    before = np.array([10, 11, 13, 14, 20], dtype=float)
    after = np.array([4, 5, 6, 7], dtype=float)
    result = run(continuous(before, after))
    pilot = result["piloto"]
    reference = stats.ttest_ind(after, before, equal_var=False)
    interval = reference.confidence_interval()
    assert pilot["difference"]["estimate"] == pytest.approx(after.mean()-before.mean())
    assert pilot["difference"]["ci95"] == pytest.approx([interval.low, interval.high])
    assert pilot["difference"]["pvalue"] == pytest.approx(reference.pvalue)
    assert pilot["difference"]["df"] == pytest.approx(reference.df)
    assert pilot["before"]["n"] == 5 and pilot["after"]["n"] == 4
    assert pilot["target"]["point_met"] is True
    assert pilot["causal_effect_established"] is False
    assert "depois − antes" in result["metodo"]


def test_proportion_uses_total_denominators_and_newcombe_score_interval():
    frame = pd.DataFrame({"Data": ["2026-01-01", "2026-01-10", "2026-02-01", "2026-02-10"],
                          "Ruins": [1, 9, 0, 2], "Total": [10, 90, 2, 98]})
    result = execute(frame, {"data": "Data", "defeitos": "Ruins", "total": "Total"}, "piloto", parameters=parameters("proportion"))
    pilot = result["piloto"]
    assert pilot["before"]["estimate"] == 10
    assert pilot["after"]["estimate"] == 2  # Not mean(0/2, 2/98).
    assert pilot["difference"]["estimate"] == -8
    # Independent score roots from SciPy, combined directly by Newcombe's formula.
    a = stats.binomtest(2, 100).proportion_ci(method="wilson")
    b = stats.binomtest(10, 100).proportion_ci(method="wilson")
    expected = [-8-100*np.hypot(0.02-a.low, b.high-0.1), -8+100*np.hypot(a.high-0.02, 0.1-b.low)]
    assert pilot["difference"]["ci95"] == pytest.approx(expected)
    assert pilot["target"]["point_met"] is True
    assert "pontos percentuais" in result["indicadores"][2][0]
    assert pilot["difference"]["pvalue"] is None
    assert "não aprova" in " ".join(result["observacoes"])


@pytest.mark.parametrize(("before", "after"), [(0, 0), (10, 10), (0, 10), (10, 0)])
def test_boundary_proportions_do_not_imply_zero_uncertainty(before, after):
    frame = pd.DataFrame({"Data": ["2026-01-02", "2026-02-02"], "Ruins": [before, after], "Total": [10, 10]})
    result = execute(frame, {"data": "Data", "defeitos": "Ruins", "total": "Total"}, "piloto", parameters=parameters("proportion"))
    diff = result["piloto"]["difference"]
    assert -100 <= diff["ci95"][0] < diff["ci95"][1] <= 100
    for period in ("before", "after"):
        summary = result["piloto"][period]
        assert summary["ci95"][0] < summary["ci95"][1]


def test_both_zero_variances_produce_description_and_unavailable_intervals():
    result = run(continuous([10, 10], [8, 8]))
    pilot = result["piloto"]
    assert pilot["difference"]["ci95"] is None
    assert pilot["difference"]["pvalue"] is None
    assert pilot["after"]["ci95"] is None
    assert pilot["target"]["uncertainty"] == "not_estimated"
    assert result["grafico"]["itens"][0]["lower"] is None
    assert "apenas descritiva" in " ".join(result["evidencias"])


def test_one_zero_variance_keeps_valid_welch_but_not_degenerate_mean_interval():
    before, after = [10, 10, 10], [6, 7, 9, 10]
    result = run(continuous(before, after))
    expected = stats.ttest_ind(after, before, equal_var=False).confidence_interval()
    assert result["piloto"]["before"]["ci95"] is None
    assert result["piloto"]["difference"]["ci95"] == pytest.approx([expected.low, expected.high])


def test_calendar_windows_include_end_of_day_and_exclude_transition_explicitly():
    frame = pd.DataFrame({"Data": ["01/01/2026", "10/01/2026 23:59:59", "2026-01-20", "2026-02-01", "2026-02-10T23:59:59"],
                          "Valor": [10, 12, None, 8, 10]})
    result = run(frame)
    assert result["piloto"]["selected_rows"] == 4
    assert result["piloto"]["excluded_rows"] == 1
    assert result["piloto"]["before"]["estimate"] == 11
    assert result["piloto"]["after"]["estimate"] == 9
    assert result["piloto"]["target"]["point_met"] is True  # Equality meets <=.
    assert result["piloto"]["target"]["uncertainty"] == "crosses"


def test_duplicate_dataframe_indices_do_not_duplicate_window_membership():
    frame = continuous([10, 12], [8, 10])
    frame.index = [1, 1, 2, 2]
    result = run(frame)
    assert result["piloto"]["selected_rows"] == 4
    assert result["piloto"]["difference"]["estimate"] == -2


@pytest.mark.parametrize("changes", [
    {"before_end": "2026-02-01"}, {"after_start": "2026-01-10"},
    {"before_start": "2026-01-11"}, {"before_end": "2026-02-30"}, {"after_start": "01/02/2026"},
    {"independence_confirmed": False}, {"independence_confirmed": "true"},
    {"comparability_confirmed": False}, {"comparability_notes": " "},
    {"definition": ""}, {"unit": ""}, {"target": None}, {"target": True}, {"target": float("nan")},
    {"action_id": "", "action_label": "Named without identity"},
])
def test_invalid_plan_is_refused(changes):
    with pytest.raises(ValueError):
        run(config=parameters(**changes))


@pytest.mark.parametrize("values", [None, "invalid", "01-02-2026", 123, "2026-02-02T10:00:00Z"])
def test_ambiguous_missing_or_timezone_dates_are_not_silently_excluded(values):
    frame = continuous()
    frame.loc[0, "Data"] = values
    with pytest.raises(ValueError):
        run(frame)


@pytest.mark.parametrize(("defective", "total"), [(-1, 10), (11, 10), (1.5, 10), (1, 0), (None, 10), (True, 10), (1, 2**53)])
def test_bad_proportion_counts_are_refused(defective, total):
    frame = pd.DataFrame({"Data": ["2026-01-02", "2026-02-02"], "Ruins": [defective, 1], "Total": [total, 10]})
    with pytest.raises(ValueError):
        execute(frame, {"data": "Data", "defeitos": "Ruins", "total": "Total"}, "piloto", parameters=parameters("proportion"))


def test_missing_or_short_windows_and_changed_direction_are_handled():
    with pytest.raises(ValueError, match="duas medições"):
        run(continuous([10], [8, 9]))
    with pytest.raises(ValueError, match="Cada janela"):
        run(config=parameters(after_start="2027-01-01", after_end="2027-01-10"))
    value = run(config=parameters(direction="increase", target=9))
    assert value["piloto"]["target"]["point_met"] is False
    assert "retome a investigação" in value["proximo_passo"]


def test_pilot_export_and_reproduction_keep_executed_parameters_over_current_plan(tmp_path):
    frame = continuous()
    raw = frame.to_csv(index=False).encode()
    config = parameters()
    mapping = {"data": "Data", "medida": "Valor"}
    result = execute(frame, mapping, "piloto", parameters=config)
    attach_provenance(result, raw, mapping, "piloto", len(frame), parameters=config)
    original = copy.deepcopy(result)
    value = {"id": str(uuid.uuid4()), "version": 1, "filename": "piloto.csv", "title": "Piloto fictício",
             "dataset_sha256": hashlib.sha256(raw).hexdigest(), "file_base64": base64.b64encode(raw).decode(),
             "mapping": mapping, "analyses": {"piloto": result}, "investigation": {"pilot": parameters(target=0)}}
    with zipfile.ZipFile(io.BytesIO(build_bundle(value))) as bundle:
        rerun = json.loads(bundle.read("reexecucoes/analise_01.json"))
        assert rerun["piloto"]["parameters"]["target"] == 9
        assert rerun["rastreabilidade"]["parameters"]["target"] == 9
        assert rerun["piloto"]["target"]["point_met"] is True
        assert json.loads(bundle.read("reproduzir.json"))["analyses"][0]["parameters"]["target"] == 9
        assert json.loads(bundle.read("analises_salvas/analise_01.json")) == original
        assert result_digest(original) == original["rastreabilidade"]["result_sha256"]
        bundle.extractall(tmp_path)
    process = subprocess.run([sys.executable, str(tmp_path / "reproduzir_analises.py")], capture_output=True, timeout=30)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    comparison = json.loads((tmp_path / "reproduzidos/comparacao.json").read_text(encoding="utf-8"))
    assert comparison["analyses"] == [{"scenario": "piloto", "identical_result": True}]
