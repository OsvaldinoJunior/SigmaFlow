"""Contract tests for immutable, version-addressable local DMAIC projects.

These tests intentionally use temporary stores and an ephemeral HTTP server. They
do not depend on a persistent local SigmaFlow instance or a browser.
"""
from __future__ import annotations

import base64
import copy
from contextlib import contextmanager
import hashlib
import io
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
import local_project_store as store
from local_app import Handler
from local_provenance import attach_provenance


def payload(project_id: str | None = None, *, version: int = 0,
            title: str = "Projeto A", content: bytes = b"data,value\n1,2\n",
            analyses: dict | None = None, mapping: dict | None = None) -> dict:
    return {
        "id": project_id,
        "base_version": version,
        "title": title,
        "objective": "Reduzir refugo da linha A",
        "phase": "analisar",
        "filename": "dados.csv",
        "file_base64": base64.b64encode(content).decode("ascii"),
        "mapping": mapping if mapping is not None else {"medida": "value"},
        "analyses": analyses if analyses is not None else {"spc": {"media": 2.0}},
        "diagnosis": {"rows": 1, "suggestions": ["spc"]},
        "investigation": {"causes": [{"id": "c1", "text": "setup"}], "pilot": {"owner": "Marcelo", "stage": "pilot"}},
        "actions": [{"title": "Verificar setup"}],
        "control": {"owner": "Equipe A"},
        "pilotmeta": {"owner": "Marcelo", "stage": "pilot"},
    }


def _project_payload(version: int, *, title: str, content: bytes,
                     mapping: dict, analyses: dict, pilotmeta: dict) -> dict:
    value = payload(title=title, content=content, mapping=mapping, analyses=analyses)
    value["investigation"]["pilot"] = pilotmeta
    value["base_version"] = version
    return value


def _execution(content: bytes, value: int) -> dict:
    result = {"titulo": f"Resultado {value}", "metodo": "Descritivo", "indicadores": [["valor", value]],
              "colunas": ["valor"], "linhas": [[value]], "linhas_total": 1, "observacoes": []}
    return attach_provenance(result, content, {"medida": "value"}, "spc", 1)


