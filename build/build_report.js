// Word report generator (Korean). Reads outputs/report_data.json + figures.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Header, Footer, PageNumber, TableOfContents,
  PageBreak, BorderStyle,
} = require("docx");
const { P, H1, H1n, H2, H3, B, N, EQ, FIG, TABLE, NOTE, numbering, styles, FONT, C, PAGE_W, PAGE_H, MARGIN } = require("./docx_helpers");

const ROOT = path.resolve(__dirname, "..");
const OUT = process.env.OUT_DIR || path.join(ROOT, "outputs");
const FIGD = path.join(OUT, "figures");
const D = JSON.parse(fs.readFileSync(path.join(OUT, "report_data.json"), "utf8"));
const INTERP = JSON.parse(fs.readFileSync(process.env.INTERP || path.join(__dirname, "interp.json"), "utf8"));
const T = D.targets;
const K = D.kor, KS = D.kor_short;
const f = (x, d = 3) => (x === null || x === undefined || Number.isNaN(x)) ? "-" : Number(x).toFixed(d);
const pct = (x, d = 0) => (x === null || x === undefined) ? "-" : (100 * x).toFixed(d) + "%";
const fig = (n) => path.join(FIGD, n);
const R = D.res;
const cnt = D.counts;

const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

// ------------------------------------------------------------------ cover
add(
  new Paragraph({ spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: "기술 보고서", font: FONT, size: 24, color: C.muted })] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "반도체 공정용 불소고무 가스켓의", font: FONT, size: 44, bold: true, color: C.navy })] }),
  new Paragraph({ spacing: { after: 400 }, children: [new TextRun({ text: "배합비–물성 예측 모델 개발", font: FONT, size: 44, bold: true, color: C.navy })] }),
  new Paragraph({ spacing: { after: 1200 }, children: [new TextRun({ text: "공개 특허 데이터 기반 가우시안 프로세스 회귀 및 베이지안 최적화 적용", font: FONT, size: 26, color: C.ink })] }),
  ...TABLE("문서 개요", ["항목", "내용"], [
    ["데이터", `공개 특허 ${cnt.raw_sources}건에서 실시예·비교예 ${cnt.raw_rows}건 수집 → 정제 후 ${cnt.model_rows}건(${cnt.model_sources}개 특허) 모델링`],
    ["대상 물성", "경도(Shore A), 인장강도, 신율, 100% 모듈러스, 압축영구줄음률"],
    ["모델", "가우시안 프로세스(GP) 회귀 — 커널·전처리 하이퍼파라미터를 베이지안 최적화(BO)로 탐색"],
    ["하이퍼파라미터 실험", `총 ${cnt.n_trials_total}회 (GP ${cnt.n_trials_gp}회 + 비교모델) — 물성별 BO 3회 독립 반복`],
    ["산출물", "엑셀 데이터·결과 파일, 본 보고서(Word), 요약 발표자료(PPT), 재현 가능한 소스코드(src/)"],
    ["작성일", "2026년 10월 8일"],
  ], [1800, 7600]),
);

// ------------------------------------------------------------------ TOC
add(new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "목차", font: FONT, size: 30, bold: true, color: C.navy })] }),
  new TableOfContents("목차", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "※ 목차가 비어 보이면 Word에서 목차를 클릭한 뒤 [필드 업데이트](F9)를 실행하세요.", font: FONT, size: 16, color: C.muted })] }));

// ------------------------------------------------------------------ executive summary
add(H1("요약"));
add(P(INTERP.summary_lead));
const sumRows = T.map((t) => [K[t], String(R[t].n_total), R[t].best_text,
  `${f(R[t].best_cv.R2)} ± ${f(R[t].best_cv.R2_std)}`, f(R[t].test.R2), `${f(R[t].test.RMSE, 2)}`, pct(R[t].test.cov95)]);
add(TABLE("물성별 최적 GP 모델과 성능 요약 (CV: 개발셋 5-fold×5회, Test: 미사용 20% 홀드아웃)",
  ["물성", "n", "최적 커널", "CV R²", "Test R²", "Test RMSE", "95% 구간 포함률"], sumRows,
  [1700, 500, 2700, 1300, 900, 1000, 1300], { align: [0, 1, 0, 1, 1, 1, 1].map((a) => a ? AlignmentType.CENTER : AlignmentType.LEFT) }));
add(NOTE("핵심 결론", INTERP.summary_points));

