// Summary deck (16:9) built as a structured pptxgenjs deck: theme + layouts + sections.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const OUT = process.env.OUT_DIR || path.join(ROOT, "outputs");
const D = JSON.parse(fs.readFileSync(path.join(OUT, "report_data.json"), "utf8"));
const INTERP = JSON.parse(fs.readFileSync(process.env.INTERP || path.join(__dirname, "interp.json"), "utf8"));
const R = D.res, T = D.targets, KS = D.kor_short, cnt = D.counts;
const f = (x, d = 2) => (x === null || x === undefined) ? "-" : Number(x).toFixed(d);

const THEME = {
  name: "Gasket GP-BO", headFontFace: "Malgun Gothic", bodyFontFace: "Malgun Gothic",
  colors: { dk1: "1B2631", lt1: "FFFFFF", dk2: "33495C", lt2: "EEF2F5", accent1: "0E7C86", accent2: "E0782B",
    accent3: "6C8EA4", accent4: "B8C7D3", accent5: "2E6B3F", accent6: "9B3D3D", hlink: "0E7C86", folHlink: "6C8EA4" },
};
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";               // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "불소고무 가스켓 배합비-물성 GP·BO 분석";
const Cs = pres.SchemeColor;

pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 8.8, h: 1.5, fontSize: 32, bold: true, color: Cs.background1, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.2, w: 8.8, h: 1.2, fontSize: 16, color: Cs.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CLOSING_DARK", background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 8.8, h: 0.8, fontSize: 28, bold: true, color: Cs.background1, valign: "middle", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 1.45, w: 8.8, h: 3.7, fontSize: 14, color: Cs.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.lt1 },
  margin: [0.5, 0.5, 0.55, 0.5],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28, w: 9.0, h: 0.62, fontSize: 24, bold: true, color: Cs.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "불소고무 가스켓 배합비–물성 GP·BO 분석", options: { x: 0.5, y: 5.22, w: 6, h: 0.25, fontSize: 9, color: Cs.accent3, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.25, fontSize: 9, color: HEX.accent3, align: "right" },
});

const sub = (s, text, y = 0.92) => s.addText(text, { x: 0.5, y, w: 9.0, h: 0.4, fontSize: 13, color: Cs.text2, margin: 0, isTextBox: true, objectName: "subtitle" });
const card = (s, x, y, w, h, name) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: Cs.background2 }, line: { color: Cs.background2 }, objectName: name });
// place a PNG inside a (w x maxH) box, keeping its aspect ratio, centred horizontally
const img = (s, file, x, y, w, name, maxH = 5.1 - y) => {
  const b = fs.readFileSync(file);
  const iw = b.readUInt32BE(16), ih = b.readUInt32BE(20);
  let W = w, H = w * ih / iw;
  if (H > maxH) { H = maxH; W = H * iw / ih; }
  s.addImage({ path: file, x: x + (w - W) / 2, y, w: W, h: H, objectName: name, altText: name });
  return H;
};
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", titleFontFace: "+mn-lt" };

// 1 ---------------------------------------------------------------- title
pres.addSection({ title: "개요" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "개요" });
s.addText("반도체 공정용 불소고무 가스켓\n배합비–물성 예측 모델", { placeholder: "title" });
s.addText("공개 특허 데이터 · 가우시안 프로세스 회귀 · 베이지안 최적화\n2026.10.08", { placeholder: "body" });
s.addNotes("공개 특허의 실시예 데이터로 FFKM/FKM 가스켓의 배합비-물성 관계를 학습한 GP 모델과, 그 하이퍼파라미터를 베이지안 최적화로 찾은 과정을 요약합니다.");

// 2 ---------------------------------------------------------------- at a glance
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "개요" });
s.addText("한눈에 보는 결과", { placeholder: "title" });
sub(s, INTERP.deck_glance);
const stats = [
  [String(cnt.raw_rows), "수집 데이터", `특허 ${cnt.raw_sources}건의 실시예·비교예`],
  [String(cnt.model_rows), "모델링 데이터", `정제 후 ${cnt.model_sources}개 특허
FFKM ${cnt.ffkm} · FKM ${cnt.fkm}`],
  [String(cnt.n_trials_total), "하이퍼파라미터 실험", "물성별 BO 3회 독립 반복"],
  [f(Math.max(...T.map((t) => R[t].test.R2)), 2), "최고 테스트 R²", INTERP.deck_best_label],
];
stats.forEach(([big, lab, small], i) => {
  const x = 0.5 + i * 2.3;
  card(s, x, 1.55, 2.1, 2.35, `stat-card-${i}`);
  s.addText(big, { x: x + 0.15, y: 1.75, w: 1.8, h: 0.9, fontSize: 40, bold: true, color: i === 3 ? Cs.accent2 : Cs.accent1, margin: 0, isTextBox: true, objectName: `stat-num-${i}` });
  s.addText(lab, { x: x + 0.15, y: 2.7, w: 1.8, h: 0.45, fontSize: 13, bold: true, color: Cs.text1, margin: 0, isTextBox: true, objectName: `stat-lab-${i}` });
  s.addText(small, { x: x + 0.15, y: 3.15, w: 1.8, h: 0.6, fontSize: 10, color: Cs.text2, margin: 0, valign: "top", isTextBox: true, objectName: `stat-sub-${i}` });
});
s.addText(INTERP.deck_glance_foot, { x: 0.5, y: 4.15, w: 9.0, h: 0.8, fontSize: 12, color: Cs.text1, margin: 0, valign: "top", isTextBox: true, objectName: "glance-foot" });

