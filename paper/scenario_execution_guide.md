# S1-S5 병렬 장시간 시뮬레이션 실행 가이드

## 1. 구현된 실행 방식
S1-S5는 하나의 명령으로 동시에 실행된다. 내부적으로는 Python `ProcessPoolExecutor`를 사용하여 시나리오별 프로세스를 따로 실행한다.

```text
S1 프로세스 -> outputs/scenarios/S1/
S2 프로세스 -> outputs/scenarios/S2/
S3 프로세스 -> outputs/scenarios/S3/
S4 프로세스 -> outputs/scenarios/S4/
S5 프로세스 -> outputs/scenarios/S5/
```

각 시나리오는 자기 폴더에만 파일을 저장하므로 CSV와 그래프가 서로 덮어써지지 않는다.

## 2. 시나리오 설정 파일
시나리오 설정은 아래 파일에서 관리한다.

```bash
simulator/config/scenarios.yaml
```

현재 설정은 다음과 같다.

| 시나리오 | 맵 크기 | 격자 | 건물 밀도 | 버티포트 | fleet_size | duration | mission_interval |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | 1500m x 1500m | 50m | 0.35 | 8 | 75 | 5400s | 30s |
| S2 | 2000m x 2000m | 50m | 0.35 | 12 | 100 | 7200s | 30s |
| S3 | 3000m x 3000m | 75m | 0.45 | 20 | 150 | 7200s | 30s |
| S4 | 5000m x 5000m | 100m | 0.30 | 32 | 200 | 7200s | 30s |
| S5 | 6000m x 6000m | 100m | 0.35 | 40 | 300 | 7200s | 30s |

기본 모델은 `D`, 즉 건물 회피와 비행체 회피를 모두 적용한 모델이다.

## 3. 장시간 임무 생성 로직
각 시나리오에서는 `duration` 동안 `mission_interval`마다 새 임무를 생성한다.

현재 로직:
1. `t = 0`부터 시작한다.
2. 30초마다 새 eVTOL 임무를 생성한다.
3. 사용 가능한 기체가 있으면 해당 기체에 임무를 배정한다.
4. 사용 가능한 기체가 없으면 가장 빨리 착륙 완료되는 기체를 기다린 뒤 재투입한다.
5. 출발 버티포트 패드가 사용 중이면 이륙을 대기한다.
6. 목적지 버티포트 패드가 사용 중이면 목적지 상공에서 `landing_wait` 상태로 대기한다.
7. `duration` 동안 생성된 모든 임무를 스케줄링하고 결과를 저장한다.

## 4. 빠른 테스트 실행
전체 실행 전에 반드시 빠른 테스트를 먼저 권장한다.

### S1만 짧게 테스트
```bash
cd /Users/apple/Desktop/eVTOLPaper
python3 -m simulator.run_scenarios_parallel --only S1 --quick-test --max-workers 1
```

결과 저장 위치:

```text
outputs/scenarios_quick/S1/
outputs/scenarios_quick/all_scenarios_summary.csv
```

### S1과 S2를 동시에 짧게 테스트
```bash
cd /Users/apple/Desktop/eVTOLPaper
python3 -m simulator.run_scenarios_parallel --only S1,S2 --quick-test --max-workers 2 --output-root outputs/scenarios_quick_parallel
```

## 5. S1-S5 전체 병렬 실행
아래 명령을 실행하면 S1-S5가 동시에 시작된다.

```bash
cd /Users/apple/Desktop/eVTOLPaper
python3 -m simulator.run_scenarios_parallel
```

기본 설정:
- `max_workers: 5`
- 출력 폴더: `outputs/scenarios`
- 실행 대상: S1, S2, S3, S4, S5

컴퓨터가 너무 느려지면 아래처럼 worker 수를 줄일 수 있다. 단, 이 경우 5개가 완전 동시 실행되지는 않고 일부 병렬 실행이 된다.

```bash
python3 -m simulator.run_scenarios_parallel --max-workers 3
```

## 5-1. 실제 컴퓨터를 약 1시간 사용하는 실행
앞의 `run_scenarios_parallel`은 `duration`만큼의 시뮬레이션 시간을 빠르게 계산하는 방식이다. 따라서 컴퓨터 성능이 좋거나 임무 수가 적으면 1~2시간짜리 가상 운항도 짧은 시간에 끝난다.

실제 컴퓨터가 약 1시간 동안 계속 계산하면서 데이터를 누적하게 하려면 아래 wall-clock 실행기를 사용한다.

```bash
cd /Users/apple/Desktop/eVTOLPaper
python3 -m simulator.run_wallclock_parallel --target-seconds 3600 --max-workers 5
```

현재 wall-clock 설정은 `simulator/config/scenarios.yaml`의 `wallclock_runner`에서 관리한다.