// ------------------------------------------------------------------ 1. intro
add(H1("1. 서론"));
add(H2("1.1 배경"));
add(P("반도체 식각(Etch), 증착(CVD·ALD), 애싱(Ashing) 장비의 챔버 리드, 게이트 밸브, 슬릿 밸브, 가스 라인 등에 사용되는 O-링·가스켓은 O₂·CF₄·NF₃ 플라즈마와 라디칼, 150~300 °C의 고온, 부식성 공정가스에 장시간 노출된다. 이 때문에 주쇄가 완전히 불소화된 과불소고무(FFKM)와 불화비닐리덴 계열 불소고무(FKM)가 주 원재료로 사용되며, 실링 성능은 원재료 고무뿐 아니라 부재료 — 보강·충전 필러(카본블랙, 실리카, 알루미나, 황산바륨, 산화티탄, 불소수지 미분말 등), 가교계(유기과산화물 + 트리알릴이소시아누레이트(TAIC) 가교조제, 니트릴 경화부위용 트리아진·비스아미노페놀·유기주석 촉매 등), 수산제, 가공조제 — 의 종류와 배합비(phr)에 의해 크게 달라진다."));
add(P("배합 개발은 통상 수십~수백 회의 시행착오 실험에 의존하며, 원료(특히 FFKM)의 가격이 높아 실험 1회의 비용이 크다. 가우시안 프로세스(GP) 회귀는 소량 데이터에서도 비선형 관계를 학습하고 예측의 불확실성(표준편차)까지 함께 제공하므로, 이를 대리모델(surrogate)로 삼아 \"다음에 어떤 배합을 시험할지\"를 정하는 베이지안 최적화(BO)와 결합하면 실험 횟수를 줄일 수 있다."));
add(H2("1.2 목적과 범위"));
add(N("공개 특허의 실시예·비교예 표로부터 반도체 공정용 불소고무 가스켓의 원재료·부재료 배합비와 물성 데이터를 100~200건 이상 확보하여 엑셀 데이터베이스로 구축한다.", "nums"));
add(N("배합비 → 물성(경도, 인장강도, 신율, 100% 모듈러스, 압축영구줄음률)을 예측하는 GP 회귀 모델을 구축한다.", "nums"));
add(N("GP 모델의 하이퍼파라미터(커널 종류, ARD, 선형항, 입력·출력 변환, 특성 집합, 초기값, 잡음 하한)를 베이지안 최적화로 탐색하되, 서로 다른 난수 시드로 여러 번 반복 실험하여 가장 우수한 설정과 그 재현성을 확인한다.", "nums"));
add(N("최적 모델을 이용해 베이지안 최적화 기반 배합 설계(차기 실험 후보 제안)를 시연하고, 실제 실험 대비 BO의 효율을 회고적으로 검증한다.", "nums"));
add(H2("1.3 산출물"));
add(TABLE("산출물 목록", ["파일", "내용"], [
  ["가스켓_배합-물성_데이터_및_GP모델.xlsx", "원자료·모델링 데이터·출처·통계·하이퍼파라미터 실험 전체 기록·최적 모델·예측값·BO 제안 배합"],
  ["가스켓_GP_BO_분석보고서.docx", "본 보고서 — 데이터 수집, 방법론, 하이퍼파라미터 설정과 분석 과정 상세"],
  ["가스켓_GP_BO_발표자료.pptx", "핵심 내용 요약 발표자료"],
  ["src/, tools/, data/, outputs/", "재현용 소스코드, 특허 표 추출 도구, 원자료(CSV), 실험 로그·그림"],
], [3600, 5800]));

// ------------------------------------------------------------------ 2. data
add(H1("2. 데이터 수집 및 정제"));
add(H2("2.1 수집 방법"));
add(P(`데이터는 Google Patents에 공개된 특허 전문의 실시예(Example)·비교예(Comparative Example) 표에서 수집하였다. 요약 생성 모델을 거치면 수치가 왜곡될 수 있으므로, 특허 HTML을 직접 내려받아 표(<table>)를 탭 구분 텍스트로 변환하는 전용 도구(tools/patent_tables.py)를 작성하여 숫자를 원문 그대로 전사하였다. 표가 이미지로만 제공되는 문서는 제외하였다.`));
add(P("조사 범위는 출원인 기준 4개 그룹으로 나누어 병렬로 수행하였다."));
add(TABLE("출원인 그룹별 수집 결과", ["그룹", "대표 출원인", "수집 행(문서)", "모델 사용 행"], [
  ["① Daikin", "Daikin Industries (DAI-EL PERFLO 등 FFKM)", `${cnt.by_batch.batch_daikin.n} (${cnt.by_batch.batch_daikin.s})`, String(D.assignee_groups.batch_daikin || 0)],
  ["② 미국계 FFKM", "DuPont·Chemours(Kalrez), 3M·Dyneon, Greene Tweed(Chemraz)", `${cnt.by_batch.batch_dupont3mgt.n} (${cnt.by_batch.batch_dupont3mgt.s})`, String(D.assignee_groups.batch_dupont3mgt || 0)],
  ["③ 일본 실링 업체", "Nichias, Valqua, Mitsubishi Cable", `${cnt.by_batch.batch_japan.n} (${cnt.by_batch.batch_japan.s})`, String(D.assignee_groups.batch_japan || 0)],
  ["④ 한국·중국", "엠앤이, 한성테크, 중앙대 산학협력단 등", `${cnt.by_batch.batch_krcn.n} (${cnt.by_batch.batch_krcn.s})`, String(D.assignee_groups.batch_krcn || 0)],
  ["합계", "", `${cnt.raw_rows} (${cnt.raw_sources})`, String(cnt.model_rows)],
], [1700, 4300, 1700, 1700], { highlightRows: [4] }));
add(P("검색은 \"perfluoroelastomer composition semiconductor seal plasma\", \"fluororubber composition sealing material semiconductor manufacturing apparatus\", \"반도체 불소고무 조성물 오링 압축영구줄음률\", \"全氟醚橡胶 半导体 密封\" 등의 질의로 후보를 찾은 뒤, 실시예 표에 배합량(phr)과 상태(normal state) 물성이 함께 수록된 문서만 채택하였다. 중국 특허는 대부분 표가 이미지로 제공되어 1건만 텍스트 추출이 가능하였고, 이마저 반도체용이 아니어서 최종 모델에서는 제외되었다."));

add(H2("2.2 데이터 스키마"));
add(P("한 행은 특허 하나의 실시예(또는 비교예) 하나이다. 모든 배합량은 고무(원재료) 100 중량부 기준 중량부(phr)로 통일하였다."));
add(TABLE("변수 정의", ["구분", "변수", "설명"], [
  ["원재료", "polymer_type / polymer_grade", "FFKM(과불소고무), FKM(불소고무) / 상품명·조성 (예: DAI-EL PERFLO GA-105)"],
  ["가교계", "cure_system", "peroxide, nitrile_triazine, nitrile_bisaminophenol, nitrile_organotin, nitrile_other, bisphenol, other"],
  ["필러(부재료)", "carbon_black, silica, alumina, barium_sulfate, titanium_oxide, fluororesin, other_inorganic_filler, organic_additive", "카본블랙(MT N990 등), 실리카, 알루미나, 황산바륨, 산화티탄, 불소수지(PTFE·PFA 등), 기타 무기(AlF₃·Si₃N₄·SiC 등), 유기첨가제(안료·폴리이미드 등) [phr]"],
  ["가교제(부재료)", "coagent, peroxide, nitrile_curative, other_curative", "가교조제(TAIC 등), 유기과산화물, 니트릴 경화제·촉매, 기타 가교제(비스페놀 AF 등) [phr]"],
  ["기타 부재료", "acid_acceptor, processing_aid", "수산제(MgO, Ca(OH)₂, ZnO), 가공조제(왁스, 이형제, PFPE 오일 등) [phr]"],
  ["물성(목표)", "hardness_shoreA", "경도, Shore A (JIS K6253 / ASTM D2240 type A)"],
  ["", "tensile_MPa / elongation_pct / m100_MPa", "인장강도 [MPa] / 파단 신율 [%] / 100% 신장 응력 [MPa]"],
  ["", "compression_set_pct + cs_condition", "압축영구줄음률 [%] 및 시험 조건(온도×시간, 압축률, 시편)"],
  ["추적 정보", "source_id, example_label, units_original, extraction_notes", "특허번호·실시예 번호, 원 단위와 환산식, 전사 시 특이사항"],
], [1500, 3300, 4600], { size: 16 }));