// 3 ---------------------------------------------------------------- data collection
pres.addSection({ title: "데이터" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "데이터" });
s.addText("특허 실시예 표에서 배합비–물성 데이터를 직접 추출", { placeholder: "title" });
const steps = [["특허 검색", "4개 출원인 그룹\n(Daikin · 미국계 · 일본 · 한중)"], ["표 직접 파싱", "Google Patents HTML\n<table> → 수치 원문 전사"],
  ["스키마 통일", "고무 100 기준 phr\nkgf/cm²·psi → MPa"], ["정제·검증", "원문 대조 감사\n8단계 정제 규칙"]];
steps.forEach(([h, d], i) => {
  const x = 0.5 + i * 2.32;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.2, w: 2.0, h: 1.35, rectRadius: 0.08, fill: { color: i === 3 ? Cs.accent1 : Cs.background2 }, line: { color: i === 3 ? Cs.accent1 : Cs.background2 }, objectName: `step-${i}` });
  s.addText(h, { x: x + 0.12, y: 1.3, w: 1.76, h: 0.4, fontSize: 14, bold: true, color: i === 3 ? Cs.background1 : Cs.text1, margin: 0, isTextBox: true, objectName: `step-h-${i}` });
  s.addText(d, { x: x + 0.12, y: 1.72, w: 1.76, h: 0.75, fontSize: 10.5, color: i === 3 ? Cs.background1 : Cs.text2, margin: 0, valign: "top", isTextBox: true, objectName: `step-d-${i}` });
  if (i < 3) s.addShape(pres.shapes.CHEVRON, { x: x + 2.06, y: 1.74, w: 0.2, h: 0.28, fill: { color: Cs.accent3 }, line: { color: Cs.accent3 }, objectName: `arrow-${i}` });
});
const grp = [["Daikin", "batch_daikin"], ["DuPont·3M·GT", "batch_dupont3mgt"], ["일본 실링사", "batch_japan"], ["한국·중국", "batch_krcn"]];
s.addChart(pres.charts.BAR, [
  { name: "수집", labels: grp.map((g) => g[0]), values: grp.map((g) => cnt.by_batch[g[1]].n) },
  { name: "모델링 사용", labels: grp.map((g) => g[0]), values: grp.map((g) => D.assignee_groups[g[1]] || 0) },
], { x: 0.5, y: 2.8, w: 5.6, h: 2.3, barDir: "bar", barGrouping: "clustered", chartColors: [HEX.accent4, HEX.accent1],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelColor: HEX.dk2, showLegend: true, legendPos: "b", legendFontSize: 9,
  catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent3, catAxisLabelFontSize: 10, valAxisLabelFontSize: 8, valGridLine: { color: "E3E8EC", size: 0.5 },
  catGridLine: { style: "none" }, showTitle: true, title: "출원인 그룹별 데이터 수 (행)", titleFontSize: 11, titleColor: HEX.dk1, ...chartText, objectName: "chart-groups" });
s.addText([
  { text: "정제 규칙 (412 → 333행)", options: { bold: true, breakLine: true, fontSize: 12, color: Cs.text1 } },
  { text: `비반도체 용도 문서 제외 ${cnt.excl_nonsemi}행`, options: { bullet: true, breakLine: true } },
  { text: `함량 불명 성분 포함 행 제외 ${cnt.excl_unknown}행`, options: { bullet: true, breakLine: true } },
  { text: `고무 블렌드 제외 ${cnt.excl_blend}행`, options: { bullet: true, breakLine: true } },
  { text: `비 Shore A 경도·모순값 제거, 패밀리 중복 ${cnt.fam_dup}행 제거`, options: { bullet: true, breakLine: true } },
  { text: "CS는 시험온도 명시·60~100 h만 사용", options: { bullet: true } },
], { x: 6.35, y: 2.85, w: 3.15, h: 2.2, fontSize: 10.5, color: Cs.text2, margin: 0, valign: "top", paraSpaceAfter: 3, isTextBox: true, objectName: "rules" });

