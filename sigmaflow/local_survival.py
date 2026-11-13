"""Kaplan–Meier for independent units with exact events/right censoring.

One row per unit; no delayed entry, recurrent events or competing-risk model.
Confidence intervals are pointwise log-log Greenwood intervals. Their boundary
values at S=0/1 are undefined and deliberately returned as None.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def kaplan_meier(times, events):
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=float)
    if times.ndim != 1 or events.ndim != 1 or len(times) != len(events) or len(times) < 2:
        raise ValueError("Kaplan–Meier requer ao menos duas unidades com tempo e evento correspondentes.")
    if not np.isfinite(times).all() or (times < 0).any() or not (times > 0).any():
        raise ValueError("Tempos devem ser finitos e não negativos, com ao menos um acompanhamento positivo.")
    if not np.isfinite(events).all() or not np.isin(events, [0, 1]).all():
        raise ValueError("Evento deve ser 1 para falha observada ou 0 para censura à direita.")

    order = np.argsort(times, kind="stable")
    times, events = times[order], events[order].astype(int)
    unique_times, starts, sizes = np.unique(times, return_index=True, return_counts=True)
    event_counts = np.add.reduceat(events, starts)
    at_risk = len(times)
    survival, greenwood, rmst, previous_time = 1.0, 0.0, 0.0, 0.0
    median = None
    z = float(stats.norm.ppf(0.975))
    table = []
    for time, removed, failures in zip(unique_times, sizes, event_counts):
        time, removed, failures = float(time), int(removed), int(failures)
        censored = removed - failures
        rmst += (time - previous_time) * survival
        # Censors tied with failures are still in this risk set. Both leave
        # only after applying the failure decrement at this time.
        survival *= 1 - failures / at_risk
        if failures and failures < at_risk:
            greenwood += failures / (at_risk * (at_risk - failures))
        lower = upper = None
        if 0 < survival < 1:
            center = math.log(-math.log(survival))
            se = math.sqrt(greenwood) / abs(math.log(survival))
            inverse = lambda value: math.exp(-math.exp(min(value, 700)))
            lower, upper = inverse(center + z*se), inverse(center - z*se)
        if median is None and (survival <= 0.5 or math.isclose(survival, 0.5, rel_tol=0, abs_tol=1e-12)):
            median = time
        table.append({"tempo": time, "risco": at_risk, "falhas": failures, "censuras": censored,
                      "sobrevivencia": float(survival), "inferior": lower, "superior": upper})
        at_risk -= removed
        previous_time = time

    return {"n": len(times), "falhas": int(events.sum()), "censuras": int(len(events)-events.sum()),
            "tau": float(times[-1]), "rmst": float(rmst), "mediana": median,
            "sobrevivencia_final": float(survival), "tabela": table}
