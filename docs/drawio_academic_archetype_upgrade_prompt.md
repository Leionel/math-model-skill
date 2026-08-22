# Prompt：升级 Math Modeling Harness 的 Draw.io 学术架构图系统

## 0. 任务目标

请修改当前 `Leionel/math-model-skill` 中的 Draw.io 生成系统，使其从：

> “自动把节点放进若干圆角矩形，再用箭头连接”

升级为：

> “基于固定科研构图范式（archetype）的论文级架构图生成系统”。

本次升级的重点 **不是重新设计配色**。仓库已经有 `style_profile`、语义角色配色、Native Draw.io XML、正交连线、可编辑源文件、QA / 导出等能力，应全部保留。

新增层只负责：

1. 图的科学叙事结构；
2. 视觉层级；
3. 模块组合方式；
4. 输入 / 核心模型 / 验证 / 输出的空间关系；
5. 不同类型科研架构图的构图语法。

最终目标是减少当前输出中明显的“卡片墙 / PPT 流程图 / 程序自动排版”感，使 Figure 1 更接近正式数学建模论文中的总体研究框架图。

---

## 1. 核心设计原则

必须明确区分以下三个概念：

```text
archetype       = 构图语法 / topology / composition grammar
style_profile   = 配色与视觉皮肤
diagram_spec    = 当前论文的具体科学内容
```

三者必须解耦。

例如，同一个：

```text
research_framework
```

应该可以使用：

```text
academic_minimal
academic_navy_teal
forest_gold
minimal_gray_blue
```

等不同 `style_profile`，而不改变整体构图逻辑。

### 1.1 禁止重新发明配色系统

不要从其他仓库复制新的 palette。

继续使用当前 Harness 已有的：

- `academic_minimal`
- `academic_navy_teal`
- `okabe_ito`
- `forest_gold`
- `slate_violet`
- `navy_coral`
- `minimal_gray_blue`

以及现有语义角色：

- `input`
- `task`
- `process`
- `model`
- `validation`
- `decision`
- `result`
- `annotation`
- `group`

Archetype 层不得硬编码新的：

- fill color；
- stroke color；
- gradient；
- shadow；
- topic color。

颜色仍由 `style_profile + role` 决定。

---

## 2. 为什么需要这次升级

当前 Draw.io 后端虽然已经具备：

- Native `.drawio`；
- DAG / left-to-right 布局；
- 语义角色；
- 低饱和配色；
- 正交箭头；
- source refs；
- SVG / PDF / PNG 导出；

但视觉语法仍高度依赖：

```text
node = rounded rectangle
edge = orthogonal arrow
layout = DAG layer
```

因此复杂程度不同的图最终容易趋同为：

```text
[Card] → [Card] → [Card] → [Card]

[Large Card]      [Large Card]
```

这会造成：

- 所有模块视觉权重接近；
- 科学主次不突出；
- Figure 1 像 PPT 卡片墙；
- 颜色承担过多结构表达；
- Validation、Result、Core Model 被画成同类“大矩形”；
- 复杂论文依然只是“更多框”。

本次升级必须解决的不是“框的位置”，而是：

> **不同科学角色应该对应不同的构图 primitive 与视觉层级。**

---

# 3. 新增概念：Composition Grammar

Archetype 不只是节点位置模板。

它必须定义一组可组合的科研图形 primitive。

建议至少支持：

```text
band
stage
hero_container
model_block
input_lane
parallel_lane
merge_hub
validation_rail
output_block
decision_gate
feedback_rail
annotation_strip
```

这些 primitive 不一定需要成为新的 `role`。

它们可以作为：

- layout primitive；
- container type；
- rendering hint；
- archetype-internal composition unit。

例如：

```text
role = validation
primitive = validation_rail
```

和：

```text
role = validation
primitive = model_block
```

在视觉上应当明显不同。

---

# 4. 固定五套主 Archetype

不要维护几十个模板。

仅实现五套稳定、可泛化的数模论文架构图范式：

```text
research_framework
computational_pipeline
parallel_integration
method_architecture
iterative_optimization
```

再保留：

```text
custom
```

作为特殊情况兜底。

---

# 5. `research_framework`

## 5.1 用途

作为默认 Figure 1。

适用于：

- 总体技术路线；
- 整体建模思路；
- 多阶段建模；
- 从数据到模型到结论的论文叙事；
- 多个模型逐步增强的研究框架。