// 4 ---------------------------------------------------------------- method
pres.addSection({ title: "방법" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "방법" });
s.addText("하이퍼파라미터를 두 계층으로 나누어 최적화", { placeholder: "title" });
sub(s, "커널 내부 값은 로그 주변우도로, 모델 설계 선택은 베이지안 최적화로 결정");
card(s, 0.5, 1.45, 4.35, 3.55, "layer1-card");
s.addText([
  { text: "계층 1 · 커널 내부 (연속값)", options: { bold: true, fontSize: 14, color: Cs.accent1, breakLine: true } },
  { text: "σf² 신호분산, ℓ 길이척도(ARD 시 성분별), σₙ² 잡음", options: { fontSize: 11, color: Cs.text1, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "방법: 로그 주변우도 최대화", options: { bold: true, fontSize: 11, color: Cs.text1, breakLine: true } },
  { text: "L-BFGS-B (최대 300회) + 무작위 재시작", options: { fontSize: 11, color: Cs.text2, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "출력 y 정규화 → σₙ²/(σf²+σₙ²) = 설명 안 되는 잡음 비율", options: { fontSize: 11, color: Cs.text2 } },
], { x: 0.7, y: 1.6, w: 3.95, h: 3.3, margin: 0, valign: "top", isTextBox: true, objectName: "layer1-text" });
card(s, 5.15, 1.45, 4.35, 3.55, "layer2-card");
s.addText([
  { text: "계층 2 · 모델 설계 (혼합형 9차원)", options: { bold: true, fontSize: 14, color: Cs.accent2, breakLine: true } },
  { text: "커널(RBF·Matérn 1/2·3/2·5/2·RQ), ARD, 선형항, 입력 log1p, 출력 log, 특성집합 4종, ℓ·σₙ 초기값, σₙ 하한", options: { fontSize: 11, color: Cs.text1, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "방법: 베이지안 최적화 (EI, ξ=0.01)", options: { bold: true, fontSize: 11, color: Cs.text1, breakLine: true } },
  { text: "대리모델 GP Matérn 5/2 ARD · 초기 무작위 8회 + 22회 EI", options: { fontSize: 11, color: Cs.text2, breakLine: true } },
  { text: "목적함수: 개발셋 5-fold CV R²", options: { fontSize: 11, color: Cs.text2, breakLine: true } },
  { text: "시드 3회 독립 반복 → 상위 3개 5×5 CV 재평가", options: { fontSize: 11, color: Cs.text2 } },
], { x: 5.35, y: 1.6, w: 3.95, h: 3.3, margin: 0, valign: "top", isTextBox: true, objectName: "layer2-text" });

// 5 ---------------------------------------------------------------- protocol
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "방법" });
s.addText("실험 설계: 테스트셋은 마지막까지 봉인", { placeholder: "title" });
const prot = [["Exp-0", "기준모델", "sklearn 기본 GP · Ridge · Random Forest"], ["Exp-1", "커널 스크리닝", "커널 5종 × ARD 유무 = 9개 설정"],
  ["Exp-2", "BO 반복 실험", "30 trial × 시드 3회 = 90 trial / 물성"], ["Exp-3", "강건성 재평가", "상위 3개 설정 5-fold × 5회 → 최종 선택"],
  ["Exp-4", "최종 검증", "20% 홀드아웃 테스트 · 특허 단위 그룹 CV"], ["Exp-5·6", "배합 설계 BO", "회고적 BO 벤치마크 · 제약 EI 배합 제안"]];
prot.forEach(([a, b, c], i) => {
  const y = 1.12 + i * 0.66;
  s.addShape(pres.shapes.OVAL, { x: 0.55, y: y + 0.05, w: 0.48, h: 0.48, fill: { color: i === 2 ? Cs.accent2 : Cs.accent1 }, line: { color: i === 2 ? Cs.accent2 : Cs.accent1 }, objectName: `prot-dot-${i}` });
  s.addText(String(i + 1), { x: 0.55, y: y + 0.05, w: 0.48, h: 0.48, fontSize: 13, bold: true, color: Cs.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `prot-num-${i}` });
  s.addText(`${a}  ${b}`, { x: 1.2, y, w: 2.7, h: 0.58, fontSize: 13, bold: true, color: Cs.text1, valign: "middle", margin: 0, isTextBox: true, objectName: `prot-h-${i}` });
  s.addText(c, { x: 3.95, y, w: 5.55, h: 0.58, fontSize: 12, color: Cs.text2, valign: "middle", margin: 0, isTextBox: true, objectName: `prot-d-${i}` });
});

// 6 ---------------------------------------------------------------- BO convergence
pres.addSection({ title: "결과" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("BO 반복 실험: 시드가 달라도 비슷한 최적값에 수렴", { placeholder: "title" });
sub(s, INTERP.deck_bo);
img(s, path.join(OUT, "figures", "F4_bo_convergence.png"), 0.5, 1.5, 9.0, "fig-bo-convergence");
s.addNotes("점은 개별 trial의 교차검증 R², 선은 시드별 누적 최고값입니다. 점선 이전은 초기 무작위 8회입니다.");

// 7 ---------------------------------------------------------------- best models table + chart
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("최적 하이퍼파라미터와 테스트 성능", { placeholder: "title" });
const hdr = ["물성", "커널", "x / y 변환", "특성집합", "CV R²", "Test R²", "95% 포함"].map((t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }));
const rows = T.map((t) => [KS[t], R[t].best_text.replace(" (등방성)", " 등방").replace(" + 선형(DotProduct)", " + 선형"),
  `${R[t].best.x_transform} / ${R[t].best.y_transform}`, R[t].best.feature_set, f(R[t].best_cv.R2), f(R[t].test.R2), `${(100 * R[t].test.cov95).toFixed(0)}%`]);
s.addTable([hdr, ...rows], { x: 0.5, y: 1.05, w: 9.0, colW: [1.2, 2.45, 1.25, 1.1, 0.95, 0.95, 1.1], fontSize: 10.5, color: HEX.dk1,
  border: { type: "solid", pt: 0.5, color: "D5DCE2" }, rowH: 0.3, valign: "middle", margin: 0.05, objectName: "best-table" });
const labs = T.map((t) => KS[t]);
s.addChart(pres.charts.BAR, [
  { name: "GP (BO 최적)", labels: labs, values: T.map((t) => Math.max(0, R[t].test.R2)) },
  { name: "Random Forest", labels: labs, values: T.map((t) => Math.max(0, R[t].test_baselines.RandomForest)) },
  { name: "Ridge", labels: labs, values: T.map((t) => Math.max(0, R[t].test_baselines.Ridge)) },
], { x: 0.5, y: 3.0, w: 9.0, h: 2.15, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent1, HEX.accent4, HEX.accent2],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 8, dataLabelColor: HEX.dk2,
  showLegend: true, legendPos: "r", legendFontSize: 9, valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0",
  catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent3, catAxisLabelFontSize: 10, valAxisLabelFontSize: 8,
  valGridLine: { color: "E3E8EC", size: 0.5 }, catGridLine: { style: "none" }, showTitle: true, title: "홀드아웃 테스트 R² (음수는 0으로 표시)",
  titleFontSize: 10, titleColor: HEX.dk1, ...chartText, objectName: "chart-test-r2" });

// 8 ---------------------------------------------------------------- parity
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("예측 vs 실측: 불확실성까지 함께 제공", { placeholder: "title" });
sub(s, INTERP.deck_parity);
img(s, path.join(OUT, "figures", "F5_parity.png"), 0.5, 1.5, 9.0, "fig-parity");

// 9 ---------------------------------------------------------------- design BO
pres.addSection({ title: "활용" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "활용" });
s.addText("배합 설계에 BO 적용: 더 적은 실험으로 최적 배합 도달", { placeholder: "title" });
sub(s, INTERP.deck_pool);
const h9 = img(s, path.join(OUT, "figures", "F9_pool_bo.png"), 0.5, 1.45, 9.0, "fig-pool-bo", 2.9);
s.addText(INTERP.deck_design, { x: 0.5, y: Math.min(1.5 + h9 + 0.1, 4.6), w: 9.0, h: 0.55, fontSize: 11, color: Cs.text1, margin: 0, valign: "top", isTextBox: true, objectName: "design-note" });

// 10 ---------------------------------------------------------------- conclusion
s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "활용" });
s.addText("결론과 다음 단계", { placeholder: "title" });
s.addText(INTERP.deck_conclusion.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < INTERP.deck_conclusion.length - 1 } })),
  { placeholder: "body", fontSize: 18, paraSpaceAfter: 14 });

const outFile = process.env.OUT_FILE || path.join(ROOT, "가스켓_GP_BO_발표자료.pptx");
pres.writeFile({ fileName: outFile }).then(async () => { await applyTheme(outFile, THEME); console.log("saved", outFile); });
