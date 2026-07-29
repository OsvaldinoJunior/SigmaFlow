"""
sigmaflow/report/template_engine/template_manager.py
======================================================
Gerenciador de templates LaTeX modulares do SigmaFlow.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "report_template"
_PREFIX = "SIGMAFLOW_"

# Mapa completo unicode → LaTeX para todos os caracteres portugueses + estatísticos
_UNICODE_TO_LATEX = {
    # Vogais com acento agudo
    "á": r"\'a", "é": r"\'e", "í": r"\'i", "ó": r"\'o", "ú": r"\'u",
    "Á": r"\'A", "É": r"\'E", "Í": r"\'I", "Ó": r"\'O", "Ú": r"\'U",
    # Vogais com acento circunflexo
    "â": r"\^a", "ê": r"\^e", "î": r"\^i", "ô": r"\^o", "û": r"\^u",
    "Â": r"\^A", "Ê": r"\^E", "Î": r"\^I", "Ô": r"\^O", "Û": r"\^U",
    # Vogais com til
    "ã": r"\~a", "õ": r"\~o", "ñ": r"\~n",
    "Ã": r"\~A", "Õ": r"\~O", "Ñ": r"\~N",
    # Vogais com grave
    "à": r"\`a", "è": r"\`e", "ì": r"\`i", "ò": r"\`o", "ù": r"\`u",
    "À": r"\`A", "È": r"\`E", "Ì": r"\`I", "Ò": r"\`O", "Ù": r"\`U",
    # Vogais com trema
    "ä": r"\"a", "ë": r"\"e", "ï": r"\"i", "ö": r"\"o", "ü": r"\"u",
    "Ä": r"\"A", "Ë": r"\"E", "Ï": r"\"I", "Ö": r"\"O", "Ü": r"\"U",
    # Cedilha
    "ç": r"\c{c}", "Ç": r"\c{C}",
    # Símbolos matemáticos comuns em outputs estatísticos
    "σ": r"$\sigma$", "μ": r"$\mu$", "α": r"$\alpha$",
    "β": r"$\beta$",  "δ": r"$\delta$",
    "≥": r"$\geq$",   "≤": r"$\leq$",   "≠": r"$\neq$",
    "±": r"$\pm$",    "×": r"$\times$",  "≈": r"$\approx$",
    "→": r"$\rightarrow$", "∞": r"$\infty$",
    # Pontuação especial
    "\u2013": "--",   # en-dash
    "\u2014": "---",  # em-dash
    "\u2026": r"\ldots{}",
    "\u00a0": "~",    # non-breaking space
}


def _sanitize_tex(text: str) -> str:
    """Converte todos os caracteres não-ASCII para comandos LaTeX equivalentes."""
    for uni, cmd in _UNICODE_TO_LATEX.items():
        text = text.replace(uni, cmd)
    # Fallback: remove qualquer unicode restante (não deve acontecer)
    result = []
    for ch in text:
        if ord(ch) < 128:
            result.append(ch)
        else:
            logger.warning("Caractere unicode não mapeado removido: U+%04X (%s)", ord(ch), ch)
            result.append("?")
    return "".join(result)


class TemplateManager:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir  = Path(output_dir)
        self._replacements: Dict[str, str] = {}

    def setup(self) -> "TemplateManager":
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        shutil.copytree(_TEMPLATE_DIR, self.output_dir)
        logger.info("Template copiado para: %s", self.output_dir)
        return self

    def set(self, key: str, value: str) -> "TemplateManager":
        self._replacements[f"{_PREFIX}{key}"] = value
        return self

    def apply(self) -> "TemplateManager":
        """
        Aplica substituições e converte TODOS os caracteres não-ASCII
        para comandos LaTeX em todos os .tex do diretório de saída.
        """
        tex_files = list(self.output_dir.rglob("*.tex"))

        for tex_path in tex_files:
            content = tex_path.read_text(encoding="utf-8")

            # 1. Substituir placeholders
            for placeholder, replacement in self._replacements.items():
                content = content.replace(placeholder, replacement)

            # 2. Sanitizar unicode → LaTeX em TODO o arquivo
            content = _sanitize_tex(content)

            tex_path.write_text(content, encoding="ascii", errors="replace")

        logger.info("Placeholders aplicados em %d arquivos .tex", len(tex_files))
        return self

    def finalize_figures(self, figure_paths: list) -> "TemplateManager":
        figures_dir = self.output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for fp in figure_paths:
            src = Path(fp)
            if src.exists():
                shutil.copy2(src, figures_dir / src.name)
                copied += 1
        logger.info("%d figura(s) copiada(s) para %s", copied, figures_dir)
        return self

    def main_tex_path(self) -> Path:
        return self.output_dir / "main.tex"

    def get_output_dir(self) -> Path:
        return self.output_dir