add(H2("2.3 단위 환산과 전사 원칙"));
add(B("kgf/cm² → MPa: × 0.0980665, psi → MPa: × 0.00689476 (소수 둘째 자리 반올림). 환산 내역은 units_original 열에 기록."));
add(B("상태(normal state) 물성만 목표값으로 사용하고, 열노화 후 물성·고온 압축영구줄음률(250~316 °C 추가 조건)·플라즈마 무게감소율 등은 참고값으로 extraction_notes 또는 별도 열에 보관."));
add(B("0 = 해당 성분 미사용, 빈칸 = 함량 불명. 추정·보간·임의 생성 값은 일절 넣지 않았다."));
add(B("특허 내 표와 본문이 불일치하는 경우(예: TAIC 2.5 vs 2 phr) 표 값을 우선하고 그 사실을 extraction_notes에 남겼다."));

add(H2("2.4 품질 검증"));
add(P(`전사 정확도를 확인하기 위해 원문 대조 감사를 수행하였다. 기준 특허 US7678858B2의 실시예 12행(경도, 인장강도, 신율, M100, 압축영구줄음률, 플라즈마 무게감소율)을 원문 표와 전수 대조하였고(예: 인장강도 250 kgf/cm² → 24.52 MPa), 다른 그룹에서 무작위로 추출한 4행(US6281296B1 Control A, US6191208B1 Example 1, US7666948B2 Example 4, EP4249550A1 Example 13)도 원문 표 값과 대조하였다. 불일치는 발견되지 않았다.`));

add(H2("2.5 정제 규칙"));
add(P(`수집된 ${cnt.raw_rows}건에 아래 규칙을 순서대로 적용하여 모델링 데이터 ${cnt.model_rows}건을 확정하였다. 모든 처리 내역은 data/cleaning_log.txt에 행 단위로 기록되어 있다.`));
add(TABLE("정제 단계별 처리 내역", ["단계", "규칙", "영향"], [
  ["1", "반도체 장비용이 아닌 문서(자동차 연료 인젝터, 오일씰, 유정용) 제외", `${cnt.excl_nonsemi}행 제외`],
  ["2", "가교계 화학종은 불명이나 가교 패키지 총량이 other_curative_phr에 기재된 경우, 나머지 가교 열을 0으로 처리(cure_system = other)", `${cnt.pkg_rule}행 보존`],
  ["3", "함량이 불명(빈칸)인 성분이 있는 행 제외 (예: 촉매량이 mmol로만 제시, TAIC·과산화물 합산 표기)", `${cnt.excl_unknown}행 제외`],
  ["4", "고무가 FFKM·FKM 블렌드, 실리콘·EPDM 혼합 등 단일 불소고무가 아닌 경우 제외", `${cnt.excl_blend}행 제외`],
  ["5", "Shore A가 아닌 경도(마이크로 경도계, Shore M) 값 제외", `${cnt.hard_blank}개 값 제외`],
  ["6", "M100이 보고되었는데 신율 < 100%인 물리적 모순값(오기) 제외", `${cnt.el_fix}개 값 제외`],
  ["7", "패밀리 특허 간 동일 배합·동일 물성 중복 행 제거", `${cnt.fam_dup}행 제거`],
  ["8", "압축영구줄음률은 시험온도가 명시되고 시험시간 60~100 h인 행만 사용, 시험온도(cs_temp_C)를 입력변수로 추가", `CS 모델 ${R.compression_set_pct ? R.compression_set_pct.n_total : "-"}행`],
], [700, 6500, 2200]));
add(P(`최종 모델링 데이터는 FFKM ${cnt.ffkm}건, FKM ${cnt.fkm}건이며, 가교계는 과산화물 ${cnt.cure_counts.peroxide || 0}건, 니트릴계(트리아진·비스아미노페놀·유기주석·기타) ${(cnt.cure_counts.nitrile_triazine || 0) + (cnt.cure_counts.nitrile_bisaminophenol || 0) + (cnt.cure_counts.nitrile_organotin || 0) + (cnt.cure_counts.nitrile_other || 0)}건, 비스페놀 ${cnt.cure_counts.bisphenol || 0}건, 기타 ${cnt.cure_counts.other || 0}건이다. 물성은 모든 행에 다 있지 않으므로 물성마다 사용 가능한 행 수가 다르다(아래 표).`));
const st = D.stats;
add(TABLE("물성별 데이터 수와 분포 (모델링 데이터)", ["물성", "n", "평균", "표준편차", "최소", "최대"],
  Object.keys(st).map((t) => [K[t], String(st[t].n), f(st[t].mean, 2), f(st[t].std, 2), f(st[t].min, 2), f(st[t].max, 2)]),
  [2800, 900, 1400, 1400, 1400, 1400], { align: [0, 1, 1, 1, 1, 1].map((a) => a ? AlignmentType.CENTER : AlignmentType.LEFT) }));

// ------------------------------------------------------------------ 3. EDA
add(H1("3. 탐색적 데이터 분석"));
add(...FIG(fig("F1_data_overview.png"), "물성별 분포와 고무 종류·가교계별 데이터 수", 6.3));
add(P(INTERP.eda_dist));
add(...FIG(fig("F2_correlation.png"), "배합 성분과 물성 간 Spearman 순위상관계수", 4.9));
add(P(INTERP.eda_corr));

