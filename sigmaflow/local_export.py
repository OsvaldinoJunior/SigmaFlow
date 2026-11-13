"""Portable evidence bundle: recorded snapshot and explicit new executions."""
from __future__ import annotations

import base64
import copy
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from local_analysis import execute
from local_data import read_table
from local_diagnosis import CATALOG, diagnose
from local_provenance import (ENGINE_SHA256, SOURCE_SNAPSHOT, attach_provenance,
                              environment_info, provenance_digest, result_digest, verify_runtime_sources)

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "local"
MAX_EXPORT_BYTES = 64 * 1024 * 1024


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2).encode("utf-8")


def _csv(result):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    def cell(value):
        if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
            return "'" + value
        return value
    writer.writerow([cell(value) for value in result["colunas"]])
    writer.writerows([[cell(value) for value in row] for row in result["linhas"]])
    return stream.getvalue().encode("utf-8-sig")


def standalone_report(data):
    html = (FRONTEND / "report.html").read_text(encoding="utf-8")
    for name in ("styles.css", "upload.css", "report.css", "project-report.css"):
        css = (FRONTEND / name).read_text(encoding="utf-8")
        html = html.replace(f'<link rel="stylesheet" href="/{name}">', f"<style>{css}</style>")
    html = re.sub(r'<script src="/[^\"]+" defer></script>', "", html)
    # Embedded data must never be allowed to close its inert script element.
    encoded = _json(data).decode("utf-8").replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    scripts = '\n<script type="application/json" id="sigmaflow-report-data">' + encoded + "</script>\n"
    for name in ("charts.js", "report.js"):
        source = (FRONTEND / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
        scripts += "<script>\n" + source + "\n</script>\n"
    csp = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; font-src data:; base-uri \'none\'; form-action \'none\'">'
    return html.replace("<head>", "<head>\n" + csp).replace("</body>", scripts + "</body>").encode("utf-8")


def build_snapshot_report(project):
    """Render only results recorded in the selected saved revision; never recalculates."""
    stored = project.get("analyses") or {}
    warnings = []
    analyses = []
    if not isinstance(stored, dict):
        stored = {}
        warnings.append("O campo de an\u00e1lises salvo n\u00e3o \u00e9 leg\u00edvel; nenhum c\u00e1lculo foi executado.")
    for scenario, result in stored.items():
        if not isinstance(result, dict) or not all(isinstance(result.get(key), list) for key in ("linhas", "colunas", "indicadores", "observacoes")):
            warnings.append(f"{scenario}: formato de resultado n\u00e3o reconhecido; preservado no projeto, omitido do relat\u00f3rio.")
            continue
        analyses.append(result)
        trace = result.get("rastreabilidade")
        if not isinstance(trace, dict):
            warnings.append(f"{scenario}: revis\u00e3o antiga sem rastreabilidade da execu\u00e7\u00e3o; resultado exibido como registro n\u00e3o verificado.")
        else:
            try:
                if trace.get("result_sha256") != result_digest(result, version=trace.get("schema_version", 1)):
                    warnings.append(f"{scenario}: hash do resultado n\u00e3o confere; revise antes de interpretar.")
                if trace.get("execution_sha256") != provenance_digest(trace, version=trace.get("schema_version", 1)):
                    warnings.append(f"{scenario}: hash dos par\u00e2metros de execu\u00e7\u00e3o n\u00e3o confere.")
            except (ValueError, TypeError, KeyError):
                warnings.append(f"{scenario}: metadados de rastreabilidade inv\u00e1lidos.")
    if not project.get("metadata_sha256"):
        warnings.append("Metadados de revis\u00e3o legados sem hash de integridade.")
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return standalone_report(_report(project, analyses, project.get("diagnosis") or {}, "snapshot", exported_at, warnings))


def _report(project, analyses, diagnosis, kind, exported_at, warnings):
    investigation = project.get("investigation") or {}
    form = {**investigation, "title": project.get("title"), "actions": project.get("actions") or [], "control": project.get("control") or {}}
    if kind == "snapshot":
        message = "Cópia das análises e anotações salvas nesta versão do projeto. Não foi recalculada para este relatório. Tabelas podem conter apenas a prévia registrada."
    else:
        message = "Nova execução feita ao exportar, com o código e ambiente identificados no pacote. Não substitui a análise salva nem representa revisão ou aprovação das conclusões. Tabelas integrais estão nos arquivos JSON/CSV."
    return {"arquivo": project["filename"], "objetivo": project.get("objective", ""), "registros": diagnosis.get("rows", "Não registrado"),
            "gerado_em": exported_at, "colunas": diagnosis.get("columns", []), "mapeamento": project.get("mapping", {}),
            "analises": [dict(result, linhas=result["linhas"][:100]) for result in analyses], "projeto": form,
            "quality_note": diagnosis.get("quality_note", "A triagem original não foi registrada neste projeto."),
            "quality_findings": diagnosis.get("quality_findings", [{"message": "Triagem original indisponível.", "caveat": "Não interprete a ausência de registro como ausência de problemas nos dados."}]),
            "detector": diagnosis.get("legacy_problems", {}),
            "export_info": {"kind": kind, "message": message, "project_id": project["id"], "project_version": project["version"],
                            "dataset_sha256": project["dataset_sha256"], "exported_at": exported_at, "warnings": warnings}}


VERIFY_SCRIPT = '''"""Verify bundle file hashes without importing or executing archived methods."""
from pathlib import Path
import hashlib
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifesto.json").read_text(encoding="utf-8"))
errors = []
for name, expected in manifest["files"].items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        errors.append(f"Ausente ou caminho inválido: {name}")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
        errors.append(f"Conteúdo alterado: {name}")
if errors:
    print("\\n".join(errors))
    raise SystemExit(1)
print(f"Integridade conferida em {len(manifest['files'])} arquivos.")
print("Hashes não são assinatura de autoria nem validação estatística. Preserve o manifesto original.")
'''

REPRODUCE_SCRIPT = '''"""Reproduce exported new executions using the archived calculation source."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root = Path(__file__).resolve().parent
def path_in_bundle(name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Caminho fora do pacote")
    return path
parser = argparse.ArgumentParser()
parser.add_argument("--permitir-ambiente-diferente", action="store_true")
args = parser.parse_args()
sys.path.insert(0, str(root / "codigo"))
from local_data import read_table
from local_analysis import execute
from local_provenance import ENGINE_SHA256, environment_info, result_digest, verify_runtime_sources
config = json.loads((root / "reproduzir.json").read_text(encoding="utf-8"))
expected_env = json.loads((root / "ambiente.json").read_text(encoding="utf-8"))
current_env = environment_info()
changes = [name for name, value in expected_env["packages"].items() if value and current_env["packages"].get(name) != value]
if current_env["python"] != expected_env["python"]:
    changes.append("python")
if changes and not args.permitir_ambiente_diferente:
    raise SystemExit("Ambiente diferente em: " + ", ".join(changes) + ". Instale as versões registradas ou use --permitir-ambiente-diferente para comparar explicitamente.")
verify_runtime_sources()
if ENGINE_SHA256 != config["engine_sha256"]:
    raise SystemExit("O código arquivado difere do código registrado para a reexecução.")
raw = path_in_bundle(config["dataset"]).read_bytes()
if hashlib.sha256(raw).hexdigest() != config["dataset_sha256"]:
    raise SystemExit("A planilha não corresponde ao hash registrado.")
frame = read_table(config["dataset"], raw)
destination = root / "reproduzidos"
destination.mkdir(exist_ok=True)
summary = []
for index, request in enumerate(config["analyses"], 1):
    result = execute(frame, request["mapping"], request["scenario"], row_limit=None, parameters=request.get("parameters", {}))
    reference = json.loads(path_in_bundle(request["reference"]).read_text(encoding="utf-8"))
    identical = result_digest(result) == result_digest(reference)
    (destination / f"analise_{index:02}.json").write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    summary.append({"scenario": request["scenario"], "identical_result": identical})
    print(f"{request['scenario']}: {'coincide' if identical else 'resultado diferente; revisar'}")
(destination / "comparacao.json").write_text(json.dumps({"environment": current_env, "environment_changes": changes, "analyses": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
if not summary:
    print("Nenhuma reexecução disponível; consulte os motivos no manifesto.")
raise SystemExit(0 if all(row["identical_result"] for row in summary) else 1)
'''


def build_bundle(project):
    verify_runtime_sources()
    raw = base64.b64decode(project["file_base64"], validate=True)
    dataset_hash = hashlib.sha256(raw).hexdigest()
    if dataset_hash != project["dataset_sha256"]:
        raise ValueError("A planilha não corresponde ao hash do projeto salvo.")
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    suffix = Path(project["filename"]).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise ValueError("Formato da planilha do projeto inválido.")
    dataset_name = f"dados/original{suffix}"
    files = {}
    def put(name, content):
        files[name] = content
        if sum(map(len, files.values())) > MAX_EXPORT_BYTES:
            raise ValueError("O conteúdo do pacote ultrapassa 64 MB. Reduza o conjunto de dados para exportar.")

    put(dataset_name, raw)
    put("projeto.json", _json({key: value for key, value in project.items() if key not in {"file_base64", "execution_history"}}))
    run_ids = set()
    for result in project.get("execution_history", []):
        trace = result.get("rastreabilidade", {}) if isinstance(result, dict) else {}
        run_id = trace.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", run_id) or run_id in run_ids:
            raise ValueError("O histórico de execuções do projeto está inválido ou repetido.")
        run_ids.add(run_id)
        schema = trace.get("schema_version", 1)
        if (trace.get("dataset_sha256") != dataset_hash
                or trace.get("result_sha256") != result_digest(result, version=schema)
                or trace.get("execution_sha256") != provenance_digest(trace, version=schema)):
            raise ValueError("Uma execução histórica não confere com os dados ou hashes registrados.")
        put(f"execucoes/{run_id}.json", _json(result))
    env = environment_info()
    put("ambiente.json", _json(env))
    requirements = [f"{name}=={value}" for name, value in env["packages"].items() if value]
    put("requirements-congelados.txt", ("\n".join(requirements) + "\n").encode("utf-8"))
    put("requirements-local.txt", (ROOT / "requirements-local.txt").read_bytes())
    for name, content in SOURCE_SNAPSHOT.items():
        put("codigo/" + name, content)

    frame = read_table(project["filename"], raw)
    allowed = {item[0] for item in CATALOG}
    records, reproduced, recorded_report, config = [], [], [], []
    for index, (scenario, saved) in enumerate((project.get("analyses") or {}).items(), 1):
        prefix = f"analise_{index:02}"
        saved_name = f"analises_salvas/{prefix}.json"
        put(saved_name, _json(saved))
        record = {"scenario": scenario, "recorded_file": saved_name, "status": "not_reexecuted"}
        records.append(record)
        if isinstance(saved, dict) and all(isinstance(saved.get(key), list) for key in ("linhas", "colunas", "indicadores", "observacoes")):
            recorded_report.append(saved)
        try:
            if scenario not in allowed or not isinstance(saved, dict):
                raise ValueError("Cenário não reconhecido pela versão atual; preservado apenas o registro original.")
            origin = saved.get("rastreabilidade") or {}
            if origin and (origin.get("dataset_sha256") != dataset_hash or origin.get("scenario") != scenario):
                raise ValueError("A origem registrada não corresponde à planilha/cenário do projeto; reexecução recusada.")
            if origin and origin.get("result_sha256") != result_digest(saved, version=origin.get("schema_version", 1)):
                raise ValueError("O resultado salvo difere do hash registrado; reexecução recusada.")
            if origin and origin.get("execution_sha256") != provenance_digest(origin, version=origin.get("schema_version", 1)):
                raise ValueError("Os parâmetros da rastreabilidade diferem do hash da execução; reexecução recusada.")
            mapping = origin.get("mapping") if origin else project.get("mapping", {})
            if not isinstance(mapping, dict):
                raise ValueError("Mapeamento registrado inválido.")
            record["mapping_basis"] = "execution_record" if origin else "project_mapping_legacy_unverified"
            parameters = origin.get("parameters", {})
            if not isinstance(parameters, dict):
                raise ValueError("Parâmetros da execução registrada inválidos.")
            result = execute(frame, mapping, scenario, row_limit=None, parameters=parameters)
            preview = copy.deepcopy(result)
            preview["linhas"] = preview["linhas"][:len(saved.get("linhas", []))]
            record["matches_recorded_preview"] = result_digest(preview) == result_digest(saved)
            record["recorded_engine_sha256"] = origin.get("engine_sha256")
            attach_provenance(result, raw, mapping, scenario, len(frame), parameters=parameters)
            name = f"reexecucoes/{prefix}.json"
            put(name, _json(result))
            csv_name = f"reexecucoes/{prefix}.csv"
            put(csv_name, _csv(result))
            record.update({"status": "reexecuted", "complete_result": name, "complete_table": csv_name,
                           "rows": result["linhas_total"], "new_run_id": result["rastreabilidade"]["run_id"]})
            reproduced.append(result)
            config.append({"scenario": scenario, "mapping": mapping, "parameters": parameters, "reference": name})
        except (ValueError, TypeError, KeyError) as exc:
            record["reason"] = str(exc)

    diagnosis = diagnose(frame, project.get("mapping") or {}, project.get("objective") or "")
    put("triagem_reexecutada.json", _json(diagnosis))
    warnings = []
    for record in records:
        label = str(record["scenario"])
        if record["status"] != "reexecuted":
            warnings.append(f"{label}: {record.get('reason', 'reexecução indisponível')} O relatório salvo preserva o registro recebido; não o atribua à planilha atual como cálculo conferido.")
        elif record.get("mapping_basis") == "project_mapping_legacy_unverified":
            warnings.append(f"{label}: a análise antiga não registra a origem dos parâmetros. O novo cálculo usou o mapeamento atual do projeto, sem confirmar como a análise antiga foi feita.")
        if record.get("matches_recorded_preview") is False:
            warnings.append(f"{label}: o novo cálculo difere da prévia salva. Revise as versões de código, ambiente e parâmetros antes de interpretar a diferença.")
    put("relatorio_salvo.html", standalone_report(_report(project, recorded_report, project.get("diagnosis") or {}, "snapshot", exported_at, warnings)))
    put("relatorio_reexecutado.html", standalone_report(_report(project, reproduced, diagnosis, "reexecucao", exported_at, warnings)))
    put("reproduzir.json", _json({"dataset": dataset_name, "dataset_sha256": dataset_hash, "engine_sha256": ENGINE_SHA256, "analyses": config}))
    put("verificar_pacote.py", VERIFY_SCRIPT.encode("utf-8"))
    put("reproduzir_analises.py", REPRODUCE_SCRIPT.encode("utf-8"))
    readme = f"""# Pacote do projeto SigmaFlow

Projeto: {project['id']} · versão {project['version']}
Exportado em UTC: {exported_at}

Abra relatorio_salvo.html para consultar a análise registrada e as anotações.
Abra relatorio_reexecutado.html para consultar os NOVOS cálculos feitos ao exportar.
Ambos são autocontidos: não precisam do servidor, internet ou sessão do navegador.
Tabelas HTML são prévias de até 100 linhas. reexecucoes/*.json e *.csv contêm as tabelas integrais dos cálculos que puderam ser reexecutados.

projeto.json e analises_salvas preservam o estado original. A exportação não substitui o projeto, não aprova fases DMAIC e não valida conclusões estatísticas.
execucoes/*.json preserva cada execução histórica, incluindo parâmetros e resultado original. Os hashes são verificados ao montar o pacote.
manifesto.json lista reexecuções, correspondência da prévia e motivos de recusa. Análises antigas sem rastreabilidade usam o mapeamento salvo do projeto como base NÃO VERIFICADA; não se atribui esse mapeamento à execução antiga.

Após extrair o ZIP, para conferir os arquivos (somente biblioteca padrão):
    python verificar_pacote.py
Hashes detectam alteração em relação ao manifesto; não são assinatura de autoria.

Para reproduzir os novos cálculos, use a versão Python registrada em ambiente.json e instale as dependências em um ambiente separado:
    python -m pip install -r requirements-congelados.txt
    python reproduzir_analises.py
O código de cálculo está em codigo/. A rotina guarda novos arquivos em reproduzidos/ e compara o resultado com a reexecução exportada. Se Python/pacotes diferirem, ela interrompe; --permitir-ambiente-diferente permite uma comparação explícita. Plataformas distintas podem produzir diferenças numéricas. A identidade do código e a comparação não comprovam validade metodológica.

CSV usa UTF-8 com BOM e ponto e vírgula. Textos que poderiam ser fórmulas em planilhas recebem apóstrofo protetor; JSON preserva os textos originais. Não altere os arquivos originais do pacote para registrar uma nova interpretação.
O pacote contém a planilha original e as anotações do projeto; sua distribuição compartilha esses dados.
"""
    put("LEIA-ME.txt", readme.encode("utf-8"))
    manifest = {"schema_version": 1, "project_id": project["id"], "project_version": project["version"], "exported_at": exported_at,
                "dataset_sha256": dataset_hash, "engine_sha256": ENGINE_SHA256, "original_filename": project["filename"],
                "revision_event": project.get("revision_event"), "derived_from": project.get("derived_from"),
                "executions": records, "csv_formula_protection": True,
                "files": {name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)} for name, content in files.items()}}
    put("manifesto.json", _json(manifest))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()
