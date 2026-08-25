#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
국내 여행지 추천 프로그램
==========================
LLM API(Anthropic Claude)와 지도/장소 검색 API(Kakao Local)를 조합하여
입력한 날짜 기준으로 국내 여행지를 추천하고, 해당 지역의 맛집을 검색한 뒤,
최종 여행 리포트를 Markdown 파일로 생성한다.

흐름:
    [1/3] LLM API 호출  -> 날씨/행사 기반 1차 추천 (JSON)
    [2/3] Kakao Local API 호출 -> 추천 지역의 맛집 검색
    [3/3] LLM API 호출  -> 최종 여행 리포트 생성 (Markdown)

실행 예:
    python travel_planner.py --date "2026-03-15"
    python travel_planner.py --date "2026-03-15" --multi        # 지역 2~3곳 추천(보너스)
    python travel_planner.py --date "2026-03-15" --no-cache      # 캐시 무시하고 새로 호출
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv가 없어도 이미 설정된 환경변수는 그대로 사용 가능하므로 계속 진행한다.
    pass


# ----------------------------------------------------------------------------
# 설정값
# ----------------------------------------------------------------------------
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# 사용할 모델. 필요 시 환경변수 ANTHROPIC_MODEL로 덮어쓸 수 있다.
# (사용 가능한 모델 목록: https://docs.claude.com/en/docs/about-claude/models)
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

KAKAO_LOCAL_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

RESULTS_DIR = Path("results")
REQUEST_TIMEOUT = 20  # seconds


# ----------------------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str, code: int = 1) -> None:
    """즉시 종료가 필요한 치명적 오류(예: API 키 미설정, 잘못된 날짜 형식)."""
    print(f"\n[오류] {msg}\n", file=sys.stderr)
    sys.exit(code)


def validate_date(date_str: str) -> str:
    date_str = date_str.strip()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        die(
            "날짜 형식이 올바르지 않습니다. 'YYYY-MM-DD' 형식으로 입력하세요.\n"
            '      예) python travel_planner.py --date "2026-03-15"'
        )

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        die(
            "유효하지 않은 날짜입니다. 실제 존재하는 날짜를 입력하세요.\n"
            '      예) python travel_planner.py --date "2026-03-15"'
        )

    return date_str


def extract_json(text: str) -> dict:
    """
    LLM 응답에서 JSON 객체만 추출해 파싱한다.
    모델이 설명 문장이나 코드블록(```json ... ```)을 함께 출력하는 경우까지 방어적으로 처리한다.
    """
    text = text.strip()
    # ```json ... ``` 형태의 코드블록 제거
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    # 첫 '{' 부터 마지막 '}' 까지만 추출 시도
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return json.loads(text)


