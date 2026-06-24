"""
gosapass 페이지 생성 스크립트
data/ JSON → docs/exam/*.html (Jinja2 템플릿)

사용법:
  python scripts/generate_pages.py                  # 전체 생성
  python scripts/generate_pages.py --jmcd 7010      # 특정 종목만
  python scripts/generate_pages.py --limit 50       # 처음 N개만
"""

import json
import sys
import re
import argparse
from datetime import date
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("[ERROR] Jinja2 미설치. pip install jinja2")
    sys.exit(1)

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = ROOT / "docs" / "exam"

# 직무분야 → CSS 클래스 매핑
FIELD_CSS = {
    "전기·전자": "electric",
    "전기전자":  "electric",
    "정보통신":  "it",
    "IT":        "it",
    "건설":      "construction",
    "안전관리":  "safety",
    "안전":      "safety",
    "기계":      "machine",
    "화학":      "chem",
    "농림어업":  "agri",
    "서비스":    "service",
}


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def get_field_class(field: str) -> str:
    for key, css in FIELD_CSS.items():
        if key in field:
            return css
    return "default"


# ── D-Day 계산 ─────────────────────────────────────────────────────────────────
EVENTS = [
    ("written_reg_start", "written_reg_end",  "{round} 필기 원서접수 진행중", "{round} 필기시험"),
    ("written_exam_start","written_exam_end",  "{round} 필기시험 진행중",     "{round} 필기 합격발표"),
    ("prac_reg_start",    "prac_reg_end",      "{round} 실기 원서접수 진행중","{round} 실기시험"),
    ("prac_exam_start",   "prac_exam_end",     "{round} 실기시험 진행중",     "{round} 최종 합격발표"),
]
NEXT_EVENTS = [
    "written_reg_start", "written_exam_start", "written_pass",
    "prac_reg_start",    "prac_exam_start",    "prac_pass_end",
]


def parse_date(s: str):
    if s:
        try:
            return date.fromisoformat(s)
        except ValueError:
            pass
    return None


def compute_dday(schedule: list[dict], today: date) -> dict | None:
    # 1. 진행 중인 접수/시험 먼저
    for i, r in enumerate(schedule):
        for start_k, end_k, active_label, next_label in EVENTS:
            s = parse_date(r.get(start_k, ""))
            e = parse_date(r.get(end_k, ""))
            if s and e and s <= today <= e:
                diff = (e - today).days
                dday_text = "접수중" if diff == 0 else f"D-{diff}"
                period = f"{r[start_k][5:]} ~ {r[end_k][5:]}"

                # 다음 이벤트 찾기
                next_date = ""
                next_lbl = next_label.format(round=r["round"])
                for ek in NEXT_EVENTS:
                    d = parse_date(r.get(ek, ""))
                    if d and d > today:
                        next_date = r[ek]
                        break

                return {
                    "start": r[start_k],
                    "end": r[end_k],
                    "event_label": active_label.format(round=r["round"]),
                    "dday_text": dday_text,
                    "period": period,
                    "next_label": next_lbl,
                    "next_date": next_date,
                    "next_text": f"다음 일정: {next_lbl} {next_date}" if next_date else "",
                    "color_class": "color-green",
                    "active_round_index": i + 1,
                }

    # 2. 가장 가까운 미래 이벤트
    best = None
    best_diff = 999
    for i, r in enumerate(schedule):
        for ek in NEXT_EVENTS:
            d = parse_date(r.get(ek, ""))
            if d and d > today:
                diff = (d - today).days
                if diff < best_diff:
                    best_diff = diff
                    label_map = {
                        "written_reg_start": f"{r['round']} 필기 원서접수 시작",
                        "written_exam_start": f"{r['round']} 필기시험",
                        "written_pass":       f"{r['round']} 필기 합격발표",
                        "prac_reg_start":     f"{r['round']} 실기 원서접수 시작",
                        "prac_exam_start":    f"{r['round']} 실기시험",
                        "prac_pass_end":      f"{r['round']} 최종 합격발표",
                    }
                    color = "color-urgent" if diff <= 3 else ("color-warning" if diff <= 7 else "color-normal")
                    best = {
                        "start": r[ek],
                        "end": r[ek],
                        "event_label": label_map.get(ek, ek),
                        "dday_text": f"D-{diff}",
                        "period": r[ek],
                        "next_label": "",
                        "next_date": "",
                        "next_text": "",
                        "color_class": color,
                        "active_round_index": i + 1,
                    }
    return best


# ── 통계 처리 ──────────────────────────────────────────────────────────────────
def build_stats_json(stats: dict) -> str:
    """detail.js가 읽는 형식으로 변환"""
    written = stats.get("written", [])
    practical = stats.get("practical", [])

    combined = {}
    for r in written:
        yr = r["year"]
        combined.setdefault(yr, {})["year"] = yr
        combined[yr]["writtenApplicants"] = r["applicants"]
        combined[yr]["writtenPassRate"] = r["passRate"]
    for r in practical:
        yr = r["year"]
        combined.setdefault(yr, {})["year"] = yr
        combined[yr]["practicalApplicants"] = r["applicants"]
        combined[yr]["practicalPassRate"] = r["passRate"]

    rows = sorted(combined.values(), key=lambda x: x["year"])
    for r in rows:
        r.setdefault("writtenApplicants", 0)
        r.setdefault("writtenPassRate", 0)
        r.setdefault("practicalApplicants", 0)
        r.setdefault("practicalPassRate", 0)
    return json.dumps(rows, ensure_ascii=False)


