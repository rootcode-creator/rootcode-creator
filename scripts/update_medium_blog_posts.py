from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

FEED_URL = "https://medium.com/feed/@rootcode-creator"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
START_MARKER = "<!-- BLOG-POST-LIST:START -->"
END_MARKER = "<!-- BLOG-POST-LIST:END -->"
MAX_POST_COUNT = 10


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_posts_from_feed() -> list[tuple[str, str]]:
    posts: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    request = Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=60) as response:
        feed_data = response.read()

    root = ET.fromstring(feed_data)
    channel = root.find("channel")
    if channel is None:
        return posts

    for item in channel.findall("item"):
        title = normalize_text(item.findtext("title") or "")
        link = normalize_text(item.findtext("link") or "")
        if not title or not link:
            continue

        link = urljoin("https://medium.com", link.split("?", 1)[0])
        if link in seen_urls:
            continue

        seen_urls.add(link)
        posts.append((title, link))

    return posts


def update_readme(posts: list[tuple[str, str]]) -> None:
    if not posts:
        raise RuntimeError("No Medium posts were found in the RSS feed.")

    readme = README_PATH.read_text(encoding="utf-8")
    blog_lines = [f"- [{title}]({url})" for title, url in posts[:MAX_POST_COUNT]]
    replacement = f"{START_MARKER}\n" + "\n".join(blog_lines) + f"\n{END_MARKER}"
    updated = re.sub(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        replacement,
        readme,
        flags=re.S,
    )

    if updated == readme:
        raise RuntimeError("README blog section was not updated.")

    README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    posts = extract_posts_from_feed()

    if not posts:
        raise RuntimeError("No Medium posts were found in the RSS feed.")

    update_readme(posts)


if __name__ == "__main__":
    main()