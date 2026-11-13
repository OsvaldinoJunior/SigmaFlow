"""Local revisions, immutable datasets and optimistic write conflicts.

The lock serializes operations in one server process, not multiple processes.
Hashes are integrity checks, not signatures or methodological approval.
"""
from __future__ import annotations
import base64
import binascii
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import uuid

ROOT = Path(__file__).resolve().parent.parent / "output" / "projetos_locais"
MAX_DATASET_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
STORE_LOCK = threading.RLock()
CONTENT_FIELDS = ("title", "objective", "phase", "mapping", "analyses", "diagnosis", "investigation", "actions", "control", "filename", "dataset_sha256", "execution_ids")
LARGE_FIELDS = {"mapping", "analyses", "diagnosis", "investigation", "actions", "control", "file_base64", "new_executions", "execution_ids"}
MAX_EXECUTIONS_PER_SAVE = 100
MAX_EXECUTION_BYTES = 2 * 1024 * 1024


class ProjectConflictError(ValueError):
    def __init__(self, current_version):
        self.current_version = current_version
        super().__init__(f"A versão salva mudou para {current_version}. Seus campos não foram gravados. Reabra a versão atual ou salve sua cópia como outro projeto.")


def _locked(function):
    @wraps(function)
    def locked(*args, **kwargs):
        with STORE_LOCK:
            return function(*args, **kwargs)
    return locked


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _version(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= 999999999:
        raise ValueError("Número de versão inválido.")
    return value


def _project_dir(project_id):
    if not UUID_RE.fullmatch(str(project_id)):
        raise ValueError("Identificador de projeto inválido.")
    root = ROOT.resolve()
    directory = root / str(project_id)
    if directory.resolve().parent != root:
        raise ValueError("O diretório do projeto está fora do armazenamento local.")
    return directory


def _history_dir(directory):
    history = directory / "historico"
    if history.resolve().parent != directory.resolve():
        raise ValueError("O histórico está fora do diretório do projeto.")
    return history


def _metadata_digest(project):
    content = {key: value for key, value in project.items() if key != "metadata_sha256"}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_record(path, project_id, version=None):
    project_root = _project_dir(project_id).resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(project_root):
        raise ValueError("O registro da revis\u00e3o est\u00e1 fora da pasta do projeto.")
    if not path.is_file():
        raise FileNotFoundError("Projeto ou versão local não encontrado.")
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Metadados do projeto excedem o limite local.")
        project = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(project, dict) or project.get("id") != str(project_id):
            raise ValueError("O identificador do registro não corresponde ao projeto.")
        _version(project.get("version"))
        if version is not None and project["version"] != version:
            raise ValueError("A versão do registro não corresponde à revisão solicitada.")
        expected = project.get("metadata_sha256")
        if expected is not None and expected != _metadata_digest(project):
            raise ValueError("Os metadados do projeto foram alterados em relação ao hash registrado.")
        return project
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("O arquivo salvo do projeto está inválido.") from exc


def _read(project_id):
    return _read_record(_project_dir(project_id) / "projeto.json", project_id)


def _metadata(project):
    return {key: value for key, value in project.items() if key not in LARGE_FIELDS}


def _check_base(payload, previous, required):
    if "base_version" not in payload:
        if required:
            raise ValueError("Informe base_version; atualize a página e reabra o projeto antes de salvar.")
        return
    expected = _version(payload["base_version"], zero=True)
    actual = previous["version"] if previous else 0
    if expected != actual:
        raise ProjectConflictError(actual)


def _write_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".projeto-", suffix=".tmp", encoding="utf-8", delete=False) as temporary:
            name = Path(temporary.name)
            json.dump(record, temporary, ensure_ascii=False, allow_nan=False, indent=2)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(name, path)
    finally:
        if name is not None and name.is_file():
            name.unlink()


@_locked
def list_projects():
    ROOT.mkdir(parents=True, exist_ok=True)
    projects = []
    for directory in ROOT.iterdir():
        if not directory.is_dir() or not UUID_RE.fullmatch(directory.name):
            continue
        try:
            project = _read(directory.name)
        except (OSError, ValueError):
            continue
        projects.append({key: project.get(key) for key in (
            "id", "title", "objective", "phase", "updated_at", "version", "filename", "dataset_sha256")})
    return sorted(projects, key=lambda item: item.get("updated_at") or "", reverse=True)


