# 반도체 공정용 불소고무 가스켓 배합비–물성 예측 (GP + 베이지안 최적화)

공개 특허의 실시예·비교예 표에서 FFKM·FKM 가스켓의 원재료·부재료 배합비(phr)와 물성을 추출하고,
가우시안 프로세스(GP) 회귀 모델의 하이퍼파라미터를 베이지안 최적화(BO)로 탐색해 물성 예측 모델을 만든 프로젝트입니다.

## 산출물

| 파일 | 내용 |
|---|---|
| `가스켓_배합-물성_데이터_및_GP모델.xlsx` | 원자료(412행), 모델링 데이터(333행), 출처, 통계, 하이퍼파라미터 실험 전체 기록(525회), 최적 모델, 예측값, BO 제안 배합 |
| `가스켓_GP_BO_분석보고서.docx` | 데이터 수집·정제, GP/BO 방법론, 하이퍼파라미터 설정과 분석 과정 상세 보고서 |
| `가스켓_GP_BO_발표자료.pptx` | 요약 발표자료 |

## 데이터

- 출처: Google Patents 공개 전문 40건(Daikin, DuPont/Chemours, 3M, Greene Tweed, Nichias, Valqua, Mitsubishi Cable, 국내 특허 등)
- 수집 412행 → 정제 규칙 8단계 적용 → 모델링 333행(33개 특허, FFKM 243 / FKM 90)
- 모든 수치는 특허 원문 표에서 전사(추정·합성 데이터 없음). 단위는 phr(고무 100 기준), MPa로 통일
- 원자료: `data/raw/batch_*.csv` (스키마: `data/raw/SCHEMA.md`), 특허 표 추출본: `data/raw/pat/*_tables.txt`
- 정제 결과: `data/gasket_dataset_clean.csv`, 처리 기록: `data/cleaning_log.txt`

## 결과 요약 (개발셋 5-fold×5 CV R² / 20% 홀드아웃 테스트 R²)

| 물성 | n | 최적 설정 | CV R² | Test R² |
|---|---|---|---|---|
| 경도 (Shore A) | 227 | Matérn ν=3/2 + ARD + 선형항, log1p 입력, log 출력, full_agg | 0.736 | 0.919 |
| 100% 모듈러스 | 264 | Matérn ν=3/2 (등방성) + 선형항, full_cure6 | 0.721 | 0.814 |
| 인장강도 | 263 | Matérn ν=1/2 (등방성), log1p 입력, full_cure6 | 0.691 | 0.483 |
| 신율 | 270 | Matérn ν=1/2 + ARD + 선형항, log 출력, compact | 0.630 | −0.192* |
| 압축영구줄음률 | 250 | Matérn ν=5/2 + ARD, log1p 입력, log 출력, full + 시험온도 | 0.327 | 0.097 |

\* 학습 범위 3배 밖(불소수지 300 phr) 테스트 1점의 외삽 오차 때문. 적용범위 내 테스트 점 기준 R²는 보고서 5.5절 참조.

## 실행 순서

```bash
pip install scikit-learn pandas numpy scipy openpyxl matplotlib joblib
python tools/patent_tables.py US7678858B2 data/raw/pat   # 특허 표 추출 예시
python src/build_dataset.py                              # 병합·정제
python src/run_experiments.py hardness_shoreA            # 물성별 실험 (Exp-0~4), 물성마다 실행
python src/merge_results.py
python src/design_bo.py                                  # 중요도, 부분의존도, 회고적 BO, 배합 제안
python src/make_figures.py && python src/make_excel.py
python src/prepare_report_data.py && python src/make_interp.py
cd build && npm install docx pptxgenjs && node build_report.js && node build_deck.js
```

`build_deck.js`는 테마 적용을 위해 환경변수 `PPTX_SKILL`(pptx 스킬의 `scripts/apply_theme.js` 위치)을 사용합니다.

## 구조

```
src/gp_core.py          GP 모델·커널 구성, 교차검증, BO 엔진(GP 대리모델 + Expected Improvement)
src/run_experiments.py  기준모델 → 커널 스크리닝 → BO 3회 반복 → 강건성 재평가 → 테스트/출처별 검증
src/design_bo.py        순열 중요도, 부분의존도, 회고적 pool BO, 제약 EI 배합 제안
outputs/                results.json, trials.csv(전체 실험 기록), pred_*.csv, figures/
```
