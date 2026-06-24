"""
gosapass 데이터 수집 스크립트
한국산업인력공단 OpenAPI -> data/ 폴더 JSON 저장

환경변수: API_KEY (GitHub Secret: DATA_GO_KR_API_KEY)
로컬: .env 파일에 API_KEY=... 설정

사용법:
  python scripts/fetch_data.py           # 전체 실행 (phase1 + phase2)
  python scripts/fetch_data.py --phase1  # 벌크 데이터만 (5 API 호출)
  python scripts/fetch_data.py --phase2  # 종목별 상세 데이터 (배치)
"""

import os
import sys
import json
import time
import re
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path

import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── 설정 ──────────────────────────────────────────────────────────────────────
BASE_URL = "http://openapi.q-net.or.kr/api/service/rest"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

MAX_PER_RUN = 150   # 종목별 배치 최대 처리 건수 (5호출 x 150 = 750/일)
CACHE_DAYS = 7      # 종목별 상세 캐시 유효기간 (일)
REQUEST_DELAY = 0.5 # API 요청 간 딜레이 (초)
TIMEOUT = 30        # API 타임아웃 (초)
MAX_RETRY = 3       # 재시도 횟수

# ── API 키 로드 ────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("API_KEY") or os.environ.get("DATA_GO_KR_API_KEY")
if not API_KEY:
    print("[ERROR] API_KEY 환경변수가 설정되지 않았습니다.")
    print("  로컬: .env 파일에 API_KEY=발급받은키 추가")
    print("  GitHub Actions: Secrets에 DATA_GO_KR_API_KEY 등록")
    sys.exit(1)


# ── 유틸 ──────────────────────────────────────────────────────────────────────
def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "stats").mkdir(exist_ok=True)


def fmt_date(raw: str) -> str:
    """YYYYMMDD -> YYYY-MM-DD. 'XXXXXXXX' 같은 미정 값은 빈 문자열."""
    if not raw or len(raw) < 8 or not raw[:8].isdigit():
        return ""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def api_get(path: str, params: dict) -> ET.Element | None:
    """API 호출 후 XML <items> 반환. 실패/재시도 포함."""
    p = dict(params)
    p["ServiceKey"] = API_KEY
    url = f"{BASE_URL}/{path}"
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=p, timeout=TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            result_code = root.findtext("./header/resultCode", "")
            if result_code not in ("00", "000", "NORMAL_CODE", "NORMAL SERVICE."):
                msg = root.findtext("./header/resultMsg", "")
                print(f"  [API 오류] {result_code}: {msg}")
                return None
            return root.find("./body/items")
        except requests.Timeout:
            print(f"  [타임아웃] {attempt}/{MAX_RETRY} 재시도...")
            time.sleep(2 ** attempt)
        except requests.RequestException as e:
            print(f"  [네트워크 오류] {e}")
            if attempt < MAX_RETRY:
                time.sleep(2 ** attempt)
        except ET.ParseError as e:
            print(f"  [XML 파싱 오류] {e}")
            return None
    return None


def items_to_list(items_el: ET.Element | None) -> list[dict]:
    """<items><item>...</item></items> -> list[dict]"""
    if items_el is None:
        return []
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in items_el.findall("item")
    ]


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        print(f"  저장: {path.relative_to(DATA_DIR.parent)}")
    except ValueError:
        print(f"  저장: {path}")


def load_json(path: Path) -> dict | list | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def is_stale(path: Path, days: int = CACHE_DAYS) -> bool:
    if not path.exists():
        return True
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).days >= days


def parse_description(desc: str) -> tuple[str, str]:
    """
    'description' 필드에서 (그룹명, 회차) 추출.
    예) '기사,산업기사(2026년도 제2회)' -> ('기사/산업기사', '제2회')
        '2026년 정기 기능사 1회'        -> ('기능사', '제1회')
    """
    # 패턴 1: "...(YYYY년도 제N회)"
    m = re.search(r'제(\d+)회', desc)
    if m:
        round_str = f"제{m.group(1)}회"
        # 그룹명: 괄호 앞 부분에서 연도 등 제거
        group = re.sub(r'\(.*\)', '', desc).strip()
        group = re.sub(r'기사,산업기사', '기사/산업기사', group)
        group = re.sub(r'\d{4}년도?\s*', '', group).strip(' ,')
        return group or desc, round_str

    # 패턴 2: "...N회" (숫자+회)
    m2 = re.search(r'(\d+)회', desc)
    if m2:
        round_str = f"제{m2.group(1)}회"
        group = re.sub(r'\d{4}년\s*정기\s*', '', desc)
        group = re.sub(r'\s*\d+회.*', '', group).strip()
        return group or desc, round_str

    return desc, ""