// ------------------------------------------------------------------ 4. methods
add(H1("4. 모델링 방법"));
add(H2("4.1 가우시안 프로세스 회귀"));
add(P("GP 회귀는 배합 벡터 x(성분별 phr 등)에서 물성 y로 가는 미지 함수 f를 \"함수 공간 위의 정규분포\"로 보고, 관측 데이터로 조건화하여 사후분포를 얻는다. 관측 잡음 ε는 특허마다 다른 시험 편차·미기재 공정조건을 흡수한다."));
add(EQ("f(x) ~ GP(0, k(x, x′)),   y = f(x) + ε,   ε ~ N(0, σₙ²)"));
add(P("새 배합 x*의 예측 평균과 분산은 다음과 같이 닫힌 형태로 계산된다. K는 학습 데이터 간 커널 행렬, k*는 x*와 학습 데이터 간 커널 벡터이다."));
add(EQ("μ(x*) = k*ᵀ (K + σₙ²I)⁻¹ y,     σ²(x*) = k(x*, x*) − k*ᵀ (K + σₙ²I)⁻¹ k*"));
add(P("커널 내부 하이퍼파라미터 θ = {신호분산 σf², 길이척도 ℓ, 잡음분산 σₙ², (RQ의 α), (선형항의 σ₀²)}는 로그 주변우도(log marginal likelihood)를 최대화하여 학습 데이터에서 자동 결정된다. 이 값은 L-BFGS-B(최대 300회 반복)로 최적화하며, 지역해를 피하기 위해 무작위 초기값에서 재시작(n_restarts)한다."));
add(EQ("log p(y | X, θ) = −½ yᵀ(K + σₙ²I)⁻¹y − ½ log|K + σₙ²I| − (n/2) log 2π"));
add(P("출력 y는 학습 시 평균 0·분산 1로 정규화(normalize_y)하고, 예측 시 원래 단위로 되돌린다. 따라서 학습된 σf², σₙ²은 정규화된 단위이며, σₙ²/(σf²+σₙ²)는 \"데이터 분산 중 설명되지 않는 잡음의 비율\"로 해석할 수 있다."));

add(H2("4.2 커널 후보"));
add(P("r은 길이척도로 나눈 두 배합 사이의 거리이다. ARD(Automatic Relevance Determination)는 성분마다 별도의 길이척도 ℓd를 두어 성분별 영향 범위를 따로 학습하는 방식이고, 등방성(isotropic)은 모든 성분에 하나의 ℓ을 쓴다. 입력은 표준화되므로 ℓ=1은 \"표준편차 1만큼 변하면 상관이 크게 줄어듦\"을 뜻한다."));
add(EQ("r² = Σ_d (x_d − x′_d)² / ℓ_d²"));
add(TABLE("커널 함수", ["커널", "식 k(r)", "특성"], [
  ["RBF (제곱지수)", "σf² · exp(−r²/2)", "무한히 매끄러운 함수 가정"],
  ["Matérn ν=1/2", "σf² · exp(−r)", "거친(연속이나 미분 불가) 함수, 급변하는 응답에 유리"],
  ["Matérn ν=3/2", "σf² · (1 + √3 r) · exp(−√3 r)", "1회 미분 가능, 중간 매끄러움"],
  ["Matérn ν=5/2", "σf² · (1 + √5 r + 5r²/3) · exp(−√5 r)", "2회 미분 가능, 물성 응답면에 흔히 사용"],
  ["Rational Quadratic", "σf² · (1 + r²/(2α))^(−α)", "여러 길이척도의 RBF 혼합 (scikit-learn 구현은 등방성만 지원)"],
  ["+ 선형항(DotProduct)", "σ₀² + x·x′", "전역적인 선형 추세(예: 필러량 ↑ → 경도 ↑)를 별도로 표현"],
  ["+ White noise", "σₙ² · δ(x, x′)", "관측 잡음 — 모든 모델에 포함, 하한(noise_floor)을 하이퍼파라미터로 탐색"],
], [2200, 3600, 3600], { size: 16 }));

add(H2("4.3 하이퍼파라미터의 두 계층"));
add(P("본 연구에서 \"하이퍼파라미터\"는 두 계층으로 구분하여 다루었다."));
add(B("**계층 1 (커널 내부, 연속값)**: σf², ℓ(ARD면 성분 수만큼), σₙ², α, σ₀² — 각 GP 학습 시 로그 주변우도 최대화로 자동 추정한다."));
add(B("**계층 2 (모델 설계, 혼합형)**: 커널 종류, ARD 여부, 선형항 여부, 입력 변환(표준화 / log(1+x) 후 표준화), 출력 변환(없음 / 로그), 특성 집합, ℓ 초기값, σₙ 초기값, σₙ 하한 — 교차검증 성능을 목적함수로 하는 베이지안 최적화로 탐색한다."));
add(TABLE("계층 2 탐색 공간 (베이지안 최적화 대상)", ["하이퍼파라미터", "유형", "후보 / 범위", "의미"], [
  ["kernel", "범주", "RBF, Matérn 1/2, 3/2, 5/2, RQ", "응답면의 매끄러움 가정"],
  ["ard", "범주", "True / False", "성분별 길이척도 여부"],
  ["linear", "범주", "False / True", "선형 추세항 추가 여부"],
  ["x_transform", "범주", "std / log1p", "phr 분포가 0에 몰리고 꼬리가 긴 점(불소수지 최대 300 phr) 보정"],
  ["y_transform", "범주", "none / log", "양수 물성의 우측 꼬리·이분산 보정"],
  ["feature_set", "범주", "full / full_agg / full_cure6 / compact", "입력 표현(아래 '입력 특성 집합' 표)"],
  ["ls_init", "연속", "log₁₀ ℓ₀ ∈ [−1, 1]", "길이척도 최적화 시작점"],
  ["noise_init", "연속", "log₁₀ σₙ₀² ∈ [−3, 0]", "잡음분산 최적화 시작점"],
  ["noise_floor", "연속", "log₁₀ σₙ²_min ∈ [−6, −2]", "잡음 하한 — 과적합(보간) 방지 강도"],
], [1600, 900, 3400, 3500], { size: 16 }));
add(TABLE("입력 특성 집합", ["이름", "구성", "차원"], [
  ["full", "개별 성분 14종(phr) + FFKM 여부 + 과산화물/니트릴 가교 지시변수", "17"],
  ["full_agg", "full + 총 필러량 + 총 가교계량", "19"],
  ["full_cure6", "개별 성분 14종 + FFKM 여부 + 가교계 6종 지시변수(과산화물, 트리아진, 비스아미노페놀, 유기주석, 기타 니트릴, 비스페놀)", "21"],
  ["compact", "카본블랙, 백색 무기필러 합, 불소수지, 유기첨가제, 가교조제, 과산화물, 니트릴 가교제, 기타 가교제, 수산제, 총 필러량 + 지시변수", "13"],
], [1400, 7000, 1000], { size: 16 }));
add(P("압축영구줄음률 모델에는 위 특성에 시험온도(cs_temp_C)를 추가하였다. 학습 데이터에서 값이 변하지 않는 열은 자동으로 제거된다."));

