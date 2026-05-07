# 최종 검증 체크리스트 상태

## 문헌 검증
- [x] MainPaper 10편 텍스트 추출 및 분석표 작성
- [x] AssistancePaper 4편 텍스트 추출 및 분석표 작성
- [x] Referenceinformation 로드맵 텍스트 추출 및 분석표 작성
- [x] examples 양식 2개 분석표 작성
- [x] 주요 수치 출처 검증표 작성
- [x] 출처 없는 값은 사용자 승인 가정값으로 분리
- [ ] K-UAM 기술로드맵 표지의 발행기관 및 발행연도 원문 이미지 대조 필요
- [ ] 최종 제출 전 examples 원본 양식의 글꼴, 여백, 단 구성, 표/그림 캡션 위치 재확인 필요

## 시뮬레이터 검증
- [x] Python으로 실행 가능
- [x] `simulator/config/default.yaml`로 주요 값 조정 가능
- [x] 격자형 도시 맵 생성 가능
- [x] 건물 옥상 버티포트 생성 가능
- [x] eVTOL 임무 및 궤적 생성 가능
- [x] 건물 회피 기능 구현
- [x] 비행체 간 회피 기능 구현
- [x] 버티포트 패드 점유 및 이착륙 대기 기능 구현
- [x] Model A/B/C/D 비교 구현
- [x] 결과 CSV 저장
- [x] 그래프 PNG 저장
- [x] 150/240/300 km/h를 내부 m/s로 변환
- [x] 500 ft 기본 안전거리와 30 m 민감도 시나리오 반영
- [x] 연구 범위는 도시 격자 맵, 건물 회피, 비행체 간 충돌 회피, 버티포트 패드 점유 모델 중심으로 정리
- [x] S1-S5 wall-clock 병렬 실행기 구현
- [x] 장시간 누적 임무 생성 및 착륙 후 기체 재투입 구현
- [x] 1시간 공식 실행 결과 CSV 집계
- [x] 전체 196개 run의 패드 점유 겹침 0건 검증

## 생성 산출물
- [x] `outputs/raw/simulation_log.csv`
- [x] `outputs/processed/summary_results.csv`
- [x] `outputs/processed/flight_results.csv`
- [x] `outputs/processed/vertiport_pad_usage.csv`
- [x] `outputs/summary/model_comparison.csv`
- [x] `figures/maps/city_map.png`
- [x] `figures/trajectories/trajectory_map.png`
- [x] `figures/collision_graphs/collision_by_aircraft_count.png`
- [x] `figures/collision_graphs/collision_by_speed.png`
- [x] `figures/collision_graphs/collision_by_density.png`
- [x] `figures/comparison_graphs/model_comparison.png`
- [x] `figures/comparison_graphs/safety_distance_sensitivity.png`
- [x] `figures/comparison_graphs/pad_delay_by_vertiport_count.png`
- [x] `outputs/scenarios_wallclock/all_scenarios_summary.csv`
- [x] `outputs/scenarios_wallclock/all_runs_summary.csv`
- [x] `outputs/scenarios_wallclock/scenario_summary_for_paper.csv`
- [x] `outputs/scenarios_wallclock/model_summary_for_paper.csv`
- [x] `figures/wallclock/wallclock_mission_completion.png`
- [x] `figures/wallclock/wallclock_collision_risk_by_scenario.png`
- [x] `figures/wallclock/wallclock_collision_risk_per_1000.png`
- [x] `figures/wallclock/wallclock_pad_delay_by_scenario.png`
- [x] `figures/wallclock/wallclock_model_risk_per_1000.png`
- [x] `figures/wallclock/wallclock_model_pad_delay.png`

## 논문 검증
- [x] 논문 초안 `paper/draft.md` 작성
- [x] 영문 초록과 국문 요약 포함
- [x] 키워드 포함
- [x] 관련 연구 작성
- [x] 시뮬레이터 구조 작성
- [x] 실험 조건과 결과 표 작성
- [x] 결과 그래프 연결
- [x] 한계점 포함
- [x] 참고문헌 초안 `paper/references.bib` 작성
- [ ] 최종 제출 전 참고문헌 형식과 서지정보 원문 대조 필요
- [ ] 최종 제출 전 KCI/학회 양식에 맞춘 편집본 작성 필요

## 실행 검증 기록
### 1시간 wall-clock 공식 실행
- 실행 폴더: `outputs/scenarios_wallclock/`
- 시나리오: S1-S5
- 비교 모델: A/B/C/D
- 전체 run 수: 196개
- 생성 임무: 211,680개
- 시나리오별 실제 실행 시간: 약 60.1-65.2분
- 패드 점유 겹침 검증: 0건
- Model D의 Model A 대비 정규화 충돌 위험 감소율: 75.8-92.1%

### 참고용 단일 실행
- 실행 명령: `python3 -m simulator.main`
- 실험 수: 64개
- 요약 결과: 64행
- 원시 궤적 로그: 204,077행
- 패드 사용 로그: 6,320행
- 기본 시나리오 Model D 총 충돌 위험: 7건

## 남은 작업
- 로드맵 표지/서지정보 원문 이미지 확인
- 논문 초안을 examples 양식의 정확한 편집 규격으로 변환
- 참고문헌의 저널명, 권호, 페이지, DOI 여부 최종 대조
- 필요 시 패드 수, turnaround time, 안전거리 민감도를 S1-S5 확장 시나리오에서도 추가 실행
