"""
main.py — SigmaFlow v10 (entry-point)
======================================
Usage
-----
    python main.py                        # normal run
    python main.py --force                # wipe outputs, then run clean
    python main.py --demo                 # generate demo datasets + run
    python main.py --demo --force         # wipe outputs, regenerate demos, run
    python main.py --input  <dir>         # custom input directory
    python main.py --output <dir>         # custom output directory
    python main.py --no-dashboard         # skip HTML dashboard
    python main.py --list                 # list registered dataset types

Full CLI alternative:
    python cli.py analyze dataset.csv
    python cli.py demo
    python cli.py dashboard
    python cli.py insights
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


# ── Demo dataset generator ────────────────────────────────────────────────────

def _demo(input_dir: Path) -> None:
    """Write five representative demo CSV datasets to *input_dir*."""
    import numpy as np
    import pandas as pd

    input_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    # 1 — Process capability
    pd.DataFrame({
        "measurement": rng.normal(10.02, 0.08, 200),
        "usl": 10.2,
        "lsl": 9.8,
    }).to_csv(input_dir / "capability_process.csv", index=False)

    # 2 — SPC with injected mean shift
    vals = rng.normal(2.5, 0.05, 120)
    vals[80:95] += 0.25
    pd.DataFrame({
        "timestamp": range(1, 121),
        "thickness": vals.round(4),
    }).to_csv(input_dir / "spc_thickness.csv", index=False)

    # 3 — Pareto defect counts
    pd.DataFrame({
        "defect_type": [
            "Dimensional", "Surface", "Weld", "Assembly",
            "Material", "Packaging", "Label", "Paint",
        ],
        "count": [320, 280, 195, 140, 95, 60, 45, 30],
    }).to_csv(input_dir / "pareto_defects.csv", index=False)

    # 4 — Logistics / service
    dist = rng.uniform(50, 800, 200)
    pd.DataFrame({
        "distance_km":   dist.round(1),
        "delivery_days": (dist / 200 + rng.normal(0, 0.4, 200)).clip(1).round(1),
        "sla_days":      [3 if d < 400 else 5 for d in dist],
    }).to_csv(input_dir / "logistics.csv", index=False)

    # 5 — Multi-variable process data
    temp    = rng.normal(75, 5, 300)
    pres    = rng.normal(2.5, 0.3, 300)
    spd     = rng.normal(100, 10, 300)
    defects = (0.3 * temp + 0.5 * pres + 0.1 * spd + rng.normal(0, 3, 300)).clip(0).round(1)
    pd.DataFrame({
        "temperature": temp.round(2),
        "pressure":    pres.round(3),
        "speed":       spd.round(1),
        "humidity":    rng.uniform(30, 80, 300).round(1),
        "defects":     defects,
    }).to_csv(input_dir / "process_variables.csv", index=False)

    print(f"  ✓ 5 demo datasets written to '{input_dir}'")


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="SigmaFlow v10 — Automated Six Sigma Analysis Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                          normal run
  python main.py --force                  wipe previous outputs, then run
  python main.py --demo                   generate demo data and run
  python main.py --demo --force           clean state + demo data + run
  python main.py --input path/to/csvs     custom input directory
  python main.py --output path/to/out     custom output directory
  python main.py --no-dashboard           skip HTML dashboard generation
  python main.py --list                   list registered dataset types
        """,
    )
    parser.add_argument(
        "--input",
        default="input/datasets",
        metavar="DIR",
        help="Directory containing CSV / Excel input files  (default: input/datasets)",
    )
    parser.add_argument(
        "--output",
        default="output",
        metavar="DIR",
        help="Root directory for all generated outputs  (default: output)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate five demo datasets before running the pipeline",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Delete all previous outputs (figures/, reports/, dashboard/, logs/) "
            "before running.  Guarantees a completely clean pipeline run."
        ),
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip HTML dashboard generation",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print registered dataset analyzer types and exit",
    )
    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = _build_parser().parse_args()

    input_dir  = ROOT / args.input
    output_dir = ROOT / args.output

    # Logging must be initialised before anything else so that messages from
    # clear_outputs() and ensure_output_dirs() are captured.
    from sigmaflow.core.logger import setup_logging
    setup_logging(log_dir=output_dir / "logs", level="INFO")

    # ── Banner ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 64)
    print("  SigmaFlow v10 — Automated Six Sigma Analysis Engine")
    print("═" * 64)

    # ── --force: wipe every previous output, then rebuild folder skeleton ─────
    if args.force:
        from sigmaflow.core.output_manager import clear_outputs

        print("\n  ⚠  Force mode enabled — clearing previous outputs …")
        logger.warning("Force mode enabled — clearing previous outputs")

        clear_outputs(output_dir)   # deletes children, recreates subdirs

        # clear_outputs already calls ensure_output_dirs internally, but we
        # emit the required log line here so it always appears in the log.
        logger.info("Output directories cleared — starting fresh pipeline run.")
        print("  ✓  Output directories cleared — starting fresh pipeline run.")

    else:
        # Normal run: just make sure all output directories exist.
        from sigmaflow.core.output_manager import ensure_output_dirs
        ensure_output_dirs(output_dir)

    # ── Dataset registry ──────────────────────────────────────────────────────
    from sigmaflow.core.dataset_registry import DatasetRegistry

    registry = DatasetRegistry().discover()

    if args.list:
        print(registry.summary())
        return

    print(registry.summary())

    # ── Optional demo dataset generation ─────────────────────────────────────
    if args.demo:
        print("\n  Generating demo datasets …")
        _demo(input_dir)

    # ── Run the main analysis pipeline ───────────────────────────────────────
    from sigmaflow.core.engine import Engine

    engine = Engine(
        input_dir=input_dir,
        output_dir=output_dir,
        registry=registry,
        run_dashboard=not args.no_dashboard,
    )
    results = engine.run()

    if not results:
        print(f"\n  No files found in '{input_dir}'.")
        print("  Use:  python main.py --demo\n")
        return

    # ── Print insights to console ─────────────────────────────────────────────
    print("\n" + "─" * 64)
    print("  INSIGHTS")
    print("─" * 64)
    for r in results:
        print(f"\n  [{r['dataset_type'].upper()}] {r['name']}")
        for ins in r.get("insights", []):
            print(f"    • {ins}")
        rca = r.get("root_cause", {})
        if rca.get("strong_candidates"):
            print(f"    🔍 Root cause: {', '.join(rca['strong_candidates'][:3])}")

    # ── Generate LaTeX / PDF report ───────────────────────────────────────────
    from sigmaflow.report.latex_report import LatexReportGenerator

    gen  = LatexReportGenerator(results, output_dir=output_dir / "reports")
    path = gen.generate()

    dash = output_dir / "dashboard" / "report.html"
    print(f"\n  ✅ Report:    {path}")
    if dash.exists():
        print(f"  ✅ Dashboard: {dash}")
    print(f"\n  outputs: figures/ | reports/ | dashboard/ | insights.json | logs/\n")


if __name__ == "__main__":
    main()
