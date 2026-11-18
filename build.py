"""Generate the catalogue and one static HTML page per article."""

import json
import re
import shutil
import subprocess
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PORTAL = "Среда ИИ"
INTRO = "Учебный портал о том, как применять ИИ в работе."
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
MATERIAL_URL = re.compile(rf"/materials/(?P<slug>{SLUG})/")


def load_catalog():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    section_ids = set()
    urls = set()
    for section in catalog:
        section_id = section["id"]
        if not re.fullmatch(SLUG, section_id) or section_id in section_ids or section_id == "main":
            raise ValueError(f"Недопустимый или повторяющийся ID раздела: {section_id}")
        section_ids.add(section_id)
        for article in section["articles"]:
            url = article["url"]
            if not MATERIAL_URL.fullmatch(url) or url in urls:
                raise ValueError(f"Недопустимый или повторяющийся URL статьи: {url}")
            urls.add(url)
    return catalog


def sidebar(catalog, section_id, is_catalog):
    links = []
    for section in catalog:
        href = f'#{section["id"]}' if is_catalog else f'/#{section["id"]}'
        current = ' aria-current="location"' if section["id"] == section_id else ""
        links.append(f'<li><a href="{href}"{current}>{escape(section["nav"])}</a></li>')
    return f"""<header class="sidebar">
    <a class="brand" href="/" aria-label="{PORTAL} — каталог">
      <span class="brand-mark" aria-hidden="true">✳</span>
      {PORTAL}
    </a>
    <nav class="sections-nav" aria-label="Разделы каталога">
      <ul>{"".join(links)}</ul>
    </nav>
  </header>"""


def page(title, description, catalog, main, *, section_id=None, is_catalog=False):
    document_title = PORTAL if is_catalog else f"{title} — {PORTAL}"
    script = '  <script src="/assets/catalog.js" defer></script>\n' if is_catalog else ""
    metrics_script = '  <script src="/assets/metrics.js" defer></script>\n' if section_id else ""
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description)}">
  <title>{escape(document_title)}</title>
  <link rel="stylesheet" href="/assets/site.css">
{script}{metrics_script}</head>
<body>
  <a class="skip-link" href="#main">Перейти к содержанию</a>
  {sidebar(catalog, section_id, is_catalog)}
  <main id="main" class="main" tabindex="-1">
    {main}
  </main>
</body>
</html>
"""


def render_card(article):
    title = escape(article["title"])
    url = article["url"]
    slug = MATERIAL_URL.fullmatch(url)["slug"]
    return f"""<li class="card" data-material="{slug}">
          <a class="card-link" href="{url}">
            <h3>{title}</h3>
            <span class="card-arrow" aria-hidden="true">→</span>
            <p>{escape(article['description'])}</p>
          </a>
          <div class="card-metrics">
            <button class="helpful-button" type="button" aria-pressed="false" disabled>
              Было полезно <span class="helpful-count">—</span>
            </button>
            <span class="views">Просмотры <span class="view-count">—</span></span>
          </div>
          <p class="card-feedback" role="status"></p>
        </li>"""


def render_section(section):
    cards = "\n".join(render_card(article) for article in section["articles"])
    section_id = section["id"]
    return f"""<section class="catalog-section" id="{section_id}" tabindex="-1"
        aria-labelledby="heading-{section_id}">
      <h2 id="heading-{section_id}">{escape(section['title'])}</h2>
      <ul class="cards">
        {cards}
      </ul>
    </section>"""


def render_markdown(path):
    if not path.is_file():
        return '<p class="material-status">Материал готовится</p>'
    result = subprocess.run(
        ["pandoc", "--from=gfm-raw_html", "--to=html5", "--wrap=none"],
        input=path.read_text(encoding="utf-8"),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout


def render_article(article, section):
    slug = MATERIAL_URL.fullmatch(article["url"])["slug"]
    body = render_markdown(ROOT / "content" / f"{slug}.md")
    return f"""<div class="reading">
      <a class="back-link" href="/#{section['id']}"><span aria-hidden="true">←</span> К каталогу</a>
      <article class="material" data-material="{slug}">
        <p class="material-section">{escape(section['title'])}</p>
        <h1>{escape(article['title'])}</h1>
        <div class="prose">{body}</div>
      </article>
    </div>"""


def build():
    catalog = load_catalog()
    sections = "\n    ".join(render_section(section) for section in catalog)
    index = f"""<header class="catalog-header">
      <h1>{PORTAL}</h1>
      <p>{INTRO}</p>
      <p class="metrics-notice" role="status"></p>
    </header>
    {sections}"""
    pages = {
        "index.html": page(PORTAL, INTRO, catalog, index, section_id=catalog[0]["id"], is_catalog=True),
        "404.html": page(
            "Страница не найдена", "Страница не найдена", catalog,
            '<div class="reading"><h1>Страница не найдена</h1>'
            '<a class="back-link" href="/"><span aria-hidden="true">←</span> К каталогу</a></div>',
        ),
    }
    for section in catalog:
        for article in section["articles"]:
            path = article["url"].lstrip("/") + "index.html"
            pages[path] = page(
                article["title"], article["description"], catalog,
                render_article(article, section), section_id=section["id"],
            )

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST / "assets")
    for path, html in pages.items():
        output = DIST / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build()
