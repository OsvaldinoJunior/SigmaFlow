"""Input/configuration and calculation-source identities for local executions."""
from __future__ import annotations

import copy
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import uuid
from datetime import datetime, timezone


MODULE_ROOT = Path(__file__).resolve().parent
CORE_FILES = ["local_analysis.py", "local_statistics.py", "local_survival.py", "local_visuals.py",
              "local_diagnosis.py", "local_data.py", "local_provenance.py", "local_pilot.py",
              "core/data_profiler.py", "core/problem_detector.py"]
SOURCE_PATHS = sorted(CORE_FILES + [path.relative_to(MODULE_ROOT).as_posix() for path in (MODULE_ROOT / "analysis").glob("*.py")])
# Freeze the source identity at process startup. Refuse later execution if the
# files changed, so cached imports and dynamically loaded modules cannot be
# attributed to a source version that was never actually run.
SOURCE_SNAPSHOT = {name: (MODULE_ROOT / name).read_bytes() for name in SOURCE_PATHS}


def source_digest(sources):
    records = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(sources.items())}
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode("utf-8")).hexdigest()


ENGINE_SHA256 = source_digest(SOURCE_SNAPSHOT)
MAX_BROWSER_INTEGER = 2**53 - 1


def verify_runtime_sources():
    for name, expected in SOURCE_SNAPSHOT.items():
        if not (MODULE_ROOT / name).is_file() or (MODULE_ROOT / name).read_bytes() != expected:
            raise ValueError("O código mudou após iniciar o servidor. Reinicie a interface local antes de calcular ou exportar.")


def environment_info():
    packages = {}
    for name in ("numpy", "pandas", "scipy", "openpyxl", "xlrd"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}


def result_digest(result, *, version=2):
    content = {key: value for key, value in result.items() if key != "rastreabilidade"}
    return _json_digest(content, version=version)


def _normalize_numbers(value):
    # JavaScript serializes 180.0 as 180 and -0.0 as 0. These are the same
    # numerical values, so their JSON spelling must not invalidate a saved run.
    # Convert integral floats exactly, without rounding other numbers or casting
    # integers to float (which would erase differences above 2**53).
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_numbers(item) for item in value]
    return value


def _json_digest(content, *, version=2):
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Versão de rastreabilidade não reconhecida; preserve o registro original.")
    normalized = content if version == 1 else _normalize_numbers(content)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def provenance_digest(record, *, version=2):
    content = {key: value for key, value in record.items() if key != "execution_sha256"}
    return _json_digest(content, version=version)


def _validate_browser_numbers(value):
    # Preserve exact-value hashing. Large integral floats may be printed by JS
    # with a different integer spelling; reject this unsupported range rather
    # than round integers or silently weaken the integrity comparison.
    if isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) > MAX_BROWSER_INTEGER:
        raise ValueError("Um resultado numérico excede a precisão suportada pelo navegador (2⁵³−1). Revise a escala/unidade dos dados antes de calcular e exportar.")
    if isinstance(value, dict):
        for item in value.values():
            _validate_browser_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_browser_numbers(item)


def attach_provenance(result, raw, mapping, scenario, input_rows, *, parameters=None):
    _validate_browser_numbers(result)
    parameters = result.get("piloto", {}).get("parameters", parameters or {})
    if not isinstance(parameters, dict):
        raise ValueError("Parâmetros de rastreabilidade inválidos.")
    result["rastreabilidade"] = {
        "schema_version": 2, "digest_algorithm": "sha256-json-exact-integral-v2", "run_id": str(uuid.uuid4()),
        "executed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario, "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "engine_sha256": ENGINE_SHA256, "mapping": copy.deepcopy(mapping),
        "parameters": copy.deepcopy(parameters),
        "input_rows": input_rows, "result_sha256": result_digest(result),
        "environment": environment_info(),
    }
    result["rastreabilidade"]["execution_sha256"] = provenance_digest(result["rastreabilidade"])
    return result
