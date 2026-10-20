"""任务包：离线两期构造语料 + 出厂驾驭层；live 的 RSS 语料源与出厂提示词。"""

from .factory_prompt import FACTORY_PROMPT_TEXT, FACTORY_PROMPT_VERSION
from .feeds import (
    FEED_BUNDLE_A,
    FEED_BUNDLE_B,
    FEED_SPARE,
    FeedFetchError,
    FeedSource,
    fetch_candidates,
    parse_feed,
)
from .fixtures import build_corpus_1, build_corpus_2, build_factory_harness

__all__ = [
    "FACTORY_PROMPT_TEXT",
    "FACTORY_PROMPT_VERSION",
    "FEED_BUNDLE_A",
    "FEED_BUNDLE_B",
    "FEED_SPARE",
    "FeedFetchError",
    "FeedSource",
    "build_corpus_1",
    "build_corpus_2",
    "build_factory_harness",
    "fetch_candidates",
    "parse_feed",
]