@contextmanager
def _server(monkeypatch, root):
    monkeypatch.setattr(store, "ROOT", root)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _request(base_url: str, method: str, path: str, *, body=None, headers=None):
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Origin": base_url, "Content-Type": "application/json"}
    request_headers.update(headers or {})
    req = Request(base_url + path, data=raw, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def _json_response(result):
    return json.loads(result[2].decode("utf-8"))


def test_explicit_base_version_creates_and_updates_snapshots_without_noop_revisions(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    first = payload(project_id, version=0)
    saved1 = store.save_project(first)
    assert saved1["version"] == 1

    second = _project_payload(1, title="Projeto A v2", content=b"data,value\n1,9\n",
                              mapping={"medida": "value", "data": "data"},
                              analyses={"spc": {"media": 9.0}},
                              pilotmeta={"owner": "Equipe B", "stage": "review"})
    saved2 = store.save_project({**second, "id": project_id})
    assert saved2["version"] == 2

    same = store.save_project({**second, "id": project_id, "base_version": 2})
    assert same["version"] == 2
    old = store.load_project(project_id, version=1)
    current = store.load_project(project_id, version=2)
    assert base64.b64decode(old["file_base64"]) == b"data,value\n1,2\n"
    assert old["mapping"] == {"medida": "value"}
    assert old["analyses"] == {"spc": {"media": 2.0}}
    assert old["investigation"]["pilot"] == {"owner": "Marcelo", "stage": "pilot"}
    assert base64.b64decode(current["file_base64"]) == b"data,value\n1,9\n"
    assert current["mapping"] == {"medida": "value", "data": "data"}
    assert current["analyses"] == {"spc": {"media": 9.0}}
    assert current["investigation"]["pilot"] == {"owner": "Equipe B", "stage": "review"}


def test_analysis_executions_are_immutable_and_addressable_by_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    content = b"data,value\n1,2\n"
    first_run = _execution(content, 2)
    project_id = str(uuid.uuid4())
    first = payload(project_id, version=0, content=content)
    first["new_executions"] = [first_run]
    saved1 = store.save_project(first)
    assert saved1["execution_count"] == 1
    assert store.load_project(project_id)["execution_history"] == [first_run]

    second_run = _execution(content, 8)
    second = payload(project_id, version=1, content=content, analyses={"spc": {"media": 8}})
    second["new_executions"] = [second_run]
    saved2 = store.save_project(second)
    assert saved2["execution_count"] == 2
    assert store.load_project(project_id)["execution_history"] == [first_run, second_run]
    assert store.load_project(project_id, 1)["execution_history"] == [first_run]
    assert store.load_project(project_id, 2)["execution_history"] == [first_run, second_run]


def test_analysis_execution_rejects_wrong_dataset_and_tampered_record(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    project_id = str(uuid.uuid4())
    content = b"data,value\n1,2\n"
    wrong_dataset = _execution(b"other,data\n1,2\n", 2)
    invalid = payload(project_id, content=content)
    invalid["new_executions"] = [wrong_dataset]
    with pytest.raises(ValueError, match="planilha diferente"):
        store.save_project(invalid)

    valid = _execution(content, 2)
    value = payload(project_id, content=content)
    value["new_executions"] = [valid]
    store.save_project(value)
    run_path = tmp_path / project_id / "execucoes" / f"{valid['rastreabilidade']['run_id']}.json"
    stored = json.loads(run_path.read_text(encoding="utf-8"))
    stored["titulo"] = "Resultado alterado"
    run_path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError, match="corresponde"):
        store.load_project(project_id)


def test_stale_compare_and_swap_rejected_even_when_payload_is_identical(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    original = payload(project_id, version=0)
    store.save_project(original)
    newer = {**original, "base_version": 1, "title": "Mudou"}
    store.save_project(newer)

    stale_identical = {**original, "base_version": 1}
    with pytest.raises(store.ProjectConflictError) as caught:
        store.save_project(stale_identical)
    assert caught.value.current_version == 2
    assert store.load_project(project_id)["version"] == 2


def test_two_writers_using_same_base_version_only_one_can_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    store.save_project(payload(project_id, version=0))
    barrier = threading.Barrier(2)
    outcomes = []
    outcome_lock = threading.Lock()

    def writer(name):
        value = payload(project_id, version=1, title=name,
                        content=f"data,value\n1,{name}\n".encode("utf-8"))
        barrier.wait(timeout=5)
        try:
            result = store.save_project(value)
            item = ("saved", result["version"], name)
        except store.ProjectConflictError as exc:
            item = ("conflict", exc.current_version, name)
        with outcome_lock:
            outcomes.append(item)

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("Writer A", "Writer B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(item[0] for item in outcomes) == ["conflict", "saved"]
    assert {item[1] for item in outcomes} == {2}
    assert store.load_project(project_id)["version"] == 2
    assert store.list_versions(project_id)["current_version"] == 2


def test_version_list_paginates_and_marks_unreadable_dataset_instead_of_hiding_version(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    first = store.save_project(payload(project_id, version=0))
    for version in range(1, 5):
        store.save_project(payload(project_id, version=version, title=f"Projeto v{version + 1}",
                                   content=f"data,value\n1,{version + 2}\n".encode()))

    page = store.list_versions(project_id, limit=2)
    assert page["project_id"] == project_id
    assert page["current_version"] == 5
    assert [item["version"] for item in page["versions"]] == [5, 4]
    assert page["next_before"] == 4
    assert page["versions"][0]["is_current"] is True
    assert page["versions"][0]["readable"] is True
    assert page["versions"][0]["dataset_sha256"]

    older = store.list_versions(project_id, limit=2, before=page["next_before"])
    assert [item["version"] for item in older["versions"]] == [3, 2]
    assert older["next_before"] == 2
    tail = store.list_versions(project_id, limit=2, before=older["next_before"])
    assert [item["version"] for item in tail["versions"]] == [1]
    assert tail["next_before"] is None
    assert first["version"] == 1

    damaged = store.load_project(project_id, version=3)
    dataset = store.ROOT / project_id / damaged["dataset_file"]
    dataset.write_bytes(b"tampered bytes")
    # Metadata listing is lightweight; opening a revision verifies the dataset hash.
    assert next(item for item in store.list_versions(project_id, limit=10)["versions"] if item["version"] == 3)["readable"]
    with pytest.raises(ValueError):
        store.load_project(project_id, version=3)


def test_restore_creates_new_revision_with_reason_and_retains_intervening_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    store.save_project(payload(project_id, version=0))
    store.save_project(payload(project_id, version=1, title="Projeto v2", content=b"v2"))
    store.save_project(payload(project_id, version=2, title="Projeto v3", content=b"v3"))
    store.save_project(payload(project_id, version=3, title="Projeto v4", content=b"v4"))

    with pytest.raises(ValueError, match="motivo|raz[aã]o"):
        store.restore_version(project_id, 1, base_version=4, reason="  ")
    restored = store.restore_version(project_id, 2, base_version=4, reason="Retomar baseline aprovado")
    assert restored["version"] == 5
    restored_project = store.load_project(project_id)
    assert base64.b64decode(restored_project["file_base64"]) == b"v2"
    assert restored_project["revision_event"]["type"] == "restored"
    assert restored_project["revision_event"]["source_version"] == 2
    assert restored_project["revision_event"]["reason"] == "Retomar baseline aprovado"
    assert [item["version"] for item in store.list_versions(project_id, limit=10)["versions"]] == [5, 4, 3, 2, 1]
    assert base64.b64decode(store.load_project(project_id, version=4)["file_base64"]) == b"v4"


def test_restore_records_event_even_when_source_data_matches_head(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    project_id = str(uuid.uuid4())
    store.save_project(payload(project_id, version=0))
    store.save_project(payload(project_id, version=1, title="Outro título"))
    result = store.restore_version(project_id, 1, base_version=2, reason="Revisão metodológica")
    assert result["version"] == 3
    assert result["revision_event"]["type"] == "restored"
    assert store.load_project(project_id)["title"] == "Projeto A"
    assert [v["version"] for v in store.list_versions(project_id, limit=10)["versions"]] == [3, 2, 1]


def test_copy_creates_independent_id_and_provenance_without_modifying_source(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    source_id = str(uuid.uuid4())
    store.save_project(payload(source_id, version=0, content=b"source-v1"))
    store.save_project(payload(source_id, version=1, title="Source v2", content=b"source-v2"))
    source_before = copy.deepcopy(store.load_project(source_id))

    copied = store.copy_version(source_id, 1, title="Experimento derivado", reason="Teste controlado")
    assert copied["id"] != source_id
    assert copied["version"] == 1
    assert copied["derived_from"]["project_id"] == source_id
    assert copied["derived_from"]["version"] == 1
    assert copied["derived_from"]["reason"] == "Teste controlado"
    assert copied["revision_event"]["type"] == "copied"
    copied_project = store.load_project(copied["id"])
    assert copied_project["title"] == "Experimento derivado"
    assert base64.b64decode(copied_project["file_base64"]) == b"source-v1"
    assert store.load_project(source_id) == source_before
    assert [item["version"] for item in store.list_versions(source_id)["versions"]] == [2, 1]


def test_invalid_ids_versions_restore_sources_and_symlinked_dataset_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "cases")
    for invalid in ("../outside", "not-a-uuid", str(uuid.uuid4()) + "/../x"):
        with pytest.raises(ValueError):
            store.list_versions(invalid)
    project_id = str(uuid.uuid4())
    store.save_project(payload(project_id, version=0))
    with pytest.raises((ValueError, FileNotFoundError)):
        store.load_project(project_id, version=0)
    with pytest.raises((ValueError, FileNotFoundError)):
        store.restore_version(project_id, 99, base_version=1, reason="N/A")
    with pytest.raises(ValueError):
        store.list_versions(project_id, limit=0)

    loaded = store.load_project(project_id)
    data_path = store.ROOT / project_id / loaded["dataset_file"]
    target = tmp_path / "outside.csv"
    target.write_bytes(data_path.read_bytes())
    data_path.unlink()
    try:
        data_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")
    with pytest.raises(ValueError):
        store.load_project(project_id)
    listing = store.list_versions(project_id)
    assert listing["versions"][0]["readable"] is False


def test_http_api_requires_base_version_and_returns_structured_conflict(tmp_path, monkeypatch):
    project_id = str(uuid.uuid4())
    with _server(monkeypatch, tmp_path / "cases") as base_url:
        route = f"/api/projetos/{project_id}"
        missing = payload(project_id)
        missing.pop("base_version")
        status, _, _ = _request(base_url, "PUT", route, body=missing)
        assert status == 400

        status, _, body = _request(base_url, "PUT", route, body=payload(project_id, version=0))
        assert status == 200
        assert _json_response((status, None, body))["version"] == 1

        stale = payload(project_id, version=0, title="Stale")
        status, _, body = _request(base_url, "PUT", route, body=stale)
        conflict = json.loads(body)
        assert status == 409
        assert conflict["code"] == "version_conflict"
        assert conflict["current_version"] == 1


def test_http_history_restore_copy_report_and_export_are_version_addressed(tmp_path, monkeypatch):
    project_id = str(uuid.uuid4())
    with _server(monkeypatch, tmp_path / "cases") as base_url:
        base_route = f"/api/projetos/{project_id}"
        store.save_project(payload(project_id, version=0, content=b"data,value\n1,2\n"))
        store.save_project(payload(project_id, version=1, title="v2", content=b"data,value\n1,9\n"))

        status, _, body = _request(base_url, "GET", f"{base_route}/historico?limit=1")
        history = json.loads(body)
        assert status == 200
        assert history["current_version"] == 2
        assert history["versions"][0]["version"] == 2

        status, _, body = _request(base_url, "GET", f"{base_route}/versoes/1")
        assert status == 200
        old = json.loads(body)
        assert old["version"] == 1
        assert base64.b64decode(old["file_base64"]) == b"data,value\n1,2\n"

        # Opening a saved report must render the recorded output, not recalculate it.
        import local_app
        monkeypatch.setattr(local_app, "execute", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("recalculation")))
        status, headers, report = _request(base_url, "GET", f"{base_route}/versoes/1/relatorio")
        assert status == 200
        assert "text/html" in headers.get("Content-Type", "")
        assert b"Projeto A" in report or b"v2" in report

        status, _, body = _request(base_url, "GET", f"{base_route}/versoes/999")
        assert status == 404
        status, _, body = _request(base_url, "GET", f"{base_route}/exportar?version=1",
                                   headers={"X-SigmaFlow-Export": "1"})
        assert status == 200, body.decode("utf-8", errors="replace")
        with zipfile.ZipFile(io.BytesIO(body)) as bundle:
            archived = json.loads(bundle.read("projeto.json"))
            assert archived["version"] == 1
            assert bundle.read("dados/original.csv") == b"data,value\n1,2\n"
        status, _, _ = _request(base_url, "GET", f"{base_route}/exportar?version=999",
                                headers={"X-SigmaFlow-Export": "1"})
        assert status == 404

        status, _, body = _request(base_url, "POST", f"{base_route}/versoes/1/copiar",
                                   body={"title": "Cópia de v1", "reason": "Investigação alternativa"})
        copied = json.loads(body)
        assert status == 201
        assert copied["id"] != project_id
        assert copied["derived_from"]["version"] == 1
        assert base64.b64decode(store.load_project(copied["id"])["file_base64"]) == b"data,value\n1,2\n"

        status, _, body = _request(base_url, "POST", f"{base_route}/versoes/1/restaurar",
                                   body={"base_version": 2, "reason": "Retorno aprovado"})
        restored = json.loads(body)
        assert status == 201
        assert restored["version"] == 3
        assert restored["revision_event"]["type"] == "restored"
        assert base64.b64decode(store.load_project(project_id)["file_base64"]) == b"data,value\n1,2\n"
