from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from langchain_text_splitters import RecursiveCharacterTextSplitter


def clean_html_to_markdown(html: str, bs_kwargs: dict | None = None) -> str:
    if bs_kwargs is None:
        bs_kwargs = {}

    soup = BeautifulSoup(html, "html.parser", **bs_kwargs)
    stripped = strip_boilerplate(soup)

    return md(str(stripped), heading_style="ATX")


def dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate articles by ID or URL, keeping first occurrence."""
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    result = []
    for article in articles:
        article_id = str(article["id"]) if article.get("id") else None
        article_url = str(article["url"]) if article.get("url") else None
        if (article_id and article_id in seen_ids) or (article_url and article_url in seen_urls):
            continue
        if article_id:
            seen_ids.add(article_id)
        if article_url:
            seen_urls.add(article_url)
        result.append(article)
    return result


def chunk(text: str, max_chars: int = 1200) -> list[str]:
    """Split text into chunks of max_chars using recursive character splitting."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def strip_boilerplate(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove boilerplate HTML elements (nav, footer, ads, comments, etc.)."""
    # Remove script and style elements
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # Remove common boilerplate tags
    for tag in soup.find_all(["nav", "footer", "aside", "noscript"]):
        tag.decompose()

    # Remove elements with common boilerplate class/id patterns
    boilerplate_selectors = [
        ".navbar",
        ".nav",
        ".navigation",
        ".sidebar",
        ".widget",
        ".ad",
        ".advertisement",
        ".footer",
        ".header",
        ".breadcrumb",
        ".comment",
        ".comments-section",
        ".social",
        ".share",
        ".subscription",
        ".cookie",
        ".popup",
        ".modal",
        "#sidebar",
        "#nav",
        "#navigation",
        "[role='complementary']",
        "[role='navigation']",
    ]

    for selector in boilerplate_selectors:
        for element in soup.select(selector):
            element.decompose()

    return soup
