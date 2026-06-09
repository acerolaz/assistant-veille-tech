from __future__ import annotations

import json
import logging
import typer

from app.db import db_session, execute
from app.ingest.news_api import NewsApiIngester
from app.ingest.scraper import Scraper
from app.ingest.cleaning import clean_html_to_markdown, dedupe
from app.rag.chroma_client import get_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy ChromaDB telemetry bug (known issue in chromadb 0.5.x)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

app = typer.Typer(help="Ingestion CLI for the veille tech index.")


@app.command()
def news(topics: list[str] = typer.Option(..., "--topic", "-t", help="Topic to query.")) -> None:
    """Fetch articles from NewsAPI and ingest into ChromaDB."""
    if not topics:
        typer.echo("❌ Error: At least one topic is required", err=True)
        raise typer.Exit(1)

    typer.echo(f"🔍 Fetching news for topics: {', '.join(topics)}")

    with db_session() as session:
        run_id: int | None = None
        if session is not None:
            row = execute(
                session,
                "INSERT INTO ingest_runs (ingester, topics, status)"
                " VALUES (:ingester, :topics, 'running') RETURNING id",
                ingester="news_api",
                topics=json.dumps(topics),
            )
            run_id = row[0] if row else None

        try:
            ingester = NewsApiIngester()
            articles = ingester.run(topics)

            if not articles:
                typer.echo("⚠️  No articles found")
                if session is not None and run_id is not None:
                    execute(
                        session,
                        "UPDATE ingest_runs"
                        " SET finished_at=NOW(), status='empty', fetched=0, stored=0"
                        " WHERE id=:run_id",
                        run_id=run_id,
                    )
                return

            fetched = len(articles)
            typer.echo(f"✓ Fetched {fetched} articles")

            for article in articles:
                if article.get("content"):
                    article["content"] = clean_html_to_markdown(article["content"])

            articles = dedupe(articles)
            typer.echo(f"✓ After deduplication: {len(articles)} articles")

            collection = get_collection()
            for article in articles:
                tags: list[str] = article.get("tags") or []
                topic = tags[0] if tags else ""
                collection.upsert(
                    ids=[article["id"]],
                    documents=[article.get("content") or ""],
                    metadatas=[
                        {
                            "title": article.get("title") or "",
                            "source": article.get("source") or "",
                            "date": str(article.get("date") or ""),
                            "url": str(article.get("url") or ""),
                            "tags": ", ".join(topics),
                        }
                    ],
                )
                if session is not None and run_id is not None:
                    execute(
                        session,
                        "INSERT INTO ingest_articles"
                        " (run_id, article_id, title, publication, url, topic)"
                        " VALUES (:run_id, :article_id, :title, :publication, :url, :topic)",
                        run_id=run_id,
                        article_id=str(article.get("id") or ""),
                        title=str(article.get("title") or ""),
                        publication=str(article.get("source") or ""),
                        url=str(article.get("url") or ""),
                        topic=topic,
                    )

            stored = len(articles)
            if session is not None and run_id is not None:
                execute(
                    session,
                    "UPDATE ingest_runs"
                    " SET finished_at=NOW(), status='ok', fetched=:fetched, stored=:stored"
                    " WHERE id=:run_id",
                    run_id=run_id,
                    fetched=fetched,
                    stored=stored,
                )
            typer.echo(f"✅ Ingested {stored} articles to ChromaDB")

        except Exception as exc:
            logger.error(f"Ingestion failed: {exc}")
            if session is not None and run_id is not None:
                execute(
                    session,
                    "UPDATE ingest_runs"
                    " SET finished_at=NOW(), status='error', error=:error"
                    " WHERE id=:run_id",
                    run_id=run_id,
                    error=str(exc),
                )
            typer.echo(f"❌ Error: {exc}", err=True)
            raise typer.Exit(1)


@app.command()
def scrape(urls: list[str] = typer.Option(..., "--url", "-u", help="URL to scrape.")) -> None:
    """Scrape URLs and ingest into ChromaDB."""
    if not urls:
        typer.echo("❌ Error: At least one URL is required", err=True)
        raise typer.Exit(1)

    typer.echo(f"🕷️  Scraping {len(urls)} URL(s)")

    try:
        scraper = Scraper()
        articles = scraper.run(urls)

        if not articles:
            typer.echo("⚠️  No content scraped")
            return

        typer.echo(f"✓ Scraped {len(articles)} articles")

        # Clean and process
        for article in articles:
            if article.get("content"):
                article["content"] = clean_html_to_markdown(article["content"])

        # Remove duplicates
        articles = dedupe(articles)
        typer.echo(f"✓ After deduplication: {len(articles)} articles")

        # Store in ChromaDB
        collection = get_collection()
        for idx, article in enumerate(articles):
            article_id = article.get("url") or article.get("title") or f"scraped-{idx}"
            if isinstance(article_id, str):
                collection.upsert(
                    ids=[article_id],
                    documents=[article.get("content", "")],
                    metadatas=[
                        {
                            "title": article.get("title", ""),
                            "source": article.get("source", "scraped"),
                            "url": article.get("url", ""),
                        }
                    ],
                )

        typer.echo(f"✅ Ingested {len(articles)} articles to ChromaDB")

    except Exception as exc:
        logger.error(f"Scraping failed: {exc}")
        typer.echo(f"❌ Error: {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
