# S1-S6 / Model A-E 병렬 장시간 시뮬레이션 실행 가이드

## 1. 변경 요약
v2 실험은 기존 S1-S5 / Model A-D 구조를 S1-S6 / Model A-E 구조로 확장한다.

| 모델 | 건물 회피 | 비행체 간 회피 | 버티포트 패드 점유 |
|---|---|---|---|
| A | off | off | off |
| B | on | off | off |
| C | off | on | off |
| D | on | on | off |
| E | on | on | on |

Model D는 순수 회피 기능 결합 조건이고, Model E는 여기에 버티포트 패드 점유 제약을 추가한 조건이다. 따라서 D와 E의 비교는 “성능 우열”이 아니라 “운영 제약 반영 효과”로 해석한다.

## 2. v2 시나리오
| 시나리오 | 역할 | 맵 크기 | 격자 | 건물 밀도 | 버티포트 | fleet size |
|---|---|---:|---:|---:|---:|---:|
| S1 | 소형 고혼잡 | 1500 m x 1500 m | 50 m | 0.35 | 8 | 75 |
| S2 | 중소형 확장 | 2000 m x 2000 m | 50 m | 0.35 | 12 | 100 |
| S3 | 중형 고밀도 | 3000 m x 3000 m | 75 m | 0.45 | 20 | 150 |
| S4 | 대형 저밀도 | 5000 m x 5000 m | 100 m | 0.30 | 32 | 200 |
| S5 | 대형 일반 밀도 | 6000 m x 6000 m | 100 m | 0.35 | 40 | 300 |
| S6 | 대형 고밀도 스트레스 | 6000 m x 6000 m | 100 m | 0.45 | 40 | 360 |

설정 파일은 다음 위치에 있다.

```bash
simulator/config/scenarios_v2.yaml
```

## 3. 짧은 테스트
먼저 S1만 짧게 확인한다.

```bash
python3 -m simulator.run_wallclock_parallel \
  --config simulator/config/scenarios_v2.yaml \
  --only S1 \
  --quick-test \
  --max-workers 1 \
  --output-root outputs/scenarios_wallclock_v2_quick
```

quick-test는 Model E만 짧게 실행하여 패드 점유 로직이 정상 작동하는지 확인한다.

## 4. 전체 실행
S1-S6를 동시에 실행한다.

```bash
python3 -m simulator.run_wallclock_parallel \
  --config simulator/config/scenarios_v2.yaml \
  --target-seconds 3600 \
  --max-workers 6
```

결과는 기본적으로 아래 폴더에 저장된다.

```bash
outputs/scenarios_wallclock_v2/
```

## 5. 결과 집계 및 그래프 생성
전체 실행이 끝난 뒤 아래 명령을 실행한다.

```bash
python3 scripts/analyze_wallclock_v2.py
```

생성되는 주요 파일은 다음과 같다.

```bash
outputs/scenarios_wallclock_v2/scenario_summary_for_paper.csv
outputs/scenarios_wallclock_v2/model_summary_for_paper.csv
outputs/scenarios_wallclock_v2/wallclock_v2_results_summary.md
figures/wallclock_v2/
```

## 6. 논문 반영 기준
v2 데이터가 생성되면 논문에서는 다음 내용을 새 결과로 교체한다.

- S1-S5 -> S1-S6
- Model A-D -> Model A-E
- 기존 Model D 해석 -> D와 E 분리 해석
- S1-S5 맵 합본 -> S1-S6 맵 합본
- 결과 표, 결과 그래프, 결론 수치
