# harness2-demo

把 Google 的 **Harness²**（Recursive Agent Harnessing）机制，落到一个具体业务场景上的演示项目。两种运行模式共用同一套架构：默认离线模式用规则零件确定性跑通机制；`--live` 模式换上真实零件——同一份提示词经 OpenRouter 同时驱动 Grok / Gemini / ChatGPT 整理 RSS 实时新闻，Harness² 循环改进的对象就是提示词本身。

- **业务场景**：一份「AI Agent & Web3 DeFi 协议新闻收集」提示词要被反复使用——收集最近 2 天两个领域的技术 / 产品动态。这份提示词及其规则，就是 Harness² 所说的**驾驭层（harness）**里最核心的组件。
- **演示内容**：完整走通 Harness² 的两个递归层——任务级递归（Propose–Probe–Compose）让单期简报从违规 13 条改进到 0 条；驾驭级递归把有证据的教训写入「改进库」，让第二期任务自带教训起步（初始违规 1 条，对比第一期从零起步的 13 条）。
- **运行方式**：Python ≥ 3.11，**只用标准库、零第三方依赖**。离线模式无需任何 API Key、全离线、确定性运行；live 模式需要 OpenRouter API key（见下文「真实 LLM 模式」一节）。

> **如实说明**：离线模式的两期候选语料是**构造的 fixture**，不是真实新闻，标题与来源名均为示意。演示叙事呼应这份提示词的真实迭代史（v1 宽松收了数据盘点 → 加事件制 → 来源一刀切被拒 → 改分级来源），所有数字都来自本项目的确定性运行，可复现、可检验。live 模式用的是真实 RSS 语料与真实模型，但结果随新闻与模型输出而变，不承诺可复现。

## 快速开始

```bash
cd harness2-demo
python3 -m harness2_demo        # 离线演示（改进库默认写到 ./improvement_library.json）
python3 -m harness2_demo --library /tmp/lib.json   # 指定改进库路径
python3 -m harness2_demo --live                    # 真实 LLM 模式（需先配 OPENROUTER_API_KEY）

pip install -e ".[dev]"         # 可选：装开发依赖（pytest）
python3 -m pytest               # 跑测试（41 项，全离线、含 live 链路的假 transport 测试）
```

也可以 `pip install -e .` 后用 `harness2-demo` 命令，效果相同。

## 真实 LLM 模式（--live）

同一条 Harness² 演示线，零件换成真实的：语料是 RSS 实时抓取，执行器是三个真模型，编辑器是 LLM 全文修订，违规判定一半是程序检查、一半是 judge 模型判定。**循环改进的对象是提示词全文本身**：任务一从新闻提示词 v5 出厂版起步，编辑模型看行为指标与违规样例产出修订全文，探测轮在同一批语料上重跑三模型，Compose 决定采纳与否；任务二的初始提示词 = 任务一最终版 + 改进库教训拼成的「经验附则」。

**配置 key（二选一）**

```bash
export OPENROUTER_API_KEY=<你的 key>
# 或：把项目根 .env.example 复制为 .env，填入 OPENROUTER_API_KEY（.env 已被 .gitignore 排除）
```

没有 key 时 `--live` 会明确报错并打印配置方法、以非零码退出，**不会假装跑通**。

**运行**

```bash
python3 -m harness2_demo --live                 # 两期完整流程（每期开跑前先打印调用计划）
python3 -m harness2_demo --live --no-probe      # 关探测轮：修订未经对照直接采纳（省调用，输出会如实标注未复测）
python3 -m harness2_demo --live --limit 20      # 每期候选上限（默认 30）
python3 -m harness2_demo --live --model-grok x-ai/grok-4.7   # 按需覆盖单个模型
```

**默认模型（OpenRouter 模型 ID，可用环境变量 `OPENROUTER_MODEL_GROK/GEMINI/CHATGPT/EDITOR/JUDGE` 或上述 CLI 参数覆盖）**

| 角色 | 默认模型 |
|---|---|
| 执行 · Grok | `x-ai/grok-4.7`（运行时侧重：X / 社交来源） |
| 执行 · Gemini | `google/gemini-3.8-flash`（侧重：官方长文 / 治理） |
| 执行 · ChatGPT | `openai/gpt-5.6-luna`（侧重：综合新闻面） |
| 编辑 / judge | 同 ChatGPT：`openai/gpt-5.6-luna` |

**预计调用量与成本**：每期 = 执行 3 次 + judge 至多 3 次 + 编辑 1 次 = 至多 7 次；开探测再加一轮执行 + judge（至多 6 次），每期至多 13 次、两期至多 26 次。`--no-probe` 时每期至多 7 次、两期至多 14 次。每次调用的输入含提示词全文 + 至多 30 条候选（标题 + 摘要），请按 OpenRouter 上对应模型的单价自行估算；运行前打印的调用计划与此一致。

