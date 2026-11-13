"""Exploratory-data checks and method labels stay explicit and cautious."""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_diagnosis import diagnose


def test_quality_flags_are_descriptive_and_doe_is_not_claimed_from_columns():
    df = pd.DataFrame({
        "data": list(range(1, 21)),
        "temperatura": list(range(10, 20)) + list(range(10, 19)) + [100],
        "id": [f"L-{i}" for i in range(20)],
        "observacao": [None] + ["ok"] * 19,
        "registro": ["dup"] * 2 + [f"r-{i}" for i in range(18)],
    })
    df.loc[1] = df.loc[0]

    result = diagnose(df)
    kinds = {finding["type"] for finding in result["quality_findings"]}

    assert {"missing", "constant", "id_candidate", "outlier_candidate", "duplicate_rows"} <= kinds
    assert not any(item["type"] == "id_candidate" and item["column"] == "data" for item in result["quality_findings"])
    assert "nenhum alerta confirma" in result["quality_note"].lower()
    doe = next(item for item in result["suggestions"] if item["id"] == "doe")
    assert "Exploração por fator" in doe["methods"]
    assert "ANOVA de um fator (exploratória)" in doe["methods"]
    assert "randomização" in doe["caveat"]
    assert result["legacy_problems"]["rationale"] is not None
    if "doe" in result["legacy_problems"]["problems"]:
        rationale = " ".join(result["legacy_problems"]["rationale"]["doe"]).lower()
        assert "formal doe is not confirmed" in rationale
        assert result["legacy_problems"]["confidence"]["doe"] == 0.3
    if "anova" in result["legacy_problems"]["problems"]:
        rationale = " ".join(result["legacy_problems"]["rationale"]["anova"]).lower()
        assert "column types alone do not confirm" in rationale
        assert result["legacy_problems"]["confidence"]["anova"] == 0.3


def test_refugo_recognizes_optional_fields_and_only_promises_available_methods():
    df = pd.DataFrame({
        "Categoria do defeito": ["A", "B"],
        "Unidades rejeitadas": [3, 1],
        "Linha de produção": ["L1", "L2"],
        "Custo unitário (R$)": [2.0, 4.0],
    })
    result = diagnose(df)
    suggestion = next(item for item in result["suggestions"] if item["id"] == "refugo")
    selected = {role["id"]: role["selected"] for role in result["roles"]}

    assert selected["defeitos"] == "Unidades rejeitadas"
    assert selected["grupo"] == "Linha de produção"
    assert selected["custo_unitario"] == "Custo unitário (R$)"
    assert any("Custo por unidade rejeitada" in item["role"] for item in suggestion["optional_found"])
    assert any(method.startswith("Pareto por custo") for method in suggestion["methods"])
    assert any(method.startswith("Estratificação por Linha de produção") for method in suggestion["methods"])
    assert not suggestion["blockers"]


def test_refugo_blocks_conflicting_cost_bases_and_explains_missing_optional_fields():
    df = pd.DataFrame({
        "Tipo de defeito": ["A", "B"], "Rejeitados": [2, 1],
        "Custo unitário": [3.0, 4.0], "Custo total R$": [6.0, 4.0],
    })
    result = diagnose(df)
    suggestion = next(item for item in result["suggestions"] if item["id"] == "refugo")

    assert len(suggestion["blockers"]) == 1
    assert "apenas custo unitário ou custo total" in suggestion["blockers"][0]
    assert "escolha uma única base de custo" in suggestion["methods"][1]
    missing_optional = next(item for item in diagnose(pd.DataFrame({"tipo de defeito":["A"], "rejeitados":[1] }))["suggestions"] if item["id"] == "refugo")
    assert "mapeie custo opcional" in missing_optional["methods"][1]
    assert "mapeie linha/turno opcional" in missing_optional["methods"][2]


def test_refugo_does_not_guess_legacy_cost_or_unit_price_as_cost_basis():
    df = pd.DataFrame({"defeito":["A","B"],"rejeitados":[1,2],"custo":[5.,8.],"preco unitario":[10.,12.]})
    result = diagnose(df)
    suggestion = next(item for item in result["suggestions"] if item["id"] == "refugo")
    selected = {role["id"]: role["selected"] for role in result["roles"]}

    assert selected["custo"] == "custo"
    assert selected["custo_unitario"] is None
    assert any("coluna legado 'custo'" in blocker for blocker in suggestion["blockers"])


def _group_options(frame):
    result = diagnose(frame)
    suggestion = next(item for item in result["suggestions"] if item["id"] == "grupos")
    return suggestion, {item["value"]: item for item in suggestion["comparison_options"]}


def test_grupos_exposes_both_complete_routes_without_choosing_one():
    df = pd.DataFrame({
        "Turno": ["A", "B"], "Medição": [10.0, 11.0],
        "Rejeitados": [1, 2], "Unidades inspecionadas": [100, 120],
    })
    suggestion, options = _group_options(df)

    assert suggestion["status"] == "revisar"
    assert options["measurement"] == {
        "value": "measurement", "label": "Medições entre grupos", "available": True, "missing": []
    }
    assert options["proportion"] == {
        "value": "proportion", "label": "Taxa de unidades rejeitadas (%)", "available": True, "missing": []
    }
    assert {item["role"] for item in suggestion["found"]} == {
        "Máquina, turno ou grupo", "Medição do processo", "Quantidade rejeitada",
        "Quantidade produzida ou inspecionada",
    }
    assert any("Wilson por grupo" in method for method in suggestion["methods"])
    assert any("Newcombe" in method and "dois grupos" in method for method in suggestion["methods"])
    assert "denominadores são disjuntos" in suggestion["caveat"]
    assert "não demonstram causalidade" in suggestion["caveat"]


def test_grupos_proportion_only_is_available_and_lists_measurement_as_missing():
    df = pd.DataFrame({"Linha": ["A", "B"], "Unidades defeituosas": [1, 2], "Unidades inspecionadas": [50, 80]})
    suggestion, options = _group_options(df)

    assert suggestion["status"] == "revisar"
    assert options["measurement"]["available"] is False
    assert options["measurement"]["missing"] == ["Medição do processo"]
    assert options["proportion"]["available"] is True
    assert options["proportion"]["missing"] == []


def test_grupos_incomplete_routes_report_each_missing_role_and_keep_status():
    df = pd.DataFrame({"Turno": ["A", "B"], "Unidades inspecionadas": [50, 80]})
    suggestion, options = _group_options(df)

    assert suggestion["status"] == "faltam dados"
    assert options["measurement"]["available"] is False
    assert options["measurement"]["missing"] == ["Medição do processo"]
    assert options["proportion"]["available"] is False
    assert options["proportion"]["missing"] == ["Quantidade rejeitada"]


def test_group_options_do_not_change_refugo_cost_blockers():
    df = pd.DataFrame({
        "Tipo de defeito": ["A", "B"], "Rejeitados": [2, 1],
        "Custo unitário": [3.0, 4.0], "Custo total R$": [6.0, 4.0],
    })
    suggestion = next(item for item in diagnose(df)["suggestions"] if item["id"] == "refugo")

    assert len(suggestion["blockers"]) == 1
    assert "apenas custo unitário ou custo total" in suggestion["blockers"][0]
    assert "comparison_options" not in suggestion