add(H2("4.4 베이지안 최적화 알고리즘"));
add(P("계층 2 하이퍼파라미터 조합 하나를 평가하는 데는 GP를 5번(5-fold) 학습해야 하므로 비용이 크다. 따라서 평가 결과를 다시 GP로 근사하고, 기대개선(Expected Improvement, EI)이 가장 큰 조합을 다음 시도로 고르는 BO를 사용하였다."));
add(EQ("EI(z) = (μ(z) − f⁺ − ξ) Φ(Z) + σ(z) φ(Z),     Z = (μ(z) − f⁺ − ξ) / σ(z)"));
add(P("여기서 z는 인코딩된 하이퍼파라미터 벡터, μ·σ는 BO 대리모델의 예측 평균·표준편차, f⁺는 현재까지의 최고 CV R², Φ·φ는 표준정규 누적분포·밀도함수, ξ는 탐색 강도이다."));
add(TABLE("BO 설정값", ["항목", "설정", "선택 이유"], [
  ["목적함수", "개발셋 5-fold 교차검증 out-of-fold R² (최대화)", "모든 trial이 동일 fold 분할을 사용 → 설정 간 공정 비교"],
  ["대리모델", "GP: Constant × Matérn 5/2 (ARD) + White, y 정규화, 재시작 3회", "범주형 one-hot + 연속형 [0,1] 혼합 입력에 안정적"],
  ["인코딩", "범주형 → one-hot, 연속형 → [0, 1] 선형 스케일", "총 20차원 대리모델 입력"],
  ["획득함수", "Expected Improvement, ξ = 0.01", "탐색(exploration)과 활용(exploitation) 균형"],
  ["획득함수 최적화", "무작위 후보 3,000개 + 현재 최적 설정의 1-변수 변이 1,000개 중 EI 최대 (중복 평가 금지)", "범주형이 섞인 공간에서 경사 없이 전역·국소 탐색 병행"],
  ["초기 설계", "무작위 8회", "대리모델 학습용 초기 데이터"],
  ["예산", "실행당 30 trial × 독립 시드 3회(seed 0, 1, 2)", "\"여러 번 반복\"하여 최적 설정의 재현성 확인"],
  ["GP 학습(탐색 중)", "L-BFGS-B 최대 300회, 재시작 1회", "탐색 비용 절감 — 최종 후보는 재시작 3회로 재평가"],
], [1800, 4400, 3200], { size: 16 }));

add(H2("4.5 실험 프로토콜"));
add(P("과적합된 평가를 막기 위해 물성마다 데이터를 개발셋 80%와 테스트셋 20%로 먼저 나누었다(물성값 5분위 층화, seed 42). 테스트셋은 하이퍼파라미터 선택 과정에 전혀 사용하지 않고 최종 평가에만 사용하였다."));
add(TABLE("실험 단계 구성", ["단계", "내용", "평가 데이터"], [
  ["Exp-0 기준모델", "① scikit-learn 기본 GP(RBF ℓ=1·σf=1 고정, α=1e-10, y 정규화 없음) ② Ridge(log1p+표준화, α=10⁻³~10³ 내부 CV) ③ Random Forest(500 trees)", "개발셋 5-fold×2 / 테스트"],
  ["Exp-1 커널 스크리닝", "커널 5종 × ARD 유무 = 9개 설정, 나머지는 기본값(log1p, y 변환 없음, full, ℓ₀=1, σₙ₀²=0.1, 하한 1e-4)", "개발셋 5-fold"],
  ["Exp-2 BO 반복 실험", "4.3절 탐색 공간에서 BO 30 trial × 시드 3회 = 90 trial", "개발셋 5-fold"],
  ["Exp-3 강건성 재평가", "Exp-1·2 전체에서 구조(커널·ARD·선형·변환·특성집합)가 다른 상위 3개 설정을 5-fold × 5회(셔플 상이), 재시작 3회로 재평가 → 평균 R² 최고 설정을 최종 선택", "개발셋 5-fold×5"],
  ["Exp-4 최종 검증", "최종 설정을 개발셋 전체로 학습 → 테스트셋 평가 / 특허 단위 그룹 교차검증(Leave-source-out, 5 groups) / 전체 데이터로 최종 모델 학습", "테스트셋, 그룹 CV"],
  ["Exp-5 회고적 BO", "데이터셋을 \"미지의 후보 풀\"로 보고, 초기 5개에서 시작해 BO(EI)·탐욕(평균)·무작위 선택으로 최고 물성 배합을 찾는 실험 30회 반복", "전체 데이터"],
  ["Exp-6 배합 설계", "제약 기대개선(cEI)으로 사양을 만족하면서 인장강도를 높일 차기 실험 배합 제안", "최종 모델"],
], [1900, 5700, 1800], { size: 16 }));
add(H3("평가지표"));
add(B("R² (결정계수), RMSE, MAE — 예측 평균의 정확도"));
add(B("95% 예측구간 포함률 — 실측값이 μ ± 1.96σ 안에 들어온 비율. 0.95에 가까울수록 불확실성 추정이 정직함(calibration)"));
add(B("NLPD (음의 로그 예측밀도) — 평균과 불확실성을 함께 평가, 낮을수록 좋음"));
add(B("Leave-source-out R² — 학습에 쓰지 않은 특허(출원인·시험법이 다른 데이터)에 대한 외삽 성능"));

