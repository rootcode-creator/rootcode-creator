from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


PROFILE_URL = "https://medium.com/@rootcode-creator"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
START_MARKER = "<!-- BLOG-POST-LIST:START -->"
END_MARKER = "<!-- BLOG-POST-LIST:END -->"
MAX_POST_COUNT = 10


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_posts(page) -> list[tuple[str, str]]:
    posts: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    anchors = page.locator('a[href*="/@rootcode-creator/"]')

    hrefs: list[str] = []
    for index in range(anchors.count()):
        href = anchors.nth(index).get_attribute("href")
        if href:
            hrefs.append(href)

    if not hrefs:
        html = page.content()
        hrefs = re.findall(r'href="([^"]*/@rootcode-creator/[^"#?]+(?:\?[^"]*)?)"', html)

    for href in hrefs:
        if not href or not re.search(r"/@rootcode-creator/[^?/#]+", href):
            continue

        link = urljoin("https://medium.com", href.split("?", 1)[0])
        if link in seen_urls:
            continue

        match = re.search(r"/@rootcode-creator/([^?/#]+)", link)
        slug = match.group(1) if match else link.rsplit("/", 1)[-1]
        title = normalize_text(slug.replace("-", " "))

        seen_urls.add(link)
        posts.append((title, link))

    return posts


def extract_canonical_title(page) -> str:
    try:
        scripts = page.locator('script[type="application/ld+json"]')
        for index in range(scripts.count()):
            raw_json = scripts.nth(index).text_content()
            if not raw_json:
                continue

            parsed = json.loads(raw_json)
            entries = parsed if isinstance(parsed, list) else [parsed]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                headline = normalize_text(str(entry.get("headline") or entry.get("name") or ""))
                if headline and headline.lower() not in {"medium", "medium.com"}:
                    return headline
    except Exception:
        pass

    try:
        page.wait_for_selector("h1", timeout=30000)
        title = normalize_text(page.locator("h1").first.inner_text())
        if title:
            return title
    except Exception:
        pass

    meta_title = page.locator('meta[property="og:title"]').first
    content = meta_title.get_attribute("content") if meta_title else None
    return normalize_text(content or "")


def update_readme(posts: list[tuple[str, str]]) -> None:
    if not posts:
        raise RuntimeError("No Medium posts were found on the profile page.")

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
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
        )
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
        profile_posts = extract_posts(page)

        posts: list[tuple[str, str]] = []
        for _profile_title, profile_url in profile_posts:
            try:
                page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
                canonical_title = extract_canonical_title(page)
            except Exception:
                canonical_title = ""

            posts.append((canonical_title or _profile_title, profile_url.split("?", 1)[0]))

        browser.close()

    update_readme(posts)


if __name__ == "__main__":
    main()