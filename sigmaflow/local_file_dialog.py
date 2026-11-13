"""Abre uma caixa nativa escolhida pelo usuário para a interface local."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from tkinter import Tk, filedialog


def main() -> dict:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.update()
    try:
        name = filedialog.askopenfilename(
            parent=root,
            title="Selecione a planilha para o SigmaFlow",
            initialdir=str(Path.home()),
            filetypes=[("Planilhas CSV e Excel", "*.csv *.xlsx *.xls"), ("Todos os arquivos", "*.*")],
        )
    finally:
        root.destroy()
    if not name:
        return {"cancelled": True}
    path = Path(name)
    if path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
        return {"error": "Selecione uma planilha CSV, XLSX ou XLS."}
    if path.stat().st_size > 10 * 1024 * 1024:
        return {"error": "A planilha deve ter no máximo 10 MB."}
    return {"name": path.name, "content": base64.b64encode(path.read_bytes()).decode("ascii")}


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        result = {"error": "Não foi possível abrir ou ler a planilha. Tente novamente."}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
