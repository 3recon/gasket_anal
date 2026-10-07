"""Merge the per-source extraction batches into one clean dataset.

Input : data/raw/batch_*.csv   (schema: data/raw/SCHEMA.md)
Output: data/gasket_dataset_raw.csv    (all extracted rows, merged)
        data/gasket_dataset_clean.csv  (rows used for modelling + QC flags)
        data/cleaning_log.txt
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

PHR = ["polymer_phr", "carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr",
       "titanium_oxide_phr", "fluororesin_phr", "other_inorganic_filler_phr",
       "organic_additive_phr", "coagent_phr", "peroxide_phr", "nitrile_curative_phr",
       "other_curative_phr", "acid_acceptor_phr", "processing_aid_phr"]
PROPS = ["hardness_shoreA", "tensile_MPa", "elongation_pct", "m100_MPa",
         "compression_set_pct", "plasma_weight_loss_pct"]
RANGES = {"hardness_shoreA": (20, 100), "tensile_MPa": (0.3, 60), "elongation_pct": (10, 1500),
          "m100_MPa": (0.1, 40), "compression_set_pct": (0, 100)}

log = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log.append(s)


frames = []
for f in sorted(glob.glob(os.path.join(RAW, "batch_*.csv"))):
    d = pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""])
    d["batch"] = os.path.basename(f).replace(".csv", "")
    say(f"{os.path.basename(f)}: {len(d)} rows, {d['source_id'].nunique()} sources")
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
for c in PHR + PROPS:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["polymer_type"] = df["polymer_type"].str.strip().str.upper()
df["cure_system"] = df["cure_system"].str.strip().str.lower()
df["source_id"] = df["source_id"].str.strip()
df["example_label"] = df["example_label"].str.strip()
say(f"merged: {len(df)} rows from {df['source_id'].nunique()} sources")

# 1) exact duplicates of (source, example)
dup = df.duplicated(["source_id", "example_label"], keep="first")
say(f"duplicate (source_id, example_label) removed: {int(dup.sum())}")
df = df[~dup].copy()

# 2) property sanity ranges -> blank out implausible values (logged)
for c, (lo, hi) in RANGES.items():
    bad = df[c].notna() & ~df[c].between(lo, hi)
    for _, r in df[bad].iterrows():
        say(f"  out-of-range {c}={r[c]} in {r['source_id']} {r['example_label']} -> set NaN")
    df.loc[bad, c] = np.nan

df.to_csv(os.path.join(ROOT, "data", "gasket_dataset_raw.csv"), index=False, encoding="utf-8-sig")

# 3) modelling subset
m = df.copy()
# formulations are normalised to 100 phr of elastomer; rows with another basis are rescaled
scale = 100.0 / m["polymer_phr"].where(m["polymer_phr"] > 0, 100.0).fillna(100.0)
rescaled = (scale - 1).abs() > 1e-6
if rescaled.any():
    say(f"rows rescaled to 100 phr polymer basis: {int(rescaled.sum())}")
for c in PHR[1:]:
    m[c] = m[c] * scale
m["polymer_phr"] = 100.0
# documents whose seals are not for semiconductor equipment (automotive / oil & gas) are excluded
NON_SEMI = ["KR102796110B1", "KR102324534B1", "KR20130014651A", "CN106633544B"]
ns = m["source_id"].isin(NON_SEMI)
say(f"excluded non-semiconductor applications ({', '.join(NON_SEMI)}): {int(ns.sum())}")
m = m[~ns]
# curative chemistry unspecified but the whole curative package is reported in other_curative_phr
# -> the split columns are not unknown, they are simply not used (0); cure_system = "other"
pkg = m["cure_system"].isna() & m["other_curative_phr"].notna()
for c in ["coagent_phr", "peroxide_phr", "nitrile_curative_phr"]:
    m.loc[pkg, c] = m.loc[pkg, c].fillna(0.0)
m.loc[pkg, "cure_system"] = "other"
say(f"rows with unspecified cure chemistry, curative total in other_curative_phr: {int(pkg.sum())}")
# schema: 0 = ingredient absent, empty = amount genuinely unknown -> such rows cannot be modelled
unk = m[PHR[1:]].isna().any(axis=1)
for _, r in m[unk].iterrows():
    miss = [c for c in PHR[1:] if pd.isna(r[c])]
    say(f"  unknown amount ({', '.join(miss)}): {r['source_id']} {r['example_label']} -> excluded")
say(f"rows excluded for unknown ingredient amounts: {int(unk.sum())}")
m = m[~unk].copy()
n0 = len(m)
m = m[m["polymer_type"].isin(["FFKM", "FKM", "FEPM"])]
say(f"excluded blends / non-fluoro polymers (polymer_type 'other'): {n0 - len(m)}")

# 3b) property-definition consistency rules (documented in the report)
#   - US10723872B2 hardness was measured with a micro-hardness tester (Shore M-type) -> not Shore A
micro = m["source_id"].eq("US10723872B2") & m["hardness_shoreA"].notna()
say(f"hardness blanked (micro-hardness, not Shore A): {int(micro.sum())}")
m.loc[micro, "hardness_shoreA"] = np.nan
#   - a 100 % modulus cannot exist if elongation at break < 100 % -> elongation is a misprint
bad_el = m["elongation_pct"].lt(100) & m["m100_MPa"].notna()
for _, r in m[bad_el].iterrows():
    say(f"  inconsistent elongation {r['elongation_pct']} with M100 reported: {r['source_id']} {r['example_label']} -> NaN")
m.loc[bad_el, "elongation_pct"] = np.nan
has_prop = m[["hardness_shoreA", "tensile_MPa", "elongation_pct", "m100_MPa",
              "compression_set_pct"]].notna().any(axis=1)
m = m[has_prop].copy()

# 4) cross-document duplicates (same formulation AND same properties, e.g. patent families)
key = m[PHR + ["polymer_type", "cure_system"] + PROPS[:5]].round(3).astype(str).agg("|".join, axis=1)
fam_dup = key.duplicated(keep="first")
for _, r in m[fam_dup].iterrows():
    say(f"  family duplicate dropped: {r['source_id']} {r['example_label']}")
m = m[~fam_dup].copy()
m.insert(0, "row_id", [f"G{i + 1:03d}" for i in range(len(m))])
m.to_csv(os.path.join(ROOT, "data", "gasket_dataset_clean.csv"), index=False, encoding="utf-8-sig")

say(f"clean modelling rows: {len(m)}  sources: {m['source_id'].nunique()}")
say(m["polymer_type"].value_counts().to_string())
say(m["cure_system"].value_counts().to_string())
say("non-null property counts:")
say(m[PROPS].notna().sum().to_string())
open(os.path.join(ROOT, "data", "cleaning_log.txt"), "w", encoding="utf-8").write("\n".join(log))
