"""Spreadsheet reader shared by the local server and portable reproduction."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


def read_table(name: str, raw: bytes) -> pd.DataFrame:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        last_error = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding=encoding)
            except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                last_error = exc
        raise ValueError("Não foi possível ler o CSV. Confira o arquivo e seu separador.") from last_error
    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(io.BytesIO(raw))
        except ImportError as exc:
            raise ValueError("Para abrir este Excel, instale openpyxl para .xlsx ou xlrd para .xls.") from exc
    raise ValueError("Formato não suportado. Use CSV, XLSX ou XLS.")
