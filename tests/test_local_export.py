"""Portable evidence preserves the recorded result and proves new outputs."""
import base64
import copy
import hashlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
import zipfile

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sigmaflow"))
from local_analysis import execute
from local_app import Handler
from local_data import read_table
from local_diagnosis import diagnose
from local_export import build_bundle
from local_provenance import ENGINE_SHA256, attach_provenance, result_digest
import local_provenance as provenance
import local_project_store as store


def project(rows=150, traced=True):
    raw = ("energyA;energyB;units\n" + "\n".join(f"{i+1};999;2" for i in range(rows))).encode()
    frame = read_table("coorte.csv", raw)
    mapping = {"energia": "energyA", "total": "units"}
    saved = execute(frame, mapping, "energia")
    if traced:
        attach_provenance(saved, raw, mapping, "energia", len(frame))
    return {"id": str(uuid.uuid4()), "version": 2, "filename": "coorte.csv", "title": "Projeto de teste",
            "dataset_sha256": hashlib.sha256(raw).hexdigest(), "file_base64": base64.b64encode(raw).decode(),
            "mapping": {"energia": "energyB", "total": "units"}, "analyses": {"energia": saved},
            "diagnosis": diagnose(frame, mapping), "investigation": {"charter": {"owner": "Equipe"}}}


def archive(value):
    return zipfile.ZipFile(io.BytesIO(build_bundle(value)))


def test_snapshot_is_preserved_and_reexecution_uses_original_run_mapping():
    value = project()
    saved_before = copy.deepcopy(value["analyses"])
    with archive(value) as bundle:
        saved = json.loads(bundle.read("analises_salvas/analise_01.json"))
        full = json.loads(bundle.read("reexecucoes/analise_01.json"))
        manifest = json.loads(bundle.read("manifesto.json"))
        assert saved == saved_before["energia"]
        assert len(saved["linhas"]) == 100
        assert len(full["linhas"]) == full["linhas_total"] == 150
        assert full["linhas"][0][1] == 1  # energyA, rather than project mapping energyB=999.
        assert full["rastreabilidade"]["mapping"]["energia"] == "energyA"
        assert full["rastreabilidade"]["run_id"] != saved["rastreabilidade"]["run_id"]
        assert full["rastreabilidade"]["result_sha256"] == result_digest(full)
        assert manifest["executions"][0]["matches_recorded_preview"] is True
        assert manifest["executions"][0]["mapping_basis"] == "execution_record"
        assert len(bundle.read("reexecucoes/analise_01.csv").decode("utf-8-sig").splitlines()) == 151
        assert manifest["engine_sha256"] == ENGINE_SHA256
    assert value["analyses"] == saved_before


def test_bundle_preserves_each_immutable_historical_run():
    value = project(rows=3)
    historical = copy.deepcopy(value["analyses"]["energia"])
    value["execution_history"] = [historical]
    run_id = historical["rastreabilidade"]["run_id"]
    with archive(value) as bundle:
        assert json.loads(bundle.read(f"execucoes/{run_id}.json")) == historical
        assert f"execucoes/{run_id}.json" in json.loads(bundle.read("manifesto.json"))["files"]


def test_legacy_mapping_is_marked_unverified_and_source_mismatch_is_not_recomputed():
    legacy = project(traced=False)
    with archive(legacy) as bundle:
        record = json.loads(bundle.read("manifesto.json"))["executions"][0]
        assert record["mapping_basis"] == "project_mapping_legacy_unverified"
        assert record["matches_recorded_preview"] is False
    invalid = project()
    invalid["analyses"]["energia"]["rastreabilidade"]["dataset_sha256"] = "0"*64
    with archive(invalid) as bundle:
        manifest = json.loads(bundle.read("manifesto.json"))
        assert manifest["executions"][0]["status"] == "not_reexecuted"
        assert "origem registrada" in manifest["executions"][0]["reason"]
        assert not any(name.startswith("reexecucoes/") for name in bundle.namelist())
        assert json.loads(bundle.read("projeto.json"))["analyses"] == invalid["analyses"]


