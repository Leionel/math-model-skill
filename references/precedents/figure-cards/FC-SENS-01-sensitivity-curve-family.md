# 参数扰动曲线族

- **figure_pattern_id**: FC-SENS-01
- **semantic_type**: sensitivity / sensitivity curve
- **problem_family**: 优化 / optimization
- **evidence_role**: sensitivity
- **data_shape**: continuous_relationship
- **chart_family**: sensitivity curve family
- **source_id**: B226
- **rights_status**: local_study_only
- **layout_grammar**: 单图内把同一指标在目标参数多个水平下的曲线叠加，每水平一条线，图例标注参数取值；两个参数各占一张图并排放置、共用阅读顺序与纵轴含义；需要时叠加基线水平参考线；敏感方向由曲线簇的发散或收敛直接读出。
- **encoding_map**: 自变量（序数/位置/时间）→横轴；因变量指标→纵轴；参数水平→颜色梯度或线型次序；敏感程度→曲线簇间距。
- **required_inputs**: 2-3 个外生参数的扫描网格（每参数 3-6 水平）×每水平下完整的指标序列。
- **why_effective**: 曲线簇发散可视化敏感度排序与"在哪个区间敏感"，比单点灵敏度表多给出区间结构，同时天然带基线对照。
- **failure_modes**: 水平取得过密导致线叠过载；各子图纵轴范围不一致夸大敏感；颜色梯度选取色盲不可辨；只给扰动曲线不给基线曲线。
- **adaptation_boundary**: 参数超过三个或指标为离散集合时应改用 tornado 或热力图；只需要单点导数时整条曲线族是浪费。
- **do_not_copy**: 不照搬原图的参数水平数、颜色顺序、坐标范围与并排布局的具体安排。
