"""Local case storage keeps dataset integrity and avoids empty autosave versions."""
import base64
from pathlib import Path
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
import local_project_store as store


def payload(project_id: str, content: bytes = b"data,value\n1,2\n") -> dict:
    return {
        "id": project_id,
        "title": "Projeto de teste",
        "filename": "dados.csv",
        "file_base64": base64.b64encode(content).decode("ascii"),
        "mapping": {"medida": "value"},
        "investigation": {"causes": [], "decisions": {"refugo": {"state": "adiar", "reason": "Aguardando dados por produto"}}},
    }


def test_save_load_and_noop_save_do_not_create_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())

    first = store.save_project(payload(project_id))
    same = store.save_project(payload(project_id))
    loaded = store.load_project(project_id)

    assert first["version"] == same["version"] == 1
    assert base64.b64decode(loaded["file_base64"]) == b"data,value\n1,2\n"
    assert loaded["mapping"] == {"medida": "value"}
    assert loaded["investigation"]["decisions"]["refugo"]["reason"] == "Aguardando dados por produto"


def test_changed_project_is_versioned_and_dataset_tampering_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    store.save_project(payload(project_id))
    updated = payload(project_id)
    updated["title"] = "Projeto revisado"
    result = store.save_project(updated)
    assert result["version"] == 2

    dataset = Path(store.ROOT / project_id / result["dataset_file"])
    dataset.write_bytes(b"alterado")
    with pytest.raises(ValueError, match="corrompidos"):
        store.load_project(project_id)


def test_invalid_project_id_is_rejected():
    with pytest.raises(ValueError, match="Identificador"):
        store.load_project("..\\outside")
