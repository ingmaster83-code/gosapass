"""
sitemap.xml 생성 스크립트
docs/exam/*.html + 주요 페이지 -> docs/sitemap.xml
"""

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
BASE_URL = "https://gosapass.kr"


def main():
    today = date.today().isoformat()
    urls = []

    # 정적 주요 페이지
    static_pages = [
        ("", "1.0", "daily"),
        ("list.html", "0.9", "daily"),
        ("calendar.html", "0.9", "daily"),
    ]
    for path, priority, freq in static_pages:
        url = f"{BASE_URL}/{path}"
        urls.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    # 자격증 상세 페이지
    exam_dir = DOCS_DIR / "exam"
    if exam_dir.exists():
        exam_files = sorted(exam_dir.glob("*.html"))
        for f in exam_files:
            name = f.stem  # 파일명 (확장자 제외)
            from urllib.parse import quote
            url = f"{BASE_URL}/exam/{quote(name)}.html"
            urls.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    out = DOCS_DIR / "sitemap.xml"
    out.write_text(sitemap, encoding="utf-8")
    print(f"sitemap.xml 생성 완료: {len(urls)}개 URL -> {out}")


if __name__ == "__main__":
    main()
