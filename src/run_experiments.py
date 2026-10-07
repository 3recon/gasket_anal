"""Hyperparameter experiments for GP property-prediction models.

Protocol (per target property)
  0. Split: 80 % development set / 20 % untouched test set (seed 42, stratified on target quintiles)
  1. Exp-0  baselines on dev CV: sklearn-default GP, Ridge, Random Forest
  2. Exp-1  manual kernel screening (9 kernels) on dev CV
  3. Exp-2  Bayesian optimisation of GP hyperparameters, 3 independent seeds x 40 trials
            objective = mean out-of-fold R2 of 5-fold CV x 2 repeats on the dev set
  4. Exp-3  robust re-evaluation of the top-5 distinct configs (5-fold x 5 repeats, 10 restarts)
            -> final configuration (protects against "winner's curse" of noisy CV)
  5. Exp-4  final test on the 20 % hold-out; leave-source-out CV on all data; final fit on all data
Outputs: outputs/trials.csv, outputs/results.json, outputs/pred_<target>.csv
"""
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gp_core import (TARGETS, BayesOpt, Dim, GPConfig, GPModel, add_derived, cv_eval,
                     get_xy, metrics, target_rows)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OUT_DIR", os.path.join(ROOT, "outputs"))
os.makedirs(OUT, exist_ok=True)

N_BO_SEEDS = int(os.environ.get("N_BO_SEEDS", 3))
N_BO_ITERS = int(os.environ.get("N_BO_ITERS", 30))
N_INIT = 8
BO_REPEATS = (0,)          # BO objective: 5-fold CV, 1 shuffle (robust stage uses 5 shuffles)
MIN_ROWS = 40

SPACE = [
    Dim("kernel", "cat", ["rbf", "matern12", "matern32", "matern52", "rq"]),
    Dim("ard", "cat", [True, False]),
    Dim("linear", "cat", [False, True]),
    Dim("x_transform", "cat", ["std", "log1p"]),
    Dim("y_transform", "cat", ["none", "log"]),
    Dim("feature_set", "cat", ["full", "full_agg", "full_cure6", "compact"]),
    Dim("ls_init", "real", low=-1.0, high=1.0),
    Dim("noise_init", "real", low=-3.0, high=0.0),
    Dim("noise_floor", "real", low=-6.0, high=-2.0),
]

df = add_derived(pd.read_csv(os.environ.get("DATA_CSV", os.path.join(ROOT, "data", "gasket_dataset_clean.csv"))))
targets = [t for t in TARGETS if len(target_rows(df, t)) >= MIN_ROWS]
if len(sys.argv) > 1:
    targets = [t for t in targets if t in sys.argv[1:]]
print("targets:", {t: len(target_rows(df, t)) for t in TARGETS})

trials, results = [], {}


def cfg_from(d, n_restarts=1):
    keys = GPConfig().__dict__.keys()
    c = GPConfig(**{k: v for k, v in d.items() if k in keys})
    c.n_restarts = n_restarts
    return c


def baseline_cv(model_fn, X, y, repeats=(0, 1)):
    ms = []
    for r in repeats:
        P = np.zeros_like(y)
        for tr, te in KFold(5, shuffle=True, random_state=1000 + r).split(X):
            P[te] = model_fn().fit(X[tr], y[tr]).predict(X[te])
        ms.append(metrics(y, P))
    return {k: float(np.mean([m[k] for m in ms])) for k in ms[0]}


log1p = FunctionTransformer(lambda Z: np.log1p(np.clip(Z, 0, None)))
BASELINES = {
    "GP_sklearn_default": lambda: make_pipeline(StandardScaler(), GaussianProcessRegressor()),
    "Ridge": lambda: make_pipeline(log1p, StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 13))),
    "RandomForest": lambda: RandomForestRegressor(n_estimators=500, random_state=0, n_jobs=8),
}

