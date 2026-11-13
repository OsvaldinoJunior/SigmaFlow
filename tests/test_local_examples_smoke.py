"""Every supplied industrial example reaches its matching local analysis."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_analysis import execute
from local_app import read_table
from local_diagnosis import diagnose
from scripts.gerar_exemplos_lss import CASES as EXAMPLES


CASES = {
    "01": "refugo", "02": "atributos", "03": "capacidade", "04": "spc",
    "05": "grupos", "06": "msa", "07": "fmea", "08": "doe",
    "09": "oee", "10": "fluxo", "11": "energia", "12": "confiabilidade", "13": "sobrevivencia", "14": "piloto", "15": "piloto",
}


@pytest.mark.parametrize(("prefix", "scenario"), CASES.items())
def test_example_is_detected_and_matching_scenario_executes(prefix, scenario):
    path = next((ROOT / "problemas_exemplos_testes_LSS").glob(f"{prefix}_*.xlsx"))
    frame = read_table(path.name, path.read_bytes())
    diagnosis = diagnose(frame)
    suggestion = next(item for item in diagnosis["suggestions"] if item["id"] == scenario)
    mapping = {role["id"]: role["selected"] for role in diagnosis["roles"]}

    assert suggestion["status"] == "revisar"
    config = next(case["parameters"] for case in EXAMPLES if case["filename"] == path.name)
    result = execute(frame, mapping, scenario, parameters=config)
    assert result["titulo"]
    assert result["metodo"]
    assert result["evidencias"]
    if scenario == "doe":
        assert "exploratória" in result["metodo"].lower()
        assert "DOE" in " ".join(result["observacoes"])
    if scenario == "piloto":
        assert result["piloto"]["excluded_rows"] == 10
        assert result["piloto"]["target"]["point_met"] is (prefix == "14")
