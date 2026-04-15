#!/usr/bin/env python3
"""Crawl latest technology articles using Selenium and save them as JSON.

This script:
1. Visits configured technology-news source pages.
2. Collects links to multiple latest articles.
3. Opens each article page and extracts the full article text.
4. Saves normalized output to latest_tech_articles.json.

Usage:
    python selenium_tech_crawler.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass
class Source:
    name: str
    listing_url: str
    listing_ready_selectors: List[str]
    listing_link_selectors: List[str]
    article_paragraph_selectors: List[str]
    max_items: int = 10


SOURCES: List[Source] = [
    Source(
        name="TechCrunch",
        listing_url="https://techcrunch.com/category/technology/",
        listing_ready_selectors=["article.loop-card", "main article"],
        listing_link_selectors=[
            "article.loop-card h3.loop-card__title a",
            "main article h2 a",
            "main article h3 a",
        ],
        article_paragraph_selectors=["div.entry-content p", "article p"],
        max_items=10,
    ),
    Source(
        name="The Verge",
        listing_url="https://www.theverge.com/tech",
        listing_ready_selectors=[
            "div.duet--content-cards--content-card",
            "main article",
        ],
        listing_link_selectors=[
            "div.duet--content-cards--content-card h2 a",
            "div.duet--content-cards--content-card h3 a",
            "main article h2 a",
            "main article h3 a",
        ],
        article_paragraph_selectors=[
            "div.duet--article--article-body-component p",
            "article p",
        ],
        max_items=10,
    ),
    Source(
        name="Wired",
        listing_url="https://www.wired.com/category/gear/",
        listing_ready_selectors=["div.SummaryItemWrapper-eiDYMl", "main article"],
        listing_link_selectors=[
            "div.SummaryItemWrapper-eiDYMl h3 a",
            "main article h2 a",
            "main article h3 a",
        ],
        article_paragraph_selectors=["div.body__inner-container p", "article p"],
        max_items=10,
    ),
]

OUTPUT_FILE = "latest_tech_articles.json"


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


def first_existing_selector(driver: webdriver.Chrome, selectors: Iterable[str], timeout: int = 20) -> str | None:
    """Return the first CSS selector that appears on the page."""
    for selector in selectors:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return selector
        except TimeoutException:
            continue
    return None


def extract_article_text(driver: webdriver.Chrome, source: Source, url: str) -> str:
    driver.get(url)

    selector = first_existing_selector(driver, source.article_paragraph_selectors, timeout=15)
    if not selector:
        return ""

    paragraphs = driver.find_elements(By.CSS_SELECTOR, selector)
    cleaned = [paragraph.text.strip() for paragraph in paragraphs if paragraph.text and paragraph.text.strip()]
    return "\n\n".join(cleaned)


def collect_listing_candidates(driver: webdriver.Chrome, source: Source) -> List[dict]:
    """Collect many candidate links from listing page using multiple fallback selectors."""
    driver.get(source.listing_url)

    ready_selector = first_existing_selector(driver, source.listing_ready_selectors, timeout=20)
    if not ready_selector:
        print(f"Timeout while loading listing page for {source.name}")
        return []

    print(f"Listing ready for {source.name} using selector: {ready_selector}")

    candidates: List[dict] = []
    seen_urls = set()

    for selector in source.listing_link_selectors:
        links = driver.find_elements(By.CSS_SELECTOR, selector)
        for link in links:
            try:
                title = link.text.strip()
                url = (link.get_attribute("href") or "").strip()
                if not title or not url.startswith("http") or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append({"headline": title, "url": url})
                if len(candidates) >= source.max_items:
                    return candidates
            except Exception:
                continue

    return candidates


def collect_latest_articles(driver: webdriver.Chrome, source: Source) -> List[dict]:
    print(f"Scraping latest articles from {source.name}...")

    candidates = collect_listing_candidates(driver, source)
    if not candidates:
        print(f"No listing candidates found for {source.name}")
        return []

    results: List[dict] = []
    for candidate in candidates:
        article_text = extract_article_text(driver, source, candidate["url"])
        if not article_text:
            continue

        results.append(
            {
                "source": source.name,
                "headline": candidate["headline"],
                "url": candidate["url"],
                "article": article_text,
            }
        )

    print(f"Collected {len(results)} full articles from {source.name}")
    return results


def main() -> None:
    collected_at = datetime.now(timezone.utc).isoformat()
    all_articles: List[dict] = []

    driver = build_driver()
    try:
        for source in SOURCES:
            all_articles.extend(collect_latest_articles(driver, source))
    finally:
        driver.quit()

    payload = {
        "collected_at_utc": collected_at,
        "article_count": len(all_articles),
        "articles": all_articles,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(all_articles)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