## 5.2 不要再画成 4–6 个同权大卡片

禁止默认：

```text
┌──────┬──────┬──────┬──────┐
│Data  │MILP  │CVaR  │Copula│
└──────┴──────┴──────┴──────┘

┌──────────────┬──────────────┐
│ Validation   │ Decision     │
└──────────────┴──────────────┘
```

应优先形成明确的科学层级。

## 5.3 推荐构图

```text
INPUT BAND
────────────────────────────────────
Data · Assumptions · Constraints
                  ↓

CORE MODELING FRAMEWORK
┌───────────────────────────────────┐
│ Baseline Model                    │
│        ↓                          │
│ Risk / Robust Extension           │
│        ↓                          │
│ Dependence / Scenario Extension   │
└───────────────────────────────────┘
                  ↓

VALIDATION RAIL
────────────────────────────────────
Feasibility · Stability · Robustness
                  ↓

OUTPUT
┌───────────────────────────────────┐
│ Strategy / Decision / Conclusion  │
└───────────────────────────────────┘
```

### 5.4 视觉要求

- 核心 Modeling Framework 应占最大视觉面积；
- Input Band 简洁；
- Validation 不默认画成一个与模型同尺寸的大卡片；
- Output 收敛成明确终点；
- 主阅读方向 2 秒内可识别；
- 图内通常不需要巨大的标题横幅，Figure caption 已承担说明责任。

---

# 6. `computational_pipeline`

## 6.1 用途

适用于对象或数据经历连续计算变换：

- 数据清洗；
- 特征工程；
- 时间序列预测；
- ML / DL；
- 聚类 / 分类；
- 仿真；
- prediction → optimization；
- 数值计算。

## 6.2 推荐构图

```text
Raw Data
   →
Preprocessing
   →
Feature Engineering
   →
Core Model
   →
Evaluation
   →
Optimization / Analysis
   →
Output
```

可允许次级输入：

```text
External Data ──────┐
                    ↓
Raw Data → Processing → Model → Result
                    ↑
Constraints ────────┘
```

## 6.3 视觉要求

- 主 pipeline 必须显著；
- 侧输入必须弱化；
- 不要把所有阶段都做成相同大小；
- Core Model 可以成为 hero block；
- 辅助步骤如 normalization / encoding 可以压缩为 compact stage。

---

# 7. `parallel_integration`

## 7.1 用途

适用于：

- 多数据源；
- 多模型；
- 多问题；
- Ensemble；
- 多指标评价；
- 多场景；
- 多条支路最终汇合。

## 7.2 推荐构图

### 多源 / 多模型

```text
Input A → Model A ─┐
                   │
Input B → Model B ─┼→ Integration → Final Model → Result
                   │
Input C → Model C ─┘
```

### 多问题

```text
                 Problem
                    ↓
         Common Data Preparation
                    ↓
       ┌────────────┼────────────┐
       ↓            ↓            ↓
   Question 1   Question 2   Question 3
       ↓            ↓            ↓
    Model A      Model B      Model C
       └────────────┼────────────┘
                    ↓
            Integrated Analysis
                    ↓
                 Result
```

## 7.3 视觉 primitive

建议使用：

```text
input_lane
parallel_lane
merge_hub
integration_block
output_block
```

不要把 `merge_hub` 做成额外的大卡片。

它应承担“汇聚”视觉作用。

---

# 8. `method_architecture`

## 8.1 用途

当“模型内部组件关系”比“时间顺序”更重要时使用：

- 耦合模型；
- 多目标优化系统；
- 图模型；
- PDE / 仿真系统；
- prediction + optimization；
- 层次模型；
- solver + constraints + objective。

## 8.2 推荐构图

```text
                     Input
                       ↓
        ┌───────────────────────────┐
        │        CORE METHOD        │
        │                           │
Data ─→ │ Module A → Core Model     │ ─→ Output
        │               ↓           │
        │         Optimizer/Solver  │
        │               ↑           │
        │          Constraints      │
        └───────────────────────────┘
                       ↓
                   Validation
```

## 8.3 视觉要求

- Core Method 必须是视觉 hero；
- 内部组件不应全部同尺寸；
- Constraints / Objective / Solver 要表达从属关系；
- 避免软件架构风格；
- 不要自动引入 API / Agent / Database / Service 等软件术语。

---

# 9. `iterative_optimization`

## 9.1 用途

