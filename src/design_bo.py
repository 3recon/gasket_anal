"""Post-analysis and formulation-level Bayesian optimisation.

Exp-5  Retrospective (pool-based) BO benchmark: the dataset is treated as a pool of
       candidate formulations whose properties are hidden. Starting from 5 random
       "experiments", each strategy chooses the next formulation to "test":
         - BO-EI     : GP (best config of the target) + Expected Improvement
         - Greedy    : GP posterior mean only (pure exploitation)
         - Random    : random order
       Repeated 30 times; we record best-so-far and the number of experiments needed
       to reach the top-5 % formulation.
Exp-6  Inverse design: GP models (fitted on all data) for hardness / tensile / elongation
       (+ compression set when the model is usable) propose new FFKM formulations that
       maximise tensile strength under specification constraints via constrained EI.
Also : out-of-fold permutation importance and partial-dependence curves for each target.

Outputs: outputs/pool_bo.json, outputs/recommendations.csv, outputs/importance.json,
         outputs/pdp.json
"""
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import norm
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gp_core import (FEATURE_SETS, PHR_COLS, TARGETS, GPConfig, GPModel, add_derived,
                     expected_improvement, get_xy, target_rows)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OUT_DIR", os.path.join(ROOT, "outputs"))
df = add_derived(pd.read_csv(os.environ.get(
    "DATA_CSV", os.path.join(ROOT, "data", "gasket_dataset_clean.csv"))))
res = json.load(open(os.path.join(OUT, "results.json")))


def cfg_of(t, restarts=2):
    c = GPConfig(**res[t]["best_config"])
    c.n_restarts = restarts
    return c


def featurize(frame):
    """Recompute derived columns for a frame of raw phr formulations."""
    return add_derived(frame)


# ------------------------------------------------------------------ importance
def _perm_fold(cfg, X, y, tr, te, n_rep, seed):
    rng = np.random.default_rng(seed)
    m = GPModel(cfg).fit(X[tr], y[tr])
    base = r2_score(y[te], m.predict(X[te]))
    out = np.zeros((X.shape[1], n_rep))
    for j in range(X.shape[1]):
        for k in range(n_rep):
            Xp = X[te].copy()
            Xp[:, j] = rng.choice(X[:, j], len(te))   # draw from the marginal distribution
            out[j, k] = base - r2_score(y[te], m.predict(Xp))
    return out


def perm_importance(t, n_rep=5):
    """Out-of-fold permutation importance (5-fold x 2 shuffles, folds run in parallel)."""
    cfg = cfg_of(t, 3)
    X, y, cols, _ = get_xy(df, t, cfg.feature_set)
    tasks = [(tr, te, 100 * r + i) for r in range(2)
             for i, (tr, te) in enumerate(KFold(5, shuffle=True, random_state=1000 + r).split(X))]
    res_ = Parallel(n_jobs=8)(delayed(_perm_fold)(cfg, X, y, tr, te, n_rep, sd) for tr, te, sd in tasks)
    D = np.concatenate(res_, axis=1)
    return {c: float(D[j].mean()) for j, c in enumerate(cols)}


def pdp(t, features, grid=25):
    """Partial dependence with GP uncertainty: average prediction over the data when one
    feature is set to each grid value (derived columns recomputed). One model per target."""
    cfg = cfg_of(t, 3)
    X, y, cols, sub = get_xy(df, t, cfg.feature_set)
    m = GPModel(cfg).fit(X, y)
    out = {}
    for feature in features:
        hi = float(np.percentile(df[feature], 97))
        xs = np.linspace(0, max(hi, 1.0), grid)
        mus, sds = [], []
        for v in xs:
            b = sub.copy()
            b[feature] = v
            b = featurize(b)
            mu, sd = m.predict(b[cols].astype(float).values, return_std=True)
            mus.append(float(mu.mean()))
            sds.append(float(np.sqrt(np.mean(sd ** 2))))
        out[feature] = {"x": xs.tolist(), "mu": mus, "sd": sds}
    return out


# ------------------------------------------------------------------ pool BO
def pool_run(t, maximize, seed, strategy, n_init=5, budget=35):
    cfg = cfg_of(t, 1)
    X, y, cols, _ = get_xy(df, t, cfg.feature_set)
    rng = np.random.default_rng(seed)
    n = len(y)
    obs = list(rng.choice(n, n_init, replace=False))
    order = list(rng.permutation([i for i in range(n) if i not in obs]))
    sign = 1 if maximize else -1
    curve = [float(sign * max(sign * y[obs]))]
    for _ in range(budget):
        rest = [i for i in range(n) if i not in obs]
        if strategy == "random":
            nxt = [i for i in order if i not in obs][0]
        else:
            m = GPModel(cfg, random_state=seed).fit(X[obs], y[obs])
            mu, sd = m.predict(X[rest], return_std=True)
            if strategy == "greedy":
                nxt = rest[int(np.argmax(sign * mu))]
            else:
                best = float(sign * max(sign * y[obs]))
                ei = expected_improvement(mu, sd, best, xi=0.01 * np.std(y), maximize=maximize)
                nxt = rest[int(np.argmax(ei))]
        obs.append(nxt)
        curve.append(float(sign * max(sign * y[obs])))
    return curve


