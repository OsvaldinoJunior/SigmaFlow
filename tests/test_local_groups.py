"""Unequal production volumes, independent proportion references, and explicit intent."""
from pathlib import Path
import math
import sys

import pandas as pd
import pytest
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sigmaflow"))
from local_analysis import execute


PARAMETERS = {"comparison_kind": "proportion", "count_basis": "defective_units", "denominators_disjoint": True}
MAPPING = {"grupo": "line", "defeitos": "rejects", "total": "inspected"}


def unequal_volumes():
    return pd.DataFrame({"line": ["A", "A", "B", "B"], "rejects": [1, 9, 5, 5], "inspected": [10, 990, 50, 50]})


def test_unequal_volumes_use_sum_of_denominators_and_match_independent_statistics():
    result = execute(unequal_volumes(), MAPPING, "grupos", parameters=PARAMETERS)
    a, b = result["group_comparison"]["groups"]
    assert (a["defective"], a["inspected"], a["rate"]) == (10, 1000, 1.0)
    assert (b["defective"], b["inspected"], b["rate"]) == (10, 100, 10.0)
    for item in (a, b):
        reference = stats.binomtest(item["defective"], item["inspected"]).proportion_ci(method="wilson")
        assert item["ci95"] == pytest.approx([100*reference.low, 100*reference.high])
    # Independent SciPy Wilson roots, Newcombe's B-A orientation in percentage points.
    ca = stats.binomtest(10, 1000).proportion_ci(method="wilson")
    cb = stats.binomtest(10, 100).proportion_ci(method="wilson")
    expected = [9 - math.hypot(10-100*cb.low, 100*ca.high-1),
                9 + math.hypot(100*cb.high-10, 1-100*ca.low)]
    contrast = result["group_comparison"]["difference"]
    assert contrast["estimate_pp"] == pytest.approx(9)
    assert contrast["ci95_pp"] == pytest.approx(expected)
    assert "em B" in result["insight"]
    assert result["grafico"]["tipo"] == "intervalos"
    assert dict(result["indicadores"])["Teste exploratório"] == "Teste exato de Fisher bilateral"


def test_explicit_measurement_choice_ignores_unrelated_count_columns_and_ambiguity_requires_choice():
    frame = unequal_volumes().assign(weight=[10., 12., 20., 22.])
    mapping = dict(MAPPING, medida="weight")
    with pytest.raises(ValueError, match="Escolha comparar"):
        execute(frame, mapping, "grupos")
    measure = execute(frame, mapping, "grupos", parameters={"comparison_kind": "measurement"})
    proportion = execute(frame, mapping, "grupos", parameters=PARAMETERS)
    assert "group_comparison" not in measure
    assert measure["linhas"][0][2] == 11.
    assert proportion["linhas"][0][3] == 1.


@pytest.mark.parametrize("parameters", [
    {}, {"comparison_kind": "proportion"},
    dict(PARAMETERS, count_basis="defect_occurrences"),
    dict(PARAMETERS, denominators_disjoint=False),
    dict(PARAMETERS, denominators_disjoint=1),
    dict(PARAMETERS, unknown=True),
])
def test_proportions_require_real_semantic_declarations(parameters):
    with pytest.raises(ValueError):
        execute(unequal_volumes(), MAPPING, "grupos", parameters=parameters)


@pytest.mark.parametrize("rejects,inspected", [(-1,10),(1.5,10),(11,10),(1,0),(True,10),(1,None)])
def test_proportions_reject_invalid_or_boolean_counts(rejects, inspected):
    frame = pd.DataFrame({"line":["A","B"],"rejects":pd.Series([rejects,1],dtype=object),"inspected":[inspected,10]})
    with pytest.raises(ValueError):
        execute(frame,MAPPING,"grupos",parameters=PARAMETERS)


