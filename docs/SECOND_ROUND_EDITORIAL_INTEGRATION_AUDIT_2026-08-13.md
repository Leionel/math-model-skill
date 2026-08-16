# 第二轮研究完整性与编辑视觉补充审计

日期：2026-08-13  
范围：当前本地仓库、`math-model-skill_aesthetic_editorial_supplement_2026-08-12.md` 与第二轮对标意见。  
判断边界：本审计不使用被审计的数学建模 Skill 作为合理性依据；社区项目只提供可核查的工程机制，不提供赛事规则或获奖因果证明。

> 快照说明（2026-08-16 补）：文中测试数量等为 2026-08-13 当日快照；当前实现状态以 [MATH_HARNESS_IMPLEMENTATION_STATUS](MATH_HARNESS_IMPLEMENTATION_STATUS.md) 为准。

## 结论

两份补充意见的主方向合理：当前短板不是模型数量，而是从题面、数据、公式、运行、claim 到最终 PDF/提交文件的连续可核验机制。应吸收“题意追踪、数据语义、公式—代码映射、正文 claim inventory、统一呈现、实际 PDF QA、安全构建与提交回执”；但不能把主观审美、固定图数、固定字体或 community template 升格为 P0。

本轮采用以下分层：

| 层 | Hard gate | 人工/警告 |
|---|---|---|
| Research semantics | 漏答 requirement、数据合同 FAIL/泄漏、公式—代码 hash 漂移、验证 FAIL、未登记数字/强 claim | 模型取舍深度与解释质量 |
| Formal delivery | 官方 profile 的页数/纸张/文件约束、构建失败、源码漂移、必要字体/分辨率违规 | 非官方样式偏好、页面密度 |
| Perceptual review | 裁切、重叠、不可读、CJK 缺失、误导性编码 | 留白、节奏、视觉平衡 |

## 去重映射

| 建议 | 本地基线 | 决定 | 本轮落点 |
|---|---|---|---|
| 题面—要求—论文追踪 | `model_contract.questions` 与 `paper_plan.requirements` 有 ID，但无题面快照/选题依据 | 新增 | `problem_snapshot.schema.json` + `check_problem_coverage.py` |
| 数据语义合同 | 只有 source hash、transformations 与自由文本 quality checks | 新增 | `data_contract.schema.json` + `check_data_contract.py`；不引入 Pandera 依赖 |
| artifact DAG/失效传播 | manifest 有 hash/Gate，但未形成自动选择性重跑 | 增强并保留边界 | 新增 schema 与重算校验器；Gate 拒绝 hash/digest 漂移、重复 producer、cycle 和 stale，自动调度重跑仍留下一迭代 |
| 公式—代码映射 | model contract 有变量/约束，但没有 code symbol/test 绑定 | 新增 | `implementation_map.schema.json` + `check_implementation_map.py` |
| 未登记 claim 扫描 | writer package 拦截新数字和无依据因果，但只检查 Writer package 范围 | 增强 | `inventory_claims.py` 产 hashable receipt；W2 enhanced profile 要求 `ok=true` |
| 呈现合同/Table Contract | frozen `display_value` 有真源，表格合同过薄 | 增强 | `presentation_contract.schema.json`、`generate_values_tex.py`、扩展 table/figure schema |
| Pareto 事实重算 | 义务框架可表达比较，但无专用非支配检查 | 新增 | `check_pareto.py` |
| 安全 LaTeX 构建 | 尚无隔离 build receipt | 新增 | `safe_build.py`：隔离副本、禁 shell escape、限制 TeX I/O、前后 tree hash |
| 实际 PDF QA | 旧文档明确承认未实现 | 新增 | `check_pdf.py`、`render_pdf.py`、`visual_review_receipt.schema.json` |
| 视觉/编辑系统 | 只有 evidence-driven figure guide | 增强 | visual profile、plot recipes、editorial style、style lint；风格默认 warning |
| F1 后提交成功 | 本地 freeze 已有，门户结果未绑定 | 新增合同 | `submission_receipt.schema.json`，仅人工登记，不自动上传 |
| 离线模式/doctor | 缺失 | 新增 | `doctor.py --offline` |
| checkpoint 动作 | pass/fail 过粗 | 迁移 | schema 允许 confirm/edit/regenerate/ask/skip_with_reason/abort；兼容旧 pass/fail |
| distributable Skill | 开发仓库与运行时包尚未拆开 | 认可但不冒充完成 | 上游 clones 被 `.gitignore` 排除；发布打包/上下文预算 eval 仍为后续发布任务 |
| 端到端 benchmark | 基线是 26 个合同回归测试 | 认可但不冒充完成 | 本轮扩展为 37 个回归测试；4–6 道独立能力 benchmark 留在发布门 |

## 不采纳或改写