**指标口径（重要）**：幻觉条目数（选出的 link 不在候选集里）与重复数是程序检查，确定性；**违规 / 合规收录数由 judge 模型逐条判定 event / non-event，是模型评的估计值、不是真值**，judge 判不出的条目单独记 `judge_failed`、两边都不算。live 的 Compose 规则因此与离线略有不同：违规总数严格下降，**且合规收录下降不超过 20%** 才采纳（离线是合规不降——judge 值噪声更大，留了容忍带）。

**语料（2026-10-20 逐个实测可达且能解析）**：任务一 bundle A = CoinDesk、Decrypt、TechCrunch AI、Google AI Blog；任务二 bundle B = The Block、PANews、Cointelegraph、The Defiant（两组来源不重叠）；备用 Blockworks。Foresight News（返回非 XML）、Odaily 与 ChainCatcher（RSS 404）实测不可用，未纳入。单个 feed 抓取失败会点名报错并继续，其余全失败才整期中止。

**两模式对照**

| 维度 | 离线模式（默认） | live 模式（--live） |
|---|---|---|
| 语料 | 构造 fixture（两期考题） | RSS 实时抓取（两组 bundle） |
| 执行器 | RuleExecutor（规则筛选） | LlmExecutor（Grok / Gemini / ChatGPT 各一份简报 + 合并视图） |
| 评估 | BehaviorEvaluator（纯可观察属性） | JudgeEvaluator（程序检查 + judge 模型判定，估计口径） |
| 编辑器 | 六个规则编辑器（逐条 Guardrails 编辑） | LlmEditor（一轮一次提示词全文修订 + 改动清单） |
| Compose | 违规降且合规不降 | 违规降且合规下降 ≤ 20% |
| 改进对象 | PromptComponent 条款 + Guardrails | 提示词全文（版本 v5 起） |
| 教训迁移 | Guardrails effect 机器应用 | 教训文本以「经验附则」附在下一期提示词末尾 |
| 成本 | 零（全离线确定性） | 见上：两期至多 26 次调用 |

## 与 Harness² 的对应关系

| Harness² 概念 | 本项目实现 |
|---|---|
| 驾驭层（harness） | `harness/`：PromptComponent（提示词正文）+ Guardrails（规则开关）+ SkillsComponent（运行时侧重表）+ 已加载教训快照 |
| 模型权重冻结 | 执行器规则与语料全程不变，演进只发生在驾驭层 |
| 任务级递归 Propose | `editors/`：规则编辑器按可观察失败类型提议编辑 |
| 任务级递归 Probe | `contrast/probe.py`：候选编辑单独应用，在同一任务上跑出行为指标 |
| 行为对照代替真值 | `contrast/evaluator.py`：指标只看产出条目的可观察属性（类型 / 距今小时 / 来源 / 事件组），不做真值打分 |
| 任务级递归 Compose | `contrast/compose.py`：违规总数严格下降**且**合规收录不降，才采纳 |
| 驾驭级递归（improvement harness） | `library/`：教训带证据与机器可应用的 effect，JSON 落盘；新任务从出厂版逐条应用教训重建配置 |
| 执行器（executor） | `executor/`：RuleExecutor 按 Guardrails 筛选 / 去重 / 排序，产出简报 |
| 执行器（live） | `executor/llm_executor.py`：LlmExecutor 同一提示词 × 三模型（OpenRouter），容错 JSON 提取，执行留痕 |
| 行为对照（live） | `contrast/live_evaluator.py`：幻觉 / 重复程序检查 + judge 模型判违规 / 合规（估计口径） |
| Propose（live） | `editors/llm_editor.py`：LlmEditor 依据指标与违规样例产出提示词全文修订 |
| 模型接入 | `llm/`：OpenRouterClient（标准库 urllib、transport 可注入）+ ModelSet 模型配置 |
| 实时语料 | `tasks/feeds.py`：RSS / Atom 抓取、去重排序；`tasks/factory_prompt.py`：v5 出厂提示词快照 |

Harness² 的八类可编辑组件在本场景的映射：

| 八类组件 | 本场景对应物 | 本演示状态 |
|---|---|---|
| system prompt | PromptComponent（版本化提示词正文） | 真实参与编辑（采纳编辑即同步条款、升版本） |
| guardrails | Guardrails（只收事件 / 窗口 / 来源策略 / 去重 / 具名 / 上限） | 真实参与执行与编辑（核心） |
| skills | SkillsComponent（grok / gemini / chatgpt / muse 侧重表） | 参与执行（简报排序），本演示不编辑它 |
| memory | 改进库教训快照（Harness.lessons）+ library 模块 | 真实参与（落盘、加载、应用） |
| tool guidance | Guardrails 的来源与去重规则即本场景的「工具接口规矩」 | 以规则项承载 |
| subagents | 本场景无子代理；对应位置是「多运行时分工」，由侧重表表达 | 仅映射说明 |
| scripts | 执行器的确定性筛选脚本即本场景的脚本层 | 以 RuleExecutor 承载 |
| plugins | 编辑器注册表即插件点：新增编辑器 = 新增插件 | 以 editors 注册承载 |

