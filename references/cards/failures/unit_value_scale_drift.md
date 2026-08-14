# Failure Card: Numerical Value and Unit Scale Drift (数值量纲与单位漂移)

## 1. 错误形式
同一结果数值在不同位置量纲不一致，例如：
- 代码输出结果为 `42,350,000`（元）；
- 正文第一节写：“总成本为 42.35 万元”；
- 摘要里写：“总成本为 42.35 百万元”；
- 图表坐标轴标签写：“Cost / kCNY (千元)”。

## 2. 为什么错
- **单位与数值脱节**：作者手工复制数字时，忽视了数字与单位前缀（元、万元、百万元、亿元；kg、吨；MW、MWh）的数学绑定关系，造成高达 100 倍甚至 1000 倍的致命数量级荒谬错误；
- **评委第一眼致命扣分**：数量级前后矛盾是评审专家最容易抓住的重大低级失误之一。

## 3. 最小反例
- 真实计算：$42,350,000\text{ 元} = 4235\text{ 万元} = 42.35\text{ 百万元} = 0.4235\text{ 亿元}$；
- 若误写成 $42.35\text{ 万元}$，直接缩水 100 倍，使得后续投资回报率和减排成本分析全部失真。

## 4. Harness 应如何发现与拦截
- **Presentation Contract 强制绑定**：在 `frozen_results.json` 中统一定义 `canonical_value`、`canonical_unit`、`display_value`、`display_unit`；
- **宏生成与自动校验（`generate_values_tex.py`）**：禁止 Writer 手打数字，统一通过 `\QTwoCostDisplay \QTwoCostUnit` 宏输出；
- 运行 `scripts/qa/check_math_semantics.py` 扫描 LaTeX 全文进行单位量纲漂移拦截。

## 5. 论文中如何正确表达
“统一采用适读单位‘百万元（million CNY）’展示主要财务指标，原始精确整数保留在支撑材料与附录表中。”
