"""RSS/Atom 解析与抓取聚合的确定性单测（假 opener，不联网）。"""

from __future__ import annotations

import pytest

from harness2_demo.tasks import (
    FeedFetchError,
    FeedSource,
    fetch_candidates,
    parse_feed,
)

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>测试源</title>
<item><title>旧闻一条</title><link>https://ex.com/old</link>
<description><![CDATA[<p>摘要 <b>加粗</b></p>]]></description>
<pubDate>Mon, 19 Oct 2026 08:00:00 GMT</pubDate></item>
<item><title>新闻一条</title><link>https://ex.com/new</link>
<description>纯文本摘要</description>
<pubDate>Tue, 20 Oct 2026 09:30:00 GMT</pubDate></item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>原子源</title>
<entry><title>Atom 条目</title><link href="https://ex.com/atom"/>
<summary>atom 摘要</summary><updated>2026-10-20T10:00:00Z</updated></entry>
<entry><title>与 RSS 重复</title><link href="https://ex.com/new"/>
<summary>同 link</summary><updated>2026-10-20T11:00:00Z</updated></entry>
</feed>"""

SRC_A = FeedSource(name="源A", url="https://a.example/feed")
SRC_B = FeedSource(name="源B", url="https://b.example/feed")


def _opener(mapping: dict[str, bytes]):
    def opener(url: str, timeout: int = 20) -> bytes:
        if url not in mapping:
            raise OSError("连接失败")
        return mapping[url]

    return opener


def test_parse_rss_fields_and_dates():
    items = parse_feed(RSS_XML.encode(), SRC_A.name)
    assert len(items) == 2
    first = items[0]
    assert first.title == "旧闻一条"
    assert first.link == "https://ex.com/old"
    assert first.summary == "摘要 加粗"  # HTML 标签已剥掉
    assert first.source_name == "源A"
    assert first.published is not None and first.published.year == 2026


def test_parse_atom_fields():
    items = parse_feed(ATOM_XML.encode(), SRC_B.name)
    assert len(items) == 2
    assert items[0].title == "Atom 条目"
    assert items[0].link == "https://ex.com/atom"
    assert items[0].published is not None and items[0].published.hour == 10


def test_fetch_dedup_sort_limit():
    opener = _opener({SRC_A.url: RSS_XML.encode(), SRC_B.url: ATOM_XML.encode()})
    errors: list[str] = []
    items = fetch_candidates([SRC_A, SRC_B], limit=10, opener=opener, errors=errors)
    assert errors == []
    links = [i.link for i in items]
    assert links.count("https://ex.com/new") == 1  # 按 link 去重（保留先出现的 RSS 版）
    assert links[0] == "https://ex.com/atom"  # 按发布时间倒序：10:00 的 Atom 条目最前
    assert items[0].source_name == "源B"
    kept = next(i for i in items if i.link == "https://ex.com/new")
    assert kept.source_name == "源A"
    limited = fetch_candidates([SRC_A, SRC_B], limit=2, opener=opener)
    assert len(limited) == 2


def test_fetch_partial_failure_records_which_feed():
    opener = _opener({SRC_A.url: RSS_XML.encode()})  # 源B 会抛错
    errors: list[str] = []
    items = fetch_candidates([SRC_A, SRC_B], opener=opener, errors=errors)
    assert len(items) == 2
    assert len(errors) == 1 and "源B" in errors[0]


def test_fetch_all_fail_raises_naming_feeds():
    opener = _opener({})
    with pytest.raises(FeedFetchError) as exc:
        fetch_candidates([SRC_A, SRC_B], opener=opener)
    assert "源A" in str(exc.value) and "源B" in str(exc.value)
