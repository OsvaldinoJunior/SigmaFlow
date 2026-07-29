"""
sigmaflow/run_dmaic.py
=======================
Simple entry-point for the Automated DMAIC Engine.

Usage (Python)
--------------
    from sigmaflow.core.dmaic_engine import DMAICEngine
    import pandas as pd

    data    = pd.read_csv("input/datasets/capability_process.csv")
    engine  = DMAICEngine(output_dir="output/dmaic")
    results = engine.run(data)

Usage (command line)
--------------------
    python run_dmaic.py input/datasets/capability_process.csv
    python run_dmaic.py data.csv --target defects --output output/dmaic
    python run_dmaic.py data.csv --phases measure analyze control
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure sigmaflow package is importable when run from the project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_dmaic",
        description="SigmaFlow — Automated DMAIC Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_dmaic.py data.csv
  python run_dmaic.py data.csv --target defects
  python run_dmaic.py data.csv --target yield --output output/dmaic
  python run_dmaic.py data.csv --phases measure analyze
        """,
    )
    parser.add_argument(
        "dataset",
        help="Path to CSV or Excel file (or pass 'demo' to use built-in demo data)",
    )
    parser.add_argument(
        "--target", "-t",
        default=None,
        help="Name of the response / quality column (auto-detected if not given)",
    )
    parser.add_argument(
        "--output", "-o",
        default="output/dmaic",
        help="Output directory for results JSON (default: output/dmaic)",
    )
    parser.add_argument(
        "--phases", "-p",
        nargs="+",
        choices=["define", "measure", "analyze", "improve", "control"],
        default=None,
        help="Phases to run (default: all five)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress banners",
    )
    return parser.parse_args()


def _demo_dataframe():
    """Generate a small demo dataset for testing."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(42)
    n   = 200
    temp     = rng.normal(72, 3, n)
    pressure = rng.normal(100, 5, n)
    time_seq = np.arange(1, n + 1)
    defects  = (
        0.3 * temp
        - 0.15 * pressure
        + rng.normal(0, 2, n)
    ).clip(0)
    operator = rng.choice(["Alice", "Bob", "Carlos"], n)
    return pd.DataFrame({
        "time":      time_seq,
        "temperature": temp.round(2),
        "pressure":    pressure.round(2),
        "operator":    operator,
        "defects":     defects.round(2),
    })


def main() -> None:
    args = _parse_args()

    import pandas as pd
    from sigmaflow.core.dmaic_engine import DMAICEngine

    # ── Load data ──────────────────────────────────────────────────────────────
    if args.dataset.lower() == "demo":
        print("📊 Using built-in demo dataset …")
        df = _demo_dataframe()
    else:
        path = Path(args.dataset)
        if not path.exists():
            print(f"❌ File not found: {path}", file=sys.stderr)
            sys.exit(1)
        print(f"📂 Loading: {path}")
        if path.suffix == ".csv":
            df = pd.read_csv(path)
        elif path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            print(f"❌ Unsupported format: {path.suffix}", file=sys.stderr)
            sys.exit(1)

    # ── Run engine ─────────────────────────────────────────────────────────────
    engine = DMAICEngine(
        target_col = args.target,
        output_dir = args.output,
        run_phases = args.phases,
        verbose    = not args.quiet,
    )

    results = engine.run(df)

    # ── Print summary ──────────────────────────────────────────────────────────
    summary = results.get("summary", {})
    print("\n" + "═" * 56)
    print("  DMAIC SUMMARY")
    print("═" * 56)
    print(f"  Dataset        : {summary.get('dataset', {}).get('rows')} rows "
          f"× {summary.get('dataset', {}).get('cols')} cols")
    print(f"  Primary target : {summary.get('primary_target', '—')}")
    cpk = summary.get("cpk")
    r2  = summary.get("r2")
    n_ooc = summary.get("n_ooc")
    if cpk is not None:
        print(f"  Cpk            : {cpk:.3f}  {'✅' if cpk>=1.33 else '⚠' if cpk>=1.0 else '🔴'}")
    if r2 is not None:
        print(f"  R²             : {r2:.3f}")
    if n_ooc is not None:
        print(f"  OOC points     : {n_ooc}  {'✅' if n_ooc==0 else '⚠'}")
    print(f"  Elapsed        : {results.get('elapsed_s', '?')}s")
    print(f"  Insights       : {summary.get('n_insights', 0)} generated")
    print(f"  Results saved  : {args.output}/dmaic_results.json")
    print("═" * 56)

    # Print insights
    insights = summary.get("all_insights", [])
    if insights:
        print("\n📋 Key Insights:")
        for ins in insights[:10]:
            print(f"   {ins}")


if __name__ == "__main__":
    main()
