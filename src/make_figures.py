"""Static figures (PNG, 200 dpi) for the Word report and the PPT deck."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gp_core import TARGETS, add_derived

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OUT_DIR", os.path.join(ROOT, "outputs"))
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

# reference palette (validated categorical order) + recessive ink
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9,
    "axes.edgecolor": "#b9b8b3", "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
    "axes.titlesize": 10, "axes.titlecolor": INK, "figure.facecolor": SURF,
    "axes.facecolor": SURF, "savefig.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False,
})
KOR = {"hardness_shoreA": "경도 (Shore A)", "tensile_MPa": "인장강도 (MPa)",
       "elongation_pct": "신율 (%)", "m100_MPa": "100% 모듈러스 (MPa)",
       "compression_set_pct": "압축영구줄음률 (%)"}
FEAT_KOR = {
    "carbon_black_phr": "카본블랙", "silica_phr": "실리카", "alumina_phr": "알루미나",
    "barium_sulfate_phr": "황산바륨", "titanium_oxide_phr": "산화티탄", "fluororesin_phr": "불소수지",
    "other_inorganic_filler_phr": "기타 무기필러", "organic_additive_phr": "유기첨가제",
    "coagent_phr": "가교조제(TAIC 등)", "peroxide_phr": "과산화물", "nitrile_curative_phr": "니트릴 가교제",
    "other_curative_phr": "기타 가교제", "acid_acceptor_phr": "수산제(MgO 등)",
    "processing_aid_phr": "가공조제", "total_filler_phr": "총 필러량", "white_inorganic_phr": "백색 무기필러",
    "total_curative_phr": "총 가교계", "is_FFKM": "FFKM 여부", "cure_peroxide": "과산화물 가교",
    "cure_nitrile": "니트릴 가교", "cs_temp_C": "CS 시험온도", "cure_nitrile_triazine": "트리아진 가교",
    "cure_nitrile_bisaminophenol": "비스아미노페놀 가교", "cure_nitrile_organotin": "유기주석 가교",
    "cure_nitrile_other": "기타 니트릴 가교", "cure_bisphenol": "비스페놀 가교", "cure_other": "기타 가교계"}

df = add_derived(pd.read_csv(os.path.join(ROOT, "data", "gasket_dataset_clean.csv")))
res = json.load(open(os.path.join(OUT, "results.json")))
trials = pd.read_csv(os.path.join(OUT, "trials.csv"))
targets = list(res)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)


# F1 data overview -----------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(10, 5.6))
for ax, t in zip(axes.flat, list(TARGETS)):
    v = df[t].dropna()
    ax.hist(v, bins=18, color=BLUE, edgecolor=SURF, linewidth=1.0)
    ax.set_title(f"{KOR[t]}  (n={len(v)})")
    ax.set_ylabel("건수")
ax = axes.flat[5]
cnt = df.groupby("polymer_type").size().reindex(["FFKM", "FKM", "FEPM"]).dropna()
cure = df["cure_group"].value_counts()
ax.barh(list(cnt.index) + [""] + [f"가교:{c}" for c in cure.index],
        list(cnt.values) + [0] + list(cure.values), color=[BLUE] * len(cnt) + [SURF] + [ORANGE] * len(cure),
        height=0.6)
ax.set_title("고무 종류 / 가교계별 데이터 수")
ax.invert_yaxis()
fig.tight_layout()
save(fig, "F1_data_overview.png")

# F2 Spearman correlation heatmap ------------------------------------------
feats = ["carbon_black_phr", "silica_phr", "alumina_phr", "barium_sulfate_phr", "titanium_oxide_phr",
         "fluororesin_phr", "other_inorganic_filler_phr", "organic_additive_phr", "coagent_phr",
         "peroxide_phr", "nitrile_curative_phr", "other_curative_phr", "acid_acceptor_phr",
         "total_filler_phr", "is_FFKM"]
C = np.array([[df[[f, t]].dropna().corr(method="spearman").iloc[0, 1] for t in TARGETS] for f in feats])
from matplotlib.colors import LinearSegmentedColormap
div = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#86b6ef", "#f0efec", "#f19a9a", "#b52b2b"])
fig, ax = plt.subplots(figsize=(6.4, 6.0))
im = ax.imshow(C, cmap=div, vmin=-0.8, vmax=0.8, aspect="auto")
ax.set_xticks(range(len(TARGETS)), [KOR[t] for t in TARGETS], rotation=30, ha="right")
ax.set_yticks(range(len(feats)), [FEAT_KOR[f] for f in feats])
ax.grid(False)
for i in range(len(feats)):
    for j in range(len(TARGETS)):
        if not np.isnan(C[i, j]):
            ax.text(j, i, f"{C[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(C[i, j]) > 0.5 else INK)
fig.colorbar(im, ax=ax, shrink=0.7, label="Spearman ρ")
ax.set_title("배합 성분 vs 물성 순위상관")
save(fig, "F2_correlation.png")

# F3 kernel screening heatmap ----------------------------------------------
labels = None
M = []
for t in targets:
    ks = res[t]["kernel_screen"]
    labels = [f"{k['kernel'].upper()}{' ARD' if k['ard'] else ''}" for k in ks]
    M.append([k["R2"] for k in ks])
M = np.array(M)
seq = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#5598e7", "#104281"])
fig, ax = plt.subplots(figsize=(8, 0.55 * len(targets) + 1.4))
im = ax.imshow(np.clip(M, 0, 1), cmap=seq, vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
ax.set_yticks(range(len(targets)), [KOR[t] for t in targets])
ax.grid(False)
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8,
                color="white" if M[i, j] > 0.55 else INK)
fig.colorbar(im, ax=ax, shrink=0.8, label="5-fold CV R²")
ax.set_title("Exp-1  커널 스크리닝 (기본 설정, 개발셋 교차검증 R²)")
save(fig, "F3_kernel_screen.png")

# F4 BO convergence ----------------------------------------------------------
n = len(targets)
fig, axes = plt.subplots(1, n, figsize=(2.6 * n, 2.8), sharey=False)
axes = np.atleast_1d(axes)
for ax, t in zip(axes, targets):
    for s, run in enumerate(res[t]["bo_runs"]):
        col = [BLUE, ORANGE, AQUA][s % 3]
        y = np.array(run["all_R2"])
        ax.scatter(np.arange(len(y)), np.clip(y, -0.2, 1), s=6, color=col, alpha=0.35, linewidths=0)
        ax.plot(run["curve"], color=col, lw=2, label=f"seed {s}")
    ax.axvline(7.5, color=INK2, lw=0.8, ls=":")
    ax.set_title(KOR[t])
    ax.set_xlabel("BO 반복 (trial)")
    lo = max(-0.2, min(min(r["all_R2"]) for r in res[t]["bo_runs"]))
    ax.set_ylim(lo, min(1, max(r["best_R2"] for r in res[t]["bo_runs"]) + 0.05))
axes[0].set_ylabel("CV R² (최고값 누적)")
axes[-1].legend(loc="lower right", fontsize=7)
fig.suptitle("Exp-2  베이지안 최적화 수렴 곡선 (점: 개별 trial, 선: best-so-far, 점선: 초기 무작위 8회 종료)",
             fontsize=9, color=INK2, y=1.03)
fig.tight_layout()
save(fig, "F4_bo_convergence.png")

# F5 parity plots ------------------------------------------------------------
fig, axes = plt.subplots(1, n, figsize=(2.9 * n, 3.0))
axes = np.atleast_1d(axes)
for ax, t in zip(axes, targets):
    p = pd.read_csv(os.path.join(OUT, f"pred_{t}.csv"))
    lo, hi = p[["y_true", "y_pred"]].min().min(), p[["y_true", "y_pred"]].max().max()
    pad = 0.05 * (hi - lo)
    ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], color=INK2, lw=0.8, ls="--")
    for sset, col, lab, ea in [("dev(OOF)", BLUE, "개발셋 OOF", 0.13), ("test", ORANGE, "테스트셋", 0.45)]:
        q = p[p["set"] == sset]
        ax.vlines(q["y_true"], q["y_pred"] - 1.96 * q["y_std"], q["y_pred"] + 1.96 * q["y_std"],
                  color=col, lw=0.7, alpha=ea)
        ax.scatter(q["y_true"], q["y_pred"], s=14, color=col, edgecolor=SURF, linewidth=0.5,
                   label=lab, zorder=3)
    r = res[t]["test"]
    ax.text(0.03, 0.97, f"Test R²={r['R2']:.2f}\nRMSE={r['RMSE']:.2f}\n95%PI 포함률={r['cov95'] * 100:.0f}%",
            transform=ax.transAxes, va="top", fontsize=7.5, color=INK)
    ax.set_title(KOR[t])
    ax.set_xlabel("실측값")
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(lo - pad, hi + pad)
axes[0].set_ylabel("GP 예측값 (±1.96σ)")
axes[-1].legend(loc="lower right", fontsize=7)
fig.tight_layout()
save(fig, "F5_parity.png")

# F6 model comparison on test ---------------------------------------------------
names = [("GP (BO 최적)", None, BLUE), ("Random Forest", "RandomForest", AQUA), ("Ridge", "Ridge", ORANGE),
         ("GP (sklearn 기본값)", "GP_sklearn_default", "#9a9893")]
fig, ax = plt.subplots(figsize=(8.5, 3.2))
w = 0.2
x = np.arange(n)
for i, (lab, key, col) in enumerate(names):
    vals = [res[t]["test"]["R2"] if key is None else res[t]["test_baselines"][key]["R2"] for t in targets]
    v = np.clip(vals, -0.2, 1)
    bars = ax.bar(x + (i - 1.5) * w, v, w * 0.92, color=col, label=lab)
    for xi, vi, raw in zip(x + (i - 1.5) * w, v, vals):
        ax.text(xi, max(vi, 0) + 0.015, f"{raw:.2f}" if raw > -0.2 else f"{raw:.0f}", ha="center",
                fontsize=6.5, color=INK2, rotation=90 if raw < -0.2 else 0)
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(x, [KOR[t] for t in targets])
ax.set_ylabel("Hold-out 테스트 R²")
ax.set_ylim(-0.25, 1.08)
ax.legend(ncol=4, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.16))
save(fig, "F6_model_compare.png")

# F7 permutation importance ------------------------------------------------------
imp_path = os.path.join(OUT, "importance.json")
if os.path.exists(imp_path):
    imp = json.load(open(imp_path))
    fig, axes = plt.subplots(1, n, figsize=(2.9 * n, 3.0))
    axes = np.atleast_1d(axes)
    for ax, t in zip(axes, targets):
        d = sorted(imp[t].items(), key=lambda kv: -kv[1])[:7][::-1]
        ax.barh([FEAT_KOR.get(k, k) for k, _ in d], [max(v, 0) for _, v in d], color=BLUE, height=0.6)
        ax.set_title(KOR[t])
        ax.set_xlabel("R² 감소량")
    fig.suptitle("순열 중요도 (교차검증 기반, 상위 7개)", fontsize=9, color=INK2, y=1.02)
    fig.tight_layout()
    save(fig, "F7_importance.png")

# F8 partial dependence --------------------------------------------------------
pdp_path = os.path.join(OUT, "pdp.json")
if os.path.exists(pdp_path):
    pdp = json.load(open(pdp_path))
    fig, axes = plt.subplots(1, n, figsize=(2.9 * n, 2.9))
    axes = np.atleast_1d(axes)
    for ax, t in zip(axes, targets):
        for i, (f, d) in enumerate(list(pdp[t].items())[:3]):
            col = [BLUE, ORANGE, AQUA][i]
            x_, mu, sd = np.array(d["x"]), np.array(d["mu"]), np.array(d["sd"])
            ax.plot(x_, mu, color=col, lw=2, label=FEAT_KOR.get(f, f))
            ax.fill_between(x_, mu - sd, mu + sd, color=col, alpha=0.12, lw=0)
        ax.set_title(KOR[t])
        ax.set_xlabel("함량 (phr)")
        ax.legend(fontsize=6.5, loc="best")
    fig.suptitle("부분의존도 (평균 예측 ± 1σ)", fontsize=9, color=INK2, y=1.02)
    fig.tight_layout()
    save(fig, "F8_pdp.png")

# F9 pool-based BO ---------------------------------------------------------------
pool_path = os.path.join(OUT, "pool_bo.json")
if os.path.exists(pool_path):
    pool = json.load(open(pool_path))
    m = len(pool)
    fig, axes = plt.subplots(1, m, figsize=(3.6 * m, 3.0))
    axes = np.atleast_1d(axes)
    for ax, (t, d) in zip(axes, pool.items()):
        for s, col, lab in [("bo_ei", BLUE, "BO (EI)"), ("greedy", AQUA, "Greedy (평균)"),
                            ("random", ORANGE, "Random")]:
            mc = np.array(d[s]["mean_curve"])
            xs = np.arange(len(mc))
            ax.plot(xs, mc, color=col, lw=2, label=lab)
            ax.fill_between(xs, d[s]["p25"], d[s]["p75"], color=col, alpha=0.12, lw=0)
        ax.axhline(d["global_best"], color=INK2, lw=0.8, ls="--")
        ax.text(len(mc) - 1, d["global_best"], " 전체 최고값", va="bottom", ha="right", fontsize=7, color=INK2)
        ax.set_title(f"{KOR[t]} {'최대화' if d['maximize'] else '최소화'} (pool={d['pool_size']})")
        ax.set_xlabel("추가 실험 횟수 (초기 5회 이후)")
    axes[0].set_ylabel("현재까지 최고 물성 (30회 반복 평균)")
    axes[-1].legend(fontsize=7)
    fig.tight_layout()
    save(fig, "F9_pool_bo.png")
print("figures written to", FIG)
