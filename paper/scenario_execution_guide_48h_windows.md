# Windows 48시간 wall-clock 시뮬레이션 실행 가이드

## 1. 목적
이 실행은 시뮬레이터 내부 시간을 48시간으로 늘리는 방식이 아니라, 실제 Windows 컴퓨터에서 약 48시간 동안 S1-S6 시나리오를 동시에 실행하여 반복 run을 누적하는 방식이다.

각 run의 내부 가상 운항 시간은 기존과 동일하게 10,800 s이며, 새 임무는 10 s 간격으로 생성된다. 48시간 실행의 목적은 run 수와 생성 임무 수를 크게 늘려 논문 결과 표와 그래프의 안정성을 높이는 것이다.

## 2. 추가된 실행 안정장치
이번 48시간 실행을 위해 다음 기능을 추가하였다.

| 기능 | 설명 |
|---|---|
| 48시간 출력 폴더 분리 | 결과를 `outputs/scenarios_wallclock_48h/`에 저장한다. |
| resume | 중간에 꺼져도 같은 실행 파일을 다시 실행하면 완료된 run 이후부터 이어서 실행한다. |
| checkpoint | 각 시나리오의 `summary/scenario_runs_summary.csv`와 `summary/latest_progress.yaml`을 run마다 갱신한다. |
| 저장량 조절 | `--save-run-details first`를 사용하여 첫 run의 상세 자료와 그림만 저장하고, 이후 run은 요약 중심으로 저장한다. |
| 48시간 분석 경로 | 분석 결과는 `figures/wallclock_48h/`와 `outputs/scenarios_wallclock_48h/`에 저장한다. |

## 3. Windows 준비
Windows 컴퓨터에 Python 3이 설치되어 있어야 한다. 프로젝트 폴더를 Windows 컴퓨터로 옮긴 뒤, 명령 프롬프트에서 프로젝트 루트로 이동하거나 아래 파일을 더블클릭한다.

```text
setup_windows.bat
```

이 파일은 `.venv` 가상환경을 만들고, 실행에 필요한 패키지를 설치한다.

설치되는 패키지는 다음 파일에 정리되어 있다.

```text
requirements_windows.txt
```

## 4. 짧은 테스트
48시간 실행 전에 반드시 짧은 테스트를 먼저 실행한다.

```text
run_quick_windows.bat
```

정상 완료되면 다음 폴더가 생성된다.

```text
outputs/scenarios_wallclock_48h_quick/
figures/wallclock_48h_quick/
```

## 5. 48시간 본 실행
짧은 테스트가 성공하면 다음 파일을 실행한다.

```text
run_48h_windows.bat
```

PowerShell을 선호하면 다음 파일을 실행해도 된다.

```text
run_48h_windows.ps1
```

본 실행 명령의 핵심은 다음과 같다.

```bash
python -m simulator.run_wallclock_parallel \
  --config simulator/config/scenarios_v2.yaml \
  --target-seconds 172800 \
  --max-workers 6 \
  --output-root outputs/scenarios_wallclock_48h \
  --resume \
  --save-run-details first
```

## 6. 중간에 꺼졌을 때
Windows가 꺼지거나 실행 창이 닫히면, 같은 파일을 다시 실행한다.

```text
run_48h_windows.bat
```

`--resume` 옵션이 적용되어 있으므로, 이미 저장된 `scenario_runs_summary.csv`를 읽고 다음 cycle부터 이어서 실행한다.

## 7. 실행 중 확인할 파일
실행 중에는 다음 파일을 보면 진행 상황을 확인할 수 있다.

```text
outputs/scenarios_wallclock_48h/S1/summary/latest_progress.yaml
outputs/scenarios_wallclock_48h/S2/summary/latest_progress.yaml
...
outputs/scenarios_wallclock_48h/S6/summary/latest_progress.yaml
```

각 시나리오별 누적 run 목록은 다음 파일에 저장된다.

```text
outputs/scenarios_wallclock_48h/S1/summary/scenario_runs_summary.csv
```

## 8. 실행 완료 후 분석
`run_48h_windows.bat`는 48시간 실행이 정상 종료되면 자동으로 분석까지 실행한다. 따로 분석만 다시 하고 싶으면 다음 파일을 실행한다.

```text
analyze_48h_windows.bat
```

생성되는 주요 파일은 다음과 같다.

```text
outputs/scenarios_wallclock_48h/all_scenarios_summary.csv
outputs/scenarios_wallclock_48h/all_runs_summary.csv
outputs/scenarios_wallclock_48h/scenario_summary_for_paper.csv
outputs/scenarios_wallclock_48h/model_summary_for_paper.csv
outputs/scenarios_wallclock_48h/wallclock_48h_results_summary.md
figures/wallclock_48h/
```

## 9. Mac 프로젝트 폴더로 가져올 데이터
Windows 실행이 끝나면 다음 폴더를 이 프로젝트 루트에 그대로 넣으면 된다.

```text
outputs/scenarios_wallclock_48h/
figures/wallclock_48h/
```

이 두 폴더가 들어오면 논문에서는 다음 내용을 48시간 결과로 교체할 수 있다.

- Abstract의 run 수와 생성 임무 수
- 실험 결과의 시나리오별 표
- Model A-E 비교 표
- 충돌 위험 그래프
- 임무 완료 그래프
- 평균 패드 지연 그래프
- 결론의 수치와 해석

## 10. 주의사항
- 48시간 실행 중 Windows 절전 모드가 켜지면 실행이 멈출 수 있으므로 전원 및 절전 설정을 꺼야 한다.
- 노트북에서는 전원 어댑터를 연결한 상태로 실행하는 것이 좋다.
- `outputs/scenarios_wallclock_48h/`는 기존 1시간 결과와 분리된 최종 후보 데이터 폴더이다.
- 기존 `outputs/scenarios_wallclock_v2/`는 삭제하지 않는 것이 좋다.
