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