## 演示流程（离线模式，一次完整运行）

**任务一（语料 19 条，出厂 v1 起步）**

1. 初始运行：宽松规则全收 19 条，违规总计 **13**（非事件 5、窗口外 2、重复 3、来源问题 3）。
2. 编辑器提议 5 条编辑（只收事件 / 窗口 48h / 去重 / 来源仅官方 / 来源分级）。
3. 逐条探测：前三条依次把违规 13 → 6 → 5 → 2；「来源仅官方」把违规降到 0，但合规事件 8 → 4——**被 Compose 拒绝**（靠少收换来的违规下降不算改进）；「来源分级」违规 2 → 0 且合规保持 8，采纳。
4. 拼装出 prompt **v2**，最终运行违规 **0**、合规事件 8/8。
5. 改进库写入 **5 条教训**（4 条采纳教训 + 1 条「不要只认官方」的负教训），每条带探测证据与 effect。

**任务二（语料 14 条，全是新面孔）**

6. 出厂 v1 + 改进库教训逐条应用 → 自带教训起步，初始运行违规只有 **1**（一个匿名社交来源——出厂规则与第一期教训都没见过的新失败）。
7. 第二轮：编辑器提议「要求具名来源」，探测通过后采纳，prompt 升到 **v3**，违规 → **0**，改进库增至 6 条。

## 一次真实运行的输出摘录

以下摘自 `python3 -m harness2_demo` 的真实输出（节选，未改数字）：

```text
【第一部分 · 任务一】候选语料 19 条，出厂驾驭层起步
步骤 1  初始运行：prompt v1；只收事件=关，窗口=168h，来源不限，去重=关，要求具名来源=关，每主题上限=20
        收录 19 条｜违规总计 13（非事件 5、窗口外 2、重复 3、来源问题 3）｜合规事件 8/8
步骤 3  逐条探测对照（同一任务上跑候选版，只看行为指标）：
        [event_only] 违规 13 → 6，合规 8 → 8｜采纳
        [window_48] 违规 6 → 5，合规 8 → 8｜采纳
        [dedup] 违规 5 → 2，合规 8 → 8｜采纳
        [source_official_only] 违规 2 → 0，合规 8 → 4｜拒绝：合规事件收录下降（8 → 4），违规下降是靠少收换来的，不算改进
        [source_tiered] 违规 2 → 0，合规 8 → 8｜采纳
步骤 4  拼装完成：采纳 4 条、拒绝 1 条，新版驾驭层：prompt v2；…
        最终运行：收录 8 条｜违规总计 0｜合规事件 8/8
【第二部分 · 任务二】
步骤 6  自带教训起步：出厂 v1 + 改进库 5 条教训 → prompt v2；…
        任务二初始运行：收录 8 条｜违规总计 1（来源问题 1）｜合规事件 7/7
步骤 9  拼装完成：…新版驾驭层：prompt v3；…要求具名来源=开…
        最终运行：收录 7 条｜违规总计 0｜合规事件 7/7
【总结对照】
  任务一：违规总计 13 → 0，合规事件 8 → 8
  任务二：自带教训起步违规总计 1（任务一从零起步是 13），一轮改进后 → 0
```

## 设计原则落地说明（项目硬性要求）

总目标：高内聚、低耦合。六大原则逐条落点：

- **单一职责（SRP）**：一类失败对应一个编辑器类（`editors/rule_editors.py` 六个类各盯一类指标）；一个模块一件事——`executor/` 只管筛选产出，`contrast/evaluator.py` 只管算指标，`library/` 只管教训存取与应用，`runner.py` 只管编排。
- **开闭原则（OCP）**：新增失败处理 = 新增一个 Editor 类并在组合根注册，runner 与 Composer 不改；新增执行器 / 存储实现同理。对修改封闭，对扩展开放。
- **里氏替换（LSP）**：`LlmEditor` 与规则编辑器实现同一 `Editor` 接口，注册进同一列表行为不变（有测试钉住）；任何实现 `Executor` / `LessonStore` 接口的类都能替换现有实现而不破坏编排。
- **接口隔离（ISP）**：四个核心抽象都是最小 Protocol——`Executor.run`、`Editor.propose`、`Evaluator.evaluate`、`LessonStore.load/save`，实现方不需要背任何用不到的方法。
- **依赖倒置（DIP）**：`DemoRunner` 与 `Composer` 的构造函数只接收 Protocol 类型的依赖；全项目唯一认识所有具体类的地方是组合根 `cli/main.py::build_runner`，装配发生在一个点。
- **迪米特法则（LoD）**：编排层不伸手进 `Harness` 内部字段，一律走它对外的方法（`apply_changes` / `with_prompt` / `with_lessons` / `describe`）；组件全是不可变数据，跨模块只传数据对象，不传对象图。

