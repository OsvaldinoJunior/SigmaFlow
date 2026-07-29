"""
sigmaflow/report/html_dashboard.py
=====================================
HTML Dashboard report generator — SigmaFlow v9.

Generates a self-contained, single-file HTML report at:
    output/dashboard/report.html

The dashboard displays all analysis results in a clean, professional
industrial interface — no server required, opens directly in any browser.

Sections
--------
- Header with run metadata
- Executive summary cards (datasets, anomalies, critical findings)
- Per-dataset panels:
    • Statistical summary table
    • Control charts (embedded PNG)
    • Capability analysis with gauge indicator
    • Histogram / distribution plots
    • Pareto chart
    • Correlation heatmap
    • Variable importance ranking
    • Insight cards (color-coded by severity)
- Footer

Design principles
-----------------
- Zero external dependencies at runtime (all CSS/JS inline)
- Works offline — PNG figures embedded as base64 OR referenced by path
- Industrial / precision aesthetic: dark header, clean data tables,
  structured typography (IBM Plex for data, Georgia for headings)
- Print-friendly sidebar layout

Usage
-----
    from sigmaflow.report.html_dashboard import HTMLDashboardGenerator

    gen = HTMLDashboardGenerator(results, output_dir="output/dashboard")
    html_path = gen.generate()
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Helper: embed PNG as base64 data URI ─────────────────────────────────────

def _img_src(path: str) -> str:
    """
    Return an <img src> value — base64-encoded if file exists, else a
    placeholder path. This makes the HTML fully self-contained.
    """
    p = Path(path)
    if p.exists():
        try:
            data = base64.b64encode(p.read_bytes()).decode()
            return f"data:image/png;base64,{data}"
        except Exception:
            pass
    return str(path).replace("\\", "/")


def _esc(s: Any) -> str:
    """Escape HTML special characters."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _sev_class(sev: str) -> str:
    return {"critical": "sev-critical", "warning": "sev-warning", "info": "sev-info"}.get(sev, "sev-info")


def _cpk_class(cpk: float) -> str:
    if cpk >= 1.67: return "cap-excellent"
    if cpk >= 1.33: return "cap-acceptable"
    if cpk >= 1.00: return "cap-marginal"
    return "cap-incapable"


def _cpk_label(cpk: float) -> str:
    if cpk >= 1.67: return "Excellent"
    if cpk >= 1.33: return "Acceptable"
    if cpk >= 1.00: return "Marginal"
    return "Not Capable"


# ─── Generator ────────────────────────────────────────────────────────────────