// ------------------------------------------------------------------ 5. results
add(H1("5. 실험 결과"));
add(H2("5.1 Exp-0 기준모델"));
add(TABLE("기준모델 교차검증 R² (개발셋 5-fold × 2회)", ["물성", "sklearn 기본 GP", "Ridge", "Random Forest", "참고: Exp-1 최고"],
  T.map((t) => [K[t], f(R[t].baselines_cv.GP_sklearn_default, 1), f(R[t].baselines_cv.Ridge), f(R[t].baselines_cv.RandomForest), f(R[t].screen_best.R2)]),
  [2600, 1700, 1500, 1700, 1900], { align: [0, 1, 1, 1, 1].map((a) => a ? AlignmentType.CENTER : AlignmentType.LEFT) }));
add(P(INTERP.baseline));

add(H2("5.2 Exp-1 커널 스크리닝"));
add(...FIG(fig("F3_kernel_screen.png"), "커널 종류·ARD 여부에 따른 교차검증 R² (기본 설정)", 6.3));
add(P(INTERP.screen));

add(H2("5.3 Exp-2 베이지안 최적화 반복 실험"));
add(...FIG(fig("F4_bo_convergence.png"), "물성별 BO 수렴 곡선 — 시드 3회 독립 반복", 6.4));
const boRows = [];
T.forEach((t) => R[t].bo_runs.forEach((b) => boRows.push([KS[t], String(b.seed), f(b.first_init_best), f(b.best), String(b.iter), b.cfg_text,
  `${b.cfg.x_transform}/${b.cfg.y_transform}/${b.cfg.feature_set}`])));
add(TABLE("시드별 BO 결과 (초기 무작위 8회 최고 → BO 30회 최고)", ["물성", "seed", "초기8 최고", "BO 최고", "도달 trial", "최고 설정 (커널)", "x변환/y변환/특성"],
  boRows, [1300, 600, 1000, 1000, 900, 2700, 1900], { size: 15 }));
add(P(INTERP.bo));
const HPN = { kernel: "커널 종류", ard: "ARD", linear: "선형항", x_transform: "입력 변환", y_transform: "출력 변환", feature_set: "특성 집합" };
const lv = (h, v) => ({ True: "사용", False: "미사용", std: "std", log1p: "log1p", none: "없음", log: "log" }[v] || (h === "kernel" ? D.kernel_kor[v] : v));
add(TABLE("하이퍼파라미터 민감도 — 선택지별 CV R² 중앙값의 최대 차이와 가장 좋은 선택지 (Exp-1·2, 물성당 99 trial)",
  ["하이퍼파라미터", ...T.map((t) => KS[t])],
  Object.keys(HPN).map((h) => [HPN[h], ...T.map((t) => { const e = D.hp_effect[t][h]; return `${f(e.range)} (${lv(h, e.best)})`; })]),
  [1700, ...T.map(() => 1540)], { size: 15 }));
add(P(INTERP.hp_effect));

add(H2("5.4 Exp-3 강건성 재평가와 최종 선택"));
add(P("BO는 한 번의 5-fold 분할에서 R²를 최대화하므로, 분할 운이 좋았던 설정이 과대평가될 수 있다(winner's curse). 이를 줄이기 위해 구조가 다른 상위 3개 설정을 서로 다른 5가지 셔플로 다시 평가하였다(25회 학습/설정)."));
const robRows = [];
T.forEach((t) => R[t].robust.forEach((r, i) => robRows.push([i === 0 ? KS[t] : "", r.cfg_text, `${r.x}/${r.y}/${r.fs}`, f(r.search), `${f(r.robust)} ± ${f(r.std)}`, pct(r.cov)])));
const hl = []; let ri = 0;
T.forEach((t) => { const bi = R[t].robust.reduce((b, r, i, a) => r.robust > a[b].robust ? i : b, 0); hl.push(ri + bi); ri += R[t].robust.length; });
add(TABLE("상위 설정 재평가 결과 (음영 = 최종 선택)", ["물성", "커널", "x/y/특성집합", "탐색 R²", "재평가 R² (5×5)", "95% 포함률"],
  robRows, [1300, 2900, 2000, 1000, 1500, 1100], { size: 15, highlightRows: hl }));
add(P(INTERP.robust));

add(H2("5.5 Exp-4 최종 검증"));
add(...FIG(fig("F5_parity.png"), "실측값 대비 GP 예측값 (파랑: 개발셋 out-of-fold, 주황: 테스트셋, 오차막대: 95% 예측구간)", 6.4));
add(TABLE("최종 모델 성능", ["물성", "Test R²", "Test RMSE", "Test MAE", "95% 포함률", "NLPD", "Leave-source-out R²"],
  T.map((t) => [K[t], f(R[t].test.R2), f(R[t].test.RMSE, 2), f(R[t].test.MAE, 2), pct(R[t].test.cov95), f(R[t].test.NLPD, 2), f(R[t].lso.R2)]),
  [2300, 1000, 1100, 1100, 1200, 900, 1800], { align: [0, 1, 1, 1, 1, 1, 1].map((a) => a ? AlignmentType.CENTER : AlignmentType.LEFT) }));
add(...FIG(fig("F6_model_compare.png"), "테스트셋 R² 비교 — BO 최적 GP vs 비교모델 (막대 위 숫자: 실제 R²)", 6.3));
add(TABLE("적용범위(applicability domain) 분석 — 테스트 점의 모든 입력이 개발셋 최소~최대 범위 안에 있는지",
  ["물성", "테스트 n", "범위 밖 n", "전체 R²", "범위 내 R²", "범위 밖 사례"],
  T.map((t) => [K[t], String(R[t].n_test), String(R[t].ad_n_out), f(R[t].test.R2), f(R[t].ad_r2_in), (R[t].ad_out_rows || []).slice(0, 3).join(", ") + ((R[t].ad_out_rows || []).length > 3 ? " 외" : "")]),
  [1900, 900, 900, 1000, 1100, 3600], { size: 15 }));