def test_tampered_saved_result_and_unknown_scenario_are_preserved_with_refusal():
    value = project()
    value["analyses"]["energia"]["indicadores"][0][1] = 9000
    value["analyses"]["../../escape"] = copy.deepcopy(value["analyses"]["energia"])
    with archive(value) as bundle:
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in bundle.namelist())
        records = json.loads(bundle.read("manifesto.json"))["executions"]
        assert all(item["status"] == "not_reexecuted" for item in records)
        assert "hash registrado" in records[0]["reason"]
        assert "O resultado salvo difere do hash registrado" in bundle.read("relatorio_salvo.html").decode()
        assert len([name for name in bundle.namelist() if name.startswith("analises_salvas/")]) == 2


def test_changed_execution_parameters_are_not_attributed_to_recorded_result():
    value = project()
    value["analyses"]["energia"]["rastreabilidade"]["mapping"]["energia"] = "energyB"
    with archive(value) as bundle:
        record = json.loads(bundle.read("manifesto.json"))["executions"][0]
        assert record["status"] == "not_reexecuted"
        assert "hash da execução" in record["reason"]


def test_result_identity_normalizes_json_number_spelling_without_rounding():
    assert result_digest({"values": [180.0, {"zero": -0.0}, 1e-7]}) == result_digest({"values": [180, {"zero": 0}, 0.0000001]})
    assert result_digest({"value": True}) != result_digest({"value": 1})
    assert result_digest({"value": 1.0000001}) != result_digest({"value": 1})
    assert result_digest({"value": 2**53 + 1}) != result_digest({"value": float(2**53 + 1)})
    with pytest.raises(ValueError):
        result_digest({"value": float("nan")})


def test_unsafe_browser_numbers_are_refused_before_attaching_an_identity():
    for value in (2**53, 2**53 + 1, 1.2345678901234568e20, -1e20):
        with pytest.raises(ValueError, match="precisão suportada"):
            attach_provenance({"value": value}, b"dataset", {}, "energia", 1)
    result = attach_provenance({"value": 2**53 - 1}, b"dataset", {}, "energia", 1)
    assert result["rastreabilidade"]["schema_version"] == 2


def test_original_version_one_hashes_are_checked_with_their_own_algorithm():
    value = project(rows=3)
    saved = value["analyses"]["energia"]
    origin = saved["rastreabilidade"]
    origin["schema_version"] = 1
    origin.pop("digest_algorithm")
    origin["result_sha256"] = provenance.result_digest(saved, version=1)
    origin["execution_sha256"] = provenance.provenance_digest(origin, version=1)
    with archive(value) as bundle:
        assert json.loads(bundle.read("manifesto.json"))["executions"][0]["status"] == "reexecuted"
        assert json.loads(bundle.read("analises_salvas/analise_01.json")) == saved