def pool_bo(t, maximize):
    y = target_rows(df, t)[t].values
    thr = np.percentile(y, 95) if maximize else np.percentile(y, 5)
    out = {"target": t, "maximize": maximize, "pool_size": int(len(y)),
           "global_best": float(y.max() if maximize else y.min()), "top5_threshold": float(thr)}
    for s in ["bo_ei", "greedy", "random"]:
        curves = Parallel(n_jobs=8)(delayed(pool_run)(t, maximize, seed, s) for seed in range(30))
        C = np.array(curves)
        hit = [(np.argmax((c >= thr) if maximize else (c <= thr)) if np.any((c >= thr) if maximize else (c <= thr))
                else np.nan) for c in C]
        out[s] = {"mean_curve": C.mean(0).tolist(), "p25": np.percentile(C, 25, 0).tolist(),
                  "p75": np.percentile(C, 75, 0).tolist(),
                  "exp_to_top5_mean": float(np.nanmean(hit)) if not np.all(np.isnan(hit)) else None,
                  "success_rate_top5": float(np.mean(~np.isnan(hit)))}
        print(f"  pool-BO {t} {s:7s}: reached top-5% in {out[s]['success_rate_top5']*100:.0f}% runs, "
              f"mean extra experiments {out[s]['exp_to_top5_mean']}")
    return out


# ------------------------------------------------------------------ inverse design
SPEC = {"hardness_shoreA": (70.0, 80.0), "elongation_pct": (150.0, None),
        "compression_set_pct": (None, 30.0)}
# practical seal-compound design space (domain constraint, fixed before looking at candidates):
# elastomer/fluoroplastic blends with >60 phr filler are a different material class
PRACTICAL = {"total_filler_phr": 60.0, "fluororesin_phr": 50.0}


