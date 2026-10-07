"""Core utilities: feature engineering, GP model construction, cross-validation,
and a small Bayesian-optimisation engine (GP surrogate + Expected Improvement).

Everything is plain scikit-learn / numpy so that every hyperparameter is explicit
and can be documented in the report.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    RBF, ConstantKernel, DotProduct, Matern, RationalQuadratic, WhiteKernel,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", message=".*lbfgs.*")

# --------------------------------------------------------------------------
# Feature definitions
# --------------------------------------------------------------------------
PHR_COLS = [
    "carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr",
    "titanium_oxide_phr", "fluororesin_phr", "other_inorganic_filler_phr",
    "organic_additive_phr", "coagent_phr", "peroxide_phr", "nitrile_curative_phr",
    "other_curative_phr", "acid_acceptor_phr", "processing_aid_phr",
]
FILLER_COLS = [
    "carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr",
    "titanium_oxide_phr", "fluororesin_phr", "other_inorganic_filler_phr",
    "organic_additive_phr",
]
WHITE_INORG = ["silica_phr", "alumina_phr", "barium_sulfate_phr",
               "titanium_oxide_phr", "other_inorganic_filler_phr"]
TARGETS = {
    "hardness_shoreA": "Hardness (Shore A)",
    "tensile_MPa": "Tensile strength (MPa)",
    "elongation_pct": "Elongation at break (%)",
    "m100_MPa": "100% modulus (MPa)",
    "compression_set_pct": "Compression set (%)",
}


CURE6 = ["peroxide", "nitrile_triazine", "nitrile_bisaminophenol", "nitrile_organotin",
         "nitrile_other", "bisphenol"]


def cure_group(s: str) -> str:
    s = str(s).lower()
    if s.startswith("peroxide"):
        return "peroxide"
    if s.startswith("nitrile"):
        return "nitrile"
    return "other"


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["total_filler_phr"] = df[FILLER_COLS].sum(axis=1)
    df["white_inorganic_phr"] = df[WHITE_INORG].sum(axis=1)
    df["total_curative_phr"] = df[["coagent_phr", "peroxide_phr",
                                   "nitrile_curative_phr", "other_curative_phr"]].sum(axis=1)
    df["cure_group"] = df["cure_system"].map(cure_group)
    df["is_FFKM"] = (df["polymer_type"] == "FFKM").astype(float)
    df["cure_peroxide"] = (df["cure_group"] == "peroxide").astype(float)
    df["cure_nitrile"] = (df["cure_group"] == "nitrile").astype(float)
    for cs in CURE6:
        df[f"cure_{cs}"] = (df["cure_system"] == cs).astype(float)
    # compression-set test temperature / duration parsed from the condition text
    cond = df["cs_condition"].fillna("").astype(str) if "cs_condition" in df else pd.Series("", index=df.index)
    m = cond.str.extract(r"(\d{3})\s*C\s*x\s*(\d+)\s*h", expand=True)
    df["cs_temp_C"] = pd.to_numeric(m[0], errors="coerce")
    df["cs_time_h"] = pd.to_numeric(m[1], errors="coerce")
    return df


FEATURE_SETS = {
    # every individual ingredient + polymer/cure indicators
    "full": PHR_COLS + ["is_FFKM", "cure_peroxide", "cure_nitrile"],
    # full + aggregate descriptors (total filler loading, total curative)
    "full_agg": PHR_COLS + ["total_filler_phr", "total_curative_phr",
                            "is_FFKM", "cure_peroxide", "cure_nitrile"],
    # full + detailed cure-chemistry indicators (6 cure systems instead of 2 groups)
    "full_cure6": PHR_COLS + ["is_FFKM"] + [f"cure_{c}" for c in CURE6],
    # domain-grouped compact descriptor set (fewer dimensions)
    "compact": ["carbon_black_phr", "white_inorganic_phr", "fluororesin_phr",
                "organic_additive_phr", "coagent_phr", "peroxide_phr",
                "nitrile_curative_phr", "other_curative_phr", "acid_acceptor_phr",
                "total_filler_phr", "is_FFKM", "cure_peroxide", "cure_nitrile"],
}


CS_TIME_RANGE = (60, 100)   # keep 70-96 h tests; long-term (336 h) tests are excluded


def target_rows(df: pd.DataFrame, target: str) -> pd.DataFrame:
    sub = df.dropna(subset=[target])
    if target == "compression_set_pct":
        lo, hi = CS_TIME_RANGE
        sub = sub[sub["cs_temp_C"].notna() & sub["cs_time_h"].between(lo, hi)]
    return sub


def get_xy(df: pd.DataFrame, target: str, feature_set: str):
    cols = list(FEATURE_SETS[feature_set])
    if target == "compression_set_pct":
        cols = cols + ["cs_temp_C"]      # test temperature is a required covariate for CS
    sub = target_rows(df, target)
    X = sub[cols].astype(float)
    # drop constant columns (they carry no information for this target)
    keep = [c for c in cols if X[c].nunique() > 1]
    return X[keep].values, sub[target].astype(float).values, keep, sub


# --------------------------------------------------------------------------
# GP model configuration
# --------------------------------------------------------------------------
@dataclass
class GPConfig:
    kernel: str = "matern52"        # rbf | matern12 | matern32 | matern52 | rq
    ard: bool = True                # anisotropic (one length-scale per feature)
    linear: bool = False            # add ConstantKernel*DotProduct trend term
    x_transform: str = "log1p"      # std | log1p  (log1p is applied before scaling)
    y_transform: str = "none"       # none | log
    feature_set: str = "full"
    ls_init: float = 0.0            # log10 of initial length-scale (in std units)
    noise_init: float = -1.0        # log10 of initial WhiteKernel noise (normalised y)
    noise_floor: float = -4.0       # log10 lower bound for WhiteKernel noise
    n_restarts: int = 3

    def as_dict(self):
        return dict(self.__dict__)


def build_kernel(cfg: GPConfig, n_features: int):
    ls0 = 10.0 ** cfg.ls_init
    ard = cfg.ard and cfg.kernel != "rq"   # sklearn RQ only supports isotropic l
    ls = np.full(n_features, ls0) if ard else ls0
    lsb = (1e-2, 1e3)
    if cfg.kernel == "rbf":
        base = RBF(length_scale=ls, length_scale_bounds=lsb)
    elif cfg.kernel == "matern12":
        base = Matern(length_scale=ls, length_scale_bounds=lsb, nu=0.5)
    elif cfg.kernel == "matern32":
        base = Matern(length_scale=ls, length_scale_bounds=lsb, nu=1.5)
    elif cfg.kernel == "matern52":
        base = Matern(length_scale=ls, length_scale_bounds=lsb, nu=2.5)
    elif cfg.kernel == "rq":
        base = RationalQuadratic(length_scale=ls0, alpha=1.0,
                                 length_scale_bounds=lsb, alpha_bounds=(1e-2, 1e3))
    else:
        raise ValueError(cfg.kernel)
    k = ConstantKernel(1.0, (1e-3, 1e3)) * base
    if cfg.linear:
        k = k + ConstantKernel(0.1, (1e-4, 1e2)) * DotProduct(sigma_0=1.0, sigma_0_bounds=(1e-3, 1e2))
    k = k + WhiteKernel(noise_level=10.0 ** cfg.noise_init,
                        noise_level_bounds=(10.0 ** cfg.noise_floor, 1e1))
    return k


LBFGS_MAXITER = 300


def lbfgs_capped(obj_func, initial_theta, bounds):
    """L-BFGS-B on the negative log-marginal-likelihood with an iteration cap
    (sklearn's default has none; ARD kernels otherwise dominate run time)."""
    from scipy.optimize import minimize
    r = minimize(obj_func, initial_theta, method="L-BFGS-B", jac=True, bounds=bounds,
                 options={"maxiter": LBFGS_MAXITER})
    return r.x, r.fun


class GPModel:
    """Pre-processing + GaussianProcessRegressor wrapped together."""

    def __init__(self, cfg: GPConfig, random_state: int = 0):
        self.cfg = cfg
        self.random_state = random_state

    def _tx(self, X, fit=False):
        Z = np.log1p(np.clip(X, 0, None)) if self.cfg.x_transform == "log1p" else X
        if fit:
            self.scaler = StandardScaler().fit(Z)
        return self.scaler.transform(Z)

    def fit(self, X, y):
        Z = self._tx(X, fit=True)
        yt = np.log(y) if self.cfg.y_transform == "log" else y
        self.gp = GaussianProcessRegressor(
            kernel=build_kernel(self.cfg, Z.shape[1]), normalize_y=True, optimizer=lbfgs_capped,
            n_restarts_optimizer=self.cfg.n_restarts, random_state=self.random_state)
        self.gp.fit(Z, yt)
        return self

    def predict(self, X, return_std=False):
        Z = self._tx(X)
        mu, sd = self.gp.predict(Z, return_std=True)
        if self.cfg.y_transform == "log":
            # log-normal back-transform: median and delta-method std
            m = np.exp(mu)
            s = m * sd
            return (m, s) if return_std else m
        return (mu, sd) if return_std else mu


def metrics(y, p, s=None):
    out = {
        "R2": r2_score(y, p),
        "RMSE": float(np.sqrt(mean_squared_error(y, p))),
        "MAE": mean_absolute_error(y, p),
    }
    if s is not None:
        z = np.abs(y - p) / np.maximum(s, 1e-12)
        out["cov95"] = float(np.mean(z <= 1.96))
        out["NLPD"] = float(np.mean(0.5 * np.log(2 * np.pi * s ** 2) + 0.5 * ((y - p) / s) ** 2))
    return out


def _fit_fold(cfg, X, y, tr, te, seed):
    m = GPModel(cfg, random_state=seed).fit(X[tr], y[tr])
    p, s = m.predict(X[te], return_std=True)
    return te, p, s


N_JOBS = int(__import__('os').environ.get('N_JOBS', 8))


def cv_eval(cfg: GPConfig, X, y, n_splits=5, repeats=(0, 1), groups=None, n_jobs=None):
    """Out-of-fold evaluation, repeated over several shuffles (folds run in parallel).
    Returns mean metrics over repeats and the OOF predictions of the first repeat."""
    from joblib import Parallel, delayed
    if groups is not None:
        repeats = (0,)
    tasks = []
    for r in repeats:
        if groups is None:
            splits = KFold(n_splits, shuffle=True, random_state=1000 + r).split(X)
        else:
            splits = GroupKFold(n_splits).split(X, y, groups)
        tasks += [(r, tr, te) for tr, te in splits]
    res = Parallel(n_jobs=n_jobs or N_JOBS)(delayed(_fit_fold)(cfg, X, y, tr, te, r) for r, tr, te in tasks)
    allm, oof0 = [], None
    for r in repeats:
        P, S = np.zeros_like(y, dtype=float), np.zeros_like(y, dtype=float)
        for (rr, _, _), (te, p, s) in zip(tasks, res):
            if rr == r:
                P[te], S[te] = p, s
        allm.append(metrics(y, P, S))
        if oof0 is None:
            oof0 = (P.copy(), S.copy())
    mean = {k: float(np.mean([m[k] for m in allm])) for k in allm[0]}
    mean["R2_std"] = float(np.std([m["R2"] for m in allm]))
    return mean, oof0


# --------------------------------------------------------------------------
# Bayesian optimisation engine (mixed categorical / integer / real space)
# --------------------------------------------------------------------------
@dataclass
class Dim:
    name: str
    kind: str                     # cat | real | int
    choices: list = field(default_factory=list)
    low: float = 0.0
    high: float = 1.0


class BayesOpt:
    """Maximise f(config) with a GP surrogate (Matern 5/2, ARD) and Expected Improvement.

    Encoding: categorical -> one-hot, real/int -> scaled to [0, 1].
    Acquisition maximisation: 3000 random candidates + 1000 local mutations of the
    incumbent; the candidate with the largest EI is evaluated next.
    """

    def __init__(self, dims, seed=0, n_init=10, xi=0.01):
        self.dims, self.rng, self.n_init, self.xi = dims, np.random.default_rng(seed), n_init, xi
        self.X, self.y, self.configs = [], [], []

    def sample(self):
        c = {}
        for d in self.dims:
            if d.kind == "cat":
                c[d.name] = d.choices[self.rng.integers(len(d.choices))]
            elif d.kind == "int":
                c[d.name] = int(self.rng.integers(d.low, d.high + 1))
            else:
                c[d.name] = float(self.rng.uniform(d.low, d.high))
        return c

    def mutate(self, c):
        c = dict(c)
        d = self.dims[self.rng.integers(len(self.dims))]
        if d.kind == "cat":
            c[d.name] = d.choices[self.rng.integers(len(d.choices))]
        elif d.kind == "int":
            c[d.name] = int(np.clip(c[d.name] + self.rng.integers(-2, 3), d.low, d.high))
        else:
            c[d.name] = float(np.clip(c[d.name] + self.rng.normal(0, 0.15 * (d.high - d.low)),
                                      d.low, d.high))
        return c

    def encode(self, c):
        v = []
        for d in self.dims:
            if d.kind == "cat":
                v += [1.0 if c[d.name] == ch else 0.0 for ch in d.choices]
            else:
                v.append((c[d.name] - d.low) / (d.high - d.low))
        return np.array(v)

    def suggest(self):
        if len(self.y) < self.n_init:
            return self.sample()
        X, y = np.array(self.X), np.array(self.y)
        k = (ConstantKernel(1.0, (1e-3, 1e3)) *
             Matern(length_scale=np.ones(X.shape[1]), length_scale_bounds=(1e-2, 1e2), nu=2.5)
             + WhiteKernel(1e-3, (1e-6, 1e-1)))
        sur = GaussianProcessRegressor(k, normalize_y=True, n_restarts_optimizer=3,
                                       random_state=int(self.rng.integers(1e6))).fit(X, y)
        best = self.configs[int(np.argmax(y))]
        cands = [self.sample() for _ in range(3000)] + [self.mutate(best) for _ in range(1000)]
        C = np.array([self.encode(c) for c in cands])
        mu, sd = sur.predict(C, return_std=True)
        imp = mu - y.max() - self.xi
        z = imp / np.maximum(sd, 1e-9)
        ei = imp * norm.cdf(z) + sd * norm.pdf(z)
        # never re-evaluate an identical encoded point
        seen = {tuple(np.round(x, 6)) for x in self.X}
        for i in np.argsort(-ei):
            if tuple(np.round(C[i], 6)) not in seen:
                return cands[i]
        return cands[int(np.argmax(ei))]

    def tell(self, c, val):
        self.configs.append(c)
        self.X.append(self.encode(c))
        self.y.append(val)


def expected_improvement(mu, sd, best, xi=0.01, maximize=True):
    imp = (mu - best - xi) if maximize else (best - mu - xi)
    z = imp / np.maximum(sd, 1e-9)
    return imp * norm.cdf(z) + sd * norm.pdf(z)