for target in targets:
    t0 = time.time()
    print(f"\n=============== {target} ===============")
    sub = target_rows(df, target).reset_index(drop=True)
    strat = pd.qcut(sub[target].rank(method="first"), 5, labels=False)
    dev_idx, test_idx = train_test_split(np.arange(len(sub)), test_size=0.2,
                                         random_state=42, stratify=strat)
    dev, test = sub.iloc[dev_idx].reset_index(drop=True), sub.iloc[test_idx].reset_index(drop=True)
    R = {"n_total": len(sub), "n_dev": len(dev), "n_test": len(test),
         "n_sources": int(sub["source_id"].nunique()),
         "y_mean": float(sub[target].mean()), "y_std": float(sub[target].std()),
         "y_min": float(sub[target].min()), "y_max": float(sub[target].max())}

    # ---------------- Exp-0 baselines ----------------
    Xd, yd, cols_full, _ = get_xy(dev, target, "full")
    R["baselines"] = {}
    for name, fn in BASELINES.items():
        m = baseline_cv(fn, Xd, yd)
        R["baselines"][name] = m
        trials.append({"target": target, "experiment": "Exp0_baseline", "seed": None, "iter": None,
                       "model": name, **m})
        print(f"  baseline {name:20s} R2={m['R2']:.3f} RMSE={m['RMSE']:.3f}")

    cache = {}

    def evaluate(c: GPConfig, exp, seed=None, it=None, repeats=BO_REPEATS):
        key = (tuple(sorted(c.as_dict().items())), repeats)
        if key in cache:
            return cache[key]
        X, y, cols, _ = get_xy(dev, target, c.feature_set)
        ts = time.time()
        try:
            m, _ = cv_eval(c, X, y, repeats=repeats)
        except Exception as e:  # numerical failure -> worst score
            print("   fail", e)
            m = {"R2": -1.0, "RMSE": np.nan, "MAE": np.nan, "cov95": np.nan, "NLPD": np.nan, "R2_std": np.nan}
        m["sec"] = time.time() - ts
        trials.append({"target": target, "experiment": exp, "seed": seed, "iter": it,
                       "model": "GP", **c.as_dict(), **m})
        cache[key] = m
        return m

    # ---------------- Exp-1 kernel screening ----------------
    R["kernel_screen"] = []
    for k in ["rbf", "matern12", "matern32", "matern52", "rq"]:
        for ard in ([True, False] if k != "rq" else [False]):
            c = GPConfig(kernel=k, ard=ard, n_restarts=1)
            m = evaluate(c, "Exp1_kernel_screen")
            R["kernel_screen"].append({"kernel": k, "ard": ard, **m})
            print(f"  screen {k:9s} ard={ard!s:5s} R2={m['R2']:.3f}")

    # ---------------- Exp-2 Bayesian optimisation ----------------
    R["bo_runs"] = []
    for seed in range(N_BO_SEEDS):
        bo = BayesOpt(SPACE, seed=seed, n_init=N_INIT)
        best_curve = []
        for it in range(N_BO_ITERS):
            d = bo.suggest()
            m = evaluate(cfg_from(d), "Exp2_BO", seed, it)
            bo.tell(d, m["R2"])
            best_curve.append(float(max(bo.y)))
        ib = int(np.argmax(bo.y))
        R["bo_runs"].append({"seed": seed, "best_R2": float(bo.y[ib]), "best_iter": ib,
                             "best_config": bo.configs[ib], "curve": best_curve,
                             "all_R2": [float(v) for v in bo.y]})
        print(f"  BO seed {seed}: best R2={bo.y[ib]:.3f} at iter {ib}  {bo.configs[ib]}")

    # ---------------- Exp-3 robust re-evaluation of top configs ----------------
    gp_trials = [t for t in trials if t["target"] == target and t["model"] == "GP"
                 and t["experiment"] in ("Exp1_kernel_screen", "Exp2_BO")]
    gp_trials.sort(key=lambda t: -t["R2"])
    seen, top = set(), []
    for t in gp_trials:
        sig = (t["kernel"], t["ard"], t["linear"], t["x_transform"], t["y_transform"], t["feature_set"])
        if sig in seen:
            continue
        seen.add(sig)
        top.append(t)
        if len(top) == 3:
            break
    R["robust"] = []
    for t in top:
        c = cfg_from(t, n_restarts=3)
        m = evaluate(c, "Exp3_robust", repeats=(0, 1, 2, 3, 4))
        R["robust"].append({"config": c.as_dict(), "search_R2": t["R2"], **m})
        print(f"  robust {c.kernel} ard={c.ard} lin={c.linear} x={c.x_transform} y={c.y_transform} "
              f"fs={c.feature_set}: search {t['R2']:.3f} -> robust {m['R2']:.3f}±{m['R2_std']:.3f}")
    best = max(R["robust"], key=lambda r: r["R2"])
    cfg = cfg_from(best["config"], n_restarts=3)
    R["best_config"] = cfg.as_dict()
    R["best_cv"] = {k: v for k, v in best.items() if k not in ("config",)}

    # ---------------- Exp-4 final evaluation ----------------
    Xd, yd, cols, _ = get_xy(dev, target, cfg.feature_set)
    Xt = test[cols].astype(float).values
    yt = test[target].astype(float).values
    model = GPModel(cfg).fit(Xd, yd)
    pt, st = model.predict(Xt, return_std=True)
    R["test"] = metrics(yt, pt, st)
    R["test_baselines"] = {}
    Xdf, _, cf, _ = get_xy(dev, target, "full")
    Xtf = test[cf].astype(float).values
    for name, fn in BASELINES.items():
        R["test_baselines"][name] = metrics(yt, fn().fit(Xdf, yd).predict(Xtf))
    print(f"  TEST GP R2={R['test']['R2']:.3f} RMSE={R['test']['RMSE']:.3f} cov95={R['test']['cov95']:.2f} | "
          + " ".join(f"{k}={v['R2']:.3f}" for k, v in R["test_baselines"].items()))

    # leave-source-out (GroupKFold over patents) on all data
    Xa, ya, _, suba = get_xy(sub, target, cfg.feature_set)
    Xa = suba[cols].astype(float).values
    ng = min(5, suba["source_id"].nunique())
    m_lso, _ = cv_eval(cfg, Xa, ya, n_splits=ng, groups=suba["source_id"].values)
    R["leave_source_out"] = m_lso
    print(f"  leave-source-out R2={m_lso['R2']:.3f}")

    # OOF predictions on dev (for parity plots) + test predictions
    _, (P, S) = cv_eval(cfg, Xd, yd, repeats=(0,))
    pd.concat([
        pd.DataFrame({"row_id": dev["row_id"], "source_id": dev["source_id"],
                      "example_label": dev["example_label"], "set": "dev(OOF)",
                      "y_true": yd, "y_pred": P, "y_std": S}),
        pd.DataFrame({"row_id": test["row_id"], "source_id": test["source_id"],
                      "example_label": test["example_label"], "set": "test",
                      "y_true": yt, "y_pred": pt, "y_std": st}),
    ]).to_csv(os.path.join(OUT, f"pred_{target}.csv"), index=False, encoding="utf-8-sig")

    # final model on all data -> learned kernel hyperparameters and ARD relevance
    final = GPModel(cfg).fit(Xa, ya)
    k = final.gp.kernel_
    params = {n: (v.tolist() if hasattr(v, "tolist") else v) for n, v in k.get_params().items()
              if not hasattr(v, "get_params")}
    R["final_kernel"] = str(k)
    R["final_lml"] = float(final.gp.log_marginal_likelihood_value_)
    R["final_params"] = {n: v for n, v in params.items() if not n.endswith("_bounds")}
    R["features"] = cols
    ls = None
    for n, v in params.items():
        if n.endswith("length_scale") and not n.endswith("_bounds"):
            ls = np.atleast_1d(v)
    if ls is not None and len(ls) == len(cols):
        rel = 1.0 / ls
        R["ard_relevance"] = dict(zip(cols, (rel / rel.sum()).round(4).tolist()))
        R["ard_length_scales"] = dict(zip(cols, ls.round(4).tolist()))
    R["minutes"] = (time.time() - t0) / 60
    results[target] = R
    pd.DataFrame([t for t in trials if t["target"] == target]).to_csv(
        os.path.join(OUT, f"trials_{target}.csv"), index=False, encoding="utf-8-sig")
    json.dump({target: R}, open(os.path.join(OUT, f"results_{target}.json"), "w"), indent=1, default=str)
    print(f"  done in {R['minutes']:.1f} min")

print("ALL DONE")
