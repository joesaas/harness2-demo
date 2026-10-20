"""实时语料：用 RSS/Atom 抓真实候选新闻（live 模式的任务语料）。

feed 清单是 2026-10-20 逐个实测后定下来的（可达且能解析出条目）：
- bundle A：CoinDesk、Decrypt、TechCrunch AI、Google AI Blog
- bundle B：The Block、PANews、Cointelegraph、The Defiant
- 备用：Blockworks（Atom，实测可用，未编入默认 bundle）
实测不可用、已弃用：Foresight News（返回非 XML）、Odaily RSS（404）、
ChainCatcher RSS（404）。两组 bundle 来源不重叠，保证两期任务的
候选条目天然不重复。

抓取只用 urllib + xml.etree；单个 feed 失败不拖垮整期：失败原因
按 feed 名记入 errors 并由调用方明确打印；全部失败才抛 FeedFetchError。
"""

from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Sequence

from ..domain import CandidateItem

_ATOM = "{http://www.w3.org/2005/Atom}"
_UA = "Mozilla/5.0 (harness2-demo live feed fetcher)"
Opener = Callable[[str], bytes]


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str


FEED_BUNDLE_A: tuple[FeedSource, ...] = (
    FeedSource("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    FeedSource("Decrypt", "https://decrypt.co/feed"),
    FeedSource("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    FeedSource("Google AI Blog", "https://blog.google/technology/ai/rss/"),
)

FEED_BUNDLE_B: tuple[FeedSource, ...] = (
    FeedSource("The Block", "https://www.theblock.co/rss.xml"),
    FeedSource("PANews", "https://www.panewslab.com/rss.xml"),
    FeedSource("Cointelegraph", "https://cointelegraph.com/rss"),
    FeedSource("The Defiant", "https://thedefiant.io/feed"),
)

FEED_SPARE: tuple[FeedSource, ...] = (
    FeedSource("Blockworks", "https://blockworks.co/feed"),
)


class FeedFetchError(RuntimeError):
    """整组 feed 全部抓取失败时抛出，消息里逐个点名失败的 feed。"""


def _default_opener(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


def _clean_text(raw: str | None, limit: int = 600) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _parse_date(raw: str | None) -> datetime | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)  # RSS 的 RFC 822 日期
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # Atom 的 ISO 日期
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_feed(data: bytes, source_name: str) -> list[CandidateItem]:
    """解析一个 RSS 2.0 或 Atom 文档，返回候选条目（未去重、未排序）。"""
    root = ET.fromstring(data)
    items: list[CandidateItem] = []
    for node in root.iter("item"):  # RSS 2.0
        link = (node.findtext("link") or "").strip()
        title = _clean_text(node.findtext("title"), limit=300)
        if not link or not title:
            continue
        items.append(
            CandidateItem(
                title=title,
                summary=_clean_text(node.findtext("description")),
                link=link,
                published=_parse_date(node.findtext("pubDate")),
                source_name=source_name,
            )
        )
    for node in root.iter(f"{_ATOM}entry"):  # Atom
        link = ""
        for link_node in node.findall(f"{_ATOM}link"):
            if link_node.get("rel") in (None, "alternate"):
                link = (link_node.get("href") or "").strip()
                break
        title = _clean_text(node.findtext(f"{_ATOM}title"), limit=300)
        if not link or not title:
            continue
        summary = node.findtext(f"{_ATOM}summary") or node.findtext(f"{_ATOM}content")
        published = node.findtext(f"{_ATOM}published") or node.findtext(f"{_ATOM}updated")
        items.append(
            CandidateItem(
                title=title,
                summary=_clean_text(summary),
                link=link,
                published=_parse_date(published),
                source_name=source_name,
            )
        )
    return items


# ---------------------------------------------------------------------------
# 抓取
# ---------------------------------------------------------------------------


def fetch_candidates(
    feeds: Sequence[FeedSource],
    *,
    limit: int = 30,
    opener: Opener | None = None,
    errors: list[str] | None = None,
) -> list[CandidateItem]:
    """抓一组 feed：按 link 去重、按发布时间倒序、截到 limit 条。

    单个 feed 失败时把「feed 名 + 原因」记入 errors（若提供）并继续；
    全部失败抛 FeedFetchError。opener 可注入（测试用）。
    """
    opener = opener or _default_opener
    collected: list[CandidateItem] = []
    failures: list[str] = []
    for feed in feeds:
        try:
            collected.extend(parse_feed(opener(feed.url), feed.name))
        except Exception as e:  # 网络、解析、编码问题都归为这个 feed 失败
            failures.append(f"{feed.name}（{feed.url}）：{type(e).__name__}: {e}")
    if errors is not None:
        errors.extend(failures)
    if not collected and failures:
        raise FeedFetchError("全部 feed 抓取失败：" + "；".join(failures))

    seen: set[str] = set()
    unique: list[CandidateItem] = []
    for item in collected:
        key = item.link.strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    unique.sort(key=lambda it: it.published or epoch, reverse=True)
    return unique[:limit]
