# Pulls NFL news from RSS feeds, chunks it, and embeds it into the Chroma vector store.
import calendar
import hashlib
import os
import re
import sys

import chromadb
import feedparser
from chromadb.utils import embedding_functions

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

COLLECTION_NAME = "nfl_news"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw or "")
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def get_collection() -> chromadb.api.models.Collection.Collection:
    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
    )


def fetch_entries(feed_urls: list[str]) -> list[dict]:
    entries = []
    for url in feed_urls:
        parsed = feedparser.parse(url)
        feed_source = parsed.feed.get("title", url)

        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = clean_html(entry.get("summary", ""))
            link = entry.get("link", "")
            entry_id = entry.get("id") or link or title
            published = entry.get("published", "")
            published_ts = 0
            if entry.get("published_parsed"):
                published_ts = int(calendar.timegm(entry["published_parsed"]))

            entries.append(
                {
                    "entry_id": entry_id,
                    "title": title,
                    "link": link,
                    "source": feed_source,
                    "published": published,
                    "published_ts": published_ts,
                    "text": f"{title}\n\n{summary}".strip(),
                }
            )
    return entries


def sync_news(collection, feed_urls: list[str]) -> int:
    entries = fetch_entries(feed_urls)

    ids, documents, metadatas = [], [], []
    for entry in entries:
        chunks = chunk_text(entry["text"])
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.sha256(f"{entry['entry_id']}::{i}".encode()).hexdigest()
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "title": entry["title"],
                    "link": entry["link"],
                    "source": entry["source"],
                    "published": entry["published"],
                    "published_ts": entry["published_ts"],
                    "chunk_index": i,
                }
            )

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def run(feed_urls: list[str] | None = None) -> int:
    feed_urls = feed_urls or config.RSS_FEED_URLS
    if not feed_urls:
        raise RuntimeError("RSS_FEED_URLS must be set in .env, or pass feed_urls explicitly")

    collection = get_collection()
    return sync_news(collection, feed_urls)


if __name__ == "__main__":
    cli_feed_urls = sys.argv[1:] or None
    chunk_count = run(cli_feed_urls)
    print(f"Synced {chunk_count} news chunks into '{COLLECTION_NAME}'.")