@_locked
def save_project(payload, *, require_base_version=False):
    return _save_project(payload, require_base_version=require_base_version)


def _save_project(payload, *, require_base_version, event=None, derived_from=None, force_revision=False):
    if not isinstance(payload, dict):
        raise ValueError("O projeto enviado é inválido.")
    project_id = str(payload.get("id") or uuid.uuid4())
    directory = _project_dir(project_id)
    previous = _read(project_id) if (directory / "projeto.json").is_file() else None
    if previous is None and _history_dir(directory).exists() and any(_history_dir(directory).glob("v*.json")):
        raise ValueError("O projeto tem histórico mas o registro atual está ausente. Preserve os arquivos para recuperação; não foi criado outro registro por cima.")
    _check_base(payload, previous, require_base_version)
    filename = Path(str(payload.get("filename") or "")).name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Anexe um arquivo CSV, XLSX ou XLS para salvar o caso.")
    try:
        content = base64.b64decode(str(payload.get("file_base64") or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Não foi possível validar os dados do projeto.") from exc
    if not content or len(content) > MAX_DATASET_BYTES:
        raise ValueError("O arquivo está vazio ou ultrapassa o limite local de 10 MB.")
    title = str(payload.get("title") or "Projeto de melhoria").strip()[:160]
    if not title:
        raise ValueError("Informe um nome para o projeto.")
    incoming = {"id": project_id, "title": title, "objective": str(payload.get("objective") or "")[:2000],
                "phase": str(payload.get("phase") or "definir")[:24], "filename": filename,
                "dataset_sha256": hashlib.sha256(content).hexdigest(), "dataset_bytes": len(content)}
    for key in ("mapping", "analyses", "diagnosis", "investigation", "control"):
        incoming[key] = payload[key] if isinstance(payload.get(key), dict) else {}
    incoming["actions"] = payload["actions"] if isinstance(payload.get("actions"), list) else []
    pending_runs = payload.get("new_executions", [])
    if not isinstance(pending_runs, list) or len(pending_runs) > MAX_EXECUTIONS_PER_SAVE:
        raise ValueError("Envie no máximo 100 novas execuções por salvamento.")
    incoming["execution_ids"] = list(previous.get("execution_ids", [])) if previous else []
    if len(incoming["execution_ids"]) + len(pending_runs) > 10000:
        raise ValueError("O histórico deste projeto atingiu o limite local de 10.000 execuções.")
    from local_provenance import provenance_digest, result_digest
    pending_ids = set()
    pending_bytes = 0
    execution_dir = directory / "execucoes"
    for run in pending_runs:
        if not isinstance(run, dict) or not isinstance(run.get("rastreabilidade"), dict):
            raise ValueError("Cada execução precisa conter rastreabilidade verificável.")
        trace = run["rastreabilidade"]
        run_id = trace.get("run_id")
        if not isinstance(run_id, str) or not UUID_RE.fullmatch(run_id) or run_id in pending_ids or run_id in incoming["execution_ids"]:
            raise ValueError("Identificador de execução inválido ou repetido.")
        if trace.get("dataset_sha256") != incoming["dataset_sha256"]:
            raise ValueError("A execução pertence a uma planilha diferente da planilha do projeto.")
        if not isinstance(trace.get("scenario"), str) or not trace["scenario"].strip():
            raise ValueError("A execução precisa identificar o método utilizado.")
        schema = trace.get("schema_version", 1)
        if trace.get("result_sha256") != result_digest(run, version=schema) or trace.get("execution_sha256") != provenance_digest(trace, version=schema):
            raise ValueError("O hash da execução não confere; ela não foi adicionada ao histórico.")
        try:
            run_size = len(json.dumps(run, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("A execução contém valores inválidos.") from exc
        if run_size > MAX_EXECUTION_BYTES:
            raise ValueError("O resultado individual excede o limite de 2 MB por execução.")
        pending_bytes += run_size
        if pending_bytes > 8 * 1024 * 1024:
            raise ValueError("As novas execuções excedem o limite de 8 MB por salvamento.")
        pending_ids.add(run_id)
        incoming["execution_ids"].append(run_id)
    incoming["execution_count"] = len(incoming["execution_ids"])
    try:
        size = len(json.dumps(incoming, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("O projeto contém campos inválidos para salvar.") from exc
    if size > 1024 * 1024:
        raise ValueError("As anotações do projeto ultrapassam o limite local de 1 MB.")
    if len(incoming["actions"]) > 500 or len(incoming["investigation"].get("causes", [])) > 500:
        raise ValueError("O projeto excedeu o limite de itens de investigação ou ações.")
    if previous and not force_revision and all(previous.get(key) == incoming.get(key) for key in CONTENT_FIELDS):
        load_project(project_id)
        return _metadata(previous)
    incoming["version"] = (previous["version"] if previous else 0) + 1
    _version(incoming["version"])
    incoming["updated_at"] = _now()
    incoming["created_at"] = previous.get("created_at", incoming["updated_at"]) if previous else incoming["updated_at"]
    incoming["revision_event"] = event or {"type": "updated" if previous else "created", "base_version": previous["version"] if previous else 0}
    origin = previous.get("derived_from") if previous else derived_from
    if origin:
        incoming["derived_from"] = origin
    directory.mkdir(parents=True, exist_ok=True)
    dataset_name = f"dados_{incoming['dataset_sha256'][:16]}{suffix}"
    data_path = directory / dataset_name
    if data_path.resolve().parent != directory.resolve():
        raise ValueError("O caminho dos dados está fora do projeto.")
    if data_path.exists():
        if hashlib.sha256(data_path.read_bytes()).hexdigest() != incoming["dataset_sha256"]:
            raise ValueError("Os dados locais foram alterados ou há conflito no arquivo; o registro existente foi preservado.")
    else:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".dados-", suffix=".tmp", delete=False) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = Path(temporary.name)
        try:
            os.replace(temporary_name, data_path)
        finally:
            if temporary_name.is_file():
                temporary_name.unlink()
    incoming["dataset_file"] = dataset_name
    for run in pending_runs:
        run_id = run["rastreabilidade"]["run_id"]
        run_path = execution_dir / f"{run_id}.json"
        if run_path.exists():
            if json.loads(run_path.read_text(encoding="utf-8")) != run:
                raise ValueError("Já existe um registro imutável diferente para este identificador de execução.")
        else:
            _write_json(run_path, run)
    if previous:
        history = _history_dir(directory)
        snapshot = history / f"v{previous['version']:04d}.json"
        if snapshot.exists():
            if _read_record(snapshot, project_id, previous["version"]) != previous:
                raise ValueError("Já há uma revisão histórica diferente com esse número; nenhum registro foi sobrescrito.")
        else:
            _write_json(snapshot, previous)
    incoming["metadata_sha256"] = _metadata_digest(incoming)
    _write_json(directory / "projeto.json", incoming)
    return _metadata(incoming)


@_locked
def load_project(project_id, version=None):
    head = _read(project_id)
    if version is not None:
        version = _version(version)
    project = head if version is None or version == head["version"] else _read_record(
        _history_dir(_project_dir(project_id)) / f"v{version:04d}.json", project_id, version)
    directory = _project_dir(project_id).resolve()
    dataset_file = str(project.get("dataset_file", ""))
    if not re.fullmatch(r"dados_[0-9a-f]{16}\.(csv|xlsx|xls)", dataset_file):
        raise ValueError("O caminho dos dados associados ao projeto é inválido.")
    data_path = (directory / dataset_file).resolve()
    if data_path.parent != directory or not data_path.is_file():
        raise ValueError("Os dados associados ao projeto não foram encontrados.")
    content = data_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != project.get("dataset_sha256"):
        raise ValueError("Os dados do projeto foram alterados ou estão corrompidos.")
    execution_history = []
    execution_dir = _project_dir(project_id) / "execucoes"
    for run_id in project.get("execution_ids", []):
        if not isinstance(run_id, str) or not UUID_RE.fullmatch(run_id):
            raise ValueError("O projeto contém um identificador de execução inválido.")
        run_path = execution_dir / f"{run_id}.json"
        if run_path.resolve().parent != execution_dir.resolve() or not run_path.is_file() or run_path.stat().st_size > MAX_EXECUTION_BYTES:
            raise ValueError("Um registro do histórico de execuções não foi encontrado.")
        record = json.loads(run_path.read_text(encoding="utf-8"))
        trace = record.get("rastreabilidade", {})
        from local_provenance import provenance_digest, result_digest
        schema = trace.get("schema_version", 1)
        if (trace.get("run_id") != run_id or trace.get("dataset_sha256") != project.get("dataset_sha256")
                or trace.get("result_sha256") != result_digest(record, version=schema)
                or trace.get("execution_sha256") != provenance_digest(trace, version=schema)):
            raise ValueError("O registro do histórico não corresponde ao seu identificador.")
        execution_history.append(record)
    return {**project, "execution_history": execution_history, "file_base64": base64.b64encode(content).decode("ascii")}


@_locked
def list_versions(project_id, *, limit=50, before=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("A página do histórico deve ter de 1 a 100 versões.")
    if before is not None:
        before = _version(before)
    head = _read(project_id)
    candidates = {head["version"]: None}
    history = _history_dir(_project_dir(project_id))
    if history.is_dir():
        for path in history.iterdir():
            match = re.fullmatch(r"v(\d{4,9})\.json", path.name)
            if match:
                number = int(match[1])
                if 0 < number < head["version"] and path.name == f"v{number:04d}.json":
                    candidates[number] = path
    numbers = sorted((number for number in candidates if before is None or number < before), reverse=True)
    versions = []
    for number in numbers[:limit]:
        try:
            project = head if candidates[number] is None else _read_record(candidates[number], project_id, number)
            entry = {key: project.get(key) for key in ("version", "title", "phase", "filename", "updated_at", "dataset_sha256", "revision_event", "derived_from", "execution_count")}
            entry.update({"is_current": number == head["version"], "readable": True,
                          "analyses_count": len(project.get("analyses") or {}),
                          "metadata_integrity": "hash_checked" if project.get("metadata_sha256") else "legacy_unverified"})
        except (ValueError, OSError) as exc:
            entry = {"version": number, "readable": False, "is_current": False, "error": str(exc)}
        versions.append(entry)
    return {"project_id": project_id, "current_version": head["version"], "versions": versions,
            "next_before": numbers[limit-1] if len(numbers) > limit else None}


def _reason(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValueError("Informe um motivo de até 2000 caracteres para registrar a origem da recuperação.")
    return reason.strip()


@_locked
def restore_version(project_id, version, base_version, reason):
    reason = _reason(reason)
    head = _read(project_id)
    _check_base({"base_version": base_version}, head, True)
    version = _version(version)
    if version >= head["version"]:
        raise ValueError("Escolha uma versão anterior à atual para restaurar como nova revisão.")
    snapshot = load_project(project_id, version)
    snapshot["base_version"] = head["version"]
    return _save_project(snapshot, require_base_version=True, force_revision=True,
                         event={"type": "restored", "base_version": head["version"], "source_version": version, "reason": reason})


@_locked
def copy_version(project_id, version, title=None, reason=""):
    reason = _reason(reason)
    version = _version(version)
    snapshot = load_project(project_id, version)
    origin = {"project_id": project_id, "version": version, "dataset_sha256": snapshot["dataset_sha256"], "reason": reason, "copied_at": _now()}
    snapshot["id"] = str(uuid.uuid4())
    snapshot["base_version"] = 0
    if title is not None and not isinstance(title, str):
        raise ValueError("O nome da cópia deve ser um texto.")
    snapshot["title"] = title.strip() if title and title.strip() else f"{snapshot['title'][:130]} — cópia v{version}"
    return _save_project(snapshot, require_base_version=True, derived_from=origin,
                         event={"type": "copied", "source_version": version, "reason": reason, "base_version": 0})


@_locked
def delete_project(project_id):
    directory = _project_dir(project_id)
    if directory.resolve().parent != ROOT.resolve():
        raise ValueError("O diretório do projeto está fora do armazenamento local.")
    if not directory.is_dir():
        raise FileNotFoundError("Projeto local não encontrado.")
    shutil.rmtree(directory)
