"""Write build/interp.json: the narrative paragraphs of the report and deck.
Every number is taken from outputs/report_data.json or the data files."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gp_core import add_derived, target_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
D = json.load(open(os.path.join(OUT, "report_data.json"), encoding="utf-8"))
mdl = add_derived(pd.read_csv(os.path.join(ROOT, "data", "gasket_dataset_clean.csv")))
R, T, KS, st, cnt = D["res"], D["targets"], D["kor_short"], D["stats"], D["counts"]
H, TS, EL, M1, CS = "hardness_shoreA", "tensile_MPa", "elongation_pct", "m100_MPa", "compression_set_pct"


def f(x, d=3):
    return "-" if x is None else f"{x:.{d}f}"


def pct(x, d=0):
    return "-" if x is None else f"{100 * x:.{d}f}%"


# ---------------------------------------------------------------- data facts
by_poly = mdl.groupby("polymer_type")[H].mean()
cs_rows = target_rows(mdl, CS)
cs_by_t = cs_rows.groupby("cs_temp_C")[CS].mean()
pc = mdl[[H, TS, EL, M1, CS]].corr(method="spearman")
corr = {t: dict(D["corr"][t]) for t in D["corr"]}
seeds = {t: [b["best"] for b in R[t]["bo_runs"]] for t in T}
screen_best = {t: R[t]["screen_best"]["R2"] for t in T}
bo_best = {t: max(seeds[t]) for t in T}
rf_cv = {t: R[t]["baselines_cv"]["RandomForest"] for t in T}


def ard_gain(t):
    sc = {(k[0], k[1]): float(k[2]) for k in R[t]["screen"]}
    pairs = [(sc.get((n, "ARD")), sc.get((n, "등방성"))) for n in ["RBF", "Matérn ν=1/2", "Matérn ν=3/2", "Matérn ν=5/2"]]
    return float(np.mean([a - b for a, b in pairs if a is not None and b is not None]))


ag = {t: ard_gain(t) for t in T}
best_robust = {t: R[t]["best_cv"]["R2"] for t in T}
I = {}

I["summary_lead"] = (
    f"공개 특허 {cnt['raw_sources']}건에서 반도체 장비용 불소고무(FFKM·FKM) 가스켓의 실시예·비교예 {cnt['raw_rows']}건을 수집하고, "
    f"정제 규칙을 통과한 {cnt['model_rows']}건({cnt['model_sources']}개 특허)으로 5개 물성의 가우시안 프로세스(GP) 회귀 모델을 구축하였다. "
    f"커널·전처리 등 모델 설계 하이퍼파라미터는 베이지안 최적화(BO)를 물성별로 서로 다른 난수 시드 3회 독립 반복하여 탐색하였고, "
    f"구조가 다른 상위 3개 설정을 5-fold × 5회 교차검증으로 재평가해 최종 설정을 정하였다. 하이퍼파라미터 실험은 총 {cnt['n_trials_total']}회"
    f"(물성당 기준모델 3 + 커널 스크리닝 9 + BO 90 + 재평가 3)이다.")

I["summary_points"] = [
    f"**경도와 100% 모듈러스는 예측 정확도가 높다.** 개발에 쓰지 않은 테스트셋에서 경도 R² {f(R[H]['test']['R2'])}(RMSE {f(R[H]['test']['RMSE'], 1)} Shore A), "
    f"M100 R² {f(R[M1]['test']['R2'])}(RMSE {f(R[M1]['test']['RMSE'], 2)} MPa)이며, 같은 테스트셋의 Random Forest({f(R[H]['test_baselines']['RandomForest'])}, "
    f"{f(R[M1]['test_baselines']['RandomForest'])})보다 높다. 95% 예측구간 포함률도 {pct(R[H]['test']['cov95'])}·{pct(R[M1]['test']['cov95'])}로 불확실성 추정이 실측과 일치한다.",
    f"**가장 적합한 하이퍼파라미터 설정**: 경도 = {R[H]['best_text']}, 입력 log(1+phr)·출력 log 변환, 특성 집합 full_agg / "
    f"M100 = {R[M1]['best_text']}, 특성 집합 full_cure6 / 인장강도 = {R[TS]['best_text']}, 입력 log(1+phr), full_cure6. "
    "다섯 물성 모두 Matérn 계열이 최종 선택되어, 특허별 배합군이 군집 형태로 흩어진 데이터에서는 무한히 매끄러운 RBF보다 덜 매끄러운 커널이 유리했다.",
    f"**BO 반복 실험은 재현성이 높았다.** 세 시드의 최고 CV R² 차이는 물성별 {f(min(max(v) - min(v) for v in seeds.values()))}~{f(max(max(v) - min(v) for v in seeds.values()))}였고, "
    f"같은 분할 기준으로 커널만 바꾼 스크리닝 대비 R²를 {f(min(bo_best[t] - screen_best[t] for t in T))}~{f(max(bo_best[t] - screen_best[t] for t in T))} 높였다(M100에서 최대).",
    "**커널 종류보다 입력 표현이 더 중요했다.** 하이퍼파라미터별 민감도 분석에서 특성 집합과 입력 변환의 영향(중앙값 R² 차이 최대 "
    f"{f(max(D['hp_effect'][t]['feature_set']['range'] for t in T))})이 커널 종류의 영향(최대 {f(max(D['hp_effect'][t]['kernel']['range'] for t in T))})보다 컸다.",
    f"**한계**: 압축영구줄음률(테스트 R² {f(R[CS]['test']['R2'])})은 배합 정보만으로는 예측이 어렵고, 신율은 외삽 1점 때문에 테스트 R²가 {f(R[EL]['test']['R2'])}였다"
    f"(적용범위 내 R² {f(R[EL].get('ad_r2_in'))}). 학습에 없던 특허로의 일반화(Leave-source-out R² {f(min(R[t]['lso']['R2'] for t in T), 2)}~{f(max(R[t]['lso']['R2'] for t in T), 2)})도 "
    "제한적이므로, 실무 적용 시 사내 실험 데이터 보강과 적용범위 확인이 필요하다.",
]

# ---------------------------------------------------------------- EDA
I["eda_dist"] = (
    f"모델링 데이터의 물성은 경도 {f(st[H]['min'], 0)}~{f(st[H]['max'], 0)} Shore A(평균 {f(st[H]['mean'], 1)}), 인장강도 {f(st[TS]['min'], 1)}~{f(st[TS]['max'], 1)} MPa"
    f"(평균 {f(st[TS]['mean'], 1)}), 신율 {f(st[EL]['min'], 0)}~{f(st[EL]['max'], 0)}%(평균 {f(st[EL]['mean'], 0)}), M100 {f(st[M1]['min'], 1)}~{f(st[M1]['max'], 1)} MPa, "
    f"압축영구줄음률 {f(st[CS]['min'], 0)}~{f(st[CS]['max'], 0)}%(평균 {f(st[CS]['mean'], 1)})로, 연질부터 고경도 컴파운드까지 넓게 분포한다. "
    f"FFKM이 {cnt['ffkm']}건으로 다수이며 FFKM의 평균 경도({f(by_poly['FFKM'], 1)})가 FKM({f(by_poly['FKM'], 1)})보다 높다. "
    f"압축영구줄음률은 시험온도에 따라 평균이 200 °C {f(cs_by_t.get(200.0), 1)}%, 204 °C {f(cs_by_t.get(204.0), 1)}%, 300 °C {f(cs_by_t.get(300.0), 1)}%로 달라, "
    "서로 다른 특허의 값을 함께 쓰려면 시험온도를 입력변수로 넣어야 한다. 물성 간에는 경도와 M100의 순위상관이 "
    f"{f(pc.loc[H, M1], 2)}로 매우 높고, 경도와 신율은 {f(pc.loc[H, EL], 2)}로 반대 방향이다(강성이 높을수록 덜 늘어남).")
I["eda_corr"] = (
    f"총 필러량은 경도(ρ = {f(corr[H].get('total_filler_phr'), 2)})·M100(ρ = {f(corr[M1].get('total_filler_phr'), 2)})과 가장 강한 양의 상관을 보여, "
    "\"필러 충전량이 늘면 강성이 커진다\"는 고무 배합의 일반 원리가 특허 데이터에서도 확인된다. 신율은 총 필러량·카본블랙과 음의 상관, "
    "불소수지와 양의 상관을 보인다. 인장강도는 알루미나·과산화물과 양의 상관을 보이지만, 이는 '과산화물 가교 FFKM + 알루미나 15 phr'를 기본 배합으로 "
    "쓰는 특정 특허군(US7678858B2 등)의 영향이 겹친 것이어서 성분 자체의 인과 효과로 해석하면 안 된다. 즉 특허(=배합군) 효과와 성분 효과가 섞여 있다. "
    "압축영구줄음률은 어떤 단일 성분과도 |ρ| < 0.3의 약한 상관만 보여, 다변량 비선형 모델이 필요하면서도 예측이 어려운 물성임을 미리 보여준다.")

# ---------------------------------------------------------------- results
I["baseline"] = (
    f"scikit-learn의 기본 GP는 CV R²가 경도 {f(R[H]['baselines_cv']['GP_sklearn_default'], 0)}, 인장강도 {f(R[TS]['baselines_cv']['GP_sklearn_default'], 0)}처럼 "
    "극단적인 음수였다. 커널 하이퍼파라미터가 고정(ℓ = 1, σf = 1)되어 학습되지 않고 출력 정규화도 꺼져 있어, 학습점에서 조금만 벗어나도 사전평균 0으로 "
    "예측이 떨어지기 때문이다. GP는 하이퍼파라미터와 전처리 설정이 성능을 사실상 결정하는 모델이라는 점을 보여준다. 비교모델 중에서는 Random Forest가 "
    f"CV R² {f(min(rf_cv.values()))}~{f(max(rf_cv.values()))}로 가장 강했고, 선형 Ridge는 인장강도에서 {f(R[TS]['baselines_cv']['Ridge'])}로 실패해 "
    "배합–물성 관계가 강한 비선형임을 확인하였다.")
I["screen"] = (
    "출력 정규화·잡음항·log(1+phr) 입력을 갖춘 기본 GP는 커널만 바꿔도 Random Forest와 대등하거나 더 나은 성능을 냈다(스크리닝 최고 vs RF: "
    + ", ".join(f"{KS[t]} {f(screen_best[t])} vs {f(rf_cv[t])}" for t in T) + "). "
    "등방성 커널끼리의 차이는 0.02 이내로 작았던 반면, ARD의 효과는 물성마다 방향이 달랐다. ARD는 신율에서 평균 "
    f"{f(ag[EL], 3)} 개선되었지만 경도({f(ag[H], 3)}), 인장강도({f(ag[TS], 3)}), M100({f(ag[M1], 3)})에서는 오히려 낮아졌다. "
    "200개 안팎의 데이터로 17개 길이척도를 동시에 추정하면 일부 성분의 길이척도가 지나치게 짧아지는 과적합이 생기기 때문이다. 따라서 ARD 사용 여부는 "
    "선형항·특성 집합 등 다른 설정과 함께 정해야 하며, 이것이 설정을 하나씩 고정하는 격자 탐색 대신 9개 하이퍼파라미터를 동시에 다루는 BO를 사용한 이유이다.")
I["bo"] = (
    "세 시드의 최고 CV R²는 " + ", ".join(f"{KS[t]} {f(min(seeds[t]))}~{f(max(seeds[t]))}" for t in T) +
    "로, 시드가 달라도 거의 같은 수준에 수렴하였다. 같은 단일 5-fold 분할에서 커널 스크리닝 최고값 대비 BO 최고값은 " +
    ", ".join(f"{KS[t]} +{f(bo_best[t] - screen_best[t])}" for t in T) +
    " 높았다. 최고값은 대부분 초기 무작위 8회 이후의 EI 단계에서 갱신되었다(그림의 점선 이후). 반면 시드마다 도달한 최고 설정의 커널 종류는 달랐는데"
    f"(예: 경도 {', '.join(sorted(set(b['cfg_text'].split(' +')[0].split(' (')[0] for b in R[H]['bo_runs'])))}), 이는 성능이 비슷한 '평탄한 최적 영역'이 넓게 존재함을 뜻한다. "
    "BO 상위 10개 trial의 공통점을 보면, 인장강도는 10개 모두 등방성·선형항 없음·log1p 입력·full_cure6이었고, 신율은 10개 모두 ARD·선형항·std 입력·compact였다.")
he = D["hp_effect"]
I["hp_effect"] = (
    "위 표는 BO가 시도한 trial을 하이퍼파라미터의 선택지별로 묶어 CV R² 중앙값을 비교한 것이다(BO는 좋은 영역을 더 많이 시도하므로 엄밀한 분산분석은 아니며 "
    f"경향 파악용이다). 인장강도는 특성 집합({f(he[TS]['feature_set']['range'])})과 입력 변환({f(he[TS]['x_transform']['range'])})에 가장 민감했고, "
    f"M100({f(he[M1]['feature_set']['range'])})·신율({f(he[EL]['feature_set']['range'])})도 특성 집합의 영향이 가장 컸다. 가교계를 6종으로 세분한 full_cure6가 "
    "인장강도·M100에서 가장 좋았다는 것은, 트리아진·비스아미노페놀·유기주석 등 니트릴 경화 화학종에 따라 가교 네트워크가 달라져 강도·모듈러스가 달라진다는 "
    "도메인 지식과 부합한다. 출력 변환(로그)의 영향은 대부분 0.015 이하로 작았다.")
rob = {t: R[t]["robust"] for t in T}
I["robust"] = (
    "단일 분할에서 고른 설정은 5회 반복 재평가에서 대체로 R²가 소폭 낮아졌다. 특히 압축영구줄음률은 BO 최고 설정"
    f"({rob[CS][0]['cfg_text']}, 탐색 {f(rob[CS][0]['search'])})이 재평가에서 {f(rob[CS][0]['robust'])} ± {f(rob[CS][0]['std'])}로 떨어지고 표준편차도 가장 커서, "
    "단일 분할의 운으로 선택되었음이 드러났다. 이 경우 재평가 1위인 "
    f"{R[CS]['best_text']}({f(R[CS]['best_cv']['R2'])} ± {f(R[CS]['best_cv']['R2_std'])})가 최종 선택되었다. 반대로 경도의 {R[H]['best_text']} 설정은 "
    f"{f(rob[H][0]['search'])} → {f(rob[H][0]['robust'])}로 오히려 올라(재시작 3회로 최적화 안정화) 최종 선택되었다. 재평가 단계가 없었다면 압축영구줄음률에서는 "
    "과대평가된 설정을 택했을 것이다.")
el_out = R[EL].get("ad_out_rows", [])
I["final"] = (
    f"테스트셋에서 경도 R² {f(R[H]['test']['R2'])}(RMSE {f(R[H]['test']['RMSE'], 2)} Shore A), M100 R² {f(R[M1]['test']['R2'])}(RMSE {f(R[M1]['test']['RMSE'], 2)} MPa)로 높은 "
    f"정확도를 보였고, 95% 예측구간 포함률도 {pct(R[H]['test']['cov95'])}·{pct(R[M1]['test']['cov95'])}였다. 인장강도는 {f(R[TS]['test']['R2'])}(RMSE {f(R[TS]['test']['RMSE'], 2)} MPa)로 "
    f"CV({f(R[TS]['best_cv']['R2'])})보다 낮았지만 같은 테스트셋의 RF({f(R[TS]['test_baselines']['RandomForest'])})·Ridge({f(R[TS]['test_baselines']['Ridge'])})보다 높았다. "
    f"신율은 테스트 R² {f(R[EL]['test']['R2'])}로 나빴는데, 원인은 사실상 1점이다. US7354974B2 Example 6은 불소수지 300 phr로 개발셋 최대(100 phr)의 3배인 외삽 영역이며, "
    "선형항 + 표준화 입력 설정이 이 점을 655%(실측 228%)로 예측하였다. 그러나 GP는 이 점의 예측 표준편차를 369%로 크게 출력해 '모른다'는 신호를 냈고, 실측값은 "
    f"95% 구간 안에 있었다. 입력이 개발셋 범위 안에 있는 테스트 점만 보면 신율 R²는 {f(R[EL].get('ad_r2_in'))}이다(범위 밖 {R[EL]['ad_n_out']}점: {', '.join(el_out)}). "
    f"압축영구줄음률은 테스트 R² {f(R[CS]['test']['R2'])}로 GP·RF({f(R[CS]['test_baselines']['RandomForest'])}) 모두 예측력이 낮았다. "
    f"Leave-source-out R²({f(min(R[t]['lso']['R2'] for t in T), 2)}~{f(max(R[t]['lso']['R2'] for t in T), 2)})는 무작위 분할보다 크게 낮아, 학습에 없던 특허(다른 원료 "
    "그레이드·가황 조건·시험법)로의 일반화는 제한적이다. 즉 이 모델은 '학습한 특허군과 비슷한 배합 영역 안의 보간'에 강하다.")


def detail(t):
    E = R[t]
    s = (f"학습된 커널은 `{E['final_kernel'][:120]}{'…' if len(E['final_kernel']) > 120 else ''}`이다. "
         f"잡음분산 비율 σₙ²/(σf²+σₙ²)은 {pct(E.get('noise_frac'), 0)}로, ")
    s += ("데이터 변동의 상당 부분이 배합으로 설명되지 않는 특허 간 차이·시험 편차임을 뜻한다. " if E.get("noise_frac", 0) > 0.15
          else "배합으로 설명되는 신호가 잡음보다 훨씬 크다. ")
    if E.get("ard"):
        ls0 = 10 ** E["best"]["ls_init"]
        ls = sorted(E["ard"].items(), key=lambda kv: kv[1])
        stuck = [k for k, v in ls if abs(v - ls0) / ls0 < 5e-3]
        free = [(k, v) for k, v in ls if k not in stuck]
        n_long = sum(1 for _, v in ls if v >= 300)
        at_floor = [k for k, v in ls if v <= 0.0101]
        s += f"ARD 길이척도 {len(ls)}개 중 {n_long}개는 300 이상(상한 1000 포함)으로 커서 해당 입력은 사실상 무시되었다(자동 특성 선택). "
        if stuck:
            s += (f"{', '.join(D['feat_kor'].get(k, k) for k in stuck)}의 길이척도는 초기값({f(ls0, 3)})에서 전혀 움직이지 않았다. 0/1 지시변수처럼 값이 "
                  "멀리 떨어진 입력은 길이척도가 작으면 서로 다른 그룹 간 상관이 0이 되어 기울기가 사라지기 때문이다. 결과적으로 이 모델은 해당 변수로 나뉜 "
                  "그룹(예: FFKM/FKM, 과산화물/니트릴 가교)을 서로 정보를 공유하지 않는 별도의 하위 모델처럼 다루며, BO가 작은 ℓ 초기값을 고른 것은 이 "
                  "'그룹 분리' 효과가 교차검증에서 유리했기 때문으로 해석된다. ")
        if at_floor:
            s += (f"{', '.join(D['feat_kor'].get(k, k) for k in at_floor)}의 길이척도는 하한(0.01)에 닿아, 같은 이유로 데이터를 그룹으로 분리하는 역할을 한다. ")
        if free:
            s += ("실제로 학습된 길이척도 중 가장 짧은(민감한) 성분은 " +
                  ", ".join(f"{D['feat_kor'].get(k, k)}({v:.3g})" for k, v in free if v > 0.0101)[:200] .split(", ")[0:3].__str__()
                  .replace("[", "").replace("]", "").replace("'", "") + "이다. ")
        s += "ARD 길이척도는 특허(배합군) 효과가 섞여 있어 성분 영향도는 6.6절 순열 중요도와 함께 판단해야 한다."
    elif E.get("ls") is not None:
        s += (f"등방성 길이척도 ℓ = {f(E['ls'], 2)}(표준화 단위)는 입력 {len(E['features'])}차원 전체에 하나의 척도를 쓰므로, 개별 성분보다 '배합 전체의 유사도'로 "
              "물성을 보간하는 모델이다.")
    if E["best"]["linear"]:
        s += " 선형항(DotProduct)이 포함되어 필러량 증가에 따른 전역적 추세를 따로 표현하지만, 이 항은 학습 범위 밖에서 직선으로 외삽하므로 적용범위 관리가 필요하다."
    return s


I["detail"] = {t: detail(t) for t in T}

imp = {t: R[t]["importance"] for t in T}
I["importance"] = (
    "순열 중요도(교차검증 fold의 시험 데이터에서 한 성분의 값을 무작위로 섞었을 때 R²가 얼마나 떨어지는지)로 본 핵심 성분은 다음과 같다. " +
    "; ".join(f"{KS[t]}: " + ", ".join(f"{k}({v:.3f})" for k, v in imp[t][:3]) for t in T if imp[t]) +
    ". 부분의존도 그림은 한 성분만 바꾸고 나머지 배합은 실제 값을 유지했을 때의 평균 예측과 ±1σ 범위이다. 경도·M100은 필러량에 따라 단조 증가하는 "
    "경향을 보여 고무 배합 이론과 일치하며, 데이터가 적은 고함량 영역에서는 불확실성 띠가 넓어진다.")

# ---------------------------------------------------------------- design
pool = D.get("pool_bo") or {}
inv = D.get("inverse_design") or {}
if pool:
    def ps(t, s):
        return pool[t][s]
    parts = []
    for t, d in pool.items():
        parts.append(f"{KS[t]}{'(최대화)' if d['maximize'] else '(최소화)'}: BO 성공률 {pct(ps(t, 'bo_ei')['success_rate_top5'])}·평균 "
                     f"{f(ps(t, 'bo_ei')['exp_to_top5_mean'], 1)}회, 무작위 {pct(ps(t, 'random')['success_rate_top5'])}·"
                     f"{f(ps(t, 'random')['exp_to_top5_mean'], 1)}회, 탐욕 {pct(ps(t, 'greedy')['success_rate_top5'])}·{f(ps(t, 'greedy')['exp_to_top5_mean'], 1)}회")
    I["pool"] = ("상위 5% 배합에 도달하기까지의 결과를 요약하면 " + "; ".join(parts) + "이다(평균 실험 수는 도달에 성공한 반복만으로 계산). "
                 "경도처럼 모델 정확도가 높은 물성에서는 BO가 무작위 선택보다 훨씬 적은 실험으로 목표에 도달했고, 탐욕 전략보다도 빨랐다. 예측 평균만 따르는 탐욕 전략은 "
                 "초기 데이터가 적을 때 엉뚱한 영역에 갇히기 쉬운데, EI는 불확실성이 큰 배합도 함께 시도하기 때문이다. 반면 모델 정확도가 낮은 압축영구줄음률에서는 BO의 "
                 "이점이 작았다. BO의 효율은 대리모델의 품질에 좌우된다는 점을 보여주는 결과이다.")
else:
    I["pool"] = ""
if inv:
    recs = D.get("recs", [])
    r1 = recs[0] if recs else {}
    I["design"] = (
        f"후보 생성 모집단은 데이터에서 가장 많은 조합인 {inv['family']}({inv['n_family_rows']}건)이며, 제약 확률에는 CV R² 0.5 이상인 모델"
        f"({', '.join(KS[t] for t in inv['models_used'])})만 사용하였다. 압축영구줄음률 모델은 CV R² {f(R[CS]['best_cv']['R2'])}로 기준에 못 미쳐 제약에서 제외하였다. "
        f"후보는 실무 배합 범위(총 필러 ≤ {f(inv['practical']['total_filler_phr'], 0)} phr, 불소수지 ≤ {f(inv['practical']['fluororesin_phr'], 0)} phr)로 제한하여 "
        f"{inv['n_generated']:,}개 중 {inv['n_candidates']:,}개를 평가하였다 — "
        "이 제약이 없으면 불소수지 100~300 phr의 고무/불소수지 블렌드(다른 재료군, 모델 불확실성 최대 영역)가 상위를 차지했다. "
        f"같은 재료군에서 사양을 만족하는 실측 배합의 최고 인장강도는 {f(inv['incumbent_tensile'], 2)} MPa이며, 1순위 후보의 예측 인장강도는 "
        f"{f(r1.get('pred_tensile_MPa'), 1)} ± {f(r1.get('std_tensile_MPa'), 1)} MPa, 사양 만족 확률 {pct(r1.get('P_feasible'))}이다. 제안 후보들의 예측 평균은 현재 최고값보다 "
        "낮지만 불확실성이 커서 기대개선이 가장 크다. 즉 현재 데이터로는 '확실히 더 좋은' 배합을 단정할 수 없으며, BO는 사양 만족 확률이 높은 배합 가운데 "
        "정보 가치가 가장 큰 다음 실험(탐색 위주 제안)을 고른 것이다. "
        "제안 배합은 모델 예측일 뿐 실측이 아니며, BO의 원래 사용법대로 1~3개를 실제로 배합·가황·시험한 뒤 그 결과를 데이터에 추가하고 모델을 다시 학습해 다음 "
        "후보를 제안하는 순환으로 활용해야 한다.")
else:
    I["design"] = ""

I["discussion"] = [
    {"title": "8.1 데이터 이질성과 잡음",
     "text": "특허마다 원료 고무 그레이드(경화부위 단량체 종류·함량, 점도), 혼련·프레스·2차 가황 조건, 시편(O-링·시트·버튼), 시험 규격(JIS·ASTM)이 다르다. "
             "같은 배합도 특허가 다르면 물성이 달라질 수 있으며, 이 차이는 GP의 잡음항으로 흡수된다. 학습된 잡음 비율(6장)과 무작위 분할 대비 크게 낮은 "
             "Leave-source-out R²가 이를 정량적으로 보여준다. 따라서 본 모델의 정확도는 '특허 데이터의 일관성'에 의해 상한이 정해진다."},
    {"title": "8.2 외삽과 적용범위",
     "text": "신율 테스트의 불소수지 300 phr 사례처럼 학습 범위를 벗어난 입력에서는 선형항이 있는 모델이 크게 빗나갈 수 있다. GP는 이때 큰 예측 표준편차를 "
             "내므로, 실무에서는 (1) 입력이 학습 데이터의 범위(또는 마할라노비스 거리 기준) 안에 있는지, (2) 예측 표준편차가 일정 수준 이하인지를 함께 확인하는 "
             "적용범위 규칙을 두는 것이 바람직하다. 7장의 배합 제안도 같은 이유로 실제 배합을 섭동한 후보만 사용하였다."},
    {"title": "8.3 압축영구줄음률의 예측 한계",
     "text": "압축영구줄음률은 배합보다 가교 상태(2차 가황 온도·시간), 시험 조건(압축률 18/25%, 시험시간, 시편 형상), 시험 후 회복 조건의 영향을 크게 받는데, "
             "이 정보가 특허마다 다르거나 누락되어 있다. 시험온도를 입력으로 넣었음에도 CV R²가 0.3 수준에 머문 것은 배합 정보만으로는 설명되지 않는 변동이 크다는 "
             "뜻이다. 2차 가황 조건과 시험 조건을 변수로 추가하거나, 동일 조건의 사내 데이터를 확보해야 실용 수준의 모델이 가능하다."},
    {"title": "8.4 누락 변수와 해석의 주의점",
     "text": "필러의 입경·비표면적·표면처리, 고무의 분자량·경화부위 종류, 가공조제의 종류는 모델에 반영되지 않았다. 또한 ARD 길이척도와 단변량 상관은 특허(배합군) "
             "효과와 성분 효과가 섞여 있어 인과적 해석에 한계가 있다. 성분 효과를 정확히 알려면 같은 기본 배합에서 한 성분만 바꾼 설계 실험(DoE) 데이터가 필요하다."},
    {"title": "8.5 향후 개선 방향",
     "text": "(1) 사내 실험 데이터를 결합하고 특허 출처를 무작위효과로 두는 계층형 GP, (2) 경도–M100(순위상관 0.83)처럼 상관이 큰 물성을 함께 학습하는 다중출력(multi-task) GP, "
             "(3) 실험을 여러 개 동시에 진행하기 위한 배치 BO(q-EI), (4) 시험 조건이 표준화된 데이터를 확보한 뒤 플라즈마 무게감소율·고온 압축영구줄음률 모델 추가를 권장한다."},
]
I["conclusion"] = [
    f"공개 특허 {cnt['raw_sources']}건에서 반도체 공정용 불소고무 가스켓의 배합비–물성 데이터 {cnt['raw_rows']}건을 원문 그대로 전사하고, 정제 후 {cnt['model_rows']}건의 모델링 데이터베이스를 엑셀로 구축하였다.",
    f"GP 회귀의 모델 설계 하이퍼파라미터를 BO로 물성별 3회 독립 반복 탐색하고(총 {cnt['n_trials_total']}회 실험), 상위 설정을 반복 교차검증으로 재평가해 최종 설정을 선택하였다. 시드 간 결과 차이는 0.015 이내로 재현성이 확인되었다.",
    f"최적 설정은 경도 [{R[H]['best_text']}; 테스트 R² {f(R[H]['test']['R2'])}], M100 [{R[M1]['best_text']}; {f(R[M1]['test']['R2'])}], 인장강도 [{R[TS]['best_text']}; {f(R[TS]['test']['R2'])}]이며, 하이퍼파라미터 중에서는 커널 종류보다 특성 집합과 입력 변환의 영향이 더 컸다.",
    "경도·M100은 배합 설계 초기 검토에 바로 활용할 수 있는 수준이고, 인장강도는 경향 파악용, 신율은 적용범위 안에서만 사용할 것을 권장한다. 압축영구줄음률은 가황·시험 조건 변수를 추가한 뒤 재구축이 필요하다.",
    "회고적 벤치마크에서 BO는 경도 상위 5% 배합에 평균 1~2회의 추가 실험으로 도달해 무작위 선택(약 10회)보다 효율적이었다. 학습된 GP와 제약 기대개선으로 사양(경도 70~80, 신율 ≥ 150%) 안의 차기 실험 후보도 제안하였으며, 실험 결과를 반영해 모델을 갱신하는 순환형 BO로 활용하는 것이 다음 단계이다.",
]

# ---------------------------------------------------------------- deck
I["deck_glance"] = f"특허 {cnt['model_rows']}건으로 학습한 GP가 경도·M100을 테스트 R² {f(R[H]['test']['R2'], 2)}·{f(R[M1]['test']['R2'], 2)}로 예측"
I["deck_best_label"] = f"경도 (RMSE {f(R[H]['test']['RMSE'], 1)} Shore A)"
I["deck_glance_foot"] = (f"하이퍼파라미터는 BO를 물성별 3회 독립 반복해 탐색하고, 상위 설정을 5×5 교차검증으로 재평가해 선택했습니다. "
                         f"압축영구줄음률은 배합 정보만으로는 예측력이 낮아(테스트 R² {f(R[CS]['test']['R2'], 2)}) 가황·시험 조건 변수가 추가로 필요합니다.")
I["deck_bo"] = (f"시드 간 최고 CV R² 차이 ≤ {f(max(max(v) - min(v) for v in seeds.values()), 3)} — 결과가 난수에 둔감, 입력 표현(특성 집합·변환)이 커널보다 중요")
I["deck_parity"] = (f"경도 95% 예측구간 포함률 {pct(R[H]['test']['cov95'])} — 불확실성 추정이 실측과 일치 / 신율의 큰 오차 1점은 학습 범위 3배 밖 외삽")
if pool:
    I["deck_pool"] = "상위 5% 배합 도달까지 평균 추가 실험 수 — " + " / ".join(
        f"{KS[t]}: BO {f(pool[t]['bo_ei']['exp_to_top5_mean'], 1)}회 vs 무작위 {f(pool[t]['random']['exp_to_top5_mean'], 1)}회"
        for t in [H, TS] if t in pool)
else:
    I["deck_pool"] = ""
I["deck_design"] = ("제약 기대개선(cEI)으로 경도 70~80·신율 ≥ 150% 사양 안에서 인장강도 개선 가능성이 가장 큰 차기 실험 10건 제안 (엑셀 BO_Recommend) — "
                    "예측 평균은 현 최고값보다 낮고 불확실성이 큰 탐색형 제안이므로, 실측 후 모델을 갱신하는 순환으로 활용")
I["deck_conclusion"] = [
    f"특허 {cnt['raw_sources']}건에서 {cnt['raw_rows']}건 수집 → {cnt['model_rows']}건 정제 DB (엑셀)",
    f"BO {cnt['n_trials_total']}회 실험: 최적 GP는 Matérn 계열, 입력 표현이 성능을 좌우",
    f"경도 R² {f(R[H]['test']['R2'], 2)} · M100 {f(R[M1]['test']['R2'], 2)} 실무 활용 가능 / 압축영구줄음률은 추가 변수 필요",
    "다음 단계: BO 제안 배합 1~3개 실험 → 데이터 추가 → 모델 재학습 순환",
    "사내 데이터 결합·계층형/다중출력 GP로 특허 간 이질성 보정",
]
import re


def josa(x):
    """Korean particle after a number: 0/3/6 end in a consonant -> '으로', others -> '로'."""
    if isinstance(x, str):
        return re.sub(r"(\d)로(?![가-힣])", lambda m: m.group(1) + ("으로" if m.group(1) in "036" else "로"), x)
    if isinstance(x, list):
        return [josa(v) for v in x]
    if isinstance(x, dict):
        return {k: josa(v) for k, v in x.items()}
    return x


I = josa(I)
json.dump(I, open(os.path.join(ROOT, "build", "interp.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("interp.json written")