只在循环本身具有科学意义时使用：

- GA；
- SA；
- ALNS；
- 参数校准；
- model fitting；
- 仿真优化；
- 迭代数值算法；
- adaptive control；
- convergence loop。

## 9.2 推荐构图

```text
Initialization
      ↓
Candidate Solution
      ↓
Evaluation
      ↓
Update / Search
      ↓
Convergence?
   No ───────────────┐
                     ↓
               Update / Search
                     │
                     └──── feedback
   Yes
      ↓
Final Solution
```

## 9.3 禁止

不要画商业式 flywheel。

禁止：

- decorative circular arrows；
- 大面积圆环；
- 无意义“闭环生态”视觉；
- 只是为了显得复杂而加入 feedback。

反馈必须对应真实算法迭代。

---

# 10. Archetype Routing

建议确定性路由：

```text
if 核心是显式迭代 / 收敛 / 更新循环:
    iterative_optimization

elif 存在至少两个真正独立支路，之后汇聚:
    parallel_integration

elif 重点解释模型内部模块与依赖:
    method_architecture

elif 重点是数据/对象的连续计算变换:
    computational_pipeline

else:
    research_framework
```

关键词只能作为辅助，不得单独决定类型。

---

# 11. Schema 修改

建议在 `diagram_spec.schema.json` 中新增：

```json
{
  "archetype": "research_framework"
}
```

枚举：

```text
research_framework
computational_pipeline
parallel_integration
method_architecture
iterative_optimization
custom
```

保持已有：

```text
kind
layout
style_profile
nodes
edges
panels
```

不要用 `layout` 代替 `archetype`。

因为：

```text
layout = left_to_right
```

只描述方向，

而：

```text
archetype = research_framework
```

描述完整科学构图逻辑。

---

# 12. 建议新增 Primitive Hint

可在 schema 中加入可选字段，例如：

```json
{
  "primitive": "validation_rail"
}
```

候选：

```text
auto
band
stage
hero_container
model_block
input_lane
parallel_lane
merge_hub
validation_rail
output_block
decision_gate
feedback_rail
annotation_strip
```

如果不希望扩充 node schema，也可以由 archetype layout engine 根据：

```text
role
emphasis
parent_id
graph position
```

自动推断 primitive。

优先推荐：

> 先自动推断，只有特殊情况才显式指定。

---

# 13. 视觉层级规则

## 13.1 禁止 All-Cards-Equal

禁止：

- 所有节点同宽；
- 所有节点同高；
- 所有容器同视觉权重；
- 每个阶段都使用同等面积。

同一 semantic tier 可以等尺寸。

不同 tier 必须有层级差。

---

## 13.2 Hero Module

每张复杂架构图最多优先突出 1–2 个 hero module。

可通过：

- 尺寸；
- 容器面积；
- 边框粗细；
- 中心位置；
- 周围留白；

实现强调。

不要依靠新增颜色强调。

---

## 13.3 Validation Rail

Validation 默认优先作为横向 rail / strip，而不是大卡片。

例如：

```text
──────────────── Validation ────────────────
Feasibility ✓   Stability ✓   Robustness ✓
```

只有当 Validation 本身包含复杂内部结构时，才允许升级成 panel。

---

## 13.4 Input Band

数据、假设、约束等总体输入可使用：

```text
input band
```

而不是把它们全部做成大型卡片。

---

## 13.5 Output Block

最终结论、方案或决策应收敛到：

```text
output block
```

避免与中间模型同权。

---

# 14. 文本压缩规则

Figure 1 不应承担全部 Results Table 的职责。

默认节点标签：

```text
2–7 words
```

优先：

```text
Deterministic MILP
Expected-CVaR Optimization
Gaussian Copula
Sensitivity Analysis
Scenario Robustness
Planting Strategy
```

避免：

```text
在 2000 次蒙特卡洛模拟下计算得到最终期望收益为……
```

具体数值优先进入：

- Result table；
- 后续 Figure；
- caption；
- 正文。

Figure 1 的任务是：

> 解释“做了什么”和“各模块如何关联”。

不是“报告全部数值”。

---

# 15. 标题规则

默认不要在图内加入占据大量空间的 PPT 式大标题条。

优先：

```text
无图内总标题
```

或仅使用小型 panel / section label。

因为论文已有：

```text
Figure 1. Overall modeling framework ...
```

只有当输出目标是：