def inverse_design(n_cand=30000, top=10):
    ff = df[df["polymer_type"] == "FFKM"]
    cure = ff["cure_group"].value_counts().idxmax()
    pool = ff[ff["cure_group"] == cure].reset_index(drop=True)
    rng = np.random.default_rng(7)
    models = {}
    for t in ["tensile_MPa", "hardness_shoreA", "elongation_pct", "compression_set_pct"]:
        # include a property model only if its development-set CV R2 (5x5) is >= 0.5
        if t in res and (t == "tensile_MPa" or res[t]["best_cv"]["R2"] >= 0.5):
            cfg = cfg_of(t, 5)
            X, y, cols, _ = get_xy(df, t, cfg.feature_set)
            models[t] = (GPModel(cfg).fit(X, y), cols)
    # candidate generator: perturb real formulations of the chosen family (stays on-manifold)
    fill = ["carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr",
            "titanium_oxide_phr", "fluororesin_phr", "other_inorganic_filler_phr"]
    maxv = {c: float(pool[c].max()) for c in PHR_COLS}
    parents = pool.sample(n_cand, replace=True, random_state=1).reset_index(drop=True)
    C = parents.copy()
    for c in PHR_COLS:
        mult = np.exp(rng.normal(0, 0.35, n_cand))
        C[c] = np.clip(C[c] * mult, 0, maxv[c])
    # with prob 0.5 add a second filler drawn from the observed range of that filler
    add = rng.random(n_cand) < 0.5
    which = rng.choice(fill, n_cand)
    for c in fill:
        sel = add & (which == c) & (maxv[c] > 0)
        C.loc[sel, c] = C.loc[sel, c] + rng.uniform(0, maxv[c], sel.sum()) * 0.5
        C[c] = np.clip(C[c], 0, maxv[c])
    C = featurize(C)
    for c, mx in PRACTICAL.items():
        C = C[C[c] <= mx]
    C = C.reset_index(drop=True)
    n_cand = len(C)
    C["cs_temp_C"] = 200.0          # CS constraint is evaluated at a 200 C test
    pred = {}
    for t, (m, cols) in models.items():
        mu, sd = m.predict(C[cols].astype(float).values, return_std=True)
        pred[t] = (mu, sd)
    # feasibility probability under the GP posteriors: P(lo <= y <= hi)
    pf = np.ones(n_cand)
    for t, (lo, hi) in SPEC.items():
        if t not in pred:
            continue
        mu, sd = pred[t]
        p_hi = norm.cdf((hi - mu) / sd) if hi is not None else 1.0
        p_lo = norm.cdf((lo - mu) / sd) if lo is not None else 0.0
        pf *= np.clip(p_hi - p_lo, 0, 1)
    # incumbent: best observed tensile among formulations meeting the measured spec
    # (hardness / elongation must be measured; CS is checked only where tested at ~200 C)
    obs = df[(df["polymer_type"] == "FFKM") & (df["cure_group"] == cure)].dropna(subset=["tensile_MPa"])
    ok = np.ones(len(obs), bool)
    for t, (lo, hi) in SPEC.items():
        if t not in pred:
            continue
        v = obs[t].values.astype(float)
        if t == "compression_set_pct":
            at200 = obs["cs_temp_C"].between(195, 205).values
            v = np.where(at200, v, np.nan)
            ok &= np.isnan(v) | (((v >= lo) if lo is not None else True) & ((v <= hi) if hi is not None else True))
        else:
            ok &= ~np.isnan(v)
            if lo is not None:
                ok &= np.nan_to_num(v, nan=-1e9) >= lo
            if hi is not None:
                ok &= np.nan_to_num(v, nan=1e9) <= hi
    best_obs = float(obs["tensile_MPa"][ok].max()) if ok.any() else float(obs["tensile_MPa"].median())
    mu_t, sd_t = pred["tensile_MPa"]
    ei = expected_improvement(mu_t, sd_t, best_obs, xi=0.01)
    score = ei * pf
    C["EI_tensile"], C["P_feasible"], C["cEI"] = ei, pf, score
    for t, (mu, sd) in pred.items():
        C[f"pred_{t}"], C[f"std_{t}"] = mu, sd
    # pick top candidates with diversity (min distance in log1p-phr space)
    Z = np.log1p(C[PHR_COLS].values)
    chosen = []
    for i in np.argsort(-score):
        if all(np.linalg.norm(Z[i] - Z[j]) > 0.8 for j in chosen):
            chosen.append(i)
        if len(chosen) == top:
            break
    rec = C.iloc[chosen].copy()
    # nearest real formulation (novelty check)
    Zp = np.log1p(df[PHR_COLS].values)
    nn = [int(np.argmin(np.linalg.norm(Zp - Z[i], axis=1))) for i in chosen]
    rec["nearest_example"] = [f"{df.iloc[j]['source_id']} {df.iloc[j]['example_label']}" for j in nn]
    rec["dist_to_nearest"] = [float(np.min(np.linalg.norm(Zp - Z[i], axis=1))) for i in chosen]
    rec.insert(0, "rank", range(1, len(rec) + 1))
    keep = (["rank", "polymer_type", "cure_system"] + PHR_COLS + ["total_filler_phr"] +
            [c for c in rec.columns if c.startswith(("pred_", "std_"))] +
            ["EI_tensile", "P_feasible", "cEI", "nearest_example", "dist_to_nearest"])
    rec[keep].to_csv(os.path.join(OUT, "recommendations.csv"), index=False, encoding="utf-8-sig")
    info = {"family": f"FFKM / {cure}", "n_family_rows": int(len(pool)), "spec": SPEC, "practical": PRACTICAL,
            "n_generated": 30000,
            "models_used": list(models), "incumbent_tensile": best_obs, "n_candidates": n_cand,
            "n_feasible_obs": int(ok.sum())}
    print("inverse design:", info)
    return info


if __name__ == "__main__" and sys.argv[1:] == ["design"]:
    info = inverse_design()
    json.dump(info, open(os.path.join(OUT, "inverse_design.json"), "w"), indent=1)
    sys.exit(0)

if __name__ == "__main__":
    out = {}
    imp, pd_out = {}, {}
    for t in res:
        print("importance", t)
        imp[t] = perm_importance(t)
        top2 = sorted(imp[t], key=lambda c: -imp[t][c])
        feats = [c for c in top2 if c.endswith("_phr") and c in PHR_COLS][:3]
        pd_out[t] = pdp(t, feats)
    json.dump(imp, open(os.path.join(OUT, "importance.json"), "w"), indent=1)
    json.dump(pd_out, open(os.path.join(OUT, "pdp.json"), "w"), indent=1)
    pool = {}
    if "tensile_MPa" in res:
        pool["tensile_MPa"] = pool_bo("tensile_MPa", True)
    if "compression_set_pct" in res:
        pool["compression_set_pct"] = pool_bo("compression_set_pct", False)
    if "hardness_shoreA" in res:
        pool["hardness_shoreA"] = pool_bo("hardness_shoreA", True)
    json.dump(pool, open(os.path.join(OUT, "pool_bo.json"), "w"), indent=1)
    info = inverse_design()
    json.dump(info, open(os.path.join(OUT, "inverse_design.json"), "w"), indent=1)
    print("DONE")
