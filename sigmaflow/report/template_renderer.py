"""
sigmaflow/report/template_renderer.py
=======================================
Motor de renderizacao de templates LaTeX usando Jinja2.

Responsabilidades:
  - Carregar templates .tex de sigmaflow/report/templates/
  - Renderizar com contexto Python via Jinja2
  - Gravar os arquivos .tex no diretorio de saida

Uso:
    from sigmaflow.report.template_renderer import TemplateRenderer

    renderer = TemplateRenderer(output_dir="output/reports/final")
    renderer.render("sections/measure.tex", context_dict, "sections/measure.tex")
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

import jinja2

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Jinja2 para LaTeX: delimitadores alternados (evitam conflito com {})
_JINJA_ENV = jinja2.Environment(
    loader          = jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    block_start_string    = "{%",
    block_end_string      = "%}",
    variable_start_string = "{{",
    variable_end_string   = "}}",
    comment_start_string  = "{#",
    comment_end_string    = "#}",
    keep_trailing_newline = True,
    autoescape            = False,     # LaTeX, nao HTML
    undefined             = jinja2.Undefined,
)

# Mapa unicode → LaTeX aplicado em todos os valores de string no contexto
_ACCENTS = {
    "á": r"\'a", "é": r"\'e", "í": r"\'i", "ó": r"\'o", "ú": r"\'u",
    "Á": r"\'A", "É": r"\'E", "Í": r"\'I", "Ó": r"\'O", "Ú": r"\'U",
    "â": r"\^a", "ê": r"\^e", "ô": r"\^o",
    "Â": r"\^A", "Ê": r"\^E", "Ô": r"\^O",
    "ã": r"\~a", "õ": r"\~o",
    "Ã": r"\~A", "Õ": r"\~O",
    "à": r"\`a",
    "ç": r"\c{c}", "Ç": r"\c{C}",
    "σ": r"$\sigma$", "μ": r"$\mu$",
    "≥": r"$\geq$",   "≤": r"$\leq$",
    "\u2013": "--", "\u2014": "---",
}


def _sanitize(text: str) -> str:
    """Converte string para ASCII LaTeX-safe."""
    s = str(text)
    for uni, cmd in _ACCENTS.items():
        s = s.replace(uni, cmd)
    return "".join(c if ord(c) < 128 else "?" for c in s)


def _sanitize_context(obj: Any) -> Any:
    """Aplica _sanitize recursivamente em dicts/lists/strings."""
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_context(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_context(item) for item in obj]
    return obj


class TemplateRenderer:
    """
    Renderiza templates LaTeX Jinja2 e grava os resultados no diretorio de saida.

    Parameters
    ----------
    output_dir : str | Path
        Diretorio raiz onde main.tex e as secoes serao escritas.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "sections").mkdir(exist_ok=True)
        (self.output_dir / "figures").mkdir(exist_ok=True)

    def render(
        self,
        template_name: str,
        context:       Dict[str, Any],
        output_rel:    str,
    ) -> Path:
        """
        Renderiza um template Jinja2 e grava o resultado.

        Parameters
        ----------
        template_name : str
            Caminho relativo ao diretorio templates/ (ex: "sections/measure.tex").
        context : dict
            Variaveis passadas ao template.
        output_rel : str
            Caminho relativo ao output_dir onde o arquivo sera gravado.

        Returns
        -------
        Path
            Caminho absoluto do arquivo gerado.
        """
        try:
            template = _JINJA_ENV.get_template(template_name)
        except jinja2.TemplateNotFound:
            logger.error("Template nao encontrado: %s", template_name)
            raise

        clean_ctx = _sanitize_context(context)

        try:
            rendered = template.render(**clean_ctx)
        except jinja2.TemplateError as exc:
            logger.error("Erro ao renderizar %s: %s", template_name, exc)
            raise

        out_path = self.output_dir / output_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="ascii", errors="replace")
        logger.debug("Renderizado: %s -> %s", template_name, out_path)
        return out_path

    def render_all(self, sections: Dict[str, Dict[str, Any]]) -> None:
        """
        Renderiza todas as secoes de uma vez.

        Parameters
        ----------
        sections : dict
            Mapa {template_name: context_dict}.
            A chave 'main' e reservada para main.tex.
        """
        for template_name, context in sections.items():
            if template_name == "main":
                self.render("main.tex", context, "main.tex")
            else:
                self.render(
                    f"sections/{template_name}.tex",
                    context,
                    f"sections/{template_name}.tex",
                )
        logger.info("Todas as secoes renderizadas em: %s", self.output_dir)

    def copy_figures(self, figure_paths: list) -> None:
        """Copia figuras para output_dir/figures/."""
        fig_dir = self.output_dir / "figures"
        fig_dir.mkdir(exist_ok=True)
        copied = 0
        for fp in figure_paths:
            src = Path(fp)
            if src.exists():
                shutil.copy2(src, fig_dir / src.name)
                copied += 1
        logger.info("%d figura(s) copiada(s) para %s", copied, fig_dir)
