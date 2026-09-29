"""
build_blog.py - content/*.md → docs/ 정적 블로그 생성 (다른 도메인에도 site.json만 바꿔 재사용)
실행: python scripts/build_blog.py
"""
import json
from datetime import date
from pathlib import Path

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader

BASE_DIR    = Path(__file__).parent.parent
DOCS_DIR    = BASE_DIR / "docs"
CONTENT_DIR = BASE_DIR / "content"
TMPL_DIR    = Path(__file__).parent / "templates"
SITE        = json.loads((BASE_DIR / "site.json").read_text(encoding="utf-8"))
TODAY_STR   = str(date.today())

env = Environment(loader=FileSystemLoader(str(TMPL_DIR)), autoescape=True)


def render(tmpl, out_path, **ctx):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(env.get_template(tmpl).render(site=SITE, **ctx), encoding="utf-8")
    print(f"  {out_path.relative_to(BASE_DIR)}")


def load_md(path):
    """상단 --- key: value --- 헤더 + 마크다운 본문"""
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        _, head, body = raw.split("---", 2)
        for line in head.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    meta.setdefault("slug", path.stem)
    meta.setdefault("date", TODAY_STR)
    meta.setdefault("description", "")
    meta["html"] = md_lib.markdown(body.strip(), extensions=["tables"])
    return meta


def is_draft(m):
    return m.get("draft", "").lower() == "true"


def main():
    domain = SITE["domain"]
    posts = [m for m in (load_md(f) for f in sorted((CONTENT_DIR / "blog").glob("*.md"))) if not is_draft(m)]
    posts.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)
    pages = [m for m in (load_md(f) for f in sorted((CONTENT_DIR / "pages").glob("*.md"))) if not is_draft(m)]

    print("[posts]")
    for m in posts:
        others = [o for o in posts if o["slug"] != m["slug"]][:4]
        ld = json.dumps({
            "@context": "https://schema.org", "@type": "Article",
            "headline": m["title"], "description": m["description"],
            "datePublished": m["date"], "dateModified": m.get("updated", m["date"]),
            "inLanguage": "ko-KR",
            "author": {"@type": "Organization", "name": SITE["author"]},
            "publisher": {"@type": "Organization", "name": SITE["name"], "url": domain},
            "mainEntityOfPage": f"{domain}/blog/{m['slug']}.html",
        }, ensure_ascii=False)
        render("blog_post.html", DOCS_DIR / "blog" / f"{m['slug']}.html", post=m, others=others, ld_json=ld)

    print("[home/pages]")
    render("home.html", DOCS_DIR / "index.html", posts=posts)
    for m in pages:
        render("page.html", DOCS_DIR / f"{m['slug']}.html", page=m)
    render("404.html", DOCS_DIR / "404.html")

    urls = [(f"{domain}/", "1.0")] + [(f"{domain}/blog/{m['slug']}.html", "0.8") for m in posts] \
           + [(f"{domain}/{m['slug']}.html", "0.4") for m in pages]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, pri in urls:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{TODAY_STR}</lastmod><priority>{pri}</priority></url>")
    lines.append("</urlset>")
    (DOCS_DIR / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")
    print(f"[sitemap] {len(urls)} URLs")


if __name__ == "__main__":
    main()
