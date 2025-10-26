#!/usr/bin/env python3
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


RE_NEWS_ITEM = re.compile(r"^\-\s+(?P<text>.+)$")
RE_FIRST_LINK = re.compile(r"\[(https?://[^\s\]]+)\s+[^\]]+\]")

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def parse_pub_date(text: str) -> datetime:
    # Try to extract leading "Month YYYY" (case-insensitive). Allow colon or not after year.
    m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b[:]?\s*", text, re.IGNORECASE)
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        month = MONTHS.get(month_name, 1)
        # Use day 1 at noon UTC to avoid timezone edge cases
        return datetime(year, month, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Fallback: now
    return datetime.now(timezone.utc)


def extract_title(text: str) -> str:
    # Remove leading date prefix if present
    text_wo_date = re.sub(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b[:]?\s*",
                          "", text, flags=re.IGNORECASE)
    # Use up to first period or 140 chars as a title
    # If there's a colon after date, that often separates a concise title already
    title = text_wo_date.strip()
    if "." in title:
        title = title.split(".", 1)[0].strip()
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    return title if title else text.strip()


def extract_link(text: str, base_url: str) -> str:
    m = RE_FIRST_LINK.search(text)
    if m:
        return m.group(1)
    return base_url


def strip_jemdoc_links(text: str) -> str:
    # Convert [url label] -> label (url)
    def repl(m):
        url, label = m.group(1), m.group(2)
        return f"{label} ({url})"
    return re.sub(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]", repl, text)


def build_rss(items, base_url: str) -> str:
    now_http = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    lines = []
    lines.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
    lines.append("<rss version=\"2.0\" xmlns:atom=\"http://www.w3.org/2005/Atom\">")
    lines.append("  <channel>")
    lines.append("    <title>Igor Molybog - News</title>")
    lines.append(f"    <link>{escape(base_url)}</link>")
    lines.append("    <description>Updates from the News section</description>")
    lines.append("    <language>en-us</language>")
    lines.append(f"    <lastBuildDate>{now_http}</lastBuildDate>")
    lines.append("    <atom:link rel=\"self\" type=\"application/rss+xml\" href=\"https://igormolybog.github.io/news.xml\" />")
    for item in items:
        title = escape(item["title"]) if item["title"] else "Update"
        link = escape(item["link"]) if item["link"] else escape(base_url)
        pub_date = item["pub_date"].strftime("%a, %d %b %Y %H:%M:%S %z")
        description = escape(item["description"]) if item["description"] else ""
        guid_seed = (item["raw"] + pub_date).encode("utf-8")
        guid = hashlib.sha1(guid_seed).hexdigest()
        lines.append("    <item>")
        lines.append(f"      <title>{title}</title>")
        lines.append(f"      <link>{link}</link>")
        lines.append(f"      <guid isPermaLink=\"false\">{guid}</guid>")
        lines.append(f"      <pubDate>{pub_date}</pubDate>")
        lines.append(f"      <description>{description}</description>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"


def main():
    repo_root = Path(__file__).resolve().parents[1]
    index_path = repo_root / "index.jemdoc"
    output_path = repo_root / "news.xml"
    base_url = "https://igormolybog.github.io/"

    text = index_path.read_text(encoding="utf-8")

    # Locate the News section
    parts = re.split(r"^==\s*News\s*$", text, flags=re.MULTILINE)
    if len(parts) < 2:
        # No News section found; write minimal feed
        rss = build_rss([], base_url)
        output_path.write_text(rss, encoding="utf-8")
        return

    news_and_after = parts[1]
    # Collect lines that start with '- '
    items = []
    for line in news_and_after.splitlines():
        m = RE_NEWS_ITEM.match(line)
        if not m:
            continue
        raw = m.group("text").strip()
        if not raw:
            continue
        pub_date = parse_pub_date(raw)
        title = extract_title(raw)
        link = extract_link(raw, base_url)
        description = strip_jemdoc_links(raw)
        items.append({
            "raw": raw,
            "pub_date": pub_date,
            "title": title,
            "link": link,
            "description": description,
        })

    rss = build_rss(items, base_url)
    output_path.write_text(rss, encoding="utf-8")


if __name__ == "__main__":
    main()