def test_browser_number_roundtrip_can_save_and_export_original_run(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "projects")
    class QuietHandler(Handler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    value = project()
    value["base_version"] = 0
    try:
        # Recreate JSON.stringify's treatment of integral floats in a response.
        saved = provenance._normalize_numbers(value["analyses"]["energia"])
        value["analyses"]["energia"] = saved
        request = Request(url + "/api/projetos/" + value["id"], method="PUT", data=json.dumps(value).encode(), headers={"Content-Type": "application/json", "Origin": url})
        with urlopen(request, timeout=30) as response:
            stored = json.load(response)
        request = Request(url + f"/api/projetos/{value['id']}/exportar?version={stored['version']}", headers={"X-SigmaFlow-Export": "1"})
        with urlopen(request, timeout=30) as response, zipfile.ZipFile(io.BytesIO(response.read())) as bundle:
            record = json.loads(bundle.read("manifesto.json"))["executions"][0]
            assert record["status"] == "reexecuted"
            assert record["matches_recorded_preview"] is True
            assert len(json.loads(bundle.read("reexecucoes/analise_01.json"))["linhas"]) == 150
            assert json.loads(bundle.read("analises_salvas/analise_01.json")) == saved
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_changed_runtime_source_blocks_false_source_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "MODULE_ROOT", tmp_path)
    monkeypatch.setattr(provenance, "SOURCE_SNAPSHOT", {"calculo.py": b"original"})
    (tmp_path / "calculo.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="código mudou"):
        provenance.verify_runtime_sources()


def test_archive_integrity_and_archived_source_reproduce_full_result(tmp_path):
    with archive(project()) as bundle:
        bundle.extractall(tmp_path)
    verify = subprocess.run([sys.executable, str(tmp_path / "verificar_pacote.py")], capture_output=True, timeout=30)
    assert verify.returncode == 0, verify.stderr.decode(errors="replace")
    reproduce = subprocess.run([sys.executable, str(tmp_path / "reproduzir_analises.py")], capture_output=True, timeout=30)
    assert reproduce.returncode == 0, reproduce.stderr.decode(errors="replace")
    comparison = json.loads((tmp_path / "reproduzidos/comparacao.json").read_text(encoding="utf-8"))
    assert comparison["analyses"] == [{"scenario": "energia", "identical_result": True}]
    (tmp_path / "dados/original.csv").write_bytes(b"changed")
    changed = subprocess.run([sys.executable, str(tmp_path / "verificar_pacote.py")], capture_output=True, timeout=30)
    assert changed.returncode == 1


def test_standalone_report_embeds_safe_data_and_csv_protects_formulas():
    value = project(rows=2)
    value["title"] = '</script><img src=x onerror="alert(1)">'
    raw = b'categoria;rejeitados\n=1+1;5\nnormal;3\n'
    mapping = {"categoria": "categoria", "defeitos": "rejeitados"}
    frame = read_table("dados.csv", raw)
    result = attach_provenance(execute(frame, mapping, "refugo", parameters={"count_basis":"defective_units"}), raw, mapping, "refugo", len(frame), parameters={"count_basis":"defective_units"})
    value.update({"file_base64": base64.b64encode(raw).decode(), "dataset_sha256": hashlib.sha256(raw).hexdigest(),
                  "mapping": mapping, "analyses": {"refugo": result}})
    with archive(value) as bundle:
        report = bundle.read("relatorio_salvo.html").decode()
        assert '<script type="application/json" id="sigmaflow-report-data">' in report
        assert '</script><img src=x' not in report
        assert '\\u003c/script\\u003e' in report
        assert '<script src=' not in report and '<link rel="stylesheet"' not in report
        assert "Content-Security-Policy" in report
        csv = bundle.read("reexecucoes/analise_01.csv").decode("utf-8-sig")
        assert "'=1+1" in csv
        assert json.loads(bundle.read("reexecucoes/analise_01.json"))["linhas"][0][0] == "=1+1"


def test_export_api_requires_local_request_and_exact_saved_version(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "projects")
    value = project(rows=3)
    stored = store.save_project(value)
    class QuietHandler(Handler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/projetos/{stored['id']}/exportar"
    try:
        with pytest.raises(HTTPError) as missing:
            urlopen(url + "?version=1", timeout=30)
        assert missing.value.code == 403
        with pytest.raises(HTTPError) as stale:
            urlopen(Request(url + "?version=999", headers={"X-SigmaFlow-Export": "1"}), timeout=30)
        assert stale.value.code == 404
        with pytest.raises(HTTPError) as foreign:
            urlopen(Request(url + "?version=1", headers={"X-SigmaFlow-Export": "1", "Origin": "https://foreign.invalid"}), timeout=30)
        assert foreign.value.code == 403
        with urlopen(Request(url + "?version=1", headers={"X-SigmaFlow-Export": "1"}), timeout=30) as response:
            assert response.headers["Content-Type"] == "application/zip"
            assert zipfile.is_zipfile(io.BytesIO(response.read()))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_analysis_api_records_dataset_mapping_and_result_identity():
    class QuietHandler(Handler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    raw = b'energia;produzido\n10;2\n20;4\n'
    mapping = {"energia": "energia", "total": "produzido"}
    try:
        request = Request(f"http://127.0.0.1:{server.server_port}/api/analises", data=json.dumps({
            "filename": "dados.csv", "content": base64.b64encode(raw).decode(), "mapping": mapping, "scenario": "energia"
        }).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        provenance = result["rastreabilidade"]
        assert provenance["dataset_sha256"] == hashlib.sha256(raw).hexdigest()
        assert provenance["mapping"] == mapping
        assert provenance["result_sha256"] == result_digest(result)
        assert provenance["engine_sha256"] == ENGINE_SHA256
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
