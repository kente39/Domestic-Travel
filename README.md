---

# Domestic Travel Recommendation Program

사용자가 입력한 날짜를 기준으로 국내 여행지를 추천하고,  
해당 지역의 맛집 정보를 수집한 뒤 여행 리포트를 생성하는 Python CLI 프로그램입니다.

- OpenAI API로 여행지 추천
- Kakao Local API로 지역별 맛집 검색
- Markdown 리포트 자동 생성
- JSON 캐시 저장 및 재사용

---

## 1. 주요 기능

- 날짜 입력 검증 (`YYYY-MM-DD`)
- 실제 존재하는 날짜인지 추가 검증
- 국내 여행지 추천
- 추천 지역별 맛집 검색
- 여행 리포트 Markdown 생성
- 원본 데이터 JSON 저장
- 캐시 재사용 및 `--no-cache` 지원
- 단일 지역 / 복수 지역 추천 지원

---

## 2. 사용 기술 및 API

- Python 3
- OpenAI API
- Kakao Local API
- `requests`
- `python-dotenv`

### OpenAI API
여행지 추천 문장을 생성하는 데 사용합니다.

### Kakao Local API
추천된 지역을 기준으로 맛집 정보를 검색하는 데 사용합니다.

---

## 3. 설치 방법

```bash
git clone <저장소 주소>
cd Domestic-Travel

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## 4. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
OPENAI_API_KEY=your_openai_api_key
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

### Kakao API 키 준비 방법
1. https://developers.kakao.com 접속
2. 내 애플리케이션 생성
3. **REST API 키** 복사
4. **카카오맵 사용 설정을 ON으로 활성화**

> 참고: Kakao API 호출이 `403 Forbidden`이면 카카오맵 사용 설정 여부를 먼저 확인하세요.

---

## 5. 실행 방법

### 단일 지역 추천

```bash
python travel_planner.py --date "2026-03-15"
```

### 복수 지역 추천

```bash
python travel_planner.py --date "2026-03-15" --multi
```

### 캐시 무시 후 새로 호출

```bash
python travel_planner.py --date "2026-03-15" --no-cache
```

---

## 6. 실행 결과

실행이 완료되면 `results/` 폴더에 아래 파일이 생성됩니다.

### 단일 지역 예시
- `results/2026-03-15_single_raw_data.json`
- `results/2026-03-15_single_travel_plan.md`

### 복수 지역 예시
- `results/2026-03-15_multi_raw_data.json`
- `results/2026-03-15_multi_travel_plan.md`

---

## 7. 프로젝트 구조

```text
Domestic-Travel/
├── travel_planner.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── results/
```

---

## 8. 예외 처리

- 날짜 형식 검증 (`YYYY-MM-DD`)
- 실제 존재하는 날짜인지 추가 검증
- API 키 누락 시 오류 메시지 출력
- 네트워크 오류 예외 처리
- 손상된 캐시 JSON 예외 처리
- 캐시 파일명에 `single` / `multi` 모드 구분 적용

---

## 9. 트러블슈팅

- `403 Forbidden`  
  → Kakao Developers에서 **카카오맵 사용 설정 ON** 확인

- `API key not found`  
  → `.env` 파일 또는 환경변수 설정 확인

- 날짜 입력 오류  
  → `YYYY-MM-DD` 형식으로 다시 입력

---

## 10. 보너스 구현 사항

- 복수 지역 추천 기능 (`--multi`)
- 캐시 무시 옵션 (`--no-cache`)
- 캐시 손상 예외 처리
- 환경변수 기반 API 키 관리

---

## 11. 요약

이 프로그램은 날짜 입력을 바탕으로 국내 여행지를 추천하고,  
맛집 정보를 수집하여 Markdown 리포트로 정리하는 자동화 도구입니다.

API 연동, 예외 처리, 캐시 활용, CLI 옵션 확장까지 구현했습니다.

---

추가로 더 편하게 하시려면, 다음 답변에서 제가  
**“저장소 주소만 채워 넣은 제출용 최종본”** 으로 한 번 더 정리해드릴 수 있습니다.