# ── Phase 1: 벌크 데이터 ──────────────────────────────────────────────────────
def fetch_exam_list() -> list[dict]:
    """모든 국가기술자격 종목 목록 조회"""
    print(">>> 종목 목록 조회 (InquiryListNationalQualifcationSVC/getList)")
    items = api_get("InquiryListNationalQualifcationSVC/getList", {})
    rows = items_to_list(items)
    result = []
    for r in rows:
        result.append({
            "jmcd":  r.get("jmcd", ""),
            "name":  r.get("jmfldnm", ""),
            "qual_type": r.get("qualgbcd", ""),
            "qual_name": r.get("qualgbnm", ""),
            "series":    r.get("seriesnm", ""),
            "field":     r.get("obligfldnm", ""),
        })
    print(f"  -> {len(result)}개 종목")
    return result


def fetch_schedule_bulk(endpoint: str, label: str) -> list[dict]:
    """
    등급별 전체 시험일정 (getEList/getPEList/getMCList/getCList)
    실제 API 필드: description, docregstartdt, docregenddt, docexamdt,
                   docpassdt, pracregstartdt, pracregenddt,
                   pracexamstartdt, pracexamenddt, pracpassdt
    """
    print(f">>> {label} 일정 조회 ({endpoint})")
    items = api_get(f"InquiryTestInformationNTQSVC/{endpoint}", {})
    rows = items_to_list(items)
    seen = set()
    result = []
    for r in rows:
        desc = r.get("description", "")
        group, round_str = parse_description(desc)
        key = (group, round_str)
        if key in seen:
            continue  # 중복 회차 제거 (다른 접수기간 항목 무시)
        seen.add(key)
        # docexamdt는 단일 날짜 (필기시험일)
        exam_dt = fmt_date(r.get("docexamdt", ""))
        result.append({
            "name":              group,
            "round":             round_str,
            "written_reg_start": fmt_date(r.get("docregstartdt", "")),
            "written_reg_end":   fmt_date(r.get("docregenddt", "")),
            "written_exam_start":exam_dt,
            "written_exam_end":  exam_dt,
            "written_pass":      fmt_date(r.get("docpassdt", "")),
            "prac_reg_start":    fmt_date(r.get("pracregstartdt", "")),
            "prac_reg_end":      fmt_date(r.get("pracregenddt", "")),
            "prac_exam_start":   fmt_date(r.get("pracexamstartdt", "")),
            "prac_exam_end":     fmt_date(r.get("pracexamenddt", "")),
            "prac_pass_start":   fmt_date(r.get("pracpassdt", "")),
            "prac_pass_end":     fmt_date(r.get("pracpassdt", "")),
        })
    print(f"  -> {len(result)}건")
    return result


def phase1():
    """벌크 데이터 수집 (약 5 API 호출)"""
    print("\n=== Phase 1: 벌크 데이터 수집 ===")
    ensure_dirs()

    # 종목 목록
    exams = fetch_exam_list()
    save_json(DATA_DIR / "exams.json", {
        "updated": date.today().isoformat(),
        "count": len(exams),
        "items": exams,
    })
    time.sleep(REQUEST_DELAY)

    # 등급별 일정
    all_schedules = []
    for endpoint, label in [
        ("getEList",  "기사/산업기사"),
        ("getPEList", "기술사"),
        ("getMCList", "기능장"),
        ("getCList",  "기능사"),
    ]:
        rows = fetch_schedule_bulk(endpoint, label)
        all_schedules.extend(rows)
        time.sleep(REQUEST_DELAY)

    save_json(DATA_DIR / "schedules.json", {
        "updated": date.today().isoformat(),
        "count": len(all_schedules),
        "items": all_schedules,
    })

    # 다가오는 시험 - index.html 용
    _build_upcoming(all_schedules)

    # docs/data/ 에 복사 (GitHub Pages에서 /data/* 로 접근)
    docs_data = DATA_DIR.parent / "docs" / "data"
    docs_data.mkdir(exist_ok=True)
    save_json(docs_data / "exams.json", {
        "updated": date.today().isoformat(),
        "count": len(exams),
        "items": exams,
    })
    save_json(docs_data / "schedules.json", {
        "updated": date.today().isoformat(),
        "count": len(all_schedules),
        "items": all_schedules,
    })

    print("\nPhase 1 완료")


