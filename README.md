# 국내 여행지 추천 프로그램

LLM API(Anthropic Claude)와 지도/장소 검색 API(Kakao Local)를 조합한 CLI 기반 국내 여행 추천 프로그램입니다.

여행 날짜를 입력하면 다음 순서로 동작합니다.

1. **[1/3] LLM API** — 입력한 날짜를 기준으로 여행하기 좋은 국내 지역을 추천하고, 날씨/행사 정보를 JSON으로 생성
2. **[2/3] 지도/장소 검색 API (Kakao Local)** — 추천된 지역의 맛집을 검색
3. **[3/3] LLM API** — 1차 추천 결과 + 맛집 목록을 종합해 최종 여행 리포트(Markdown)를 생성

---

## 1. 프로그램 개요

| 구성 요소 | 사용 API |
|---|---|
| 여행지 추천 / 최종 리포트 생성 (LLM) | Anthropic Claude API (`/v1/messages`) |
| 맛집(장소) 검색 | Kakao Local API (`/v2/local/search/keyword.json`) |

- 두 API 모두 표준 REST 방식(HTTP GET/POST + JSON)으로 직접 호출합니다.
- LLM의 1차 추천 결과(JSON)를 그대로 다음 단계인 장소 검색의 입력(`recommended_city`)으로 사용합니다.
- 장소 검색이 실패하거나 결과가 0건이어도 프로그램은 멈추지 않고, "데이터 없음"으로 표시한 뒤 리포트 생성까지 계속 진행합니다.

## 2. 사전 준비

### 2-1. Python 환경

- Python 3.10 이상 필요

```bash
cd travel_planner
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2-2. API 키 발급

**Anthropic Claude API 키**
1. https://console.anthropic.com/settings/keys 접속 후 로그인
2. "Create Key"로 API 키 발급 (크레딧이 남아있는 계정 사용)

**Kakao REST API 키**
1. https://developers.kakao.com 접속 후 로그인
2. [내 애플리케이션] → 애플리케이션 추가
3. [앱 키] 메뉴에서 **REST API 키** 복사
   (Kakao Local API는 별도 활성화 없이 REST API 키만으로 사용 가능합니다)

> 다른 지도 API(Naver Local Search 등)를 사용하고 싶다면 `travel_planner.py`의
> `search_restaurants()` 함수 내부 요청 부분만 해당 API 스펙에 맞게 교체하면 됩니다.

## 3. API 키 설정 방법 (보안 주의)

**⚠️ API 키를 코드에 직접 작성하지 마세요.** 이 프로그램은 `.env` 파일 또는 환경변수에서만 키를 읽어옵니다.

### 방법 A. `.env` 파일 사용 (권장)

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래처럼 실제 키 값을 채워 넣습니다.

```
ANTHROPIC_API_KEY=발급받은_실제_키
KAKAO_REST_API_KEY=발급받은_실제_키
```

- `.env`는 `.gitignore`에 이미 포함되어 있어 Git 저장소에 커밋되지 않습니다.
- **`.env` 파일과 그 안의 키 값은 절대 제출물(README, 로그, 결과 파일 등)에 포함하지 마세요.**

### 방법 B. 환경변수 직접 설정

macOS / Linux (현재 터미널 세션에만 적용):
```bash
export ANTHROPIC_API_KEY="YOUR_KEY"
export KAKAO_REST_API_KEY="YOUR_KEY"
```

Windows PowerShell (현재 세션에만 적용):
```powershell
$env:ANTHROPIC_API_KEY="YOUR_KEY"
$env:KAKAO_REST_API_KEY="YOUR_KEY"
```

### 왜 이렇게 관리해야 하나요?
- 협업/공유(Git, 캡처, 채팅 등) 중 실수로 키가 노출되는 사고를 막기 위해서입니다.
- 키를 교체해도 코드를 수정할 필요가 없어 운영/배포에 유리합니다.
- 과금·쿼터가 걸린 서비스에서 키 유출로 인한 비용 사고를 예방합니다.

## 4. 실행 방법

```bash
python travel_planner.py --date "2026-03-15"
```

### 옵션

| 옵션 | 필수 | 설명 |
|---|---|---|
| `--date "YYYY-MM-DD"` | ✅ | 여행 날짜. 형식이 틀리면 사용법을 출력하고 종료합니다. |
| `--multi` | ❌ | [보너스] 여행지를 1곳이 아닌 2~3곳으로 확장 추천 |
| `--no-cache` | ❌ | [보너스] 같은 날짜로 재실행 시에도 캐시를 쓰지 않고 API를 새로 호출 |

### 실행 예시

```bash
$ python travel_planner.py --date "2026-03-15"
[1/3] 1차 추천 생성 중(LLM)...
    - recommended_city: "제주"
