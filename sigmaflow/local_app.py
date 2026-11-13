"""Servidor local de demonstração: python sigmaflow/local_app.py."""
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from local_diagnosis import diagnose
from local_analysis import execute
from local_project_store import (ProjectConflictError, copy_version, delete_project,
                                 list_projects, list_versions, load_project,
                                 restore_version, save_project)
from local_data import read_table
from local_export import build_bundle, build_snapshot_report
from local_provenance import attach_provenance, verify_runtime_sources

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "local"
MAX_REQUEST = 24 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024
FILES = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css", "/upload.css": "upload.css",
         "/charts.js": "charts.js", "/case-store.js": "case-store.js", "/case-workspace.css": "case-workspace.css",
         "/relatorio": "report.html", "/report.js": "report.js", "/report.css": "report.css", "/project-report.css": "project-report.css"}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, result: dict) -> None:
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/projetos":
            if self.headers.get("Host", "") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                self._json(403, {"error": "A API de projetos só está disponível na interface local."})
                return
            self._json(200, {"projects": list_projects()})
            return
        if path.startswith("/api/projetos/"):
            if self.headers.get("Host", "") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                self._json(403, {"error": "A API de projetos s\u00f3 est\u00e1 dispon?vel na interface local."})
                return
            parts = path.removeprefix("/api/projetos/").split("/")
            project_id = parts[0]
            if len(parts) == 2 and parts[1] == "historico":
                query = parse_qs(urlsplit(self.path).query)
                try:
                    limit = int(query.get("limit", ["50"])[0])
                    before = int(query["before"][0]) if query.get("before") else None
                    self._json(200, list_versions(project_id, limit=limit, before=before))
                except (ValueError, TypeError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if len(parts) >= 3 and parts[1] == "versoes":
                try:
                    version = int(parts[2])
                    if len(parts) == 4 and parts[3] == "relatorio":
                        project = load_project(project_id, version=version)
                        data = build_snapshot_report(project)
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(data)
                    elif len(parts) == 3:
                        self._json(200, load_project(project_id, version=version))
                    else:
                        self.send_error(404)
                except FileNotFoundError as exc:
                    self._json(404, {"error": str(exc)})
                except (ValueError, TypeError) as exc:
                    self._json(404 if "n\u00e3o encontrado" in str(exc).lower() else 400, {"error": str(exc)})
                return
            if len(parts) == 2 and parts[1] == "exportar":
                host = self.headers.get("Host", "")
                origin = self.headers.get("Origin")
                if self.headers.get("X-SigmaFlow-Export") != "1" or (origin and origin != f"http://{host}"):
                    self._json(403, {"error": "Baixe o pacote pela interface local."})
                    return
                try:
                    version = int(parse_qs(urlsplit(self.path).query).get("version", [""])[0])
                    project = load_project(project_id, version=version)
                    data = build_bundle(project)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f'attachment; filename="sigmaflow-{project["id"]}-v{version}.zip"')
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                except FileNotFoundError as exc:
                    self._json(404, {"error": str(exc)})
                except (ValueError, TypeError, KeyError) as exc:
                    self._json(404 if "n\u00e3o encontrado" in str(exc).lower() else 400, {"error": str(exc) or "N\u00e3o foi poss\u00f3vel preparar o pacote do projeto."})
                except Exception:
                    self._json(500, {"error": "N\u00e3o foi poss\u00f3vel gerar o pacote local do projeto."})
                return
            if len(parts) != 1:
                self.send_error(404)
                return
            try:
                self._json(200, load_project(project_id))
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            return
        name = FILES.get(path)
        if not name:
            self.send_error(404)
            return
        data = (FRONTEND / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(name)[0] or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        if "/versoes/" in route and (route.endswith("/copiar") or route.endswith("/restaurar")):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in allowed or origin != f"http://{host}":
                self._json(403, {"error": "Origem n\u00e3o autorizada."})
                return
            try:
                payload = self._project_payload()
                parts = route.removeprefix("/api/projetos/").split("/")
                if len(parts) != 4 or parts[1] != "versoes":
                    self.send_error(404)
                    return
                version = int(parts[2])
                if parts[3] == "copiar":
                    result = copy_version(parts[0], version, title=payload.get("title"), reason=payload.get("reason", ""))
                else:
                    result = restore_version(parts[0], version, payload.get("base_version"), payload.get("reason", ""))
                self._json(201, result)
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc) or "Projeto inv\u00e1lido."})
            return
        if route not in {"/api/diagnostico", "/api/selecionar-planilha", "/api/analises"}:
            self.send_error(404)
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts or (origin and origin != f"http://{host}"):
            self._json(403, {"error": "Origem não autorizada."})
            return
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            self._json(415, {"error": "Envie os dados em JSON."})
            return
        if route == "/api/selecionar-planilha":
            allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in allowed_hosts or origin != f"http://{host}":
                self._json(403, {"error": "Selecione o arquivo a partir da página local."})
                return
            try:
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).with_name("local_file_dialog.py"))],
                    capture_output=True, timeout=180, check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._json(200, json.loads(result.stdout.decode("utf-8")))
            except subprocess.TimeoutExpired:
                self._json(408, {"error": "A seleção demorou muito. Clique novamente para escolher a planilha."})
            except (OSError, ValueError, subprocess.CalledProcessError):
                self._json(500, {"error": "Não foi possível abrir o seletor do computador."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST:
                raise ValueError("Arquivo muito grande. O limite é 10 MB.")
            payload = json.loads(self.rfile.read(length))
            raw = base64.b64decode(payload.get("content", ""), validate=True)
            if not raw or len(raw) > MAX_FILE:
                raise ValueError("Arquivo vazio ou maior que 10 MB.")
            mapping = payload.get("mapping", {})
            if not isinstance(mapping, dict):
                raise ValueError("Mapeamento de colunas inválido.")
            verify_runtime_sources()
            df = read_table(str(payload.get("filename", "")), raw)
            if route == "/api/analises":
                scenario = str(payload.get("scenario", ""))
                parameters = payload.get("parameters", {})
                result = execute(df, mapping, scenario, parameters=parameters)
                attach_provenance(result, raw, mapping, scenario, len(df), parameters=parameters)
            else:
                result = diagnose(df, mapping, str(payload.get("objective", ""))[:2000])
            self._json(200, result)
        except (ValueError, TypeError, KeyError, binascii.Error, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc) or "Arquivo ou dados inválidos."})
        except Exception:
            self._json(500, {"error": "Não foi possível analisar o arquivo. Confira o formato e tente novamente."})

    def _project_payload(self) -> dict:
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise ValueError("Envie os dados do projeto em JSON.")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST:
            raise ValueError("O projeto ou arquivo é inválido ou ultrapassa 10 MB.")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("O projeto enviado é inválido.")
        return payload

    def do_PUT(self) -> None:
        path = urlsplit(self.path).path
        if not path.startswith("/api/projetos/"):
            self.send_error(404)
            return
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts or origin != f"http://{host}":
            self._json(403, {"error": "Origem não autorizada."})
            return
        try:
            payload = self._project_payload()
            project_id = path.removeprefix("/api/projetos/")
            if payload.get("id") and payload["id"] != project_id:
                raise ValueError("O identificador do projeto não corresponde à rota.")
            payload["id"] = project_id
            self._json(200, save_project(payload, require_base_version=True))
        except ProjectConflictError as exc:
            self._json(409, {"error": str(exc), "code": "version_conflict", "current_version": exc.current_version})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc) or "Projeto inv\u00e1lido."})
        except Exception:
            self._json(500, {"error": "N\u00e3o foi poss\u00f3vel salvar o projeto neste computador."})

    def do_DELETE(self) -> None:
        path = urlsplit(self.path).path
        if not path.startswith("/api/projetos/"):
            self.send_error(404)
            return
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts or origin != f"http://{host}":
            self._json(403, {"error": "Origem não autorizada."})
            return
        try:
            delete_project(path.removeprefix("/api/projetos/"))
            self._json(200, {"deleted": True})
        except FileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})


def main() -> None:
    port = int(os.environ.get("SIGMAFLOW_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SigmaFlow local: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
