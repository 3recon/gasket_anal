"""Collect every number quoted in the Word report / PPT into outputs/report_data.json."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gp_core import TARGETS, add_derived, target_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OUT_DIR", os.path.join(ROOT, "outputs"))
raw = pd.read_csv(os.path.join(ROOT, "data", "gasket_dataset_raw.csv"))
mdl = add_derived(pd.read_csv(os.path.join(ROOT, "data", "gasket_dataset_clean.csv")))
res = json.load(open(os.path.join(OUT, "results.json")))
trials = pd.read_csv(os.path.join(OUT, "trials.csv"))
log = open(os.path.join(ROOT, "data", "cleaning_log.txt"), encoding="utf-8").read()

KOR = {"hardness_shoreA": "경도 (Shore A)", "tensile_MPa": "인장강도 (MPa)", "elongation_pct": "신율 (%)",
       "m100_MPa": "100% 모듈러스 (MPa)", "compression_set_pct": "압축영구줄음률 (%)"}
KOR_SHORT = {"hardness_shoreA": "경도", "tensile_MPa": "인장강도", "elongation_pct": "신율",
             "m100_MPa": "M100", "compression_set_pct": "압축영구줄음률"}
UNIT = {"hardness_shoreA": "Shore A", "tensile_MPa": "MPa", "elongation_pct": "%", "m100_MPa": "MPa",
        "compression_set_pct": "%p"}
FEAT_KOR = {
    "carbon_black_phr": "카본블랙", "silica_phr": "실리카", "alumina_phr": "알루미나",
    "barium_sulfate_phr": "황산바륨", "titanium_oxide_phr": "산화티탄", "fluororesin_phr": "불소수지",
    "other_inorganic_filler_phr": "기타 무기필러", "organic_additive_phr": "유기첨가제",
    "coagent_phr": "가교조제", "peroxide_phr": "과산화물", "nitrile_curative_phr": "니트릴 가교제",
    "other_curative_phr": "기타 가교제", "acid_acceptor_phr": "수산제",
    "processing_aid_phr": "가공조제", "total_filler_phr": "총 필러량", "white_inorganic_phr": "백색 무기필러",
    "total_curative_phr": "총 가교계", "is_FFKM": "FFKM 여부", "cure_peroxide": "과산화물 가교",
    "cure_nitrile": "니트릴 가교", "cs_temp_C": "CS 시험온도",
    "cure_nitrile_triazine": "트리아진 가교", "cure_nitrile_bisaminophenol": "비스아미노페놀 가교",
    "cure_nitrile_organotin": "유기주석 가교", "cure_nitrile_other": "기타 니트릴 가교", "cure_bisphenol": "비스페놀 가교", "cure_other": "기타 가교계"}
KERNEL_KOR = {"rbf": "RBF", "matern12": "Matérn ν=1/2", "matern32": "Matérn ν=3/2",
              "matern52": "Matérn ν=5/2", "rq": "Rational Quadratic"}
FS_KOR = {"full": "full (개별 성분 14 + 지표 3)", "full_agg": "full_agg (full + 총필러·총가교계)",
          "full_cure6": "full_cure6 (개별 성분 + 가교계 6종 지시변수)", "compact": "compact (그룹화 9 + 총필러 + 지표)"}


def f(x, d=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def cfg_text(c):
    k = KERNEL_KOR[c["kernel"]] + (" + ARD" if c["ard"] and c["kernel"] != "rq" else " (등방성)")
    if c["linear"]:
        k += " + 선형(DotProduct)"
    return k


def count(pattern):
    m = re.search(pattern, log)
    return int(m.group(1)) if m else 0


D = {"targets": list(res), "kor": KOR, "kor_short": KOR_SHORT, "unit": UNIT}
D["counts"] = {
    "raw_rows": int(len(raw)), "raw_sources": int(raw["source_id"].nunique()),
    "model_rows": int(len(mdl)), "model_sources": int(mdl["source_id"].nunique()),
    "excl_nonsemi": count(r"excluded non-semiconductor applications \([^)]*\): (\d+)"),
    "pkg_rule": count(r"curative total in other_curative_phr: (\d+)"),
    "excl_unknown": count(r"rows excluded for unknown ingredient amounts: (\d+)"),
    "excl_blend": count(r"polymer_type 'other'\): (\d+)"),
    "hard_blank": count(r"hardness blanked \(micro-hardness, not Shore A\): (\d+)"),
    "el_fix": len(re.findall(r"inconsistent elongation", log)),
    "fam_dup": len(re.findall(r"family duplicate dropped", log)),
    "ffkm": int((mdl["polymer_type"] == "FFKM").sum()), "fkm": int((mdl["polymer_type"] == "FKM").sum()),
    "cure_counts": mdl["cure_system"].value_counts().to_dict(),
    "n_trials_total": int(len(trials)), "n_trials_gp": int((trials["model"] == "GP").sum()),
}
by_batch = raw.groupby("batch").agg(n=("source_id", "size"), s=("source_id", "nunique")).to_dict("index")
D["counts"]["by_batch"] = by_batch

# sources table ------------------------------------------------------------------
src = raw.groupby("source_id").agg(assignee=("assignee", "first"), title=("title", "first"),
                                   n=("source_id", "size"), batch=("batch", "first"))
src["model"] = mdl.groupby("source_id").size()
src["model"] = src["model"].fillna(0).astype(int)
order = {"batch_daikin": 0, "batch_dupont3mgt": 1, "batch_japan": 2, "batch_krcn": 3}
src = src.reset_index().sort_values(["batch", "source_id"], key=lambda s: s.map(order) if s.name == "batch" else s)


def short_assignee(a):
    a = re.sub(r"\s*\(.*?\)", "", str(a))
    a = a.replace("Federal State Unitary Enterprise S V Lebedev Institute of Synthetic Rubber; ", "")
    return a[:42]


D["sources"] = [[r.source_id, short_assignee(r.assignee), str(r.title)[:80], int(r.n), int(r.model)]
                for r in src.itertuples()]
D["assignee_groups"] = {k: int(v) for k, v in mdl.assign(
    grp=mdl["source_id"].map(dict(zip(raw["source_id"], raw["batch"])))).groupby("grp").size().items()}

# property stats -----------------------------------------------------------------------
D["stats"] = {}
for t in TARGETS:
    v = target_rows(mdl, t)[t]
    D["stats"][t] = {"n": int(len(v)), "mean": float(v.mean()), "std": float(v.std()),
                     "min": float(v.min()), "max": float(v.max())}
feats = ["carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr", "titanium_oxide_phr",
         "fluororesin_phr", "other_inorganic_filler_phr", "organic_additive_phr", "coagent_phr",
         "peroxide_phr", "nitrile_curative_phr", "other_curative_phr", "acid_acceptor_phr",
         "total_filler_phr", "is_FFKM"]
D["corr"] = {}
for t in TARGETS:
    s = {fe: float(mdl[[fe, t]].dropna().corr(method="spearman").iloc[0, 1]) for fe in feats}
    s = {k: v for k, v in s.items() if not np.isnan(v)}
    D["corr"][t] = sorted(s.items(), key=lambda kv: -abs(kv[1]))[:4]
D["usage"] = {fe: int((mdl[fe] > 0).sum()) for fe in feats if fe.endswith("_phr")}
D["phr_max"] = {fe: float(mdl[fe].max()) for fe in feats if fe.endswith("_phr")}

# per-target results ------------------------------------------------------------------
imp = json.load(open(os.path.join(OUT, "importance.json"))) if os.path.exists(os.path.join(OUT, "importance.json")) else {}
D["res"] = {}
for t, R in res.items():
    c = R["best_config"]
    fp = R["final_params"]
    amp = next((v for k, v in fp.items() if k.endswith("constant_value")), None)
    noise = next((v for k, v in fp.items() if k.endswith("noise_level")), None)
    ls = next((v for k, v in fp.items() if k.endswith("length_scale")), None)
    rq_alpha = next((v for k, v in fp.items() if k.endswith("__alpha")), None)
    nu = next((v for k, v in fp.items() if k.endswith("__nu")), None)
    tr = trials[(trials["target"] == t)]
    bo = tr[tr["experiment"] == "Exp2_BO"]
    E = {
        "n_total": R["n_total"], "n_dev": R["n_dev"], "n_test": R["n_test"], "n_sources": R["n_sources"],
        "y_std": R["y_std"],
        "baselines_cv": {k: v["R2"] for k, v in R["baselines"].items()},
        "baselines_cv_rmse": {k: v["RMSE"] for k, v in R["baselines"].items()},
        "screen": [[KERNEL_KOR[k["kernel"]], "ARD" if k["ard"] else "등방성", f(k["R2"]), f(k["RMSE"], 2),
                    f(k["cov95"] * 100, 0) + "%", f(k["sec"], 1)] for k in R["kernel_screen"]],
        "screen_best": max(R["kernel_screen"], key=lambda k: k["R2"]),
        "bo_runs": [{"seed": b["seed"], "best": b["best_R2"], "iter": b["best_iter"] + 1,
                     "cfg": b["best_config"], "cfg_text": cfg_text(b["best_config"]),
                     "first_init_best": max(b["all_R2"][:8]), "curve": b["curve"]} for b in R["bo_runs"]],
        "bo_n": int(len(bo)), "bo_ard_share": float(bo["ard"].astype(str).eq("True").mean()) if len(bo) else 0,
        "bo_kernel_counts": bo["kernel"].value_counts().to_dict(),
        "robust": [{"cfg_text": cfg_text(r["config"]), "x": r["config"]["x_transform"], "y": r["config"]["y_transform"],
                    "fs": r["config"]["feature_set"], "search": r["search_R2"], "robust": r["R2"], "std": r["R2_std"],
                    "rmse": r["RMSE"], "cov": r["cov95"]} for r in R["robust"]],
        "best": c, "best_text": cfg_text(c), "best_cv": R["best_cv"], "test": R["test"],
        "test_baselines": {k: v["R2"] for k, v in R["test_baselines"].items()},
        "test_baselines_rmse": {k: v["RMSE"] for k, v in R["test_baselines"].items()},
        "lso": R["leave_source_out"], "final_kernel": R["final_kernel"], "lml": R["final_lml"],
        "amp": amp, "noise": noise, "ls": ls, "rq_alpha": rq_alpha, "nu": nu, "features": R["features"],
        "features_kor": [FEAT_KOR.get(x, x) for x in R["features"]],
        "ard": R.get("ard_length_scales"),
        "importance": sorted(((FEAT_KOR.get(k, k), v) for k, v in imp.get(t, {}).items()), key=lambda kv: -kv[1])[:6],
    }
    # applicability domain: test rows whose every input lies inside the dev-set range
    pr = pd.read_csv(os.path.join(OUT, f"pred_{t}.csv"))
    feats_t = R["features"]
    dv = mdl.set_index("row_id").loc[pr.loc[pr["set"] == "dev(OOF)", "row_id"], feats_t]
    te = pr[pr["set"] == "test"].copy()
    Xte = mdl.set_index("row_id").loc[te["row_id"], feats_t]
    inside = ((Xte >= dv.min() - 1e-9) & (Xte <= dv.max() + 1e-9)).all(axis=1).values
    from sklearn.metrics import r2_score, mean_squared_error
    E["ad_n_out"] = int((~inside).sum())
    E["ad_out_rows"] = [f"{r.source_id} {r.example_label}" for r in te[~inside].itertuples()]
    if inside.sum() > 3:
        yi, pi = te["y_true"].values[inside], te["y_pred"].values[inside]
        E["ad_r2_in"] = float(r2_score(yi, pi))
        E["ad_rmse_in"] = float(np.sqrt(mean_squared_error(yi, pi)))
    # noise fraction: WhiteKernel noise relative to total normalised variance
    if amp is not None and noise is not None:
        E["noise_frac"] = float(noise / (amp + noise))
    D["res"][t] = E

# hyperparameter sensitivity: median CV R2 per level over Exp-1 + Exp-2 trials
gp = trials[(trials["model"] == "GP") & trials["experiment"].isin(["Exp1_kernel_screen", "Exp2_BO"])].copy()
for c in ["ard", "linear"]:
    gp[c] = gp[c].astype(str)
HP = ["kernel", "ard", "linear", "x_transform", "y_transform", "feature_set"]
D["hp_effect"] = {}
for t in res:
    g = gp[gp["target"] == t]
    eff = {}
    for h in HP:
        med = g.groupby(h)["R2"].median()
        cnts = g.groupby(h).size()
        med = med[cnts >= 3]
        eff[h] = {"best": str(med.idxmax()), "worst": str(med.idxmin()), "range": float(med.max() - med.min()),
                  "levels": {str(k): float(v) for k, v in med.items()}}
    D["hp_effect"][t] = eff
    top = g.nlargest(10, "R2")
    D["res"][t]["top10"] = {h: top[h].astype(str).value_counts().to_dict() for h in HP}
    D["res"][t]["bo_min"] = float(g[g["experiment"] == "Exp2_BO"]["R2"].min())
    D["res"][t]["bo_median"] = float(g[g["experiment"] == "Exp2_BO"]["R2"].median())

for name in ["pool_bo", "inverse_design"]:
    p = os.path.join(OUT, f"{name}.json")
    D[name] = json.load(open(p)) if os.path.exists(p) else None
rp = os.path.join(OUT, "recommendations.csv")
if os.path.exists(rp):
    rec = pd.read_csv(rp)
    D["recs"] = rec.head(5).to_dict("records")
D["kernel_kor"], D["fs_kor"], D["feat_kor"] = KERNEL_KOR, FS_KOR, FEAT_KOR
json.dump(D, open(os.path.join(OUT, "report_data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("report_data.json written")
