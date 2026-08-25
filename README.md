# Domestic Travel Recommendation Program

사용자가 입력한 날짜를 기준으로 국내 여행지를 추천하고,
해당 지역의 맛집 정보를 수집한 뒤 여행 리포트를 생성하는 Python CLI 프로그램입니다.

- Anthropic Claude API로 여행지 추천 및 리포트 생성
- Kakao Local API로 지역별 맛집 검색
- Markdown 리포트 자동 생성
- JSON 캐시 저장 및 재사용

---

## 1. 주요 기능

- 날짜 입력 검증 (`YYYY-MM-DD`) + 실제 존재하는 날짜인지 추가 검증
- 국내 여행지 추천 (단일 / 복수 지역)
- 추천 지역별 맛집 검색
- 여행 리포트 Markdown 생성 + 원본 데이터 JSON 저장
- 캐시 재사용 및 `--no-cache` 지원

---

## 2. 동작 흐름

1. **[1/3] LLM API (Claude)** — 입력 날짜 기준 여행지 추천, 날씨/행사 정보를 JSON으로 생성
2. **[2/3] Kakao Local API** — 추천 지역의 맛집 검색
3. **[3/3] LLM API (Claude)** — 1차 추천 + 맛집 목록을 종합해 최종 Markdown 리포트 생성

| 구성 요소 | 사용 API |
|---|---|
| 여행지 추천 / 리포트 생성 | Anthropic Claude API (`/v1/messages`) |
| 맛집(장소) 검색 | Kakao Local API (`/v2/local/search/keyword.json`) |

- 두 API 모두 표준 REST(HTTP + JSON)로 직접 호출합니다.
- 장소 검색이 실패하거나 0건이어도 멈추지 않고 "데이터 없음"으로 리포트를 계속 생성합니다.

---

## 3. 사용 기술

- Python 3.10 이상
- Anthropic Claude API
- Kakao Local API
- `requests`, `python-dotenv`

---

## 4. 설치 방법

```bash
git clone <저장소 주소>
cd Domestic-Travel

python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 5. 환경변수 설정 (보안 주의)

**⚠️ API 키를 코드에 직접 작성하지 마세요.** `.env` 파일 또는 환경변수에서만 키를 읽어옵니다.

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
ANTHROPIC_API_KEY=발급받은_실제_키
KAKAO_REST_API_KEY=발급받은_실제_키
```

- `.env`는 `.gitignore`에 포함되어 Git에 커밋되지 않습니다.
- **키 값은 절대 제출물(README, 로그, 결과 파일, 스크린샷)에 포함하지 마세요.**

### Anthropic Claude API 키
1. https://console.anthropic.com/settings/keys 접속 후 로그인
2. "Create Key"로 발급 (크레딧 남은 계정 사용)

### Kakao REST API 키
1. https://developers.kakao.com 접속 후 로그인
2. [내 애플리케이션] → 애플리케이션 추가
3. [앱 키] 메뉴에서 **REST API 키** 복사
4. **카카오맵 사용 설정을 ON으로 활성화**

> 참고: Kakao Local API 호출이 `403 Forbidden`이면 해당 앱의 **카카오맵 사용 설정이 ON인지** 먼저 확인하세요.

### (참고) GitHub Codespaces 사용 시
`.env` 대신 저장소 **Settings → Secrets and variables → Codespaces**에
`ANTHROPIC_API_KEY`, `KAKAO_REST_API_KEY`를 등록하면 Codespace 실행 시 자동 주입됩니다.
(등록 후 Codespace 재시작 필요)

---

## 6. 실행 방법

```bash
# 단일 지역 추천
python travel_planner.py --date "2026-03-15"

# 복수 지역 추천 (보너스)
python travel_planner.py --date "2026-03-15" --multi

# 캐시 무시 후 새로 호출 (보너스)
python travel_planner.py --date "2026-03-15" --no-cache
```

### 실행 예시

```bash
$ python travel_planner.py --date "2026-03-15"
[1/3] 1차 추천 생성 중(LLM)...
    - recommended_city: "제주"
[2/3] 맛집 검색 중(지도/장소 API)...
    - [제주] 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
    - 리포트 생성 완료

완료! results/2026-03-15_single_travel_plan.md 를 확인하세요.
(원본 데이터: results/2026-03-15_single_raw_data.json)
```

같은 날짜로 다시 실행하면 저장된 원본 JSON을 재사용해 API 호출 없이 리포트만 재생성합니다.
새로 호출하려면 `--no-cache`를 붙이세요.

---

## 7. 실행 결과

실행 후 `results/` 폴더에 파일이 생성됩니다.

### 단일 지역
- `results/2026-03-15_single_raw_data.json`
- `results/2026-03-15_single_travel_plan.md`

### 복수 지역
- `results/2026-03-15_multi_raw_data.json`
- `results/2026-03-15_multi_travel_plan.md`

원본 JSON 구조 예:
```json
{
  "date": "2026-03-15",
  "recommendation": { "recommended_city": "제주", "weather": "...", "events": ["..."], "reason": "..." },
  "restaurants_by_city": { "제주": [ { "name": "...", "address": "...", "category": "...", "url": "...", "x": "...", "y": "..." } ] },
  "errors": []
}
```

---

## 8. 오류 / 예외 처리

| 상황 | 동작 |
|---|---|
| API 키 미설정 | 즉시 종료 + 설정 방법 안내 |
| 날짜 형식/존재하지 않는 날짜 | 즉시 종료 + 사용법 출력 |
| 지도 API 실패 (네트워크/401·403/429) | 맛집 "데이터 없음" 처리 후 리포트 계속 생성 |
| 장소 검색 0건 | 중단 없이 "데이터 없음"으로 진행 |
| LLM JSON 파싱 실패 | 축소 프롬프트로 1회 재시도, 실패 시 기본값 대체 |
| 손상된 캐시 JSON | 캐시 무시하고 새로 API 호출 |

모든 오류는 원본 JSON의 `errors` 배열과 리포트의 "오류 요약" 섹션에 기록됩니다.

---

## 9. 트러블슈팅

- `403 Forbidden` (Kakao) → 카카오맵 사용 설정 **ON** 확인
- `API key not found` → `.env` 또는 환경변수 설정 확인
- 날짜 입력 오류 → `YYYY-MM-DD` 형식으로 입력

---

## 10. 프로젝트 구조

```text
Domestic-Travel/
├── travel_planner.py    # 메인 프로그램
├── requirements.txt      # 의존 패키지 (requests, python-dotenv)
├── .env.example           # 환경변수 예시 (실제 키 없음)
├── .gitignore
├── README.md
└── results/                # 실행 후 생성됨 (JSON + Markdown 리포트)
```

---

## 11. 보너스 구현 사항

- ✅ 복수 지역 추천 (`--multi`)
- ✅ 결과 캐싱 및 캐시 무시 옵션 (`--no-cache`)
- ✅ 손상된 캐시 JSON 예외 처리
- ✅ 환경변수 기반 API 키 관리