[2/3] 맛집 검색 중(지도/장소 API)...
    - [제주] 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
    - 리포트 생성 완료

완료! results/2026-03-15_travel_plan.md 를 확인하세요.
(원본 데이터: results/2026-03-15_raw_data.json)
```

같은 날짜로 다시 실행하면(기본값), 이미 저장된 원본 JSON이 있을 경우 LLM/지도 API 호출을 건너뛰고 리포트만 재생성합니다. 새로 호출하고 싶다면 `--no-cache`를 붙이세요.

## 5. 결과물 확인 방법

실행이 끝나면 `results/` 폴더에 아래 두 파일이 생성됩니다. (파일명은 입력한 날짜 기준)

- `results/{date}_single_raw_data.json (또는 _multi_)` — 1차 추천 JSON + 맛집 검색 결과 + 오류 요약(`errors`)이 담긴 원본 데이터
- `results/{date}_single_travel_plan.md (또는 _multi_)` — 추천 지역 / 추천 이유 / 날씨 / 행사·축제 / 맛집 리스트 / 1일 일정 / 오류 요약이 포함된 최종 Markdown 리포트

`results/{date}_single_raw_data.json (또는 _multi_)` 구조 예:
```json
{
  "date": "2026-03-15",
  "recommendation": { "recommended_city": "제주", "weather": "...", "events": ["..."], "reason": "..." },
  "restaurants_by_city": { "제주": [ { "name": "...", "address": "...", "category": "...", "url": "...", "x": "...", "y": "..." } ] },
  "errors": []
}
```

## 6. 오류 처리 정책

| 상황 | 동작 |
|---|---|
| `ANTHROPIC_API_KEY` / `KAKAO_REST_API_KEY` 미설정 | 즉시 종료 + 설정 방법 안내 출력 |
| 날짜 형식 오류 | 즉시 종료 + 사용법 출력 |
| 지도/장소 API 실패 (네트워크/401·403 인증/429 쿼터 등) | 맛집 섹션을 "데이터 없음"으로 처리하고 리포트 생성까지 계속 진행 |
| 장소 검색 결과 0건 | 중단하지 않고 "데이터 없음"으로 다음 단계 진행 |
| LLM 1차 추천 JSON 파싱 실패 | 축소된 프롬프트로 1회 재시도, 그래도 실패하면 기본값으로 대체 후 진행 |

모든 오류는 원본 JSON의 `errors` 배열과 최종 리포트의 "오류 요약" 섹션에 기록됩니다.

## 7. 프로젝트 구조

```
travel_planner/
├── travel_planner.py    # 메인 프로그램
├── requirements.txt      # 의존 패키지
├── .env.example           # 환경변수 예시 (실제 키 없음)
├── .gitignore
├── README.md
└── results/                # 실행 후 생성됨 (JSON + Markdown 리포트)
```

## 8. 보너스 구현 여부

- ✅ **복수 지역 추천**: `--multi` 옵션으로 `recommended_cities`를 2~3개 받아 지역별 맛집 검색 및 리포트 섹션 구성
- ✅ **결과 캐싱**: 같은 `--date`로 재실행 시 저장된 원본 JSON이 있으면 API 재호출 없이 리포트만 재생성 (`--no-cache`로 무시 가능)
