"""Merge per-target experiment outputs into outputs/results.json and outputs/trials.csv."""
import glob, json, os
import pandas as pd
from gp_core import TARGETS
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
res = {}
for t in TARGETS:
    f = os.path.join(OUT, f"results_{t}.json")
    if os.path.exists(f):
        res.update(json.load(open(f)))
json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
tr = [pd.read_csv(os.path.join(OUT, f"trials_{t}.csv")) for t in TARGETS
      if os.path.exists(os.path.join(OUT, f"trials_{t}.csv"))]
pd.concat(tr, ignore_index=True).to_csv(os.path.join(OUT, "trials.csv"), index=False, encoding="utf-8-sig")
print("merged targets:", list(res))