# ----------------------------------------------------------------------------
# LLM API (Anthropic Claude) 호출
# ----------------------------------------------------------------------------
def call_anthropic(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        # LLM 응답 생성은 요청 본문(system/messages)을 서버로 보내 새 결과를
        # 만들어내는 작업이므로 POST를 사용한다.(#10)
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Anthropic API 네트워크 오류: {e}")

    if resp.status_code == 401:
        raise PermissionError("Anthropic API 인증 실패(401). ANTHROPIC_API_KEY 값을 확인하세요.")
    if resp.status_code == 429:
        raise RuntimeError("Anthropic API 쿼터/속도 제한(429)에 도달했습니다.")
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic API 오류: HTTP {resp.status_code} - {resp.text[:300]}")

    data = resp.json()
    parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
    return "".join(parts)


def get_recommendation(api_key: str, date_str: str, multi: bool, errors: list) -> dict:
    """
    [1/3] 날씨/행사 정보를 바탕으로 1차 여행지 추천을 JSON으로 받는다.
    파싱 실패 시 "필수 키만 다시 JSON으로 출력"하도록 프롬프트를 수정해 1회 재시도한다.
    """
    if multi:
        schema_hint = (
            '{"recommended_cities": ["<도시1>", "<도시2>", "<도시3>"], '
            '"weather": "<해당 시기 일반적 날씨 요약>", '
            '"events": ["<행사/축제 후보1>", "<행사/축제 후보2>"], '
            '"reason": "<추천 근거 2~4문장>"}'
        )
    else:
        schema_hint = (
            '{"recommended_city": "<도시명>", '
            '"weather": "<해당 시기 일반적 날씨 요약>", '
            '"events": ["<행사/축제 후보1>", "<행사/축제 후보2>"], '
            '"reason": "<추천 근거 2~4문장>"}'
        )

    system_prompt = (
        "당신은 국내 여행 추천 전문가입니다. "
        "반드시 아래 JSON 스키마와 완전히 동일한 키를 가진 JSON '만' 출력하세요. "
        "설명, 인사말, 코드블록 표시(```) 등 JSON 이외의 텍스트는 절대 포함하지 마세요."
    )
    user_prompt = (
        f"여행 날짜: {date_str}\n"
        f"이 날짜에 여행하기 좋은 국내 지역을 {'2~3곳' if multi else '1곳'} 추천해줘.\n"
        f"실제 최신 날씨/행사 데이터의 정확도는 중요하지 않고, 해당 시기에 일반적으로 기대되는 "
        f"날씨와 행사 후보를 자연스럽게 서술하면 돼.\n"
        f"다음 JSON 스키마를 정확히 따라서 출력해:\n{schema_hint}"
    )

    def _try(prompt_for_this_try: str) -> dict:
        raw = call_anthropic(api_key, system_prompt, prompt_for_this_try)
        return extract_json(raw)

    try:
        return _try(user_prompt)
    except (json.JSONDecodeError, ValueError) as e:
        log("    - 1차 추천 JSON 파싱 실패. 축소된 프롬프트로 1회 재시도합니다...")
        retry_prompt = (
            f"이전 응답이 JSON 파싱에 실패했습니다. 아래 필수 키만 포함한 "
            f"순수 JSON 텍스트만 다시 출력하세요. 그 외 어떤 텍스트도 포함하지 마세요.\n"
            f"{schema_hint}\n대상 날짜: {date_str}"
        )
        try:
            return _try(retry_prompt)
        except (json.JSONDecodeError, ValueError) as e2:
            errors.append({
                "step": "recommendation",
                "type": "JSON_PARSE_ERROR",
                "message": f"1차 추천 JSON 파싱 2회 실패: {e2}",
            })
            # 다음 단계로 진행할 수 있도록 최소한의 기본값을 채워 반환한다.
            fallback = {
                "weather": "정보 없음(파싱 실패)",
                "events": [],
                "reason": "LLM 응답 파싱에 실패하여 기본값으로 대체되었습니다.",
            }
            if multi:
                fallback["recommended_cities"] = []
            else:
                fallback["recommended_city"] = "확인 필요"
            return fallback


def get_final_report(api_key: str, date_str: str, recommendation: dict,
                      restaurants_by_city: dict, errors: list) -> str:
    """[3/3] 1차 추천 + 맛집 목록 + 오류 요약을 바탕으로 최종 Markdown 리포트를 생성한다."""
    system_prompt = (
        "당신은 여행 리포트 작성 전문가입니다. 주어진 데이터를 바탕으로 "
        "한국어 Markdown 여행 리포트를 작성하세요. 데이터에 없는 내용을 지어내지 말고, "
        "주어진 정보만 활용하세요."
    )
    user_prompt = (
        f"아래 데이터를 바탕으로 '{date_str} 국내 여행 추천 리포트'를 Markdown으로 작성해줘.\n\n"
        f"[1차 추천 데이터]\n{json.dumps(recommendation, ensure_ascii=False, indent=2)}\n\n"
        f"[지역별 맛집 검색 결과]\n{json.dumps(restaurants_by_city, ensure_ascii=False, indent=2)}\n\n"
        f"[오류 요약]\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
        "리포트는 다음 섹션을 이 순서대로 포함해야 해 (지역이 여러 곳이면 지역별로 소제목을 나눠줘):\n"
        "# {날짜} 국내 여행 추천 리포트\n"
        "## 추천 지역\n"
        "## 추천 이유\n"
        "## 날씨 요약\n"
        "## 행사/축제\n"
        "## 맛집 추천 (검색 결과가 0건인 지역은 '데이터 없음'으로 표기)\n"
        "## 1일 일정 제안 (오전/오후/저녁)\n"
        "## 오류 요약 (errors 리스트가 비어 있으면 '없음'으로 표기)\n\n"
        "Markdown 텍스트만 출력하고, 다른 설명은 붙이지 마."
    )
    return call_anthropic(api_key, system_prompt, user_prompt, max_tokens=2500)


# ----------------------------------------------------------------------------
# 지도/장소 검색 API (어댑터 패턴)
# ----------------------------------------------------------------------------
# [#8] 지도 제공자를 교체하기 쉽도록 어댑터 인터페이스로 추상화한다.
#      - PlaceSearchAdapter: 공통 인터페이스(추상)
#      - KakaoLocalAdapter : Kakao Local 구현체
#      다른 제공자(Naver 등)를 쓰려면 PlaceSearchAdapter를 상속한 새 클래스를
#      만들어 search()만 구현하면 되고, 나머지 코드는 바꿀 필요가 없다.
class PlaceSearchAdapter:
    """지도/장소 검색 어댑터 공통 인터페이스."""

    def search(self, city: str, errors: list, size: int = 5) -> list:
        """도시명으로 맛집을 검색해 표준 형식의 리스트로 반환한다.
        실패해도 예외를 던지지 않고, errors에 기록 후 빈 리스트를 반환한다."""
        raise NotImplementedError


class KakaoLocalAdapter(PlaceSearchAdapter):
    """Kakao Local(키워드 검색) 구현체."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, city: str, errors: list, size: int = 5) -> list:
        # 검색은 서버 상태를 바꾸지 않고 결과만 조회하므로 GET을 사용한다.(#10)
        headers = {"Authorization": f"KakaoAK {self.api_key}"}
        params = {"query": f"{city} 맛집", "size": size, "sort": "accuracy"}

        try:
            resp = requests.get(KAKAO_LOCAL_SEARCH_URL, headers=headers,
                                 params=params, timeout=REQUEST_TIMEOUT)
        except (requests.exceptions.RequestException, UnicodeEncodeError) as e:
            # UnicodeEncodeError: 키에 한글 등 latin-1 불가 문자가 들어간 경우 방어
            errors.append({"step": "place_search", "type": "NETWORK_ERROR", "message": str(e)})
            return []

        if resp.status_code in (401, 403):
            errors.append({
                "step": "place_search", "type": "AUTH_ERROR",
                "message": f"HTTP {resp.status_code} - 키/권한/카카오맵 사용설정을 확인하세요.",
            })
            return []
        if resp.status_code == 429:
            errors.append({"step": "place_search", "type": "QUOTA_ERROR", "message": "HTTP 429 - 쿼터 초과"})
            return []
        if resp.status_code >= 400:
            errors.append({
                "step": "place_search", "type": "API_ERROR",
                "message": f"HTTP {resp.status_code} - {resp.text[:200]}",
            })
            return []

        try:
            data = resp.json()
        except ValueError as e:
            errors.append({"step": "place_search", "type": "PARSE_ERROR", "message": str(e)})
            return []

        documents = data.get("documents", [])
        if not documents:
            errors.append({
                "step": "place_search", "type": "EMPTY_RESULT",
                "message": f"0 results for query='{city} 맛집'",
            })
            return []

        restaurants = []
        for doc in documents:
            restaurants.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
                "x": doc.get("x", ""),  # 경도(longitude)
                "y": doc.get("y", ""),  # 위도(latitude)
            })
        return restaurants


def search_restaurants(kakao_key: str, city: str, errors: list, size: int = 5) -> list:
    """
    [2/3] 맛집 검색 진입점(하위 호환용 얇은 래퍼).
    내부적으로 KakaoLocalAdapter를 사용한다. 제공자를 바꾸려면 아래 어댑터만 교체하면 된다.
    """
    adapter = KakaoLocalAdapter(kakao_key)
    return adapter.search(city, errors, size)


# ----------------------------------------------------------------------------
# 메인 로직
# ----------------------------------------------------------------------------
def load_cached_raw_data(raw_path: Path):
    """
    캐시 JSON 파일을 안전하게 읽는다.
    - JSON 형식이 깨졌거나
    - 파일 읽기 실패가 있거나
    - 필수 구조가 없으면
    None을 반환하여 새 API 호출로 진행하게 한다.
    (반환 타입: dict | None)
    """
    try:
        text = raw_path.read_text(encoding="utf-8")
        cached = json.loads(text)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        log(f"[캐시] JSON 파싱 실패로 캐시를 무시합니다: {e}")
        return None
    except OSError as e:
        log(f"[캐시] 파일 읽기 실패로 캐시를 무시합니다: {e}")
        return None

    if not isinstance(cached, dict):
        log("[캐시] 캐시 구조가 올바르지 않아 무시합니다: 최상위 JSON 객체(dict)가 아닙니다.")
        return None

    required_keys = {"date", "recommendation", "restaurants_by_city", "errors"}
    missing_keys = required_keys - set(cached.keys())
    if missing_keys:
        log(f"[캐시] 캐시에 필수 키가 없어 무시합니다: {sorted(missing_keys)}")
        return None

    if not isinstance(cached.get("recommendation"), dict):
        log("[캐시] recommendation 구조가 올바르지 않아 캐시를 무시합니다.")
        return None
    if not isinstance(cached.get("restaurants_by_city"), dict):
        log("[캐시] restaurants_by_city 구조가 올바르지 않아 캐시를 무시합니다.")
        return None
    if not isinstance(cached.get("errors"), list):
        log("[캐시] errors 구조가 올바르지 않아 캐시를 무시합니다.")
        return None

    return cached


def normalize_city(name: str) -> str:
    """
    [#17] 추천 도시명을 장소 검색에 쓰기 좋게 정규화한다.
    - 앞뒤 공백 제거
    - 괄호와 그 안의 부연 설명 제거  예) "제주(제주도)" -> "제주"
    - 쉼표 이후 제거                예) "강릉, 강원도" -> "강릉"
    - "특별시/광역시/특별자치시/특별자치도" 접미사 정리 예) "서울특별시" -> "서울"
    """
    if not isinstance(name, str):
        return ""
    name = name.strip()
    name = re.sub(r"[\(（].*?[\)）]", "", name)   # 괄호 부연 제거
    name = name.split(",")[0].split("，")[0]        # 쉼표 이후 제거
    name = re.sub(r"(특별자치시|특별자치도|특별시|광역시)$", "", name.strip())
    return name.strip()


def get_cities_from_recommendation(recommendation: dict, multi: bool) -> list:
    if multi:
        raw_cities = recommendation.get("recommended_cities") or []
    else:
        city = recommendation.get("recommended_city")
        raw_cities = [city] if city else []

    # 정규화 + 빈값 제거 + 중복 제거(순서 유지)
    seen = set()
    cities = []
    for c in raw_cities:
        norm = normalize_city(c)
        if norm and norm not in seen:
            seen.add(norm)
            cities.append(norm)
    return cities


def run(date_str: str, multi: bool, use_cache: bool) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    mode_suffix = "_multi" if multi else "_single"
    raw_path = RESULTS_DIR / f"{date_str}{mode_suffix}_raw_data.json"
    report_path = RESULTS_DIR / f"{date_str}{mode_suffix}_travel_plan.md"

    # --- API 키 확인 (미설정 시 즉시 종료) ---
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    kakao_key = os.environ.get("KAKAO_REST_API_KEY")

    if not anthropic_key:
        die(
            "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "      .env 파일에 ANTHROPIC_API_KEY=발급받은키 형태로 추가하거나,\n"
            "      터미널에서 export ANTHROPIC_API_KEY=\"YOUR_KEY\" 로 설정한 뒤 다시 실행하세요."
        )
    if not kakao_key:
        die(
            "KAKAO_REST_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "      .env 파일에 KAKAO_REST_API_KEY=발급받은키 형태로 추가하거나,\n"
            "      터미널에서 export KAKAO_REST_API_KEY=\"YOUR_KEY\" 로 설정한 뒤 다시 실행하세요."
        )

    errors: list = []

    # --- 캐시 확인(보너스: 같은 --date로 재실행 시 API 호출 생략) ---
    cached = None
    if use_cache and raw_path.exists():
        cached = load_cached_raw_data(raw_path)

    if cached is not None:
        log(f"[캐시] 기존 결과 발견: {raw_path} (API 호출을 건너뛰고 리포트만 재생성합니다)")
        recommendation = cached["recommendation"]
        restaurants_by_city = cached["restaurants_by_city"]
        errors = cached["errors"]

        log("[1/3] 캐시된 1차 추천 데이터 사용")
        for city, places in restaurants_by_city.items():
            count = len(places) if isinstance(places, list) else 0
            log(f"[2/3] 캐시된 맛집 데이터 사용: {city} ({count}곳)")
    else:
        if use_cache and raw_path.exists():
            log("[캐시] 손상되었거나 형식이 올바르지 않아 새로 생성합니다.")

        # --- [1/3] LLM: 1차 추천 ---
        log("[1/3] 1차 추천 생성 중(LLM)...")
        recommendation = get_recommendation(anthropic_key, date_str, multi, errors)
        cities = get_cities_from_recommendation(recommendation, multi)
        if cities:
            for c in cities:
                log(f"    - recommended_city: \"{c}\"")
        else:
            log("    - (추천 지역을 확인하지 못했습니다. errors 섹션을 확인하세요)")

        # --- [2/3] Kakao Local: 맛집 검색 ---
        log("[2/3] 맛집 검색 중(지도/장소 API)...")
        restaurants_by_city = {}
        if not cities:
            errors.append({
                "step": "place_search", "type": "SKIPPED",
                "message": "추천 지역이 없어 맛집 검색을 건너뛰었습니다.",
            })
            log("    - 추천 지역이 없어 맛집 검색을 건너뜁니다.")
        else:
            for city in cities:
                found = search_restaurants(kakao_key, city, errors)
                restaurants_by_city[city] = found
                log(f"    - [{city}] 맛집 {len(found)}곳 검색 완료" if found
                    else f"    - [{city}] 맛집 검색 결과 0건")

        # --- 원본 데이터 저장 ---
        raw_data = {
            "date": date_str,
            "recommendation": recommendation,
            "restaurants_by_city": restaurants_by_city,
            "errors": errors,
        }
        raw_path.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- [3/3] LLM: 최종 리포트 생성 ---
    log("[3/3] 최종 리포트 생성 중(LLM)...")
    try:
        report_md = get_final_report(anthropic_key, date_str, recommendation,
                                      restaurants_by_city, errors)
    except (PermissionError, RuntimeError) as e:
        # 리포트 생성 자체가 실패하면 최소한의 텍스트로라도 결과를 남긴다.
        errors.append({"step": "final_report", "type": "LLM_ERROR", "message": str(e)})
        report_md = (
            f"# {date_str} 국내 여행 추천 리포트\n\n"
            f"리포트 생성 중 오류가 발생했습니다: {e}\n\n"
            f"## 오류 요약(errors)\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n"
        )

    report_path.write_text(report_md, encoding="utf-8")

    # 최신 errors를 원본 데이터 파일에도 반영(리포트 생성 단계 오류 포함)
    try:
        raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_data["errors"] = errors
        raw_path.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    log("    - 리포트 생성 완료")
    log(f"\n완료! {report_path} 를 확인하세요.")
    log(f"(원본 데이터: {raw_path})")


def parse_args():
    parser = argparse.ArgumentParser(
        description="국내 여행지 추천 프로그램 (LLM API + 지도 API)",
        epilog='예) python travel_planner.py --date "2026-03-15"',
    )
    parser.add_argument("--date", required=True, help='여행 날짜 (형식: "YYYY-MM-DD")')
    parser.add_argument("--multi", action="store_true",
                         help="[보너스] 여행지를 1곳이 아닌 2~3곳으로 확장 추천")
    parser.add_argument("--no-cache", action="store_true",
                         help="[보너스] 같은 날짜의 캐시된 결과가 있어도 무시하고 API를 새로 호출")
    return parser.parse_args()


def main():
    args = parse_args()
    date_str = validate_date(args.date)
    try:
        run(date_str, multi=args.multi, use_cache=not args.no_cache)
    except KeyboardInterrupt:
        die("사용자에 의해 중단되었습니다.", code=130)


if __name__ == "__main__":
    main()
