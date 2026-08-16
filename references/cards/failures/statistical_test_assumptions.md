# Failure Card: Statistical Test Assumption Misuse (检验假设与多重比较误用)

## 1. 错误形式
- 不检查正态性/方差齐性就直接 t 检验、ANOVA；
- 小样本（n<30/组）用正态近似报 p 值；
- 对 30 个指标各做一次 t 检验，报"显著差异 X 个"，不做多重比较校正；
- 把 p=0.052 写成"接近显著，仍说明有差异"；
- 配对设计用独立样本检验（或反之）。

## 2. 为什么错
- t 检验/ANOVA 的 p 值以假设成立为条件；偏态/异方差下真实第一类错误率可偏离名义值数倍；
- 多重比较下"至少一个 p<0.05"的概率随检验数上升：30 次独立检验时假阳性期望 1.5 个，不校正必然"发现"差异（多重比较问题，Bonferroni/BH 校正即为此设）；
- p 值是"假设为真时数据这么极端的概率"，不是"假设为假的概率"；0.052 与 0.048 无实质差别。

## 3. 最小反例
两组各 8 个样本，从同一分布抽取，重复整个实验 1000 次：不做校正地比较 20 个指标，约 64% 的实验会"发现"至少一个 p<0.05 的"显著差异"——全部是噪声。

## 4. Harness 应如何发现与拦截
- 模型合同：统计推断类结论声明 `characteristics` 含 `statistical_inference`，触发 `references/validation/profiles/prediction.md` 与 validation_obligations 的"假设检查、效应量/不确定性、多重比较或抽样边界"义务；
- `check_math_semantics.py`：`check_consistency` 的强词检查——"显著"作为解锁词需要绑定证据（editorial_style 强词表中 p<0.05 + 预定义阈值才解锁"显著"）；
- 测量快照：检验统计量、p 值、效应量（Cohen's d 等）、检验方法名作为 metric 落盘，`evaluate_obligations` 独立重算比较；
- 人工边界（W2）：多重比较校正方法（Bonferroni/Holm/BH）与理由须在正文写明。

## 5. 论文中如何正确表达
"两组样本 Shapiro–Wilk 检验均未拒绝正态性（p=0.31/0.42），Levene 检验方差齐（p=0.55），故采用独立样本 t 检验：t(14)=2.9，p=0.011，Cohen's d=1.45。对 12 项指标按 Holm 步进法校正后该项仍显著（校正后 p=0.033）。"