def compute_difficulty(stats: dict) -> dict | None:
    practical = stats.get("practical", [])
    written = stats.get("written", [])
    if not practical or not written:
        return None

    prac_rates = [r["passRate"] for r in practical[-3:] if r["passRate"] > 0]
    writ_rates = [r["passRate"] for r in written[-3:] if r["passRate"] > 0]
    if not prac_rates or not writ_rates:
        return None

    prac_avg = round(sum(prac_rates) / len(prac_rates), 1)
    writ_avg = round(sum(writ_rates) / len(writ_rates), 1)
    avg = (prac_avg + writ_avg) / 2

    if avg >= 60:
        level, label = 1, "쉬움"
    elif avg >= 45:
        level, label = 2, "보통"
    elif avg >= 30:
        level, label = 3, "어려움"
    elif avg >= 20:
        level, label = 4, "매우 어려움"
    else:
        level, label = 5, "최상급"

    return {"level": level, "label": label, "prac_avg": prac_avg, "writ_avg": writ_avg}


# ── 메인 생성 로직 ─────────────────────────────────────────────────────────────
def generate_pages(target_jmcd: str = None, limit: int = None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    # urlencode 필터 추가
    from urllib.parse import quote
    env.filters["urlencode"] = lambda s: quote(str(s))

    tmpl = env.get_template("detail.html.j2")

    exams_data = load_json(DATA_DIR / "exams.json")
    if not exams_data:
        print("[ERROR] data/exams.json 없음")
        sys.exit(1)

    # 그룹 일정 로드 (개별 일정 없는 경우 폴백용)
    group_schedule_map: dict[str, list] = {}
    schedules_data = load_json(DATA_DIR.parent / "docs" / "data" / "schedules.json") or {}
    for s in schedules_data.get("items", []):
        key = s["name"]
        group_schedule_map.setdefault(key, []).append(s)

    # qual_name → 그룹 일정 키 매핑
    QUAL_GROUP = {
        "기사":      "기사/산업기사",
        "산업기사":  "기사/산업기사",
        "기술사":    "기술사",
        "기능장":    "기능장",
        "기능사":    "기능사",
    }

    today = date.today()
    year = today.year
    today_str = today.isoformat()

    exams = exams_data["items"]
    if target_jmcd:
        exams = [e for e in exams if e["jmcd"] == target_jmcd]
    if limit:
        exams = exams[:limit]

    generated = 0
    for exam in exams:
        jmcd = exam["jmcd"]
        name = exam["name"]
        if not jmcd or not name:
            continue

        # 종목별 상세 데이터 (없으면 빈 값으로 진행)
        detail = load_json(DATA_DIR / "stats" / f"{jmcd}.json") or {}

        fee = detail.get("fee", {})
        info = detail.get("info", [])
        stats = detail.get("stats", {})

        # 시험일정: 개별 일정 우선, 없으면 그룹 일정 폴백
        schedule = detail.get("schedule", [])
        if not schedule:
            qual_name = exam.get("series", "")
            group_key = QUAL_GROUP.get(qual_name, "")
            if group_key and group_key in group_schedule_map:
                schedule = group_schedule_map[group_key]

        # D-Day 계산
        dday = compute_dday(schedule, today) if schedule else None

        # 통계 JSON (detail.js 형식)
        stats_json = build_stats_json(stats) if stats else "[]"

        # 난이도
        difficulty = compute_difficulty(stats) if stats else None

        # 사이드바 추가 데이터
        exam_rounds = len(schedule) if schedule else 0

        recent_applicants = 0
        recent_passers = 0
        recent_year = ""
        written = stats.get("written", []) if stats else []
        practical = stats.get("practical", []) if stats else []
        for row in reversed(written):
            if row.get("applicants", 0) > 0:
                recent_applicants = row["applicants"]
                recent_passers = row.get("passers", 0)
                recent_year = str(row["year"])
                break
        if not recent_applicants:
            for row in reversed(practical):
                if row.get("applicants", 0) > 0:
                    recent_applicants = row["applicants"]
                    recent_passers = row.get("passers", 0)
                    recent_year = str(row["year"])
                    break

        ctx = {
            "exam": {
                **exam,
                "field_class": get_field_class(exam.get("field", "")),
            },
            "year": year,
            "today": today_str,
            "schedule": schedule,
            "dday": dday,
            "fee": fee,
            "info": info,
            "stats": stats,
            "stats_json": stats_json,
            "difficulty": difficulty,
            "exam_rounds": exam_rounds,
            "recent_applicants": recent_applicants,
            "recent_passers": recent_passers,
            "recent_year": recent_year,
        }

        # 파일명: 슬래시 등 경로 구분자 제거 (GitHub Pages 지원)
        safe_name = name.replace("/", "-").replace("\\", "-").replace(":", "-")
        out_path = OUTPUT_DIR / f"{safe_name}.html"
        out_path.write_text(tmpl.render(**ctx), encoding="utf-8")
        generated += 1

        if generated % 50 == 0:
            print(f"  {generated}개 생성됨...")

    print(f"\n완료: {generated}개 페이지 생성 -> {OUTPUT_DIR.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="gosapass 페이지 생성")
    parser.add_argument("--jmcd", help="특정 종목코드만 생성")
    parser.add_argument("--limit", type=int, help="처음 N개만 생성")
    args = parser.parse_args()
    generate_pages(target_jmcd=args.jmcd, limit=args.limit)


if __name__ == "__main__":
    main()