def _build_upcoming(schedules: list[dict]):
    """개별 시험 단위 30일 이내 이벤트 -> docs/data/upcoming.json"""
    today = date.today()

    # 그룹 일정 룩업: "기사/산업기사" → [schedule_item, ...]
    group_sched: dict[str, list] = {}
    for s in schedules:
        group_sched.setdefault(s["name"], []).append(s)

    SERIES_GROUP = {
        "기사":   "기사/산업기사",
        "기술사": "기술사",
        "기능장": "기능장",
        "기능사": "기능사",
    }

    EVENT_KEYS = [
        ("written_reg_end",    "필기 접수마감"),
        ("written_exam_start", "필기 시험"),
        ("written_pass",       "필기 합격발표"),
        ("prac_reg_end",       "실기 접수마감"),
        ("prac_exam_start",    "실기 시험"),
        ("prac_pass_end",      "실기 합격발표"),
    ]

    # 종목 목록 로드
    exams_path = DATA_DIR / "exams.json"
    if not exams_path.exists():
        return
    exams = json.loads(exams_path.read_text(encoding="utf-8")).get("items", [])

    # 응시자 수 기준 정렬 (인기 종목 우선 노출)
    def get_applicants(jmcd: str) -> int:
        p = DATA_DIR / "stats" / f"{jmcd}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            for row in reversed(d.get("stats", {}).get("written", [])):
                if row.get("applicants", 0) > 0:
                    return row["applicants"]
        return 0

    exams_sorted = sorted(exams, key=lambda e: get_applicants(e["jmcd"]), reverse=True)

    upcoming = []
    # (그룹, 회차, 이벤트, 날짜) 조합당 가장 인기 있는 1개만 노출
    seen: set[tuple] = set()

    for exam in exams_sorted:
        jmcd  = exam["jmcd"]
        name  = exam["name"]
        series = exam.get("series", "")
        if not jmcd or not name:
            continue

        # 개별 일정 우선, 없으면 그룹 폴백
        exam_schedule: list[dict] = []
        stats_path = DATA_DIR / "stats" / f"{jmcd}.json"
        if stats_path.exists():
            exam_schedule = json.loads(stats_path.read_text(encoding="utf-8")).get("schedule", [])
        if not exam_schedule:
            group_key = SERIES_GROUP.get(series, "")
            exam_schedule = group_sched.get(group_key, [])

        for s in exam_schedule:
            round_str = s.get("round", "")
            group_key = SERIES_GROUP.get(series, series)
            for event_key, event_label in EVENT_KEYS:
                d_str = s.get(event_key, "")
                if not d_str:
                    continue
                try:
                    d = date.fromisoformat(d_str)
                except ValueError:
                    continue
                diff = (d - today).days
                if not (-3 <= diff <= 30):
                    continue
                dedup = (group_key, round_str, event_label, d_str)
                if dedup in seen:
                    continue
                seen.add(dedup)
                upcoming.append({
                    "name":  name,
                    "round": round_str,
                    "event": event_label,
                    "date":  d_str,
                    "dday":  diff,
                })

    upcoming.sort(key=lambda x: x["date"])
    out_path = DATA_DIR.parent / "docs" / "data"
    out_path.mkdir(exist_ok=True)
    save_json(out_path / "upcoming.json", {
        "updated": today.isoformat(),
        "items": upcoming,
    })


# ── Phase 2: 종목별 상세 데이터 ──────────────────────────────────────────────
def fetch_jm_schedule(jmcd: str) -> list[dict]:
    """종목별 시행일정 (getJMList) — 실제 필드 기준"""
    items = api_get("InquiryTestInformationNTQSVC/getJMList", {"jmCd": jmcd})
    rows = items_to_list(items)
    result = []
    for r in rows:
        desc = r.get("description", "") or r.get("implplannm", "")
        _, round_str = parse_description(desc)
        if not round_str:
            round_str = desc
        exam_dt = fmt_date(r.get("docexamdt", ""))
        result.append({
            "round":             round_str or desc,
            "written_reg_start": fmt_date(r.get("docregstartdt", "")),
            "written_reg_end":   fmt_date(r.get("docregenddt", "")),
            "written_exam_start":exam_dt,
            "written_exam_end":  exam_dt,
            "written_pass":      fmt_date(r.get("docpassdt", "")),
            "prac_reg_start":    fmt_date(r.get("pracregstartdt", "")),
            "prac_reg_end":      fmt_date(r.get("pracregenddt", "")),
            "prac_exam_start":   fmt_date(r.get("pracexamstartdt", "")),
            "prac_exam_end":     fmt_date(r.get("pracexamenddt", "")),
            "prac_pass_start":   fmt_date(r.get("pracpassdt", "")),
            "prac_pass_end":     fmt_date(r.get("pracpassdt", "")),
        })
    return result