结构上的结果：核心链路 `runner → (Executor, Editor, Evaluator, LessonStore)` 全部面向抽象，模块间依赖单向（`domain` 被所有人依赖、自身零依赖）。

live 零件服从同一套纪律：`OpenRouterClient` 的 transport 可注入（默认 urllib 实现），测试用假 transport 即可确定性覆盖整条 live 链路，不需要真 key；`LlmExecutor` / `JudgeEvaluator` / `LlmEditor` 与离线对应物是同一角色的两种实现——编排形状一致（执行 → 评估 → 提议 → 探测 → 拼装 → 写库），但因数据类型不同（真实候选没有内容类型、产出是模型生成的条目、指标含 judge 估计）未共用离线 Protocol，各自在模块 docstring 里写明契约；`LiveRunner` 只依赖这三个组件的公开接口，live 的装配点同样只有一个：`cli/main.py::build_live_runner`。改进库不分模式：同一 `LessonStore` 接口、同一 JSON 落盘。

## 目录结构

```text
harness2-demo/
├── pyproject.toml            # 零运行时依赖；pytest 在 dev extra
├── README.md
├── docs/
│   └── mechanism.md          # 机制说明：两层递归与本演示的取舍
├── harness2_demo/
│   ├── __init__.py / __main__.py
│   ├── domain.py             # NewsItem / Metrics / CandidateItem 等领域数据（零依赖）
│   ├── harness/              # 驾驭层组件：Prompt / Guardrails / Skills / Harness
│   ├── llm/                  # OpenRouterClient（urllib、transport 可注入）+ 模型配置 + JSON 提取
│   ├── executor/             # Executor 接口 + RuleExecutor + LlmExecutor（live）
│   ├── editors/              # Editor 接口 + 六个规则编辑器 + LlmEditor（live 全文修订）
│   ├── contrast/             # Evaluator（行为指标）+ Probe + Compose + JudgeEvaluator（live）
│   ├── library/              # Lesson + LessonStore 接口 + JSON 实现 + Applier
│   ├── tasks/                # 两期构造语料 + 出厂驾驭层 + RSS feeds + v5 出厂提示词（live）
│   ├── runner.py             # DemoRunner 编排（只依赖抽象）
│   ├── runner_live.py        # LiveRunner 编排（真实零件的同一条演示线）
│   └── cli/                  # 入口与组合根（离线 / live 两套装配）
└── tests/                    # 41 项：离线全链路 + live 链路（假 transport 确定性覆盖）
```

## 边界与未做事项（如实列出）

- **离线语料是构造 fixture**：条目、来源名、时间都是为演示设计的考题，不是真实新闻抓取结果；**离线模式不做任何网络请求，live 模式会抓 RSS 并调用 OpenRouter**。
- **离线执行器是规则实现**：它演示的是「驾驭层如何决定产出」；真实执行在 live 模式的 `LlmExecutor`（三模型真调，见上文）。
- **离线编辑器为规则驱动**：失败类型 → 编辑的映射写死在六个编辑器类里；live 模式的 `LlmEditor` 是真调模型的全文修订。两种模式里提议者都可换，采纳权始终在行为对照手里。
- **行为对照不是真值**：离线指标来自可观察属性；live 的违规 / 合规还含 judge 模型的判定，是**单模型评判的估计**（judge 与被评对象同为 LLM、会看走眼），幻觉与重复才是确定性检查。真实场景中口径本身需要人来定，这正是驾驭层要人写规则的原因。
- **live 语料只有 RSS 标题 + 摘要**：执行模型与 judge 看不到原文全文，长文里的细节无从核验；候选按发布时间排序、上限默认 30 条，超出窗口的旧内容可能根本进不了候选集。
- **live 编辑是全文修订，不是条款级编辑**：编辑模型一轮产出一份完整新提示词（附改动清单说明依据），粒度比离线的 Guardrails 逐项编辑粗；改动清单是模型自述，未逐条机器校验。
- **改进库是单文件 JSON**：为的是可直接打开检视；`LessonStore` 接口已隔离，换存储不动编排。live 教训的 effect 为空、靠文本附则迁移（live 驾驭层是提示词全文，没有 Guardrails 字段可映射）。
- **递归轮数固定为每期一轮**：Harness² 的预算 k（多轮探测）未做——离线以「逐条编辑各探测一次」近似，live 以「一份全文修订探测一次」近似，均未做多轮迭代与并行探测。
