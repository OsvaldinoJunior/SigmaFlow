"""Generate v10 demo datasets including MSA, FMEA, DOE, and regression."""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
out = Path("input/datasets")
out.mkdir(parents=True, exist_ok=True)

# 1. Capability process
pd.DataFrame({"measurement": rng.normal(10.02,0.08,200),"usl":10.2,"lsl":9.8})\
    .to_csv(out/"capability_process.csv",index=False)

# 2. SPC with drift
vals = rng.normal(2.5,0.05,120); vals[80:95]+=0.25
pd.DataFrame({"timestamp":range(1,121),"thickness":vals.round(4)})\
    .to_csv(out/"spc_thickness.csv",index=False)

# 3. Pareto
pd.DataFrame({"defect_type":["Dimensional","Surface","Weld","Assembly","Material","Packaging","Label","Paint"],
              "count":[320,280,195,140,95,60,45,30]})\
    .to_csv(out/"pareto_defects.csv",index=False)

# 4. Multi-variable (regression + root cause)
temp = rng.normal(75,5,300); pres = rng.normal(2.5,.3,300); spd = rng.normal(100,10,300)
defects = (0.3*temp + 0.5*pres + 0.1*spd + rng.normal(0,3,300)).clip(0).round(1)
pd.DataFrame({"temperature":temp.round(2),"pressure":pres.round(3),"speed":spd.round(1),
              "humidity":rng.uniform(30,80,300).round(1),"defects":defects})\
    .to_csv(out/"process_variables.csv",index=False)

# 5. MSA dataset (Gauge R&R)
parts = list(range(1, 11)) * 3 * 2   # 10 parts × 3 operators × 2 reps
ops   = [f"Op{o}" for o in ([1]*20 + [2]*20 + [3]*20)]
true_vals = {p: rng.normal(10 + p*0.2, 0.05) for p in range(1,11)}
meas = []
for p, o in zip(parts, ops):
    base    = true_vals[p % 10 or 10]
    op_bias = {"Op1": 0.0, "Op2": 0.03, "Op3": -0.02}[o]
    meas.append(round(float(rng.normal(base + op_bias, 0.04)), 4))
pd.DataFrame({"Part": parts, "Operator": ops, "Measurement": meas})\
    .to_csv(out/"msa_gauge_rr.csv", index=False)
print(f"  ✓ MSA dataset: {len(parts)} rows")

# 6. FMEA dataset
pd.DataFrame({
    "Failure_Mode": [
        "Weld crack","Dimensional out-of-spec","Surface contamination",
        "Incorrect torque","Material delamination","Seal failure",
        "Electrical short","Label missing",
    ],
    "Severity":    [9, 7, 5, 8, 9, 8, 10, 2],
    "Occurrence":  [3, 5, 4, 3, 2, 4,  2, 6],
    "Detection":   [4, 3, 5, 4, 6, 3,  3, 7],
}).to_csv(out/"fmea_analysis.csv", index=False)
print("  ✓ FMEA dataset")

# 7. DOE dataset (2-factor factorial)
factors = []
for temp_l in ["Low","High"]:
    for press_l in ["Low","High"]:
        for _ in range(5):
            base = (8 if temp_l=="High" else 5) + (3 if press_l=="High" else 1)
            factors.append({"Temperature": temp_l, "Pressure": press_l,
                            "Yield": round(rng.normal(base, 0.8), 2)})
pd.DataFrame(factors).to_csv(out/"doe_factorial.csv", index=False)
print("  ✓ DOE dataset")

print(f"\nAll demo datasets written to '{out}'")
