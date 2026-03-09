"""
cli.py — SigmaFlow v10 Command-Line Interface
=============================================
Professional CLI for SigmaFlow v10.

Commands
--------
    sigmaflow analyze <file_or_folder>  Full pipeline
    sigmaflow demo                      Demo data + full pipeline
    sigmaflow report                    Re-generate LaTeX/PDF report
    sigmaflow insights                  Print insights.json
    sigmaflow dashboard                 Re-generate HTML dashboard only
    sigmaflow list                      List registered analyzers

Examples
--------
    python cli.py analyze process_data.csv
    python cli.py analyze input/datasets/
    python cli.py demo
    python cli.py insights
    python cli.py dashboard
    python cli.py list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sigmaflow.core.logger import setup_logging, get_logger, log_stage

setup_logging(log_dir=None, level="INFO")
logger = get_logger("sigmaflow.cli")


# ─── Demo generator ───────────────────────────────────────────────────────────

def _generate_demo_datasets(input_dir: Path) -> None:
    import numpy as np
    import pandas as pd

    input_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    # 1. Capability
    pd.DataFrame({
        "measurement": rng.normal(10.02, 0.08, 200),
        "usl": 10.2, "lsl": 9.8,
    }).to_csv(input_dir / "capability_process.csv", index=False)

    # 2. SPC with drift
    vals = rng.normal(2.5, 0.05, 120)
    vals[80:95] += 0.25
    pd.DataFrame({
        "timestamp": range(1, 121),
        "thickness": vals.round(4),
    }).to_csv(input_dir / "spc_thickness.csv", index=False)

    # 3. Pareto
    pd.DataFrame({
        "defect_type": ["Dimensional","Surface","Weld","Assembly",
                        "Material","Packaging","Label","Paint"],
        "count": [320, 280, 195, 140, 95, 60, 45, 30],
    }).to_csv(input_dir / "pareto_defects.csv", index=False)

    # 4. Logistics
    dist = rng.uniform(50, 800, 200)
    pd.DataFrame({
        "distance_km":   dist.round(1),
        "delivery_days": (dist / 200 + rng.normal(0, 0.4, 200)).clip(1).round(1),
        "sla_days":      [3 if d < 400 else 5 for d in dist],
    }).to_csv(input_dir / "logistics.csv", index=False)

    # 5. Multi-variable (root cause demo)
    temp = rng.normal(75, 5, 300)
    pres = rng.normal(2.5, 0.3, 300)
    spd  = rng.normal(100, 10, 300)
    defects = (0.3 * temp + 0.5 * pres + 0.1 * spd + rng.normal(0, 3, 300)).clip(0).round(1)
    pd.DataFrame({
        "temperature": temp.round(2),
        "pressure":    pres.round(3),
        "speed":       spd.round(1),
        "humidity":    rng.uniform(30, 80, 300).round(1),
        "defects":     defects,
    }).to_csv(input_dir / "process_variables.csv", index=False)

    print(f"  ✓ 5 demo datasets written to '{input_dir}'")


# ─── Banner ───────────────────────────────────────────────────────────────────

def _banner() -> None:
    print("\n" + "═" * 64)
    print("  SigmaFlow v10 — Automated Six Sigma Analysis Engine")
    print("═" * 64 + "\n")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_analyze(args: argparse.Namespace) -> None:
    from sigmaflow.core.engine import Engine
    from sigmaflow.core.dataset_registry import DatasetRegistry
    import shutil

    target     = Path(args.path)
    output_dir = Path(args.output)

    if target.is_file():
        input_dir = ROOT / "input" / "datasets"
        input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, input_dir / target.name)
    elif target.is_dir():
        input_dir = target
    else:
        print(f"  ✗ Path not found: {target}")
        sys.exit(1)

    _banner()
    registry = DatasetRegistry().discover()
    print(registry.summary())

    engine  = Engine(input_dir=input_dir, output_dir=output_dir, registry=registry)
    results = engine.run()

    if not results:
        print(f"\n  No datasets processed. Put CSV files in '{input_dir}'.\n")
        return

    _print_summary(results)
    _generate_report(results, output_dir)
    _print_outputs(output_dir)


def cmd_demo(args: argparse.Namespace) -> None:
    from sigmaflow.core.engine import Engine
    from sigmaflow.core.dataset_registry import DatasetRegistry

    input_dir  = ROOT / "input" / "datasets"
    output_dir = Path(args.output)

    _banner()
    log_stage("Generating demo datasets")
    _generate_demo_datasets(input_dir)

    registry = DatasetRegistry().discover()
    print(registry.summary())

    engine  = Engine(input_dir=input_dir, output_dir=output_dir, registry=registry)
    results = engine.run()

    _print_summary(results)
    _generate_report(results, output_dir)
    _print_outputs(output_dir)


def cmd_report(args: argparse.Namespace) -> None:
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ insights.json not found at '{insights_file}'")
        print("    Run 'python cli.py analyze' first.")
        sys.exit(1)
    with insights_file.open(encoding="utf-8") as f:
        results = json.load(f)
    _generate_report(results, Path(args.output))


def cmd_insights(args: argparse.Namespace) -> None:
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ No insights.json found at '{insights_file}'")
        print("    Run 'python cli.py analyze' or 'python cli.py demo' first.")
        return

    with insights_file.open(encoding="utf-8") as f:
        data = json.load(f)

    print("\n" + "═" * 64)
    print("  SigmaFlow v10 — Insights Summary")
    print("═" * 64)

    for dataset in data:
        print(f"\n  [{dataset.get('type','?').upper()}] {dataset.get('dataset','?')}")

        abstract = dataset.get("abstract", "")
        if abstract:
            short = abstract[:220] + ("..." if len(abstract) > 220 else "")
            print(f"    {short}")

        for ins in dataset.get("insights", []):
            sev  = ins.get("severity", "info").upper()
            rule = ins.get("rule", "").replace("_", " ").title()
            desc = ins.get("description", "")
            rec  = ins.get("recommendation", "")[:110]
            print(f"\n    [{sev}] {rule}")
            print(f"    • {desc}")
            if rec:
                print(f"    → {rec}...")

        for rca in dataset.get("root_cause", []):
            print(f"\n    [ROOT CAUSE] {rca.get('description','')}")

    print()


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Regenerate the HTML dashboard from existing insights.json."""
    insights_file = Path(args.output) / "insights.json"
    if not insights_file.exists():
        print(f"  ✗ No insights.json found at '{insights_file}'")
        print("    Run 'python cli.py analyze' first.")
        sys.exit(1)

    log_stage("Generating HTML Dashboard")
    from sigmaflow.report.html_dashboard import HTMLDashboardGenerator
    with insights_file.open(encoding="utf-8") as f:
        results = json.load(f)
    gen  = HTMLDashboardGenerator(results, output_dir=Path(args.output) / "dashboard")
    path = gen.generate()
    print(f"\n  ✅ Dashboard: {path}")
    print("    Open in any browser — fully self-contained HTML.\n")