| 항목 | 현재값 | 의미 |
|---|---:|---|
| target_seconds | 3600 | 실제 실행 목표 시간 |
| max_workers | 5 | S1-S5 동시 실행 프로세스 수 |
| models | A, B, C, D | 회피 없음/건물 회피/기체 회피/전체 회피 비교 |
| duration | 10800s | 각 반복 실행의 가상 운항 시간 |
| mission_interval | 10s | 가상 시간 기준 임무 생성 간격 |
| time_step | 10s | 이동 상태 샘플링 간격 |
| conflict_time_step | 20s | 충돌 위험 검사 간격 |
| output_root | outputs/scenarios_wallclock | 결과 저장 루트 |

이 실행기는 S1-S5를 동시에 시작하고, 각 시나리오 프로세스가 실제 경과 시간이 목표치에 도달할 때까지 반복적으로 데이터를 생성한다. 각 반복에서는 A-D 비교 모델을 순환 실행하며, 매 반복마다 새 랜덤 시드를 사용한다.

빠른 점검용 명령은 다음과 같다.

```bash
python3 -m simulator.run_wallclock_parallel --only S1 --quick-test --max-workers 1
```

실행 중 진행 상황은 터미널 로그와 아래 파일에서 확인할 수 있다.

```text
outputs/scenarios_wallclock/S1/summary/latest_progress.yaml
outputs/scenarios_wallclock/S2/summary/latest_progress.yaml
outputs/scenarios_wallclock/S3/summary/latest_progress.yaml
outputs/scenarios_wallclock/S4/summary/latest_progress.yaml
outputs/scenarios_wallclock/S5/summary/latest_progress.yaml
```

실행이 끝나면 전체 요약은 아래 파일로 저장된다.

```text
outputs/scenarios_wallclock/all_scenarios_summary.csv
outputs/scenarios_wallclock/all_runs_summary.csv
```

## 6. 결과 폴더 구조
전체 실행 후 결과는 다음 구조로 저장된다.

```text
outputs/scenarios/
├── S1/
│   ├── raw/simulation_log.csv
│   ├── processed/summary_results.csv
│   ├── processed/flight_results.csv
│   ├── processed/vertiport_pad_usage.csv
│   ├── processed/vehicle_reuse.csv
│   ├── figures/maps/city_map.png
│   ├── figures/trajectories/trajectory_map.png
│   └── scenario_config.yaml
├── S2/
├── S3/
├── S4/
├── S5/
└── all_scenarios_summary.csv
```

## 7. 주요 결과 파일
시나리오별 핵심 파일:

```text
outputs/scenarios/S1/processed/summary_results.csv
outputs/scenarios/S1/processed/flight_results.csv
outputs/scenarios/S1/processed/vertiport_pad_usage.csv
outputs/scenarios/S1/processed/vehicle_reuse.csv
outputs/scenarios/S1/raw/simulation_log.csv
```

전체 통합 요약:

```text
outputs/scenarios/all_scenarios_summary.csv
```

## 8. 실행 결과 확인 명령
파일이 생성되었는지 확인:

```bash
find outputs/scenarios -maxdepth 4 -type f | sort
```

통합 요약 확인:

```bash
python3 - <<'PY'
import pandas as pd
df = pd.read_csv("outputs/scenarios/all_scenarios_summary.csv")
print(df[[
    "scenario_name",
    "generated_missions",
    "completed_within_duration",
    "collision_risk_count",
    "avg_pad_delay_s",
    "max_pad_delay_s"
]].to_string(index=False))
PY
```

패드 점유 겹침 검증 예시:

```bash
python3 - <<'PY'
import pandas as pd
from pathlib import Path

root = Path("outputs/scenarios")
for scenario_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    path = scenario_dir / "processed" / "vertiport_pad_usage.csv"
    usage = pd.read_csv(path)
    violations = []
    for (_, vertiport_id), df in usage.groupby(["scenario_id", "vertiport_id"]):
        intervals = sorted(zip(df.start_s, df.end_s))
        for i, (s1, e1) in enumerate(intervals):
            for s2, e2 in intervals[i + 1:]:
                if s2 >= e1:
                    break
                violations.append((vertiport_id, s1, e1, s2, e2))
                break
    print(scenario_dir.name, "pad overlap violations:", len(violations))
PY
```

## 9. 논문 수정 흐름
전체 데이터 추출이 끝나면 사용자 메시지로 “다 뽑았습니다”라고 알려주면 된다. 이후 다음 파일을 기준으로 논문을 수정한다.

```text
outputs/scenarios/all_scenarios_summary.csv
outputs/scenarios/S1/processed/summary_results.csv
outputs/scenarios/S2/processed/summary_results.csv
outputs/scenarios/S3/processed/summary_results.csv
outputs/scenarios/S4/processed/summary_results.csv
outputs/scenarios/S5/processed/summary_results.csv
outputs/scenarios/S*/processed/vertiport_pad_usage.csv
outputs/scenarios/S*/processed/vehicle_reuse.csv
```

논문에는 다음 항목을 추가 반영한다.
- S1-S5 확장 도시 시나리오
- 장시간 누적 임무 생성 방식
- 착륙 후 기체 재투입 방식
- 버티포트 패드 점유와 대기시간
- 맵 크기·버티포트 수·fleet size 증가에 따른 혼잡도 변화
- 시나리오별 충돌 위험, 평균 패드 지연, 기체 재사용 횟수