add(P(INTERP.final));

// ------------------------------------------------------------------ 6. best model detail
add(H1("6. 최적 모델 상세 — 하이퍼파라미터 설정과 해석"));
add(P("다음은 물성별로 최종 선택된 계층 2 설정과, 그 설정으로 전체 데이터를 학습했을 때 로그 주변우도 최대화로 얻어진 계층 1 값이다. 이 설정을 그대로 사용하면 동일한 모델을 재현할 수 있다(엑셀 Best_Models 시트, outputs/results.json)."));
T.forEach((t) => {
  const E = R[t], c = E.best;
  add(H2(`6.${T.indexOf(t) + 1} ${K[t]}`));
  add(TABLE(`${KS[t]} 최종 하이퍼파라미터`, ["구분", "항목", "값"], [
    ["설계(BO 탐색)", "커널", E.best_text],
    ["", "입력 변환 / 출력 변환", `${c.x_transform === "log1p" ? "log(1+phr) 후 표준화" : "표준화"} / ${c.y_transform === "log" ? "로그 변환" : "변환 없음"}`],
    ["", "특성 집합", `${D.fs_kor[c.feature_set]} → 실제 사용 ${E.features.length}개`],
    ["", "ℓ 초기값 / σₙ² 초기값 / σₙ² 하한", `10^${f(c.ls_init, 2)} = ${f(Math.pow(10, c.ls_init), 3)} / 10^${f(c.noise_init, 2)} = ${f(Math.pow(10, c.noise_init), 4)} / 10^${f(c.noise_floor, 2)}`],
    ["", "재시작 횟수 / 최적화기", `${c.n_restarts}회 / L-BFGS-B (max 300 iter)`],
    ["학습값(전체 데이터)", "신호분산 σf² (정규화 단위)", f(E.amp, 4)],
    ["", "잡음분산 σₙ² (정규화 단위)", `${f(E.noise, 4)}  → 잡음 비율 σₙ²/(σf²+σₙ²) = ${pct(E.noise_frac, 1)}`],
    ["", "길이척도 ℓ", Array.isArray(E.ls) ? `ARD ${E.ls.length}개 (아래 표 참조)` : f(E.ls, 3)],
    ...(E.rq_alpha !== null && E.rq_alpha !== undefined ? [["", "RQ α", f(E.rq_alpha, 3)]] : []),
    ["", "로그 주변우도", f(E.lml, 2)],
    ["", "학습된 커널 (원문)", E.final_kernel.length > 160 ? E.final_kernel.slice(0, 160) + " …" : E.final_kernel],
    ["성능", "CV R² (5×5) / Test R² / LSO R²", `${f(E.best_cv.R2)} ± ${f(E.best_cv.R2_std)} / ${f(E.test.R2)} / ${f(E.lso.R2)}`],
  ], [1800, 2900, 4700], { size: 16 }));
  if (E.ard) {
    const ls0 = Math.pow(10, E.best.ls_init);
    const note = (v) => Math.abs(v - ls0) / ls0 < 5e-3 ? "초기값 그대로 (기울기 소실 → 그룹 분리)" : (v <= 0.0101 ? "하한 도달 (그룹 분리)" : (v >= 300 ? "사실상 무시" : "학습됨"));
    const items = Object.entries(E.ard).sort((a, b) => a[1] - b[1]);
    add(TABLE(`${KS[t]} ARD 길이척도 전체 (짧을수록 민감, ℓ 초기값 ${f(ls0, 3)})`, ["성분", "ℓ (표준화 단위)", "1/ℓ", "상태"],
      items.map(([k, v]) => [D.feat_kor[k] || k, f(v, 3), f(1 / v, 3), note(v)]), [2800, 1900, 1500, 3200], { size: 15 }));
  }
  if (INTERP.detail && INTERP.detail[t]) add(P(INTERP.detail[t]));
});
add(H2("6.6 성분 영향도와 부분의존도"));
add(...FIG(fig("F7_importance.png"), "순열 중요도 — 해당 성분 값을 섞었을 때 교차검증 R²가 감소한 정도", 6.4));
add(...FIG(fig("F8_pdp.png"), "부분의존도 — 한 성분만 바꾸고 나머지는 실제 배합을 유지했을 때 평균 예측 ±1σ", 6.4));
add(P(INTERP.importance));