def fetch_jm_fee(jmcd: str) -> dict:
    """응시 수수료"""
    items = api_get("InquiryTestInformationNTQSVC/getFeeList", {"jmCd": jmcd})
    rows = items_to_list(items)
    fee = {"written": "", "practical": "", "raw": ""}
    for r in rows:
        contents = r.get("contents", "")
        fee["raw"] = contents
        nums = re.findall(r"\d{4,6}", contents)
        if len(nums) >= 2:
            fee["written"] = nums[0]
            fee["practical"] = nums[1]
        elif len(nums) == 1:
            fee["written"] = nums[0]
    return fee


def fetch_jm_info(jmcd: str) -> list[dict]:
    """종목별 자격정보 (시험과목, 응시자격 등)"""
    items = api_get("InquiryInformationTradeNTQSVC/getList", {"jmCd": jmcd})
    rows = items_to_list(items)
    return [{"type": r.get("infogb", ""), "content": r.get("contents", "")} for r in rows]


def fetch_jm_stats(jmcd: str, base_yy: str) -> dict:
    """종목별 연도별 합격 통계 (필기 + 실기)"""
    pi_items = api_get("InquiryStatSVC/getEventYearPiList", {"jmCd": jmcd, "baseYY": base_yy})
    pi_rows = items_to_list(pi_items)
    si_items = api_get("InquiryStatSVC/getEventYearSiList", {"jmCd": jmcd, "baseYY": base_yy})
    si_rows = items_to_list(si_items)

    def parse_yearly(rows: list[dict], base_year: int) -> list[dict]:
        if not rows:
            return []
        r = rows[0]
        result = []
        for i in range(5, 0, -1):
            year = base_year - (i - 1)
            applicants = int(r.get(f"ilecnt{i}", 0) or 0)
            passers    = int(r.get(f"ilpcnt{i}", 0) or 0)
            rate = round(passers / applicants * 100, 1) if applicants > 0 else 0.0
            result.append({"year": year, "applicants": applicants, "passers": passers, "passRate": rate})
        return result

    base_year = int(base_yy)
    return {
        "written":   parse_yearly(pi_rows, base_year),
        "practical": parse_yearly(si_rows, base_year),
    }


def phase2():
    """종목별 상세 데이터 수집 (배치, MAX_PER_RUN 건 제한)"""
    print("\n=== Phase 2: 종목별 상세 데이터 수집 ===")
    ensure_dirs()

    exams_data = load_json(DATA_DIR / "exams.json")
    if not exams_data:
        print("[ERROR] data/exams.json 없음. 먼저 --phase1 실행 필요")
        sys.exit(1)

    exams = exams_data["items"]
    # 당해 연도 통계는 미집계 상태 → 전년도 기준으로 최근 5년 데이터 조회
    base_yy = str(date.today().year - 1)

    stale = [e for e in exams if e["jmcd"] and is_stale(DATA_DIR / "stats" / f"{e['jmcd']}.json")]
    print(f"  캐시 만료: {len(stale)}개 / 전체: {len(exams)}개")

    batch = stale[:MAX_PER_RUN]
    print(f"  이번 배치: {len(batch)}개")

    api_calls = 0
    processed = 0
    for exam in batch:
        jmcd = exam["jmcd"]
        name = exam["name"]
        processed += 1
        print(f"  [{processed:3}/{len(batch)}] {name} ({jmcd})")

        detail = {
            "jmcd":    jmcd,
            "name":    name,
            "series":  exam["series"],
            "field":   exam["field"],
            "updated": date.today().isoformat(),
        }

        # 시험일정
        schedule = fetch_jm_schedule(jmcd)
        detail["schedule"] = schedule
        api_calls += 1
        time.sleep(REQUEST_DELAY)

        # 수수료
        fee = fetch_jm_fee(jmcd)
        detail["fee"] = fee
        api_calls += 1
        time.sleep(REQUEST_DELAY)

        # 자격정보
        info = fetch_jm_info(jmcd)
        detail["info"] = info
        api_calls += 1
        time.sleep(REQUEST_DELAY)

        # 통계
        stats = fetch_jm_stats(jmcd, base_yy)
        detail["stats"] = stats
        api_calls += 2
        time.sleep(REQUEST_DELAY)

        save_json(DATA_DIR / "stats" / f"{jmcd}.json", detail)

        if api_calls >= 900:
            print(f"  [안전] API {api_calls}회 도달. 배치 중단.")
            break

    print(f"\nPhase 2 완료 -- {processed}개 처리, 총 {api_calls}회 API 호출")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="gosapass 데이터 수집")
    parser.add_argument("--phase1", action="store_true")
    parser.add_argument("--phase2", action="store_true")
    args = parser.parse_args()

    if args.phase1:
        phase1()
    elif args.phase2:
        phase2()
    else:
        phase1()
        phase2()


if __name__ == "__main__":
    main()