def cmd_list(args: argparse.Namespace) -> None:
    from sigmaflow.core.dataset_registry import DatasetRegistry
    print(DatasetRegistry().discover().summary())


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _print_summary(results: list) -> None:
    print("\n" + "─" * 64)
    print("  INSIGHTS SUMMARY")
    print("─" * 64)
    for r in results:
        print(f"\n  [{r['dataset_type'].upper()}] {r['name']}")
        for ins in r.get("insights", []):
            print(f"    • {ins}")
        structured = r.get("structured_insights", [])
        n_crit = sum(1 for s in structured if s.get("severity") == "critical")
        n_warn = sum(1 for s in structured if s.get("severity") == "warning")
        if n_crit: print(f"    ⚠  {n_crit} critical finding(s)")
        if n_warn: print(f"    ⚡ {n_warn} warning(s)")
        rca = r.get("root_cause", {})
        if rca.get("strong_candidates"):
            print(f"    🔍 Root cause candidates: {', '.join(rca['strong_candidates'][:3])}")


def _generate_report(results: list, output_dir: Path) -> None:
    from sigmaflow.report.latex_report import LatexReportGenerator
    log_stage("Generating LaTeX Report")
    gen  = LatexReportGenerator(results, output_dir=output_dir / "reports")
    path = gen.generate()
    log_stage("Compiling PDF")
    print(f"  ✅  Report: {path}")


def _print_outputs(output_dir: Path) -> None:
    print(f"\n  Output directory: {output_dir}/")
    print(f"  ├── figures/           PNG charts per dataset")
    print(f"  ├── reports/           report.tex + report.pdf")
    print(f"  ├── dashboard/         report.html  ← open in browser")
    print(f"  ├── insights.json      Machine-readable insights")
    print(f"  └── logs/              Timestamped log files\n")


# ─── Entry-point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sigmaflow",
        description="SigmaFlow v10 — Automated Six Sigma Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--output", "-o", default="output", help="Output directory (default: output/)")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze",   help="Analyze a file or folder");  p.add_argument("path"); p.set_defaults(func=cmd_analyze)
    p = sub.add_parser("demo",      help="Generate demo data + run");   p.set_defaults(func=cmd_demo)
    p = sub.add_parser("report",    help="Re-generate LaTeX report");   p.set_defaults(func=cmd_report)
    p = sub.add_parser("insights",  help="Print insights to console");  p.set_defaults(func=cmd_insights)
    p = sub.add_parser("dashboard", help="Re-generate HTML dashboard"); p.set_defaults(func=cmd_dashboard)
    p = sub.add_parser("list",      help="List registered analyzers");  p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
