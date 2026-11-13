"""Known-value and independent-reference checks for right-censored KM."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_survival import kaplan_meier
from local_analysis import execute
from local_diagnosis import diagnose


def test_tied_failure_and_censor_keep_censor_in_risk_set():
    result = kaplan_meier([2, 2, 3, 4], [1, 0, 1, 0])
    assert [row["risco"] for row in result["tabela"]] == [4, 2, 1]
    assert [row["sobrevivencia"] for row in result["tabela"]] == pytest.approx([.75, .375, .375])
    assert result["tabela"][0]["inferior"] == pytest.approx(.12794691759514576)
    assert result["tabela"][0]["superior"] == pytest.approx(.9605486422850784)
    assert result["tabela"][1]["inferior"] == pytest.approx(.010971121574844577)
    assert result["tabela"][1]["superior"] == pytest.approx(.8080010724813435)
    assert result["mediana"] == 3
    assert result["rmst"] == pytest.approx(3.125)


@pytest.mark.parametrize("times, events, survival, median, rmst", [
    ([1, 2, 3, 4], [1, 1, 1, 1], [.75, .5, .25, 0], 2, 2.5),
    ([0, 2, 5], [0, 0, 0], [1, 1, 1], None, 5),
    ([0, 0, 2], [1, 0, 1], [2/3, 0], 2, 4/3),
    ([5, 5, 5], [1, 1, 1], [0], 5, 5),
])
def test_boundaries_and_median_definition(times, events, survival, median, rmst):
    result = kaplan_meier(times, events)
    assert [row["sobrevivencia"] for row in result["tabela"]] == pytest.approx(survival)
    assert result["mediana"] == median
    assert result["rmst"] == pytest.approx(rmst)
    for row in result["tabela"]:
        if row["sobrevivencia"] in (0, 1):
            assert row["inferior"] is None and row["superior"] is None


def test_matches_scipy_censored_ecdf_reference():
    if not hasattr(stats, "ecdf"):
        pytest.skip("Independent SciPy reference requires ecdf in this version")
    failures = np.asarray([77, 47, 81, 56, 80], dtype=float)
    censored = np.asarray([62, 60, 43, 71, 37], dtype=float)
    result = kaplan_meier(np.r_[failures, censored], [1]*5 + [0]*5)
    reference = stats.ecdf(stats.CensoredData(uncensored=failures, right=censored)).sf
    assert [row["tempo"] for row in result["tabela"]] == pytest.approx(reference.quantiles)
    assert [row["sobrevivencia"] for row in result["tabela"]] == pytest.approx(reference.probabilities)
    assert result["mediana"] == 77
    assert result["rmst"] == pytest.approx(72.375)


@pytest.mark.parametrize("times, events", [
    ([1], [1]), ([1, 2], [0]), ([1, -1], [1, 0]), ([0, 0], [1, 0]),
    ([1, np.inf], [1, 0]), ([1, 2], [0, np.nan]), ([1, 2], [1, 2]),
])
def test_rejects_invalid_followup_and_ambiguous_status(times, events):
    with pytest.raises(ValueError):
        kaplan_meier(times, events)


def test_local_scenario_and_failure_counts_preserve_censors():
    frame = pd.DataFrame({"ativo": ["A", "B", "C", "D"], "tempo observado": [2, 2, 3, 4], "evento": [1, 0, 1, 0]})
    diagnosis = diagnose(frame)
    suggestion = next(item for item in diagnosis["suggestions"] if item["id"] == "sobrevivencia")
    assert suggestion["status"] == "revisar"
    mapping = {role["id"]: role["selected"] for role in diagnosis["roles"]}
    result = execute(frame, mapping, "sobrevivencia")
    assert result["grafico"]["tipo"] == "sobrevivencia"
    assert result["grafico"]["pontos"][0]["sobrevivencia"] == 100
    assert result["grafico"]["pontos"][1]["sobrevivencia"] == pytest.approx(75)
    assert result["sobrevivencia"]["falhas"] == 2
    assert result["sobrevivencia"]["censuras"] == 2
    assert any("RMST" in text for text in result["evidencias"])
    counted = execute(frame, mapping, "confiabilidade")
    assert dict(counted["indicadores"])["Registros"] == 2
    assert {row[0] for row in counted["linhas"]} == {"A", "C"}
    with pytest.raises(ValueError, match="identificador único"):
        execute(frame.assign(ativo=["A", "A", "C", "D"]), mapping, "sobrevivencia")


def test_no_failure_does_not_claim_certain_lifetime():
    frame = pd.DataFrame({"ativo": ["A", "B"], "tempo": [3, 4], "evento": [0, 0]})
    mapping = {"ativo": "ativo", "tempo_falha": "tempo", "evento": "evento"}
    result = execute(frame, mapping, "sobrevivencia")
    assert "não foi alcançada" in result["insight"]
    assert all(item["inferior"] is None for item in result["grafico"]["pontos"])
    assert any("não comprovam" in note for note in result["observacoes"])
    assert dict(execute(frame, mapping, "confiabilidade")["indicadores"])["Registros"] == 0