- PPT；
- 海报；
- standalone infographic；

才考虑明显的 title banner。

---

# 16. 外部参考项目的使用方式

可借鉴：

## `ai-jiaqian/drawio-figure-replicator`

重点吸收：

- Research Framework 的整体骨架；
- Model Pipeline 的连续流程；
- Agent Platform Architecture 的中心容器构图；
- Experience Flywheel 中“循环关系”的思想。

但：

- 不直接运行时依赖其仓库；
- 不直接复制外部 XML；
- 不保留软件平台语义；
- 不照搬 16:9 concept-board 比例。

## `QIANJINYDX/research-drawio-skill`

重点吸收：

- scientific archetype 思想；
- 一张图一个主阅读顺序；
- academic hierarchy；
- compact labels；
- semantic grouping；
- orthogonal routing；
- 复杂图降密度；
- paper-scale inspection；
- QA 思路。

不要引入第二套 palette。

---

# 17. 参考图与模板的关系

不要把 archetype 实现成：

```text
复制固定 .drawio → 替换文本
```

核心实现仍应是：

```text
diagram_spec
    ↓
archetype resolver
    ↓
composition grammar
    ↓
primitive planner
    ↓
geometry engine
    ↓
existing semantic styling
    ↓
style_profile
    ↓
native draw.io XML
```

模板文件只用于：

- visual regression；
- example；
- layout reference；
- QA benchmark。

---

# 18. 推荐目录结构

```text
assets/
└── drawio/
    └── archetypes/
        ├── research_framework/
        │   ├── README.md
        │   ├── example_spec.json
        │   └── preview.svg
        ├── computational_pipeline/
        ├── parallel_integration/
        ├── method_architecture/
        └── iterative_optimization/
```

复杂外部案例放到：

```text
references/
└── visualization/
    └── advanced_layout_examples.md
```

不要把：

- ContextForge；
- SkillCircuit；
- GAN；
- U-Net；
- Transformer；

作为默认模板。

---

# 19. Generator 架构修改

当前类似：

```text
diagram_spec
    ↓
DAG layering
    ↓
190 × 72 rounded nodes
    ↓
orthogonal arrows
```

应升级为：

```text
diagram_spec
    ↓
archetype resolver
    ↓
composition grammar
    ↓
primitive assignment
    ↓
archetype-specific geometry
    ↓
existing role styling
    ↓
existing palette
    ↓
native draw.io
```

建议内部 API：

```python
resolve_archetype(spec)

plan_research_framework(spec)
plan_computational_pipeline(spec)
plan_parallel_integration(spec)
plan_method_architecture(spec)
plan_iterative_optimization(spec)

render_band(...)
render_stage(...)
render_hero_container(...)
render_validation_rail(...)
render_output_block(...)
render_feedback_rail(...)
```

注意：

`plan_*()` 负责结构和 geometry。

`render_*()` 不自行选择 palette。

最终颜色仍调用现有 role/style system。

---

# 20. Layout Engine 要求

## 20.1 不再只使用统一 node_w / node_h

允许：

```text
hero block     > normal block
band           = wide + shallow
validation rail= wide + shallow
output block   = medium
annotation     = compact
```

尺寸由 primitive + content density 决定。

---

## 20.2 留白成为结构的一部分

不同 module tier 之间应保留更大的 gutter。

例如：

```text
inside-module gap < between-module gap < between-tier gap
```

不要所有间距都固定成同一个值。

---

## 20.3 自动控制文字密度

当节点文字过多时，优先：

1. 压缩文本；
2. 拆成 label + sublabel；
3. 提升节点尺寸；
4. 转成 compact bullet group；

不要简单无限增大卡片。

---

# 21. QA 新增规则

除已有 QA 外，增加 Composition QA。

## 21.1 Hierarchy Check

检测：

- 是否所有主要 node 尺寸几乎一样；
- 是否没有 hero module；
- 是否 validation 与 core model 同权；
- 是否 output 不明显。

可作为 warning，而非绝对 hard fail。

---

## 21.2 Card-Wall Warning

当图中：

- 超过 5 个大型 rounded rectangle；
- 尺寸高度接近；
- 颜色各不相同；
- 且缺少 container / rail / band / merge；

给出：

```text
CARD_WALL_RISK
```

提示：

> consider archetype-specific composition primitives instead of uniform cards.

---

## 21.3 Title Banner Warning

