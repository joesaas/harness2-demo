"""构造语料与出厂驾驭层。

重要说明：这里的条目全部是为演示构造的 fixture，不是真实新闻，
标题与来源名都是示意。构造原则是「每类失败都有代表、每条规则
都有独立考题」：
- 数据盘点 / 趋势综述 / 融资 / 行情：只有「只收事件」能拦；
- 窗口外的技术事件与旧闻重发：只有窗口规则能拦；
- 同事件多来源：只有去重能处理；
- 盘点站与未知来源的事件：只有来源分级能处理；
- 只有社交 / 资讯来源的合规事件：用来称量「只认官方」的代价。
"""

from __future__ import annotations

from ..domain import NewsItem
from ..harness import Guardrails, Harness, PromptComponent, SkillsComponent


def _item(id, title, topic, ctype, hours, cat, name, group) -> NewsItem:
    return NewsItem(
        id=id,
        title=title,
        topic=topic,
        content_type=ctype,
        hours_ago=hours,
        source_category=cat,
        source_name=name,
        event_group=group,
    )


def build_corpus_1() -> list[NewsItem]:
    """第一期语料（19 条）：合规事件 8 组，陷阱齐备，出厂规则下违规总数 13。"""
    return [
        # ---- DeFi：合规事件 ----
        _item("d1", "Aave 社区提交 V4 部署治理提案（ARFC 阶段）", "defi", "治理提案", 5, "官方", "Aave 治理论坛", "g-aave"),
        _item("d2", "Uniswap 新版本上线主网", "defi", "技术事件", 10, "官方", "Uniswap 官方博客", "g-uni"),
        _item("d2b", "Uniswap 新版本上线主网", "defi", "技术事件", 12, "资讯", "CoinDesk", "g-uni"),
        _item("d2c", "Uniswap 新版本上线主网", "defi", "技术事件", 14, "社交", "Uniswap 官方 X 账号", "g-uni"),
        _item("d3", "以太坊执行客户端发布新版本", "defi", "技术事件", 20, "资讯", "The Block", "g-ethclient"),
        _item("d4", "Morpho 新借贷金库集成上线", "defi", "技术事件", 30, "社交", "Morpho 官方 X 账号", "g-morpho"),
        # ---- DeFi：陷阱 ----
        _item("t1", "DeFi 总锁仓量周度盘点", "defi", "数据盘点", 6, "资讯", "PANews", "g-tvl"),
        _item("t2", "2026 年借贷协议趋势综述", "defi", "趋势综述", 12, "盘点站", "某内容盘点站", "g-trend"),
        _item("t3", "某借贷协议完成新一轮融资", "defi", "融资", 4, "资讯", "Odaily", "g-fund"),
        _item("t4", "某治理代币价格异动快讯", "defi", "行情", 2, "社交", "行情播报账号", "g-price"),
        _item("t5", "去年跨链桥升级报道（重发）", "defi", "旧闻重发", 150, "资讯", "ChainCatcher", "g-old"),
        _item("t7", "佚名信源称某新工具即将发布", "defi", "技术事件", 10, "未知", "匿名信源", "g-anon"),
        _item("t8", "内容站转载：某新协议上线", "defi", "技术事件", 15, "盘点站", "某内容盘点站", "g-seo"),
        # ---- Agent：合规事件 ----
        _item("a1", "MCP 规范发布小版本更新", "agent", "技术事件", 3, "官方", "MCP 官方仓库", "g-mcp"),
        _item("a2", "开源 Agent 框架发布 v2.0", "agent", "技术事件", 8, "官方", "GitHub Release", "g-framework"),
        _item("a2b", "开源 Agent 框架发布 v2.0", "agent", "技术事件", 9, "资讯", "TechCrunch", "g-framework"),
        _item("a3", "头部编程 Agent 产品发布功能更新", "agent", "技术事件", 26, "资讯", "The Decoder", "g-coding"),
        _item("a4", "Agent 安全评估研究发布", "agent", "技术事件", 40, "社交", "研究者具名 X 账号", "g-sec"),
        # ---- Agent：陷阱 ----
        _item("t6", "浏览器 Agent 三天前发布（窗口外）", "agent", "技术事件", 80, "官方", "项目官方博客", "g-oldagent"),
    ]


def build_corpus_2() -> list[NewsItem]:
    """第二期语料（14 条）：全是新面孔；带教训起步后只剩 1 个违规（匿名社交来源）。"""
    return [
        # ---- 合规事件（7 组）----
        _item("d5", "Lido 社区提交质押模块升级提案", "defi", "治理提案", 7, "官方", "Lido 治理论坛", "g-lido"),
        _item("d6", "Curve 新稳定币池上线", "defi", "技术事件", 12, "官方", "Curve 官方博客", "g-curve"),
        _item("d6b", "Curve 新稳定币池上线", "defi", "技术事件", 13, "资讯", "The Defiant", "g-curve"),
        _item("d7", "Solana 客户端发布性能升级版本", "defi", "技术事件", 22, "资讯", "CoinDesk", "g-sol"),
        _item("d8", "跨链协议完成新链部署", "defi", "技术事件", 28, "社交", "协议官方 X 账号", "g-bridge"),
        _item("a5", "Agent 框架发布插件系统", "agent", "技术事件", 4, "官方", "GitHub Release", "g-plugin"),
        _item("a6", "多 Agent 协作工具开源发布", "agent", "技术事件", 9, "社交", "作者具名 X 账号", "g-multi"),
        _item("a7", "浏览器 Agent 发布新版本", "agent", "技术事件", 33, "资讯", "TechCrunch", "g-browser"),
        # ---- 陷阱：都会被带教训起步的规则拦下 ----
        _item("t9", "稳定币供应量月度统计", "defi", "数据盘点", 5, "资讯", "PANews", "g-supply"),
        _item("t10", "五天前的协议参数调整公告", "defi", "技术事件", 120, "官方", "协议官方博客", "g-oldparam"),
        _item("t11", "某钱包新品推广软文", "agent", "营销软文", 6, "资讯", "某资讯平台", "g-ad"),
        _item("t13", "内容站 DeFi 趋势盘点文", "defi", "趋势综述", 8, "盘点站", "某内容盘点站", "g-trend2"),
        _item("t14", "ETF 资金流行情快讯", "defi", "行情", 3, "资讯", "某资讯平台", "g-etf"),
        # ---- 陷阱：本期唯一漏网者——类别是社交（分级放行）、但发布者匿名 ----
        _item("t12", "匿名账号爆料：某新协议即将上线", "agent", "技术事件", 11, "社交", "", "g-anon2"),
    ]


def build_factory_harness(runtime: str = "muse") -> Harness:
    """出厂驾驭层（v1）：对应这份提示词真实迭代史的起点——宽松、数量优先。"""
    return Harness(
        prompt=PromptComponent(
            version=1,
            clauses=(
                "收集最近一段时间的 AI Agent 与 Web3 DeFi 协议动态",
                "两个主题都要覆盖，来源不限，数量优先",
            ),
        ),
        guardrails=Guardrails(),  # 默认值即 v1：不分事件、窗口一周、来源不限、不去重
        skills=SkillsComponent(),
        runtime=runtime,
    )