class HTMLDashboardGenerator:
    """
    Builds a self-contained HTML dashboard from SigmaFlow pipeline results.

    Parameters
    ----------
    results : list[dict]
        Output from Engine.run().
    output_dir : str | Path
        Directory where report.html is saved.
    title : str
        Dashboard title shown in the header.
    """

    def __init__(
        self,
        results: List[Dict[str, Any]],
        output_dir: str | Path = "output/dashboard",
        title: str = "SigmaFlow — Statistical Analysis Dashboard",
    ) -> None:
        self.results    = results
        self.output_dir = Path(output_dir)
        self.title      = title

    def generate(self) -> str:
        """
        Generate the HTML dashboard file.

        Returns
        -------
        str
            Absolute path to the generated report.html.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out = self.output_dir / "report.html"

        html = self._build_document()
        out.write_text(html, encoding="utf-8")
        logger.info("HTML dashboard written: %s", out)
        return str(out)

    # ── Full document ─────────────────────────────────────────────────────────

    def _build_document(self) -> str:
        ts = datetime.now().strftime("%d %B %Y, %H:%M")

        # Summary stats for header cards
        n_datasets = len(self.results)
        n_critical = sum(
            sum(1 for s in r.get("structured_insights", []) if s.get("severity") == "critical")
            for r in self.results
        )
        n_warning = sum(
            sum(1 for s in r.get("structured_insights", []) if s.get("severity") == "warning")
            for r in self.results
        )
        n_plots = sum(len(r.get("plots", [])) for r in self.results)

        dataset_nav = "\n".join(
            f'<a href="#ds-{i}" class="nav-link">'
            f'<span class="nav-type">{_esc(r.get("dataset_type","?").upper())}</span>'
            f'<span class="nav-name">{_esc(r.get("name","?"))}</span>'
            f'</a>'
            for i, r in enumerate(self.results)
        )

        dataset_sections = "\n\n".join(
            self._dataset_section(r, i) for i, r in enumerate(self.results)
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(self.title)}</title>
<style>
{self._css()}
</style>
</head>
<body>

<!-- ── SIDEBAR NAV ─────────────────────────────────────────────────────── -->
<nav class="sidebar">
  <div class="sidebar-header">
    <div class="logo">σ</div>
    <div class="logo-text">
      <span class="logo-title">SigmaFlow</span>
      <span class="logo-version">v9</span>
    </div>
  </div>
  <div class="nav-section-label">Datasets</div>
  {dataset_nav}
  <div class="sidebar-footer">
    <div class="sf-date">{_esc(ts)}</div>
    <div class="sf-note">Automated Six Sigma Report</div>
  </div>
</nav>

<!-- ── MAIN CONTENT ────────────────────────────────────────────────────── -->
<main class="main-content">

  <!-- Header -->
  <header class="page-header">
    <h1>{_esc(self.title)}</h1>
    <p class="header-sub">Statistical Process Control &amp; Six Sigma Analysis · {_esc(ts)}</p>
  </header>

  <!-- Summary cards -->
  <section class="summary-cards">
    <div class="card card-blue">
      <div class="card-value">{n_datasets}</div>
      <div class="card-label">Datasets Analyzed</div>
    </div>
    <div class="card card-red">
      <div class="card-value">{n_critical}</div>
      <div class="card-label">Critical Findings</div>
    </div>
    <div class="card card-orange">
      <div class="card-value">{n_warning}</div>
      <div class="card-label">Warnings</div>
    </div>
    <div class="card card-gray">
      <div class="card-value">{n_plots}</div>
      <div class="card-label">Charts Generated</div>
    </div>
  </section>

  <!-- Dataset sections -->
  {dataset_sections}

  <!-- Footer -->
  <footer class="page-footer">
    <p>Generated by <strong>SigmaFlow v9</strong> · Automated Statistical Process Control Analysis</p>
    <p>This report is for engineering analysis only. Review all findings with a qualified process engineer.</p>
  </footer>

</main>

<script>
{self._js()}
</script>
</body>
</html>"""

    # ── Per-dataset section ───────────────────────────────────────────────────

    def _dataset_section(self, r: Dict[str, Any], idx: int) -> str:
        name   = r.get("name", "unknown")
        dtype  = r.get("dataset_type", "unknown").upper()
        shape  = r.get("shape")
        rows   = shape[0] if shape else "?"
        cols   = shape[1] if shape else "?"

        structured = r.get("structured_insights", [])
        n_crit = sum(1 for s in structured if s.get("severity") == "critical")
        n_warn = sum(1 for s in structured if s.get("severity") == "warning")

        abstract  = r.get("abstract", "")
        analysis  = r.get("analysis", {})
        plots     = r.get("plots", [])
        rca       = r.get("root_cause", {})

        # Badge color for type
        type_badge = f'<span class="type-badge type-{dtype.lower()[:3]}">{_esc(dtype)}</span>'

        # Severity pill
        sev_html = ""
        if n_crit:
            sev_html += f'<span class="sev-pill sev-critical">⚠ {n_crit} Critical</span>'
        if n_warn:
            sev_html += f'<span class="sev-pill sev-warning">⚡ {n_warn} Warning</span>'
        if not n_crit and not n_warn:
            sev_html = '<span class="sev-pill sev-ok">✓ Stable</span>'

        return f"""
<section class="dataset-section" id="ds-{idx}">
  <div class="ds-header">
    <div class="ds-title-row">
      {type_badge}
      <h2 class="ds-name">{_esc(name)}</h2>
      <div class="ds-pills">{sev_html}</div>
    </div>
    <div class="ds-meta">
      <span class="meta-item">📊 {_esc(rows)} rows × {_esc(cols)} columns</span>
      <span class="meta-item">⏱ {_esc(r.get('elapsed_s','?'))}s</span>
    </div>
  </div>

  {f'<p class="abstract-text">{_esc(abstract)}</p>' if abstract else ''}

  <!-- Stats + Capability row -->
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">Statistical Summary</div>
      {self._stats_table(analysis)}
    </div>
    <div class="panel">
      <div class="panel-title">Capability Analysis</div>
      {self._capability_panel(analysis)}
    </div>
  </div>

  <!-- Charts grid -->
  {self._charts_grid(plots, rca)}

  <!-- Insight cards -->
  {self._insights_panel(structured)}

  <!-- Root cause table -->
  {self._rca_table(rca)}

</section>
<hr class="section-divider">"""

    # ── Stats table ───────────────────────────────────────────────────────────

    def _stats_table(self, analysis: Dict[str, Any]) -> str:
        flat = _flatten_dict(analysis)
        if not flat:
            return '<p class="empty-msg">No statistical data available.</p>'

        rows = ""
        for k, v in list(flat.items())[:25]:
            key_clean = k.replace("_", " ").replace(".", " › ").title()
            rows += f'<tr><td class="key-cell">{_esc(key_clean)}</td><td class="val-cell">{_esc(v)}</td></tr>'

        return f"""
<div class="table-scroll">
<table class="data-table">
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    # ── Capability panel ──────────────────────────────────────────────────────

    def _capability_panel(self, analysis: Dict[str, Any]) -> str:
        cap = analysis.get("capability", {})
        if not cap:
            return '<p class="empty-msg">No specification limits detected.</p>'

        cpk   = cap.get("Cpk")
        cp    = cap.get("Cp")
        dpmo  = cap.get("dpmo")
        sigma = cap.get("sigma_level")
        usl   = cap.get("usl", "—")
        lsl   = cap.get("lsl", "—")

        if cpk is not None:
            cap_class = _cpk_class(cpk)
            cap_label = _cpk_label(cpk)
            gauge_pct = min(100, max(0, cpk / 2.0 * 100))  # 0–2 → 0–100%
            gauge_html = f"""