论文模式下，如果图内 title banner 高度占 canvas 超过合理比例，提示：

```text
PPT_TITLE_BANNER_RISK
```

---

## 21.4 Information Density Warning

Figure 1 中若出现过多：

- 数值；
- 长 bullet；
- 全句描述；
- 重复 result；

提示：

```text
OVERVIEW_OVERLOADED
```

---

# 22. 与现有 style_profile 的兼容性测试

每个 archetype 至少测试两套配色。

例如：

```text
research_framework
    + academic_minimal
    + forest_gold
```

```text
method_architecture
    + slate_violet
    + minimal_gray_blue
```

必须证明：

> Archetype 没有依赖任何固定颜色。

---

# 23. 建议 Regression Cases

至少新增五个测试 case：

## Case A — Research Framework

```text
Agricultural Planning:
Data
→ Deterministic MILP
→ Expected-CVaR
→ Gaussian Copula
→ Validation
→ Decision
```

预期：

- 数据为 band；
- 三个模型为 core chain；
- validation 为 rail；
- decision 为 output；
- 不出现 6 个同权彩色大卡片。

---

## Case B — Computational Pipeline

```text
Raw data
→ Cleaning
→ Feature engineering
→ XGBoost
→ Evaluation
→ Optimization
→ Forecast
```

---

## Case C — Parallel Integration

```text
Economic data → Model A
Weather data  → Model B
Spatial data  → Model C
→ Fusion
→ Final strategy
```

---

## Case D — Method Architecture

```text
Input
→ Predictor
→ Optimization Core
← Constraints
← Objective
→ Decision
↓ Validation
```

---

## Case E — Iterative Optimization

```text
Initialize
→ ALNS destroy/repair
→ Evaluate
→ Acceptance
→ Update
→ Convergence?
→ Final solution
```

---

# 24. Acceptance Criteria

本次升级完成后，必须满足：

## 结构

- 支持 5 个 primary archetype；
- 支持 `custom`；
- Archetype 与 style_profile 解耦；
- 不改变科学节点含义；
- source refs 机制保留。

## 视觉

- Figure 1 不再默认形成卡片墙；
- 同图中允许多种 primitive；
- Core Model、Validation、Output 有明显层级；
- 不依赖额外颜色区分阶段；
- 不新增阴影和渐变；
- 不默认出现 PPT 大标题条。

## 学术

- 一眼可读出主科学叙事；
- Figure 1 以结构说明为主，而非结果堆积；
- labels 保持精简；
- validation / output / input 等角色具有合理视觉语法；
- 输出更接近 research schematic，而不是 SaaS / PPT diagram。

## 兼容性

已有未声明 `archetype` 的 spec 应：

```text
fallback → research_framework
```

或根据旧 `kind/layout` 进行安全映射。

不得静默改变已有图的科学拓扑。

---

# 25. 实施顺序

## Phase 1 — Schema

新增：

```text
archetype
```

以及可选：

```text
primitive
```

## Phase 2 — Archetype Resolver

实现确定性 routing。

## Phase 3 — Composition Planner

新增五套 `plan_*()`。

## Phase 4 — Primitive Renderer

加入：

```text
band
rail
hero_container
merge_hub
output_block
feedback_rail
```

## Phase 5 — Existing Style Integration

完全复用当前：

```text
role → palette
style_profile
edge style
font
source refs
```

## Phase 6 — QA

增加：

```text
CARD_WALL_RISK
PPT_TITLE_BANNER_RISK
OVERVIEW_OVERLOADED
WEAK_HIERARCHY
```

## Phase 7 — Regression

至少为 5 个 archetype 生成：

```text
.drawio
.svg
.png preview
```

并人工检查论文尺寸下的可读性。

---

# 26. 最终原则

整个新系统应遵循：

```text
Scientific Content
        ↓
Choose Archetype
        ↓
Build Composition Grammar
        ↓
Assign Visual Primitives
        ↓
Compute Geometry
        ↓
Apply Existing Semantic Roles
        ↓
Apply Existing style_profile
        ↓
Generate Native Draw.io
        ↓
QA / Export
```

最重要的原则：

> **Archetype 决定构图，不决定配色。**

以及：

> **不要把“科研架构图”理解成“更多更漂亮的矩形”。**

目标是让每张图都具备清晰的科学叙事、视觉层级和信息压缩能力，而不是仅仅完成节点自动排版。
