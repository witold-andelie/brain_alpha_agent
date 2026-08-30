# 研究方法与来源

本项目不把论文结论或论坛观点当作 Alpha 结果。它们只用于提出候选假设，最终判断必须来自当前 BRAIN 数据集上的真实 simulation 和稳健性测试。

## 公开来源

### 101 Formulaic Alphas

Zura Kakushadze, *101 Formulaic Alphas*, arXiv:1601.00991, 2016.

https://arxiv.org/abs/1601.00991

对本项目的可用启发：

- 将短周期信号和更长期基本面信号分开研究。
- 关注 Alpha 之间的相关性，而不是只挑单个 Sharpe 最高的公式。
- 明确检查波动率状态依赖。
- 不把 Turnover 当作收益解释的唯一变量。

这篇论文中的公式不应直接复制为当前数据集上的候选结论。

### Multiple testing

Campbell R. Harvey, Yan Liu and Heqing Zhu, *. . . and the Cross-Section of Expected Returns*, NBER Working Paper 20592, 2014; published in *Review of Financial Studies*, 2016.

https://www.nber.org/papers/w20592

对本项目的可用启发：

- 大量尝试会提高偶然发现的概率。
- 新因子应使用比传统显著性标准更严格的验证门槛。
- 研究记录必须保留候选数量、失败结果和测试配置，不能只保存成功结果。

## 已落实到代码的规则

- 所有 simulation 的候选快照、请求、场景、来源、原始响应和标准化指标都追加写入 SQLite。
- payload 必须包含所选候选的精确公式，scenario 不能覆盖候选身份字段。
- `assess` 默认要求至少三个实质不同的真实场景，并同时包含 baseline 和 whipsaw。
- 检查 Sharpe、Fitness、Turnover、Drawdown 和 Coverage。
- 拒绝非有限指标、无分母 Coverage、未知来源、mock/offline 和重复场景。
- 检查多场景 Sharpe 稳定性、whipsaw Sharpe 衰减和 whipsaw Turnover。
- 对已有 Alpha 相关性超过阈值的结果拒绝通过。
- 对只改变空格或大小写的公式做规范化去重。
- Moltbook 内容以低置信度 `KnowledgeItem` 保存，并保留来源 URL。
- Moltbook 结果不会调用 Alpha 创建、提交或社交写接口。

## 仍需完成

- 用官方真实结果区分训练期、验证期和样本外期。
- 自动检测 change point，并把真实日期窗口标记为 trend、whipsaw 和 stress。
- 保存每次尝试和失败原因，控制多重检验偏差。
- 增加候选之间的相关性矩阵和重复因子淘汰。
- 增加 region、universe、neutralization、delay 和时间窗口的批量场景运行。
- 由人工确认后，才允许研究结论进入长期知识库。