// ------------------------------------------------------------------ 7. BO design
add(H1("7. 베이지안 최적화를 이용한 배합 설계"));
add(H2("7.1 회고적 BO 벤치마크 (Exp-5)"));
add(P("BO가 실제 배합 개발에서 실험 횟수를 줄일 수 있는지 확인하기 위해, 수집 데이터 전체를 \"물성을 아직 모르는 후보 배합의 풀\"로 간주하고 가상의 개발을 반복하였다. 무작위로 고른 5개 배합에서 시작하여 매 단계 한 개의 배합을 \"실험\"(=정답 공개)하며, 최종 GP 설정으로 학습한 모델의 EI가 가장 큰 배합을 고르는 BO, 예측 평균이 가장 좋은 배합을 고르는 탐욕(greedy) 전략, 무작위 선택을 비교하였다(각 30회 반복, 35회 추가 실험)."));
add(...FIG(fig("F9_pool_bo.png"), "회고적 BO 벤치마크 — 추가 실험 횟수에 따른 현재까지 최고 물성 (선: 30회 평균, 음영: 사분위 범위)", 6.4));
if (D.pool_bo) {
  const pr = [];
  Object.entries(D.pool_bo).forEach(([t, d]) => ["bo_ei", "greedy", "random"].forEach((s, i) => pr.push([i === 0 ? `${KS[t]} ${d.maximize ? "최대화" : "최소화"}` : "",
    { bo_ei: "BO (EI)", greedy: "Greedy", random: "Random" }[s], pct(d[s].success_rate_top5), d[s].exp_to_top5_mean === null ? "-" : f(d[s].exp_to_top5_mean, 1)])));
  add(TABLE("상위 5% 배합 도달 성능 (35회 추가 실험 이내)", ["목표", "전략", "도달 성공률", "평균 추가 실험 수"], pr, [2800, 2000, 2200, 2400]));
}
add(P(INTERP.pool));
add(H2("7.2 제약 기대개선을 이용한 차기 실험 배합 제안 (Exp-6)"));
add(P("최종 GP 모델들을 이용해, 반도체 O-링에서 흔히 요구되는 사양(경도 70~80 Shore A, 신율 ≥ 150%)을 만족할 확률이 높으면서 인장강도의 기대개선이 가장 큰 배합을 탐색하였다(200 °C 압축영구줄음률 ≤ 30% 조건은 해당 모델의 CV R²가 0.5 미만이어서 제약에서 제외). 후보는 데이터에서 가장 많은 고무·가교계 조합의 실제 배합을 무작위로 변형(성분량 로그정규 섭동, 필러 추가)하여 30,000개를 생성함으로써, 학습 데이터 범위를 크게 벗어나는 외삽을 피하였다."));
add(EQ("cEI(x) = EI_인장강도(x) × Π_j P(l_j ≤ g_j(x) ≤ u_j)"));
if (D.recs) {
  const fx = (r, k) => (r[k] === undefined || r[k] === null) ? "-" : Number(r[k]).toFixed(1);
  const rr = D.recs.map((r) => {
    const parts = [];
    [["carbon_black_phr", "CB"], ["silica_phr", "SiO₂"], ["alumina_phr", "Al₂O₃"], ["barium_sulfate_phr", "BaSO₄"], ["titanium_oxide_phr", "TiO₂"], ["fluororesin_phr", "불소수지"],
      ["other_inorganic_filler_phr", "기타무기"], ["organic_additive_phr", "유기"], ["coagent_phr", "조제"], ["peroxide_phr", "과산화물"], ["nitrile_curative_phr", "니트릴가교"],
      ["other_curative_phr", "기타가교"], ["acid_acceptor_phr", "수산제"], ["processing_aid_phr", "가공조제"]]
      .forEach(([k, l]) => { if (r[k] > 0.05) parts.push(`${l} ${Number(r[k]).toFixed(1)}`); });
    return [String(r.rank), parts.join(", "), `${fx(r, "pred_tensile_MPa")} ± ${fx(r, "std_tensile_MPa")}`,
      r.pred_hardness_shoreA !== undefined ? `${fx(r, "pred_hardness_shoreA")} ± ${fx(r, "std_hardness_shoreA")}` : "-",
      r.pred_elongation_pct !== undefined ? `${Number(r.pred_elongation_pct).toFixed(0)} ± ${Number(r.std_elongation_pct).toFixed(0)}` : "-",
      pct(r.P_feasible)];
  });
  add(TABLE(`BO 제안 배합 상위 5개 (${D.inverse_design.family}, 단위 phr / 고무 100) — 예측값이며 실측 아님`,
    ["순위", "배합 (phr, 고무 100 기준)", "인장강도 MPa", "경도 Shore A", "신율 %", "사양 만족확률"], rr,
    [600, 4300, 1300, 1200, 1100, 1100], { size: 15 }));
}
add(P(INTERP.design));

// ------------------------------------------------------------------ 8. discussion
add(H1("8. 고찰 및 한계"));
INTERP.discussion.forEach((d) => { add(H3(d.title)); add(P(d.text)); });

// ------------------------------------------------------------------ 9. conclusion
add(H1("9. 결론"));
INTERP.conclusion.forEach((c) => add(N(c, "nums2")));

// ------------------------------------------------------------------ appendix
add(H1("부록 A. 데이터 출처 목록"));
add(P("Google Patents 공개 전문(https://patents.google.com/patent/<특허번호>/en). \"모델\" 열이 0인 문서는 2.5절 정제 규칙에 의해 모델링에서 제외되었다."));
add(TABLE("수집 문서 목록", ["특허번호", "출원인", "발명의 명칭", "수집", "모델"],
  D.sources.map((s) => [s[0], s[1], s[2], String(s[3]), String(s[4])]), [1700, 2200, 4300, 600, 600], { size: 14 }));
add(H1("부록 B. 재현 방법"));
add(TABLE("파일 구성과 실행 순서", ["순서", "명령 / 파일", "설명"], [
  ["1", "python tools/patent_tables.py <특허번호> data/raw/pat", "특허 HTML 다운로드 및 표 추출"],
  ["2", "data/raw/batch_*.csv, data/raw/SCHEMA.md", "추출 원자료(그룹별)와 스키마"],
  ["3", "python src/build_dataset.py", "병합·정제 → data/gasket_dataset_raw.csv, data/gasket_dataset_clean.csv, cleaning_log.txt"],
  ["4", "python src/run_experiments.py <물성>", "Exp-0~4 (물성별 병렬 실행 가능) → outputs/results_*.json, trials_*.csv, pred_*.csv"],
  ["5", "python src/merge_results.py", "물성별 결과 병합"],
  ["6", "python src/design_bo.py", "Exp-5·6, 순열 중요도, 부분의존도"],
  ["7", "python src/make_figures.py / make_excel.py", "그림, 엑셀 생성"],
  ["8", "node build/build_report.js / build_deck.js", "보고서·발표자료 생성"],
  ["환경", "Python 3.11, scikit-learn 1.7.0, NumPy 2.4, pandas 2.2, SciPy / Node 22, docx 9.9, pptxgenjs 4.0", "핵심 GP·BO 구현: src/gp_core.py"],
], [800, 4300, 4300], { size: 15 }));

// ------------------------------------------------------------------ document
const doc = new Document({
  creator: "GP-BO Gasket Study", title: "반도체 공정용 불소고무 가스켓 배합비-물성 예측 모델 개발 보고서",
  styles, numbering, features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "불소고무 가스켓 배합비–물성 GP·BO 분석 보고서", font: FONT, size: 16, color: C.muted })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: C.muted })] })] }) },
    children,
  }],
});
const outFile = process.env.OUT_FILE || path.join(ROOT, "가스켓_GP_BO_분석보고서.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("saved", outFile); });
