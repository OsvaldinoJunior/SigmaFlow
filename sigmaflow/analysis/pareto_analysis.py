"""
sigmaflow/analysis/pareto_analysis.py
=======================================
Pareto analysis functions (80/20 rule).

The Pareto principle states that ~80% of effects come from ~20% of causes.
In quality management this is used to prioritize which defect types,
failure modes, or root causes to address first.

Functions
---------
    compute_pareto(series_counts, category_col, count_col) → dict
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def compute_pareto(
    df: pd.DataFrame,
    category_col: str,
    count_col: str,
) -> Dict[str, Any]:
    """
    Compute Pareto analysis from a frequency table.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset with at least one category column and one count column.
    category_col : str
        Column with defect/cause category names.
    count_col : str
        Column with occurrence counts or frequencies.

    Returns
    -------
    dict
        Keys: categories, counts, cumulative_pct, vital_few, useful_many,
              vital_few_pct (% of causes that explain 80% of effects).
    """
    # Sort by frequency descending
    sorted_df = (
        df[[category_col, count_col]]
        .dropna()
        .sort_values(count_col, ascending=False)
        .reset_index(drop=True)
    )

    total = sorted_df[count_col].sum()
    if total == 0:
        return {"error": "All counts are zero."}

    sorted_df["pct"]        = sorted_df[count_col] / total * 100
    sorted_df["cumulative"] = sorted_df["pct"].cumsum()

    # Identify vital few (categories accounting for first 80%)
    vital_mask   = sorted_df["cumulative"] <= 80.0
    # Include the category that crosses 80%
    crossover    = sorted_df[~vital_mask].index[0] if not vital_mask.all() else sorted_df.index[-1]
    vital_mask.iloc[crossover] = True

    vital_few    = sorted_df.loc[vital_mask, category_col].tolist()
    useful_many  = sorted_df.loc[~vital_mask, category_col].tolist()

    vital_few_pct = round(len(vital_few) / len(sorted_df) * 100, 1)

    return {
        "categories":      sorted_df[category_col].tolist(),
        "counts":          sorted_df[count_col].tolist(),
        "cumulative_pct":  sorted_df["cumulative"].round(1).tolist(),
        "vital_few":       vital_few,
        "useful_many":     useful_many,
        "vital_few_pct":   vital_few_pct,
        "total":           int(total),
    }