- 不把 XeLaTeX/LuaLaTeX 写成所有赛事的唯一引擎；由 visual profile 允许列表决定。
- 不设置固定图数、固定 panel 数、统一 300 DPI、统一字号或统一“Nature 风格”。数值由赛事 profile 决定。
- 不用 `pdffonts` 的 WinAnsi/Identity 标签单独判断中文丢失；它只触发渲染复核。
- 不把页面密度、留白和“高级感”设为 P0；只有不可读、裁切、官方格式违规或视觉误导才阻断。
- 不引入固定多 Agent 组织、Word/DOCX 双链、Typst、算法百科、DVC/Pandera 运行时依赖。
- 不自动上传比赛门户；`submission_receipt` 只证明用户实际提交文件与 F1 hash 一致。

## 模板 clone 与许可证决策

模板与绘图上游状态已锁定到 `vendor/template_sources.json`：

用户指定的三个 Overleaf 页面已经逐项核实：MCM 页面标示 CC BY 4.0，并使用 `mcmthesis` 文档类；辽宁 `lnumcmthesis` 页面标示 LPPL 1.3c；CUMCM 页面标示 CC BY 4.0，并明确源自 LaTeXStudio 的 2021 模板。Overleaf 公开页只能复制到登录账户后导出 source ZIP，不提供匿名 Git 提交，因此 manifest 将三者记为 `page-only`，没有伪造 commit；下面的 Git clone 是可验证的兼容上游，不声称与 Overleaf 派生包逐字节相同。

| 上游 | 锁定提交 | 许可证/状态 | 允许用途 |
|---|---|---|---|
| CUMCMThesis | `90d3e854...` | 仓库未发现 LICENSE 或明确仓库级再分发授权 | 本地检查与兼容测试；禁止随 Skill 分发 |
| mcmthesis | `8ac05e2c...` | LPPL 1.3c or later | 满足 LPPL 条件后可作为兼容来源；不是 COMAP 官方规范 |
| Eisvogel | `93cc5b8e...` | BSD-3-Clause；捆绑字体/媒体另有许可证 | 仅借鉴构建与编辑工程；资产需单独审计 |
| SciencePlots | `b9b16959...` | MIT | 绘图样式参考；运行时使用自有轻量 style，不强依赖该包 |
| Scientific Visualization Book | `62fa569f...`，已稀疏下载 | 书本 CC BY-NC-SA 4.0；代码 BSD-3-Clause；仅本地参考 | 可选参考，distribution blocked |
| Python Graph Gallery | `566349bf...`，已稀疏下载 | 根仓库 LICENSE 为 0BSD；仅本地参考 | 可选参考，distribution blocked |

clone 工作区位于 `vendor/upstream/`，被 Git 忽略；可用 `vendor/clone_templates.ps1` 重建并验证锁定提交，大型参考库需显式 `-IncludeLargeReferences`，并只恢复 manifest 中列出的稀疏路径。Scientific Visualization Book 与 Python Graph Gallery 已完成本地稀疏下载，但不随 Skill 分发。CUMCMThesis 与 mcmthesis 已分别完成隔离、禁 shell-escape 的真实编译；全页渲染分别覆盖 12 页和 11 页。兼容审计同时发现：该 CUMCM 示例含未嵌入 `Times-Roman`，mcmthesis 示例默认是 Letter 纸而不是 A4；两者因此都不能未经当届 profile 修补直接升级为生产模板。生产模板必须由当届官方 rule/profile 补丁并通过真实 PDF QA，不能直接把 community snapshot 作为官方模板。

## 已实施与尚未完成

已实施的是“合同 + 可执行检查 + Gate 可选增强 profile”的最小闭环。设置 `run_manifest.enhanced_integrity_profile=true` 后，M1/W1/W2 会要求新增 artifacts。默认 false 保留 schema 1.1 项目的显式迁移窗口，避免把旧项目静默解释为已经通过新门槛。

以下仍未声称完成：

1. artifact DAG 已能检测 stale，但自动选择性重跑调度器尚未实现；
2. CUMCM/MCM 两条清洗后的正式 golden template 及当届官方 patch；
3. 4–6 道端到端能力 benchmark 与上下文预算 eval；
4. 可安装精简 Skill 的发布构建、CI/release 治理；
5. 真实门户提交后的 `submission_receipt` 自动核验（当前只提供 schema，且保持人工提交）。

## Promotion gate

下一次声称“编辑视觉系统可用于终稿”前，至少必须：

1. 用真实 LaTeX fixture 生成 `build_receipt`，源码前后 hash 一致；
2. 用真实 PDF 生成全页 render/contact sheet 和 `pdf_visual_qa`；
3. 人工或多模态逐页审阅并绑定同一 PDF/hash；
4. claim inventory 无未解决数字、比较、因果、最优性或外部事实；
5. problem/data/implementation/presentation contracts 与 run ID 对齐；
6. 全量回归、schema 解析与静态检查通过。
