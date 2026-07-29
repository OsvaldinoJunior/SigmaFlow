"""
sigmaflow/report/latex_report.py  (v8)
========================================
Scientific-quality LaTeX report generator — SigmaFlow v8.

New report structure (v8):
    1. Title page
    2. Abstract         ← auto-generated summary of findings
    3. Table of contents
    4. Introduction     ← methodology overview
    5. Methodology      ← statistical methods used
    6. Dataset Description
    7. Statistical Analysis (tables)
    8. Process Stability Analysis (control charts)
    9. Capability Analysis (Cp, Cpk with interpretation)
   10. Detected Anomalies (Western Electric rules)
   11. Root Cause Indicators (correlation ranking table)
   12. Recommendations
   13. Conclusion

Usage
-----
    from sigmaflow.report.latex_report import LatexReportGenerator
    gen = LatexReportGenerator(results, output_dir="output/reports")
    pdf_path = gen.generate()
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── LaTeX escape ─────────────────────────────────────────────────────────────
#
# IMPORTANT — ordering matters.
#
# str.maketrans() replaces all chars in a single pass, so it cannot be used
# here: after we turn "\" into "\textbackslash{}" the braces "{" and "}"
# would be escaped again in a second pass.
#
# The solution is a *sentinel* strategy:
#   1. Replace every real "\" with a placeholder that never appears in text.
#   2. Escape all other special characters normally.
#   3. Swap the placeholder for "\textbackslash{}".
#
# This guarantees that the braces in "\textbackslash{}" are never re-escaped.

# ── Unicode → LaTeX command map ───────────────────────────────────────────────
# Common non-ASCII characters that appear in statistical / scientific output
# and must be converted to LaTeX commands because the report uses [T1]{fontenc}
# with lmodern (not XeLaTeX / LuaLaTeX, which handle Unicode natively).
_UNICODE_MAP: dict[str, str] = {
    # Greek letters (lower)
    "α": r"\(\alpha\)",   "β": r"\(\beta\)",    "γ": r"\(\gamma\)",
    "δ": r"\(\delta\)",   "ε": r"\(\varepsilon\)","ζ": r"\(\zeta\)",
    "η": r"\(\eta\)",     "θ": r"\(\theta\)",   "ι": r"\(\iota\)",
    "κ": r"\(\kappa\)",   "λ": r"\(\lambda\)",  "μ": r"\(\mu\)",
    "ν": r"\(\nu\)",      "ξ": r"\(\xi\)",      "π": r"\(\pi\)",
    "ρ": r"\(\rho\)",     "σ": r"\(\sigma\)",   "τ": r"\(\tau\)",
    "υ": r"\(\upsilon\)", "φ": r"\(\varphi\)",  "χ": r"\(\chi\)",
    "ψ": r"\(\psi\)",     "ω": r"\(\omega\)",
    # Greek letters (upper)
    "Α": "A",  "Β": "B",  "Γ": r"\(\Gamma\)",   "Δ": r"\(\Delta\)",
    "Ε": "E",  "Ζ": "Z",  "Η": "H",             "Θ": r"\(\Theta\)",
    "Ι": "I",  "Κ": "K",  "Λ": r"\(\Lambda\)",  "Μ": "M",
    "Ν": "N",  "Ξ": r"\(\Xi\)",  "Ο": "O",      "Π": r"\(\Pi\)",
    "Ρ": "R",  "Σ": r"\(\Sigma\)", "Τ": "T",    "Υ": r"\(\Upsilon\)",
    "Φ": r"\(\Phi\)", "Χ": "X",  "Ψ": r"\(\Psi\)", "Ω": r"\(\Omega\)",
    # Mathematical / typographic symbols
    "±": r"\(\pm\)",       "×": r"\(\times\)",   "÷": r"\(\div\)",
    "≤": r"\(\leq\)",      "≥": r"\(\geq\)",     "≠": r"\(\neq\)",
    "≈": r"\(\approx\)",   "∞": r"\(\infty\)",   "√": r"\(\sqrt{}\)",
    "∑": r"\(\sum\)",      "∏": r"\(\prod\)",    "∫": r"\(\int\)",
    "→": r"\(\rightarrow\)", "←": r"\(\leftarrow\)",
    "↑": r"\(\uparrow\)",  "↓": r"\(\downarrow\)",
    "•": r"\textbullet{}",
    "·": r"\(\cdot\)",
    "°": r"\(\circ\)",
    "′": r"'",   "″": r"''",
    # Accented Latin characters (common in dataset names / author names)
    "á": r"\'{a}",  "é": r"\'{e}",  "í": r"\'{i}",
    "ó": r"\'{o}",  "ú": r"\'{u}",  "ý": r"\'{y}",
    "Á": r"\'{A}",  "É": r"\'{E}",  "Í": r"\'{I}",
    "Ó": r"\'{O}",  "Ú": r"\'{U}",
    "à": r"\`{a}",  "è": r"\`{e}",  "ì": r"\`{i}",
    "ò": r"\`{o}",  "ù": r"\`{u}",
    "â": r"\^{a}",  "ê": r"\^{e}",  "î": r"\^{i}",
    "ô": r"\^{o}",  "û": r"\^{u}",
    "ä": r'\"{a}',  "ë": r'\"{e}',  "ï": r'\"{i}',
    "ö": r'\"{o}',  "ü": r'\"{u}',  "ÿ": r'\"{y}',
    "Ä": r'\"{A}',  "Ë": r'\"{E}',  "Ï": r'\"{I}',
    "Ö": r'\"{O}',  "Ü": r'\"{U}',
    "ã": r"\~{a}",  "õ": r"\~{o}",  "ñ": r"\~{n}",
    "Ã": r"\~{A}",  "Õ": r"\~{O}",  "Ñ": r"\~{N}",
    "ç": r"\c{c}",  "Ç": r"\c{C}",
    "ß": r"\ss{}",
    # Typographic punctuation
    "\u2018": "`",   "\u2019": "'",    # ' '
    "\u201c": "``",  "\u201d": "''",   # " "
    "\u2013": "--",  "\u2014": "---",  # – —
    "\u2026": r"\ldots{}",             # …
    "\u00a0": "~",                     # non-breaking space
}


def latex_escape(text: str) -> str:
    """Return *text* with every LaTeX-unsafe character safely escaped.

    Handles two categories of problematic content:

    1. **LaTeX special characters** (``& % $ # _ { } ~ ^ \\``) — replaced
       with their standard LaTeX escape sequences.
    2. **Non-ASCII / Unicode characters** — replaced with the appropriate
       LaTeX commands (e.g. ``τ`` → ``\\(\\tau\\)``).  Any remaining
       non-ASCII characters not covered by the built-in map are replaced
       with ``?`` so the document always compiles.

    This function is safe to call on dataset names, column names, insight
    strings, captions, and any other dynamic content written into the
    ``.tex`` file.

    Parameters
    ----------
    text:
        Plain-text string that may contain LaTeX-special or Unicode chars.

    Returns
    -------
    str
        LaTeX-safe string, ready for use inside ``\\section{…}``,
        table cells, ``\\caption{…}``, etc.

    Examples
    --------
    >>> latex_escape("cost_per_unit & 50% profit")
    'cost\\_per\\_unit \\& 50\\% profit'
    >>> latex_escape("τ (Kendall tau)")
    '\\(\\tau\\) (Kendall tau)'
    >>> latex_escape("mean ± 3σ")
    'mean \\(\\pm\\) 3\\(\\sigma\\)'
    """
    if not isinstance(text, str):
        text = str(text)

    # ── Phase A: escape ASCII-only content ───────────────────────────────────
    # Use a sentinel so that backslashes are not re-escaped when we later
    # introduce \textbackslash{}.
    _BS = "\x00BSLASH\x00"
    ascii_only = "".join(ch if ord(ch) < 128 else "\x00NONASCII\x00" + ch for ch in text)

    # Protect real backslashes in the ASCII portion.
    ascii_only = ascii_only.replace("\\", _BS)

    _REPLACEMENTS = [
        ("&", r"\&"),   ("%", r"\%"),   ("$", r"\$"),
        ("#", r"\#"),   ("_", r"\_"),   ("{", r"\{"),
        ("}", r"\}"),   ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, escaped in _REPLACEMENTS:
        ascii_only = ascii_only.replace(char, escaped)

    ascii_only = ascii_only.replace(_BS, r"\textbackslash{}")

    # ── Phase B: restore non-ASCII characters with their LaTeX equivalents ───
    # We process the escaped ASCII string character-by-character, replacing
    # the \x00NONASCII\x00<ch> markers with the correct LaTeX command.
    # Because we insert the LaTeX command *after* all ASCII escaping is done,
    # the backslashes and braces in commands like \(\tau\) are never touched.
    _NAS = "\x00NONASCII\x00"
    result = []
    i = 0
    while i < len(ascii_only):
        if ascii_only[i:i+len(_NAS)] == _NAS:
            ch = ascii_only[i+len(_NAS)]        # the original Unicode char
            result.append(_UNICODE_MAP.get(ch, "?"))
            i += len(_NAS) + 1
        else:
            result.append(ascii_only[i])
            i += 1

    return "".join(result)


# Module-internal shorthand: _e(x) == latex_escape(str(x))
def _e(s: Any) -> str:
    """Escape *s* for LaTeX output (alias for :func:`latex_escape`)."""
    return latex_escape(str(s))

def _sev_color(sev: str) -> str:
    return {"critical": "sigmaRed", "warning": "sigmaOrange", "info": "sigmaGreen"}.get(sev, "black")


class LatexReportGenerator:
    """
    Builds a full scientific LaTeX report from SigmaFlow pipeline results.

    Parameters
    ----------
    results : list[dict]   Output from Engine.run()
    output_dir : str|Path  Where .tex and .pdf are saved
    title : str            Report title
    author : str           Author name
    """

    def __init__(
        self,
        results: List[Dict[str, Any]],
        output_dir: str | Path = "output/reports",
        title: str = "SigmaFlow — Automated DMAIC Analysis Report",
        author: str = "SigmaFlow Engine v8",
    ) -> None:
        self.results    = results
        self.output_dir = Path(output_dir)
        self.title      = title
        self.author     = author

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.output_dir / "process_analysis_report.tex"
        pdf_path = self.output_dir / "process_analysis_report.pdf"

        tex_path.write_text(self._build_document(), encoding="utf-8")
        logger.info("LaTeX written: %s", tex_path)

        if self._compile(tex_path, pdf_path):
            logger.info("PDF compiled: %s", pdf_path)
            return str(pdf_path)
        logger.warning("PDF compilation unavailable — .tex ready at %s", tex_path)
        return str(tex_path)

    # ── Full document ─────────────────────────────────────────────────────────

    def _build_document(self) -> str:
        ts       = datetime.now().strftime("%d %B %Y, %H:%M")
        sections = "\n\n".join(self._dataset_section(r) for r in self.results)

        return rf"""
\documentclass[12pt,a4paper]{{article}}

%% ── Packages ─────────────────────────────────────────────────────────────────
\usepackage[a4paper, top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{{geometry}}
\usepackage{{graphicx, float, booktabs, longtable, hyperref, xcolor}}
\usepackage{{enumitem, fancyhdr, titlesec, array, amsmath, microtype}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage{{lmodern}}

%% ── Color palette ────────────────────────────────────────────────────────────
\definecolor{{sigmaBlue}}{{RGB}}{{21,101,192}}
\definecolor{{sigmaGreen}}{{RGB}}{{46,125,50}}
\definecolor{{sigmaRed}}{{RGB}}{{198,40,40}}
\definecolor{{sigmaOrange}}{{RGB}}{{230,81,0}}
\definecolor{{sigmaGray}}{{RGB}}{{117,117,117}}
\definecolor{{abstractBg}}{{RGB}}{{240,244,255}}

%% ── Hyperlinks ───────────────────────────────────────────────────────────────
\hypersetup{{colorlinks=true, linkcolor=sigmaBlue, urlcolor=sigmaBlue,
  pdftitle={{{_e(self.title)}}}, pdfauthor={{{_e(self.author)}}}}}

%% ── Section style ────────────────────────────────────────────────────────────
\titleformat{{\section}}{{\color{{sigmaBlue}}\Large\bfseries}}{{\thesection}}{{1em}}{{}}
\titleformat{{\subsection}}{{\color{{sigmaBlue}}\large\bfseries}}{{\thesubsection}}{{1em}}{{}}
\titleformat{{\subsubsection}}{{\color{{sigmaGray}}\normalsize\bfseries}}{{\thesubsubsection}}{{1em}}{{}}

%% ── Header / Footer ──────────────────────────────────────────────────────────
\pagestyle{{fancy}}
\fancyhf{{}}
\lhead{{\small\color{{sigmaGray}}SigmaFlow v8 — Statistical Analysis Report}}
\rhead{{\small\color{{sigmaGray}}{_e(ts)}}}
\cfoot{{\small\thepage}}

%% ── Title ────────────────────────────────────────────────────────────────────
\title{{
  \vspace{{1.5cm}}
  {{\color{{sigmaBlue}}\Huge\bfseries {_e(self.title)}}}\\[0.6em]
  {{\large\color{{sigmaGray}} Automated Lean Six Sigma / DMAIC Analysis}}\\[2em]
  {{\normalsize\textbf{{Engine:}} {_e(self.author)}}}
}}
\author{{}}
\date{{{_e(ts)}}}

\begin{{document}}
\maketitle
\thispagestyle{{empty}}
\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section*{{Abstract}}
\addcontentsline{{toc}}{{section}}{{Abstract}}
%% ══════════════════════════════════════════════════════════════════════════════

\begin{{flushleft}}
\colorbox{{abstractBg}}{{\parbox{{0.96\textwidth}}{{
\smallskip
{self._build_abstract()}
\smallskip
}}}}
\end{{flushleft}}

\newpage
\tableofcontents
\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section{{Introduction}}
%% ══════════════════════════════════════════════════════════════════════════════

{self._intro()}

\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section{{Methodology}}
%% ══════════════════════════════════════════════════════════════════════════════

{self._methodology()}

\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section{{Dataset Analysis}}
%% ══════════════════════════════════════════════════════════════════════════════

{sections}

\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section{{Recommendations}}
%% ══════════════════════════════════════════════════════════════════════════════

{self._recommendations()}

\newpage

%% ══════════════════════════════════════════════════════════════════════════════
\section{{Conclusion}}
%% ══════════════════════════════════════════════════════════════════════════════

{self._conclusion()}

\end{{document}}
""".strip()

    # ── Fixed sections ────────────────────────────────────────────────────────

    def _build_abstract(self) -> str:
        abstracts = [r.get("abstract", "") for r in self.results if r.get("abstract")]
        if abstracts:
            return " ".join(_e(a) for a in abstracts)
        n = len(self.results)
        return (
            f"This report presents an automated statistical analysis performed by "
            f"the SigmaFlow v8 engine. A total of {n} dataset(s) were evaluated using "
            f"Statistical Process Control (SPC) and Six Sigma methodologies. "
            f"Results include control chart analysis, process capability indices, "
            f"Western Electric rule evaluation, and root cause correlation analysis. "
            f"Findings are presented with interpretations and recommendations."
        )

    def _intro(self) -> str:
        n = len(self.results)
        return rf"""
This report was automatically generated by \textbf{{SigmaFlow v8}}, a modular
Python framework for industrial process analysis. A total of
\textbf{{{n} dataset(s)}} were processed through the complete analysis pipeline.

\medskip

The analysis pipeline consists of the following stages:

\begin{{enumerate}}[leftmargin=2em]
  \item \textbf{{Dataset Detection}} — Automatic classification of dataset type
        (SPC, capability, logistics, Pareto, service, DOE).
  \item \textbf{{Statistical Analysis}} — Descriptive statistics, control limits,
        capability indices (Cp, Cpk), and trend detection.
  \item \textbf{{Visualization}} — Control charts, histograms, Pareto charts,
        capability plots, and correlation heatmaps.
  \item \textbf{{Root Cause Detection}} — Pearson and Spearman correlation analysis
        to identify variables most associated with defects or variation.
  \item \textbf{{Insight Generation}} — Western Electric Rules and statistical
        rules evaluated against the data; insights exported as JSON.
  \item \textbf{{Report Generation}} — This document: fully annotated with
        interpretations and recommendations.
\end{{enumerate}}

\begin{{center}}
\begin{{tabular}}{{lllcc}}
\toprule
\textbf{{Dataset}} & \textbf{{Type}} & \textbf{{Shape}} & \textbf{{Time (s)}} & \textbf{{Insights}} \\
\midrule
""" + "\n".join(
            f"  {_e(r.get('name','?'))} & "
            f"{_e(r.get('dataset_type','?').upper())} & "
            f"{_e(str(r['shape'][0])+'×'+str(r['shape'][1]) if r.get('shape') else '—')} & "
            f"{_e(r.get('elapsed_s','?'))}s & "
            f"{len(r.get('structured_insights', r.get('insights',[])))}\\\\"
            for r in self.results
        ) + r"""
\bottomrule
\end{tabular}
\end{center}"""

    def _methodology(self) -> str:
        return r"""
The following statistical methods and tools are employed in this analysis:

\subsubsection*{Statistical Process Control (SPC)}

Control charts are used to distinguish between \textit{common-cause variation}
(inherent randomness) and \textit{special-cause variation} (assignable, non-random
events). The \textbf{XmR chart} (Individuals and Moving Range) is used for
individual observations. Control limits are set at $\mu \pm 3\sigma$.

\subsubsection*{Western Electric Rules}

Four detection rules are applied to identify non-random patterns:

\begin{itemize}[leftmargin=2em]
  \item \textbf{Rule 1} — Any single point outside $\pm 3\sigma$ limits
        (probability $\approx$ 0.27\% under normality).
  \item \textbf{Rule 2} — Nine consecutive points on the same side of the
        center line (probability $\approx$ 0.4\%).
  \item \textbf{Rule 3} — Six consecutive points trending upward or downward
        (indicates drift).
  \item \textbf{Rule 4} — Fourteen consecutive points alternating direction
        (indicates over-adjustment or dual-stream process).
\end{itemize}

\subsubsection*{Process Capability Indices}

When specification limits are available, the following indices are computed:

\begin{center}
\begin{tabular}{lll}
\toprule
\textbf{Index} & \textbf{Formula} & \textbf{Interpretation} \\
\midrule
$C_p$  & $(USL - LSL) / 6\sigma$ & Potential capability (centered) \\
$C_{pk}$ & $\min(C_{pu}, C_{pl})$ & Actual capability (off-centering penalty) \\
$C_{pu}$ & $(USL - \mu) / 3\sigma$ & Upper one-sided capability \\
$C_{pl}$ & $(\mu - LSL) / 3\sigma$ & Lower one-sided capability \\
\bottomrule
\end{tabular}
\end{center}

\medskip

\textbf{Capability thresholds:}
\begin{itemize}[leftmargin=2em]
  \item $C_{pk} < 1.00$ \textrightarrow\ Process \textcolor{sigmaRed}{\textbf{not capable}}
  \item $1.00 \le C_{pk} < 1.33$ \textrightarrow\ \textcolor{sigmaOrange}{\textbf{Marginal}} capability
  \item $1.33 \le C_{pk} < 1.67$ \textrightarrow\ \textcolor{sigmaGreen}{\textbf{Acceptable}} capability
  \item $C_{pk} \ge 1.67$ \textrightarrow\ \textcolor{sigmaGreen}{\textbf{Excellent}} (Six Sigma level)
\end{itemize}

\subsubsection*{Root Cause Analysis}

Pearson and Spearman rank correlations are computed between all process
variables and the primary quality output. Variables are ranked by absolute
correlation to identify the most likely process drivers.

\begin{center}
\begin{tabular}{ll}
\toprule
\textbf{|r| threshold} & \textbf{Strength} \\
\midrule
$|r| \ge 0.70$ & Strong association — high priority investigation \\
$0.50 \le |r| < 0.70$ & Moderate association — medium priority \\
$0.30 \le |r| < 0.50$ & Weak association — monitor \\
$|r| < 0.30$ & Negligible \\
\bottomrule
\end{tabular}
\end{center}"""

    def _recommendations(self) -> str:
        totals = {"critical": 0, "warning": 0, "info": 0}
        for r in self.results:
            for ins in r.get("structured_insights", []):
                sev = ins.get("severity", "info")
                totals[sev] = totals.get(sev, 0) + 1

        # Gather all strong root cause candidates
        all_strong = []
        for r in self.results:
            rca = r.get("root_cause", {})
            for v in rca.get("ranked_variables", []):
                if abs(v.get("pearson_r", 0)) >= 0.70:
                    all_strong.append((r["name"], v["variable"], v["pearson_r"]))

        rca_section = ""
        if all_strong:
            rows = "\n".join(
                f"  {_e(ds)} & {_e(var)} & {_e(f'{r:+.3f}')} \\\\"
                for ds, var, r in all_strong[:10]
            )
            rca_section = rf"""
\subsubsection*{{Priority Variables for Investigation}}

The following variables showed strong correlation ($|r| \ge 0.70$) with
the quality target and should be investigated first:

\begin{{center}}
\begin{{tabular}}{{lll}}
\toprule
\textbf{{Dataset}} & \textbf{{Variable}} & \textbf{{Pearson r}} \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
\end{{center}}
"""

        return rf"""
Based on the automated analysis, the following actions are recommended:

\begin{{enumerate}}[leftmargin=2em]
  \item \textcolor{{sigmaRed}}{{\textbf{{Address {totals['critical']} critical finding(s) immediately.}}}}
        Investigate all points flagged by Western Electric rules outside $3\sigma$ limits.
        Document findings and corrective actions.
  \item \textcolor{{sigmaOrange}}{{\textbf{{Review {totals['warning']} warning(s)}}}} with the
        process engineering team. Schedule corrective actions within the next sprint cycle.
  \item \textbf{{Re-run SigmaFlow}} after implementing improvements to verify effectiveness
        of corrective actions.
  \item \textbf{{Expand data collection}} on variables identified in root cause analysis
        to confirm or refute correlation findings.
  \item \textbf{{Set up real-time monitoring}} for datasets with out-of-control processes.
\end{{enumerate}}

{rca_section}

\medskip\noindent
\textit{{All findings should be reviewed by a qualified process engineer before
implementing corrective actions. Correlation does not imply causation.}}"""

    def _conclusion(self) -> str:
        totals = {"critical": 0, "warning": 0, "info": 0}
        for r in self.results:
            for ins in r.get("structured_insights", []):
                totals[ins.get("severity", "info")] = totals.get(ins.get("severity", "info"), 0) + 1
        return rf"""
The SigmaFlow v8 automated analysis successfully processed
\textbf{{{len(self.results)} dataset(s)}} and produced the following summary:

\begin{{center}}
\begin{{tabular}}{{lc}}
\toprule
\textbf{{Finding Category}} & \textbf{{Count}} \\
\midrule
\textcolor{{sigmaRed}}{{Critical}} (immediate action) & {totals['critical']} \\
\textcolor{{sigmaOrange}}{{Warning}} (monitor / address) & {totals['warning']} \\
\textcolor{{sigmaGreen}}{{Informational}} (stable) & {totals['info']} \\
\bottomrule
\end{{tabular}}
\end{{center}}

\medskip

This report was generated automatically by \textbf{{SigmaFlow v8}}.
All outputs — figures, insights.json, report.tex, and report.pdf —
are available in the \texttt{{output/}} directory.
Statistical findings and recommendations should be reviewed by a
qualified Six Sigma practitioner or process engineer."""

    # ── Dataset section ───────────────────────────────────────────────────────

    def _dataset_section(self, r: Dict[str, Any]) -> str:
        name    = _e(r.get("name", "unknown"))
        dtype   = _e(r.get("dataset_type", "unknown").upper())
        shape   = r.get("shape")
        elapsed = r.get("elapsed_s", "?")

        lines = [
            rf"\subsection{{{name} — {dtype}}}",
            r"\subsubsection*{Dataset Overview}",
            r"\begin{description}[leftmargin=3.5cm, style=nextline]",
            rf"  \item[Dataset]    \textbf{{{name}}}",
            rf"  \item[Type]       \textbf{{{dtype}}}",
            rf"  \item[Dimensions] {_e(str(shape[0])+' rows × '+str(shape[1])+' columns') if shape else '—'}",
            rf"  \item[Processing] {_e(elapsed)} seconds",
            r"\end{description}",
        ]

        # Abstract for this dataset
        abstract = r.get("abstract", "")
        if abstract:
            lines += [
                r"\subsubsection*{Summary}",
                _e(abstract),
            ]

        # Statistical results table
        analysis = r.get("analysis", {})
        flat     = self._flatten(analysis)
        if flat:
            lines += [
                r"\subsubsection*{Statistical Analysis Results}",
                r"\begin{longtable}{>{\bfseries}p{6.5cm} p{8.5cm}}",
                r"\toprule \textbf{Metric} & \textbf{Value} \\ \midrule",
                r"\endfirsthead",
                r"\multicolumn{2}{c}{\small(continued)} \\",
                r"\toprule \textbf{Metric} & \textbf{Value} \\ \midrule",
                r"\endhead",
            ]
            for k, v in list(flat.items())[:40]:
                lines.append(rf"  {_e(k)} & {_e(v)} \\")
            lines += [r"\bottomrule", r"\end{longtable}"]

        # Capability interpretation
        cap = analysis.get("capability", {})
        if cap:
            lines += [self._capability_section(cap)]

        # Process Stability — control charts
        plots = r.get("plots", [])
        chart_plots = [p for p in plots if any(kw in Path(p).name for kw in
                        ("control", "xmr", "spc", "trend", "capability"))]
        if chart_plots:
            lines.append(r"\subsubsection*{Process Stability Analysis}")
            for p in chart_plots[:3]:
                lines += self._figure_block(p)

        # Pareto / distribution charts
        other_plots = [p for p in plots if p not in chart_plots and
                       "heatmap" not in p and "importance" not in p]
        if other_plots:
            lines.append(r"\subsubsection*{Graphical Results}")
            for p in other_plots[:3]:
                lines += self._figure_block(p)

        # Western Electric / anomaly insights
        structured = r.get("structured_insights", [])
        if structured:
            lines += [self._anomaly_section(structured)]

        # Root cause section
        rca = r.get("root_cause", {})
        if rca and not rca.get("error"):
            lines += [self._root_cause_section(rca, plots)]

        # Errors
        errors = r.get("errors", {})
        if errors:
            lines += [
                r"\subsubsection*{\textcolor{sigmaRed}{Processing Warnings}}",
                r"\begin{itemize}[leftmargin=2em]",
            ]
            for k, v in errors.items():
                lines.append(rf"  \item \texttt{{{_e(k)}}}: {_e(v)}")
            lines.append(r"\end{itemize}")

        lines.append(r"\newpage")
        return "\n".join(lines)

    def _capability_section(self, cap: Dict[str, Any]) -> str:
        cpk = cap.get("Cpk")
        cp  = cap.get("Cp")
        if cpk is None:
            return ""
        if cpk >= 1.67:
            level, color = "Excellent (Six Sigma capable)", "sigmaGreen"
            interp = f"The process capability index ($C_{{pk}} = {cpk:.3f}$) indicates \textbf{{excellent capability}}. The process consistently operates well within specification limits."
        elif cpk >= 1.33:
            level, color = "Acceptable", "sigmaGreen"
            interp = f"The process capability index ($C_{{pk}} = {cpk:.3f}$) indicates \textbf{{acceptable capability}}. The process meets industry standard requirements."
        elif cpk >= 1.00:
            level, color = "Marginal", "sigmaOrange"
            interp = f"The process capability index ($C_{{pk}} = {cpk:.3f}$) indicates \textbf{{marginal capability}}. Close monitoring is required; small shifts could cause out-of-spec production."
        else:
            level, color = "Not Capable", "sigmaRed"
            interp = f"The process capability index ($C_{{pk}} = {cpk:.3f}$) indicates the process is \textbf{{not capable}} of consistently meeting specification limits. Immediate investigation is required."

        dpmo  = cap.get("dpmo", 0)
        sigma = cap.get("sigma_level", 0)
        usl   = cap.get("usl", "—")
        lsl   = cap.get("lsl", "—")

        return rf"""
\subsubsection*{{Capability Analysis}}

\begin{{center}}
\begin{{tabular}}{{lclc}}
\toprule
\textbf{{Index}} & \textbf{{Value}} & \textbf{{Index}} & \textbf{{Value}} \\
\midrule
$C_p$  & {_e(round(cp,3) if cp else '—')}  & $C_{{pk}}$ & \textcolor{{{color}}}{{\textbf{{{_e(round(cpk,3))}}}}} \\
USL    & {_e(usl)} & LSL    & {_e(lsl)} \\
DPMO   & {_e(f'{dpmo:,.0f}' if dpmo else '—')} & Sigma level & {_e(f'{sigma:.2f}σ' if sigma else '—')} \\
\bottomrule
\end{{tabular}}
\end{{center}}

\textbf{{Capability verdict:}} \textcolor{{{color}}}{{\textbf{{{_e(level)}}}}}.
{interp}
"""

    def _anomaly_section(self, structured: List[Dict[str, Any]]) -> str:
        critical = [s for s in structured if s.get("severity") == "critical"]
        warnings = [s for s in structured if s.get("severity") == "warning"]
        info     = [s for s in structured if s.get("severity") == "info"]

        lines = [r"\subsubsection*{Detected Anomalies \& Statistical Insights}"]

        for group, color, label in [
            (critical, "sigmaRed",    "Critical Findings"),
            (warnings, "sigmaOrange", "Warnings"),
            (info,     "sigmaGreen",  "Informational"),
        ]:
            if not group:
                continue
            lines.append(rf"\paragraph{{\textcolor{{{color}}}{{{label}}}}}")
            for ins in group:
                rule  = _e(ins.get("rule","")).replace("\\_","_").replace("_"," ").title()
                desc  = _e(ins.get("description",""))
                mean  = _e(ins.get("meaning",""))
                rec   = _e(ins.get("recommendation",""))
                lines += [
                    rf"\textbf{{{rule}}}",
                    r"\begin{itemize}[leftmargin=2em, itemsep=0pt]",
                    rf"  \item \textbf{{Finding:}} {desc}",
                    rf"  \item \textbf{{Interpretation:}} {mean}",
                    rf"  \item \textbf{{Recommended Investigation:}} {rec}",
                    r"\end{itemize}",
                    r"\medskip",
                ]
        return "\n".join(lines)

    def _root_cause_section(self, rca: Dict[str, Any], plots: List[str]) -> str:
        target  = _e(rca.get("target_col", "—"))
        ranked  = rca.get("ranked_variables", [])
        interp  = _e(rca.get("interpretation", ""))
        strong  = rca.get("strong_candidates", [])

        lines = [
            r"\subsubsection*{Root Cause Indicators}",
            rf"Correlation analysis was performed using the variable \textbf{{{target}}} as the quality target.",
            r"\medskip",
            interp,
        ]

        if ranked:
            lines += [
                r"\paragraph{Variable Importance Ranking}",
                r"\begin{center}",
                r"\begin{tabular}{lrrl}",
                r"\toprule \textbf{Variable} & \textbf{Pearson r} & \textbf{Spearman r} & \textbf{Strength} \\",
                r"\midrule",
            ]
            for v in ranked[:12]:
                color = (
                    "sigmaRed"    if abs(v["pearson_r"]) >= 0.70 else
                    "sigmaOrange" if abs(v["pearson_r"]) >= 0.50 else
                    "sigmaGray"
                )
                lines.append(
                    rf"  {_e(v['variable'])} & "
                    rf"\textcolor{{{color}}}{{\textbf{{{_e(f'{v[chr(112)+chr(101)+chr(97)+chr(114)+chr(115)+chr(111)+chr(110)+chr(95)+chr(114)]:+.3f}')}}}}} & "
                    rf"{_e(f'{v[chr(115)+chr(112)+chr(101)+chr(97)+chr(114)+chr(109)+chr(97)+chr(110)+chr(95)+chr(114)]:+.3f}')} & "
                    rf"{_e(v['strength'].capitalize())} \\\\"
                )
            lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]

        # Correlation heatmap + importance chart
        heatmap = next((p for p in plots if "heatmap" in p), None)
        varmap  = next((p for p in plots if "importance" in p), None)
        for fig_path in filter(None, [heatmap, varmap]):
            lines += self._figure_block(fig_path)

        return "\n".join(lines)

    def _figure_block(self, p: str) -> List[str]:
        pp  = str(p).replace("\\", "/")
        cap = _e(Path(p).stem.replace("_", " ").title())
        return [
            r"\begin{figure}[H]",
            r"  \centering",
            rf"  \includegraphics[width=0.95\linewidth]{{{pp}}}",
            rf"  \caption{{{cap}}}",
            r"\end{figure}",
            r"\medskip",
        ]

    # ── Flatten nested dict ───────────────────────────────────────────────────

    @staticmethod
    def _flatten(d: Any, prefix: str = "", sep: str = ".") -> Dict[str, str]:
        items: Dict[str, str] = {}
        if isinstance(d, dict):
            for k, v in d.items():
                new_key = f"{prefix}{sep}{k}" if prefix else str(k)
                if isinstance(v, (dict, list)):
                    items.update(LatexReportGenerator._flatten(v, new_key, sep))
                else:
                    items[new_key] = str(round(v, 4) if isinstance(v, float) else v)
        elif isinstance(d, list):
            for i, v in enumerate(d[:6]):
                items.update(LatexReportGenerator._flatten(v, f"{prefix}[{i}]", sep))
        return items

    # ── PDF compilation ───────────────────────────────────────────────────────

    def _compile(self, tex_path: Path, pdf_path: Path) -> bool:
        engine = shutil.which("pdflatex") or shutil.which("xelatex")
        if not engine:
            print("  ℹ  LaTeX not installed — .tex file ready for manual compilation.")
            print("     Install: sudo apt install texlive-full")
            return False
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            tmp_tex = tmp_dir / tex_path.name
            shutil.copy2(tex_path, tmp_tex)
            for _ in range(2):
                proc = subprocess.run(
                    [engine, "-interaction=nonstopmode", "-halt-on-error",
                     "-output-directory", str(tmp_dir), str(tmp_tex)],
                    capture_output=True, text=True, timeout=120,
                )
            tmp_pdf = tmp_dir / tex_path.with_suffix(".pdf").name
            if tmp_pdf.exists():
                shutil.copy2(tmp_pdf, pdf_path)
                return True
            for line in proc.stdout.splitlines():
                if "Error" in line or "!" in line:
                    logger.error("LaTeX: %s", line)
        return False
