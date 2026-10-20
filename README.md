# harness2-demo

把 Google 的 **Harness²**（Recursive Agent Harnessing）机制，落到一个具体业务场景上的离线演示项目。

- **业务场景**：一份「AI Agent & Web3 DeFi 协议新闻收集」提示词要被反复使用——收集最近 2 天两个领域的技术 / 产品动态。这份提示词及其规则，就是 Harness² 所说的**驾驭层（harness）**里最核心的组件。
- **演示内容**：完整走通 Harness² 的两个递归层——任务级递归（Propose–Probe–Compose）让单期简报从违规 13 条改进到 0 条；驾驭级递归把有证据的教训写入「改进库」，让第二期任务自带教训起步（初始违规 1 条，对比第一期从零起步的 13 条）。
- **运行方式**：Python ≥ 3.11，**只用标准库、零第三方依赖、无需任何 API Key**，全离线、确定性运行（与 Harness² 官方 local demo 的定位一致）。

> **如实说明**：演示用的两期候选语料是**构造的 fixture**，不是真实新闻，标题与来源名均为示意。演示叙事呼应这份提示词的真实迭代史（v1 宽松收了数据盘点 → 加事件制 → 来源一刀切被拒 → 改分级来源），但所有数字都来自本项目的确定性运行，可复现、可检验。

## 快速开始

```bash
cd harness2-demo
python3 -m harness2_demo        # 跑完整演示（改进库默认写到 ./improvement_library.json）
python3 -m harness2_demo --library /tmp/lib.json   # 指定改进库路径

pip install -e ".[dev]"         # 可选：装开发依赖（pytest）
python3 -m pytest               # 跑测试（21 项，全离线）
```

也可以 `pip install -e .` 后用 `harness2-demo` 命令，效果相同。

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

## 演示流程（一次完整运行）

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
- **里氏替换（LSP）**：`LlmEditor`（占位）与规则编辑器实现同一 `Editor` 接口，注册进同一列表行为不变（有测试钉住）；任何实现 `Executor` / `LessonStore` 接口的类都能替换现有实现而不破坏编排。
- **接口隔离（ISP）**：四个核心抽象都是最小 Protocol——`Executor.run`、`Editor.propose`、`Evaluator.evaluate`、`LessonStore.load/save`，实现方不需要背任何用不到的方法。
- **依赖倒置（DIP）**：`DemoRunner` 与 `Composer` 的构造函数只接收 Protocol 类型的依赖；全项目唯一认识所有具体类的地方是组合根 `cli/main.py::build_runner`，装配发生在一个点。
- **迪米特法则（LoD）**：编排层不伸手进 `Harness` 内部字段，一律走它对外的方法（`apply_changes` / `with_prompt` / `with_lessons` / `describe`）；组件全是不可变数据，跨模块只传数据对象，不传对象图。

结构上的结果：核心链路 `runner → (Executor, Editor, Evaluator, LessonStore)` 全部面向抽象，模块间依赖单向（`domain` 被所有人依赖、自身零依赖）。

## 目录结构

```text
harness2-demo/
├── pyproject.toml            # 零运行时依赖；pytest 在 dev extra
├── README.md
├── docs/
│   └── mechanism.md          # 机制说明：两层递归与本演示的取舍
├── harness2_demo/
│   ├── __init__.py / __main__.py
│   ├── domain.py             # NewsItem / Metrics（零依赖的领域数据）
│   ├── harness/              # 驾驭层组件：Prompt / Guardrails / Skills / Harness
│   ├── executor/             # Executor 接口 + RuleExecutor
│   ├── editors/              # Editor 接口 + 六个规则编辑器 + LlmEditor 占位
│   ├── contrast/             # Evaluator（行为指标）+ Probe + Compose
│   ├── library/              # Lesson + LessonStore 接口 + JSON 实现 + Applier
│   ├── tasks/                # 两期构造语料 + 出厂驾驭层
│   ├── runner.py             # DemoRunner 编排（只依赖抽象）
│   └── cli/                  # 入口与组合根
└── tests/                    # 21 项：执行器 / 编辑器 / 拼装 / 改进库 / 端到端
```

## 边界与未做事项（如实列出）

- **语料是构造 fixture**：条目、来源名、时间都是为演示设计的考题，不是真实新闻抓取结果；本项目不做任何网络请求。
- **执行器是规则实现，不是真调模型**：它演示的是「驾驭层如何决定产出」，不是新闻收集本身。换成 LLM 执行器只需实现 `Executor` 接口。
- **编辑器为规则驱动**：失败类型 → 编辑的映射写死在六个编辑器类里。`LlmEditor` 只留接口与接入说明（见 `editors/llm_editor.py`），不真调模型——提议者可换，采纳权始终在行为对照手里。
- **行为对照不是真值**：指标来自可观察属性，构造语料里「合规」定义与业务口径一致；真实场景中口径本身需要人来定，这正是驾驭层要人写规则的原因。
- **改进库是单文件 JSON**：为的是可直接打开检视；`LessonStore` 接口已隔离，换存储不动编排。
- **递归轮数固定为每期一轮**：Harness² 的预算 k（多轮探测）在本演示里以「逐条编辑各探测一次」近似，未做多轮迭代与并行探测。
