"""
examples/run_dmaic_example.py
==============================
Executable example demonstrating a complete SigmaFlow DMAIC pipeline.

This script:
1. Generates a realistic manufacturing process dataset
2. Saves it to input/datasets/
3. Runs the full SigmaFlow analysis pipeline
4. Prints a summary of results and insights
5. Reports where to find the generated figures, dashboard, and PDF report

Usage
-----
    python examples/run_dmaic_example.py

Requirements
------------
    pip install -r requirements.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make sure the project root is importable whether run from root or examples/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── 1. Generate synthetic manufacturing dataset ───────────────────────────────

def generate_demo_dataset(n: int = 150, seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic manufacturing process dataset.

    Parameters
    ----------
    n : int
        Number of observations (default 150).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        DataFrame with process measurements and control variables.
    """
    rng = np.random.default_rng(seed)

    temperature = rng.normal(loc=185.0, scale=3.5, size=n)   # °C
    pressure    = rng.normal(loc=12.0,  scale=0.8, size=n)   # bar
    speed       = rng.uniform(low=80,   high=120,  size=n)   # RPM

    # Quality metric influenced by process variables + noise
    thickness = (
        10.0
        + 0.02  * (temperature - 185)
        - 0.05  * (pressure - 12)
        + 0.01  * (speed - 100)
        + rng.normal(0, 0.12, n)
    )

    shift = rng.choice(["A", "B", "C"], size=n)

    return pd.DataFrame({
        "temperature_c": temperature.round(2),
        "pressure_bar":  pressure.round(3),
        "speed_rpm":     speed.round(1),
        "thickness_mm":  thickness.round(4),
        "shift":         shift,
        "usl":           10.3,
        "lsl":           9.7,
    })


# ── 2. Save dataset ────────────────────────────────────────────────────────────

def save_dataset(df: pd.DataFrame, path: Path) -> None:
    """
    Save a DataFrame to Excel.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset to save.
    path : Path
        Destination file path (.xlsx).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    print(f"  ✓ Dataset saved → {path}  ({df.shape[0]} rows × {df.shape[1]} cols)")


# ── 3. Run analysis ────────────────────────────────────────────────────────────

def run_pipeline(input_dir: Path, output_dir: Path) -> list[dict]:
    """
    Execute the full SigmaFlow analysis pipeline.

    Parameters
    ----------
    input_dir : Path
        Directory containing dataset files.
    output_dir : Path
        Directory where all outputs (figures, reports, dashboard) are written.

    Returns
    -------
    list[dict]
        List of result dicts, one per processed dataset.
    """
    from sigmaflow.core.engine import Engine

    engine = Engine(
        input_dir      = input_dir,
        output_dir     = output_dir,
        run_root_cause = True,
        run_dashboard  = True,
        run_statistics = True,
    )
    return engine.run()


# ── 4. Print summary ───────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    """
    Print a human-readable summary of pipeline results.

    Parameters
    ----------
    results : list[dict]
        Pipeline result list returned by Engine.run().
    """
    print("\n" + "=" * 60)
    print("  SIGMAFLOW — RESULTS SUMMARY")
    print("=" * 60)

    for r in results:
        print(f"\n📊  Dataset : {r['name']}")
        print(f"    Type    : {r['dataset_type'].upper()}")
        print(f"    Shape   : {r['shape'][0]} rows × {r['shape'][1]} cols")
        print(f"    Time    : {r['elapsed_s']:.2f} s")

        # Capability metrics
        cap = r.get("analysis", {}).get("capability", {})
        if cap:
            cpk  = cap.get("Cpk", "N/A")
            dpmo = cap.get("dpmo", "N/A")
            sig  = cap.get("sigma_level", "N/A")
            print(f"\n    Process Capability:")
            print(f"      Cpk         = {cpk:.3f}" if isinstance(cpk, float) else f"      Cpk = {cpk}")
            print(f"      DPMO        = {dpmo:,.1f}" if isinstance(dpmo, float) else f"      DPMO = {dpmo}")
            print(f"      Sigma level = {sig:.2f}σ" if isinstance(sig, float) else f"      Sigma = {sig}")

        # Structured insights
        structured = r.get("structured_insights", [])
        criticals  = [i for i in structured if i.get("severity") == "critical"]
        warnings   = [i for i in structured if i.get("severity") == "warning"]
        if structured:
            print(f"\n    Insights: {len(structured)} total  "
                  f"({len(criticals)} critical, {len(warnings)} warnings)")
            for insight in structured[:5]:
                icon = "🔴" if insight["severity"] == "critical" else \
                       "🟡" if insight["severity"] == "warning" else "🔵"
                print(f"      {icon} {insight.get('description', '')}")

        # Text insights
        text_insights = r.get("insights", [])
        if text_insights:
            print(f"\n    Analysis Findings:")
            for line in text_insights[:4]:
                print(f"      → {line}")

        # Errors
        errors = r.get("errors", {})
        if errors:
            print(f"\n    ⚠ Errors encountered: {list(errors.keys())}")

        # Abstract
        abstract = r.get("abstract", "")
        if abstract:
            print(f"\n    Abstract:\n      {abstract}")

        # Figures
        plots = r.get("plots", [])
        if plots:
            print(f"\n    Generated {len(plots)} figure(s):")
            for p in plots:
                print(f"      ✓ {Path(p).name}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the complete SigmaFlow DMAIC example pipeline."""
    input_dir  = ROOT / "input" / "datasets"
    output_dir = ROOT / "output"
    dataset    = input_dir / "dmaic_example.xlsx"

    print("\n" + "=" * 60)
    print("  SIGMAFLOW — DMAIC EXAMPLE PIPELINE")
    print("=" * 60)

    # Step 1: Generate
    print("\n[1/4] Generating demo manufacturing dataset …")
    df = generate_demo_dataset(n=150)

    # Step 2: Save
    print("[2/4] Saving dataset …")
    save_dataset(df, dataset)

    # Step 3: Run pipeline
    print("[3/4] Running SigmaFlow pipeline …")
    results = run_pipeline(input_dir, output_dir)

    # Step 4: Print summary
    print("[4/4] Pipeline complete.")
    print_summary(results)

    # Output locations
    print("\n" + "=" * 60)
    print("  OUTPUT LOCATIONS")
    print("=" * 60)
    print(f"  Figures   → {output_dir / 'figures'}")
    print(f"  Dashboard → {output_dir / 'dashboard' / 'report.html'}")
    print(f"  Report    → {output_dir / 'reports' / 'process_analysis_report.pdf'}")
    print(f"  Insights  → {output_dir / 'insights.json'}")
    print()


if __name__ == "__main__":
    main()