def test_zero_events_keep_uncertainty_and_sparse_groups_do_not_claim_omnibus_significance():
    frame = pd.DataFrame({"line":["A","B"],"rejects":[0,0],"inspected":[10,100]})
    result = execute(frame,MAPPING,"grupos",parameters=PARAMETERS)
    assert all(item["ci95"][1] > 0 for item in result["group_comparison"]["groups"])
    assert result["group_comparison"]["difference"]["ci95_pp"][0] < 0
    assert result["group_comparison"]["difference"]["ci95_pp"][1] > 0
    assert "p-valor" not in dict(result["indicadores"])
    sparse = pd.DataFrame({"line":["A","B","C"],"rejects":[0,1,1],"inspected":[2,2,2]})
    result = execute(sparse,MAPPING,"grupos",parameters=PARAMETERS)
    assert result["group_comparison"]["difference"] is None
    assert "p-valor" not in dict(result["indicadores"])
    assert any("abaixo de 5" in item for item in result["evidencias"])


def test_sparse_two_group_test_matches_fisher_and_reversal_changes_effect_direction():
    frame = pd.DataFrame({"line":["A","B"],"rejects":[1,4],"inspected":[10,10]})
    result = execute(frame,MAPPING,"grupos",parameters=PARAMETERS)
    metrics = dict(result["indicadores"])
    assert metrics["Teste exploratório"] == "Teste exato de Fisher bilateral"
    assert float(metrics["p-valor"].replace(",", ".")) == pytest.approx(stats.fisher_exact([[1,9],[4,6]]).pvalue, abs=5e-7)
    forward = result["group_comparison"]["difference"]
    reverse = execute(frame.iloc[::-1],MAPPING,"grupos",parameters=PARAMETERS)["group_comparison"]["difference"]
    assert reverse["estimate_pp"] == pytest.approx(-forward["estimate_pp"])
    assert reverse["ci95_pp"] == pytest.approx([-forward["ci95_pp"][1],-forward["ci95_pp"][0]])


def test_dense_multiple_groups_match_chisquare_without_unadjusted_pairwise_claims():
    frame = pd.DataFrame({"line":["A","B","C"],"rejects":[10,20,20],"inspected":[100,200,100]})
    result = execute(frame,MAPPING,"grupos",parameters=PARAMETERS)
    metrics = dict(result["indicadores"])
    assert metrics["Teste exploratório"] == "Qui-quadrado de independência"
    expected = stats.chi2_contingency([[10,90],[20,180],[20,80]], correction=False)
    assert float(metrics["p-valor"].replace(",", ".")) == pytest.approx(expected.pvalue, abs=5e-7)
    assert result["group_comparison"]["difference"] is None


def test_export_reexecutes_the_explicit_comparison_with_its_original_parameters():
    import base64
    import hashlib
    import io
    import json
    import uuid
    import zipfile
    from local_export import build_bundle
    from local_provenance import attach_provenance

    frame = unequal_volumes()
    raw = frame.to_csv(index=False).encode("utf-8")
    saved = execute(frame,MAPPING,"grupos",parameters=PARAMETERS)
    attach_provenance(saved,raw,MAPPING,"grupos",len(frame),parameters=PARAMETERS)
    project = {"id": str(uuid.uuid4()), "version":1, "filename":"taxas.csv", "title":"Taxas entre linhas",
               "file_base64":base64.b64encode(raw).decode(),"dataset_sha256":hashlib.sha256(raw).hexdigest(),
               "mapping":MAPPING,"analyses":{"grupos":saved},"investigation":{}}
    with zipfile.ZipFile(io.BytesIO(build_bundle(project))) as bundle:
        reproduced = json.loads(bundle.read("reexecucoes/analise_01.json"))
        plan = json.loads(bundle.read("reproduzir.json"))
        assert reproduced["group_comparison"] == saved["group_comparison"]
        assert reproduced["rastreabilidade"]["parameters"] == PARAMETERS
        assert plan["analyses"][0]["parameters"] == PARAMETERS
