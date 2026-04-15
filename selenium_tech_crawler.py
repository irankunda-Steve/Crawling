#!/usr/bin/env python3
"""Crawl latest technology articles using Selenium and save them as JSON.

This script:
1. Visits configured technology-news source pages.
2. Collects links to the latest articles.
3. Opens each article page and extracts the full article text.
4. Saves normalized output to latest_tech_articles.json.

Usage:
    python selenium_tech_crawler.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

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
    listing_item_selector: str
    listing_title_selector: str
    listing_link_selector: str
    article_paragraph_selectors: List[str]
    max_items: int = 5


SOURCES: List[Source] = [
    Source(
        name="TechCrunch",
        listing_url="https://techcrunch.com/category/technology/",
        listing_item_selector="article.loop-card",
        listing_title_selector="h3.loop-card__title a",
        listing_link_selector="h3.loop-card__title a",
        article_paragraph_selectors=[
            "div.entry-content p",
            "article p",
        ],
        max_items=5,
    ),
    Source(
        name="The Verge",
        listing_url="https://www.theverge.com/tech",
        listing_item_selector="div.duet--content-cards--content-card",
        listing_title_selector="h2 a, h3 a",
        listing_link_selector="h2 a, h3 a",
        article_paragraph_selectors=[
            "div.duet--article--article-body-component p",
            "article p",
        ],
        max_items=5,
    ),
    Source(
        name="Wired",
        listing_url="https://www.wired.com/category/gear/",
        listing_item_selector="div.SummaryItemWrapper-eiDYMl",
        listing_title_selector="h3 a",
        listing_link_selector="h3 a",
        article_paragraph_selectors=[
            "div.body__inner-container p",
            "article p",
        ],
        max_items=5,
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


def extract_article_text(driver: webdriver.Chrome, source: Source, url: str) -> str:
    """Open an article page and extract full text paragraphs."""
    driver.get(url)

    for selector in source.article_paragraph_selectors:
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            continue

        paragraphs = driver.find_elements(By.CSS_SELECTOR, selector)
        cleaned = [p.text.strip() for p in paragraphs if p.text and p.text.strip()]
        if cleaned:
            return "\n\n".join(cleaned)

    return ""


def collect_latest_articles(driver: webdriver.Chrome, source: Source) -> List[dict]:
    """Collect latest article metadata from a listing page, then crawl full content."""
    print(f"Scraping latest articles from {source.name}...")
    driver.get(source.listing_url)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, source.listing_item_selector))
        )
    except TimeoutException:
        print(f"Timeout while loading listing page for {source.name}")
        return []

    listing_items = driver.find_elements(By.CSS_SELECTOR, source.listing_item_selector)
    candidates: List[dict] = []

    for item in listing_items:
        try:
            title_el = item.find_element(By.CSS_SELECTOR, source.listing_title_selector)
            link_el = item.find_element(By.CSS_SELECTOR, source.listing_link_selector)
            title = title_el.text.strip()
            link = (link_el.get_attribute("href") or "").strip()

            if not title or not link or not link.startswith("http"):
                continue

            candidates.append({"headline": title, "url": link})
            if len(candidates) >= source.max_items:
                break
        except Exception:
            continue

    results: List[dict] = []
    for candidate in candidates:
        article_text = extract_article_text(driver, source, candidate["url"])
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