<div class="gauge-container">
  <div class="gauge-bar-bg">
    <div class="gauge-bar {cap_class}" style="width:{gauge_pct:.0f}%"></div>
  </div>
  <div class="gauge-labels">
    <span>0</span><span>1.0</span><span>1.33</span><span>1.67</span><span>2.0+</span>
  </div>
  <div class="gauge-verdict {cap_class}">{_esc(cap_label)}</div>
</div>"""
        else:
            gauge_html = ""

        rows = ""
        for label, val in [
            ("Cp",          cp),
            ("Cpk",         cpk),
            ("DPMO",        f"{dpmo:,.0f}" if dpmo else None),
            ("Sigma Level", f"{sigma:.2f}σ" if sigma else None),
            ("USL",         usl),
            ("LSL",         lsl),
        ]:
            if val is not None:
                rows += f'<tr><td class="key-cell">{label}</td><td class="val-cell">{_esc(str(round(val,3) if isinstance(val,float) else val))}</td></tr>'

        table = f"""
<table class="data-table">
<thead><tr><th>Index</th><th>Value</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""

        return gauge_html + table

    # ── Charts grid ───────────────────────────────────────────────────────────

    def _charts_grid(self, plots: List[str], rca: Dict[str, Any]) -> str:
        if not plots:
            return ""

        # Classify plots by type
        groups = {
            "Control Charts":      [p for p in plots if any(k in Path(p).name for k in ("xmr", "control", "spc"))],
            "Distribution":        [p for p in plots if any(k in Path(p).name for k in ("histogram", "capability"))],
            "Pareto / Defects":    [p for p in plots if any(k in Path(p).name for k in ("pareto", "defect", "distribution"))],
            "Trend Analysis":      [p for p in plots if "trend" in Path(p).name],
            "Root Cause Analysis": [p for p in plots if any(k in Path(p).name for k in ("heatmap", "importance", "correlation"))],
            "Other Charts":        [p for p in plots if not any(
                k in Path(p).name for k in ("xmr","control","spc","histogram","capability","pareto","defect","distribution","trend","heatmap","importance","correlation")
            )],
        }

        html = '<div class="charts-container">'
        for group_name, group_plots in groups.items():
            if not group_plots:
                continue
            html += f'<div class="chart-group"><div class="chart-group-title">{_esc(group_name)}</div>'
            html += '<div class="chart-row">'
            for p in group_plots[:4]:
                cap = Path(p).stem.replace("_", " ").title()
                src = _img_src(p)
                html += f"""
<div class="chart-card">
  <img src="{src}" alt="{_esc(cap)}" class="chart-img" loading="lazy"
       onclick="openLightbox(this.src, '{_esc(cap)}')" title="Click to enlarge">
  <div class="chart-caption">{_esc(cap)}</div>
</div>"""
            html += "</div></div>"
        html += "</div>"
        return html

    # ── Insights panel ────────────────────────────────────────────────────────

    def _insights_panel(self, structured: List[Dict[str, Any]]) -> str:
        if not structured:
            return ""

        cards = ""
        for ins in structured:
            sev   = ins.get("severity", "info")
            rule  = ins.get("rule", "").replace("_", " ").title()
            desc  = ins.get("description", "")
            mean  = ins.get("meaning", "")
            rec   = ins.get("recommendation", "")
            cls   = _sev_class(sev)
            icon  = {"critical": "⚠", "warning": "⚡", "info": "ℹ"}.get(sev, "ℹ")

            cards += f"""
<div class="insight-card {cls}">
  <div class="insight-header">
    <span class="insight-icon">{icon}</span>
    <span class="insight-rule">{_esc(rule)}</span>
    <span class="insight-sev {cls}">{_esc(sev.upper())}</span>
  </div>
  <p class="insight-desc">{_esc(desc)}</p>
  {f'<p class="insight-meaning"><strong>Meaning:</strong> {_esc(mean)}</p>' if mean else ''}
  {f'<p class="insight-rec"><strong>Action:</strong> {_esc(rec[:200])}{"..." if len(rec)>200 else ""}</p>' if rec else ''}
</div>"""

        return f"""
<div class="panel">
  <div class="panel-title">Statistical Insights &amp; Anomalies</div>
  <div class="insights-grid">{cards}</div>
</div>"""

    # ── Root cause table ──────────────────────────────────────────────────────

    def _rca_table(self, rca: Any) -> str:
        # rca may be a dict (from engine) or a list (from insights.json root_cause)
        if isinstance(rca, list):
            if not rca:
                return ""
            # Build a simplified table from the root_cause insight list
            rows = ""
            for item in rca[:12]:
                desc = _esc(item.get("description", ""))
                sev  = item.get("severity", "info")
                rows += f'<tr><td colspan="3">{desc}</td><td><span class="strength-badge strength-{sev}">{sev.capitalize()}</span></td></tr>'
            return f"""
<div class="panel">
  <div class="panel-title">Root Cause Indicators</div>
  <div class="table-scroll">
  <table class="data-table">
  <thead><tr><th colspan="3">Finding</th><th>Severity</th></tr></thead>
  <tbody>{rows}</tbody>
  </table>
  </div>
  <p class="rca-note">Correlation indicates statistical association, not confirmed causation.</p>
</div>"""

        ranked = rca.get("ranked_variables", [])
        if not ranked:
            return ""

        target = rca.get("target_col", "?")
        interp = rca.get("interpretation", "")

        rows = ""
        for v in ranked[:15]:
            r_val = v.get("pearson_r", 0)
            abs_r = abs(r_val) if r_val == r_val else 0.0  # NaN guard
            strength = v.get("strength", "negligible")
            bar_w = int(min(100, abs_r * 100))
            bar_color = ("#C62828" if abs_r >= 0.70 else
                         "#E65100" if abs_r >= 0.50 else
                         "#1565C0" if abs_r >= 0.30 else "#9E9E9E")
            sign = "+" if r_val >= 0 else "−"
            rows += f"""
<tr>
  <td class="key-cell">{_esc(v.get('variable',''))}</td>
  <td class="val-cell corr-cell">
    <div class="corr-bar-wrap">
      <div class="corr-bar" style="width:{bar_w}%;background:{bar_color}"></div>
    </div>
    <span class="corr-val">{sign}{abs_r:.3f}</span>
  </td>
  <td class="val-cell">{_esc(f"{v.get('spearman_r',0):+.3f}")}</td>
  <td class="val-cell"><span class="strength-badge strength-{strength}">{_esc(strength.capitalize())}</span></td>
</tr>"""

        return f"""
<div class="panel">
  <div class="panel-title">Root Cause Indicators — Variable Importance</div>
  <p class="rca-interp">{_esc(interp[:300] + ('...' if len(interp)>300 else ''))}</p>
  <p class="rca-target">Target variable: <strong>{_esc(target)}</strong></p>
  <div class="table-scroll">
  <table class="data-table">
  <thead><tr><th>Variable</th><th>Pearson r</th><th>Spearman r</th><th>Strength</th></tr></thead>
  <tbody>{rows}</tbody>
  </table>
  </div>
  <p class="rca-note">Note: Correlation indicates statistical association, not confirmed causation.</p>
</div>"""

    # ── CSS ───────────────────────────────────────────────────────────────────

    def _css(self) -> str:
        return """
/* ── Reset & base ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --blue:       #1565C0;
  --blue-lt:    #E3F2FD;
  --blue-mid:   #42A5F5;
  --red:        #C62828;
  --red-lt:     #FFEBEE;
  --orange:     #E65100;
  --orange-lt:  #FFF3E0;
  --green:      #2E7D32;
  --green-lt:   #E8F5E9;
  --gray:       #546E7A;
  --gray-lt:    #ECEFF1;
  --dark:       #102027;
  --dark-mid:   #1C313A;
  --sidebar-w:  240px;
  --font-mono:  'IBM Plex Mono', 'Courier New', monospace;
  --font-body:  'IBM Plex Sans', Georgia, serif;
  --font-head:  Georgia, 'Times New Roman', serif;
}

html { scroll-behavior: smooth; }

body {
  font-family: var(--font-body);
  background: #F4F6F9;
  color: #212121;
  display: flex;
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.6;
}

/* ── Sidebar ────────────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-w);
  min-height: 100vh;
  background: var(--dark);
  position: fixed;
  top: 0; left: 0;
  display: flex;
  flex-direction: column;
  z-index: 100;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.logo {
  width: 36px; height: 36px;
  background: var(--blue);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 900;
  color: white; font-family: var(--font-head);
  flex-shrink: 0;
}

.logo-title { display: block; color: white; font-weight: 700; font-size: 15px; }
.logo-version { display: block; color: #90A4AE; font-size: 11px; letter-spacing: 0.05em; }

.nav-section-label {
  padding: 16px 16px 6px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #546E7A;
  font-weight: 600;
}

.nav-link {
  display: flex;
  flex-direction: column;
  padding: 10px 16px;
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.nav-link:hover {
  background: rgba(255,255,255,0.06);
  border-left-color: var(--blue-mid);
}
.nav-type { font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--blue-mid); font-weight: 700; }
.nav-name { color: #CFD8DC; font-size: 12px; margin-top: 2px; }

.sidebar-footer {
  margin-top: auto;
  padding: 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.sf-date { color: #78909C; font-size: 11px; }
.sf-note { color: #546E7A; font-size: 10px; margin-top: 3px; }

/* ── Main ───────────────────────────────────────────────────── */
.main-content {
  margin-left: var(--sidebar-w);
  flex: 1;
  padding: 0 0 40px;
}

/* ── Page header ────────────────────────────────────────────── */
.page-header {
  background: linear-gradient(135deg, var(--dark) 0%, var(--dark-mid) 100%);
  color: white;
  padding: 36px 40px;
}
.page-header h1 {
  font-family: var(--font-head);
  font-size: 26px;
  font-weight: 400;
  letter-spacing: -0.01em;
}
.header-sub {
  color: #90A4AE;
  font-size: 12px;
  margin-top: 6px;
  font-family: var(--font-mono);
}

/* ── Summary cards ──────────────────────────────────────────── */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border-bottom: 2px solid #CFD8DC;
}
.card {
  padding: 20px 24px;
  border-right: 1px solid #CFD8DC;
}
.card:last-child { border-right: none; }
.card-value { font-size: 36px; font-weight: 700; font-family: var(--font-mono); line-height: 1; }
.card-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 6px; color: var(--gray); }
.card-blue  { background: var(--blue-lt);   border-top: 3px solid var(--blue);   } .card-blue  .card-value { color: var(--blue);   }
.card-red   { background: var(--red-lt);    border-top: 3px solid var(--red);    } .card-red   .card-value { color: var(--red);    }
.card-orange{ background: var(--orange-lt); border-top: 3px solid var(--orange); } .card-orange .card-value{ color: var(--orange); }
.card-gray  { background: var(--gray-lt);   border-top: 3px solid var(--gray);   } .card-gray  .card-value { color: var(--gray);   }

/* ── Dataset sections ───────────────────────────────────────── */
.dataset-section { padding: 28px 40px 0; }
.section-divider { border: none; border-top: 2px dashed #CFD8DC; margin: 32px 40px 0; }

.ds-header { margin-bottom: 16px; }
.ds-title-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ds-name { font-family: var(--font-head); font-size: 20px; font-weight: 400; }

.type-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--dark);
  color: white;
}
.type-spc { background: #1565C0; }
.type-cap { background: #2E7D32; }
.type-log { background: #E65100; }
.type-roo { background: #6A1B9A; }
.type-ser { background: #00838F; }
.type-doe { background: #4527A0; }

.ds-pills { display: flex; gap: 8px; margin-left: auto; }
.sev-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}
.sev-pill.sev-critical { background: var(--red-lt); color: var(--red); }
.sev-pill.sev-warning  { background: var(--orange-lt); color: var(--orange); }
.sev-pill.sev-ok       { background: var(--green-lt); color: var(--green); }

.ds-meta { display: flex; gap: 16px; margin-top: 6px; }
.meta-item { font-size: 11px; color: var(--gray); font-family: var(--font-mono); }

.abstract-text {
  background: var(--blue-lt);
  border-left: 3px solid var(--blue);
  padding: 12px 16px;
  border-radius: 0 6px 6px 0;
  font-size: 13px;
  color: #1A237E;
  margin-bottom: 20px;
  line-height: 1.7;
}

/* ── Panels ─────────────────────────────────────────────────── */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.panel {
  background: white;
  border: 1px solid #E0E0E0;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  font-weight: 700;
  color: var(--gray);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ECEFF1;
}

/* ── Tables ─────────────────────────────────────────────────── */
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: var(--dark);
  color: white;
  padding: 7px 10px;
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.data-table td { padding: 6px 10px; border-bottom: 1px solid #ECEFF1; }
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover { background: #F5F5F5; }
.key-cell { color: #546E7A; font-family: var(--font-mono); font-size: 11px; }
.val-cell { font-family: var(--font-mono); font-weight: 600; }

/* ── Capability gauge ───────────────────────────────────────── */
.gauge-container { margin-bottom: 16px; }
.gauge-bar-bg {
  height: 14px;
  background: #ECEFF1;
  border-radius: 7px;
  overflow: hidden;
  margin-bottom: 4px;
}
.gauge-bar {
  height: 100%;
  border-radius: 7px;
  transition: width 0.6s ease;
}
.gauge-labels { display: flex; justify-content: space-between; font-size: 9px; color: #90A4AE; font-family: var(--font-mono); margin-bottom: 8px; }
.gauge-verdict { display: inline-block; padding: 4px 14px; border-radius: 12px; font-size: 13px; font-weight: 700; }
.cap-excellent  .gauge-bar { background: var(--green); }   .cap-excellent  .gauge-verdict { background: var(--green-lt); color: var(--green); }
.cap-acceptable .gauge-bar { background: #1976D2; }         .cap-acceptable .gauge-verdict { background: var(--blue-lt); color: var(--blue); }
.cap-marginal   .gauge-bar { background: var(--orange); }  .cap-marginal   .gauge-verdict { background: var(--orange-lt); color: var(--orange); }
.cap-incapable  .gauge-bar { background: var(--red); }     .cap-incapable  .gauge-verdict { background: var(--red-lt); color: var(--red); }

/* ── Charts ─────────────────────────────────────────────────── */
.charts-container { margin-bottom: 16px; }
.chart-group { margin-bottom: 16px; }
.chart-group-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  font-weight: 700;
  color: var(--gray);
  margin-bottom: 10px;
  padding-left: 2px;
}
.chart-row { display: flex; gap: 12px; flex-wrap: wrap; }
.chart-card {
  flex: 1;
  min-width: 260px;
  max-width: 520px;
  background: white;
  border: 1px solid #E0E0E0;
  border-radius: 6px;
  overflow: hidden;
  cursor: zoom-in;
  transition: box-shadow 0.2s;
}
.chart-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
.chart-img { width: 100%; display: block; }
.chart-caption {
  padding: 8px 12px;
  font-size: 11px;
  color: var(--gray);
  background: #FAFAFA;
  border-top: 1px solid #ECEFF1;
  text-align: center;
}

/* ── Insight cards ──────────────────────────────────────────── */
.insights-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
.insight-card {
  border-radius: 6px;
  padding: 14px 16px;
  border-left: 4px solid;
}
.insight-card.sev-critical { background: var(--red-lt);    border-color: var(--red);    }
.insight-card.sev-warning  { background: var(--orange-lt); border-color: var(--orange); }
.insight-card.sev-info     { background: var(--green-lt);  border-color: var(--green);  }

.insight-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.insight-icon  { font-size: 16px; }
.insight-rule  { font-weight: 700; font-size: 12px; flex: 1; }
.insight-sev   { font-size: 9px; font-weight: 700; letter-spacing: 0.1em; padding: 2px 8px; border-radius: 10px; }
.insight-sev.sev-critical { background: var(--red);    color: white; }
.insight-sev.sev-warning  { background: var(--orange); color: white; }
.insight-sev.sev-info     { background: var(--green);  color: white; }

.insight-desc    { font-size: 12px; margin-bottom: 6px; }
.insight-meaning { font-size: 11px; color: #455A64; margin-bottom: 4px; line-height: 1.5; }
.insight-rec     { font-size: 11px; color: #455A64; font-style: italic; }

/* ── Root cause bar chart ───────────────────────────────────── */
.corr-cell { display: flex; align-items: center; gap: 8px; }
.corr-bar-wrap { flex: 1; height: 8px; background: #ECEFF1; border-radius: 4px; overflow: hidden; }
.corr-bar { height: 100%; border-radius: 4px; }
.corr-val { font-family: var(--font-mono); font-size: 12px; white-space: nowrap; }
.strength-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }
.strength-strong   { background: #FFCDD2; color: #B71C1C; }
.strength-moderate { background: #FFE0B2; color: #BF360C; }
.strength-weak     { background: #BBDEFB; color: #0D47A1; }
.strength-negligible { background: #ECEFF1; color: #546E7A; }

.rca-interp { font-size: 12px; color: #546E7A; margin-bottom: 8px; line-height: 1.6; }
.rca-target { font-size: 12px; margin-bottom: 12px; }
.rca-note   { font-size: 10px; color: #90A4AE; margin-top: 10px; font-style: italic; }

/* ── Footer ─────────────────────────────────────────────────── */
.page-footer {
  text-align: center;
  padding: 28px 40px;
  color: #90A4AE;
  font-size: 11px;
  border-top: 1px solid #E0E0E0;
  margin-top: 32px;
  line-height: 1.8;
}

/* ── Lightbox ───────────────────────────────────────────────── */
#lightbox {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.88);
  z-index: 9999;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 20px;
}
#lightbox.open { display: flex; }
#lightbox img { max-width: 92vw; max-height: 85vh; border-radius: 4px; box-shadow: 0 8px 40px rgba(0,0,0,0.6); }
#lightbox-caption { color: #CFD8DC; margin-top: 12px; font-size: 13px; }
#lightbox-close { position: absolute; top: 16px; right: 20px; color: white; font-size: 28px; cursor: pointer; background: none; border: none; line-height: 1; }

/* ── Misc ───────────────────────────────────────────────────── */
.empty-msg { color: #90A4AE; font-size: 12px; font-style: italic; padding: 8px 0; }

@media (max-width: 900px) {
  .sidebar { display: none; }
  .main-content { margin-left: 0; }
  .two-col { grid-template-columns: 1fr; }
  .summary-cards { grid-template-columns: 1fr 1fr; }
}
"""

    # ── JavaScript ────────────────────────────────────────────────────────────

    def _js(self) -> str:
        return """
// Lightbox for chart zoom
function openLightbox(src, caption) {
  const lb  = document.getElementById('lightbox');
  const img = document.getElementById('lightbox-img');
  const cap = document.getElementById('lightbox-caption');
  img.src = src;
  cap.textContent = caption;
  lb.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

// Smooth active nav on scroll
const sections = document.querySelectorAll('.dataset-section');
const navLinks = document.querySelectorAll('.nav-link');

const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      navLinks.forEach(l => l.classList.remove('active'));
      const id = entry.target.id;
      const active = document.querySelector(`.nav-link[href="#${id}"]`);
      if (active) active.classList.add('active');
    }
  });
}, { threshold: 0.3 });

sections.forEach(s => observer.observe(s));

// Inject lightbox HTML
document.body.insertAdjacentHTML('beforeend', `
  <div id="lightbox" onclick="closeLightbox()">
    <button id="lightbox-close" onclick="closeLightbox()">✕</button>
    <img id="lightbox-img" src="" alt="" onclick="event.stopPropagation()">
    <div id="lightbox-caption"></div>
  </div>
`);

console.log('SigmaFlow v9 Dashboard loaded.');
"""


# ── Flatten nested dict helper ────────────────────────────────────────────────

def _flatten_dict(d: Any, prefix: str = "", sep: str = " › ") -> Dict[str, str]:
    items: Dict[str, str] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{prefix}{sep}{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                items.update(_flatten_dict(v, new_key, sep))
            else:
                items[new_key] = str(round(v, 4) if isinstance(v, float) else v)
    elif isinstance(d, list):
        for i, v in enumerate(d[:5]):
            items.update(_flatten_dict(v, f"{prefix}[{i}]", sep))
    return items
