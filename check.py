"""Check the generated catalogue and material URLs over HTTP."""

import argparse
from html import escape
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from build import MATERIAL_URL, ROOT, load_catalog


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.sections = []
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and "id" in attrs:
            self.sections.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append((attrs.get("class"), attrs["href"]))


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_page(base, path, *, reload=False):
    headers = {"Cache-Control": "no-cache"} if reload else {}
    with urlopen(Request(base + path, headers=headers), timeout=10) as response:
        check(response.status == 200 and response.url == base + path, f"Адрес изменился: {path}")
        check(response.headers.get_content_type() == "text/html", f"Ожидался HTML: {path}")
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Адрес сайта, например http://127.0.0.1:8096")
    base = parser.parse_args().base_url.rstrip("/")
    catalog = load_catalog()
    html = read_page(base, "/")
    index = Document(html)
    section_ids = [section["id"] for section in catalog]
    check(index.sections == section_ids, "Порядок разделов отличается от каталога")
    check(
        [href for _, href in index.links if href.lstrip("#") in section_ids]
        == [f"#{section_id}" for section_id in section_ids],
        "Ссылки навигации отличаются от разделов",
    )
    urls = [article["url"] for section in catalog for article in section["articles"]]
    check([href for css, href in index.links if css == "card"] == urls, "Отличаются ссылки карточек")
    for section in catalog:
        for article in section["articles"]:
            url = article["url"]
            html = read_page(base, url)
            check(html == read_page(base, url, reload=True), f"Страница изменилась при обновлении: {url}")
            check(f"<h1>{escape(article['title'])}</h1>" in html, f"Отличается заголовок: {url}")
            slug = MATERIAL_URL.fullmatch(url)["slug"]
            if not (ROOT / "content" / f"{slug}.md").is_file():
                check("Материал готовится" in html, f"Отсутствует статус материала: {url}")
            back_link = ("back-link", f"/#{section['id']}")
            check(back_link in Document(html).links, f"Отсутствует возврат в раздел: {url}")

    try:
        read_page(base, "/no-such-page/")
    except HTTPError as error:
        check(error.code == 404, f"Ожидался 404, получен {error.code}")
    else:
        raise RuntimeError("Несуществующая страница открылась")

    print(f"HTTP OK: {len(section_ids)} разделов, {len(urls)} страниц, обновление, возврат и 404.")


if __name__ == "__main__":
    main()
