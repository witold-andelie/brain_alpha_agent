# Brain Alpha Agent

Auditable research agent for generating and evaluating WorldQuant BRAIN-style
alpha formulas. It is intentionally **research-only**: it does not bypass
BRAIN controls, scrape private endpoints, or submit alphas automatically.

## Start

From this directory:

```powershell
$env:PYTHONPATH="src"
py -3 -m brain_alpha_agent
```

The REPL supports:

```text
/generate
/validate rank(zscore(roic))
/evaluate ALPHA_ID
/rank
/import-revenue
/status
/quit
```

The shorter installed command is `brain-alpha`.

## CLI

```powershell
py -3 -m brain_alpha_agent generate --region USA --universe TOP3000 --delay 1
py -3 -m brain_alpha_agent validate "rank(zscore(roic))"
py -3 -m brain_alpha_agent rank
py -3 -m brain_alpha_agent import-revenue --revenue-db ../revenue_agent/data/paper.db
py -3 -m brain_alpha_agent import-reference --reference-path "D:\CS_materials\量化\101_Alphas_项目"
py -3 -m brain_alpha_agent simulate ALPHA_ID --payload simulation.json
py -3 -m brain_alpha_agent simulate ALPHA_ID --payload simulation.json --offline
```

`simulate` is the only command that calls the BRAIN simulation endpoint. It
requires `BRAIN_USERNAME` and `BRAIN_PASSWORD` in the local environment and an
exact API request body in a JSON file. The completed response is stored in
SQLite with its normalized metrics. Use `--offline` to run the complete flow
with a deterministic local fake session; this mode never reads credentials or
opens a network connection. Verify the request schema against the official
account API before using real credentials.

## Architecture

```text
financial hypothesis
-> typed/allowlisted formula validation
-> candidate memory (SQLite)
-> official BRAIN evaluator adapter
-> robustness and quality score
-> deduplication and human review
-> explicit submission outside this MVP
```

The included evaluator is deterministic and offline. It exists for testing the
pipeline only; its numbers are not market results and must not be interpreted
as BRAIN performance. A future official adapter must use documented BRAIN
interfaces, rate limits, credentials from environment/secret storage, and
human confirmation before submission.

## Shared Learning

`import-revenue` reads only aggregate learning state from `revenue_agent`:
paper attack/defense weights, observations, return, and drawdown. It does not
copy positions or orders. Imported knowledge is a weak research prior, never a
formula or trading instruction.

## Quality Gates

Before an alpha is considered for submission, add an official evaluator that
records fitness, Sharpe, returns, turnover, drawdown, weight concentration,
sub-universe results, period stability, and correlation to existing alphas.
Hard gates should reject future-data usage, invalid fields/operators, unstable
sub-universe results, high turnover, excessive drawdown, and duplicates.

## Research Reference

The research design is informed by the publicly available paper [101 Formulaic
Alphas](https://arxiv.org/abs/1601.00991) by Zura Kakushadze. We use its public
observations as methodology, not as a list of formulas to copy:

- separate short-horizon signals from longer-horizon fundamental signals;
- measure alpha correlation and novelty at the portfolio level;
- test volatility regime dependence explicitly;
- treat turnover as one risk dimension, not the sole explanation of returns;
- prefer families of simple, interpretable formulas over one complicated formula;
- validate across time periods, sub-universes, and regions.

The current templates are original, deliberately small examples in the families
value/quality, growth/quality, mean reversion, volume confirmation, and low
volatility. Their offline mock scores are not BRAIN scores.

## Local 101 Alpha Reference

The local project at `D:\CS_materials\量化\101_Alphas_项目` is imported as a
reference catalog:

```powershell
py -3 -m brain_alpha_agent import-reference --reference-path "D:\CS_materials\量化\101_Alphas_项目"
```

This imports the BRAIN expression text and keeps its source path. It does not
automatically submit or treat those historical expressions as validated on the
current BRAIN dataset. The catalog is used for factor-family coverage,
operator discovery, deduplication, and research prompts.

## Course2 Reference

The local Course2 material is also imported as a controlled batch reference:

```powershell
py -3 -m brain_alpha_agent import-course --course-path "D:\CS_materials\量化\Course2_作业答案\src\必做4_批量生成Alpha.py"
```

It contributes 25 template variations, coverage accounting from Long-Count and
Short-Count, field-update-frequency experiments using `ts_std_dev(field, d)`,
and a news/sentiment field-discovery workflow. The original course code stores
credentials in `config.py`; this agent does not. Use `BRAIN_USERNAME` and
`BRAIN_PASSWORD` environment variables instead.

Read-only field discovery, when official access is configured:

```powershell
py -3 -m brain_alpha_agent fields --search sentiment --limit 20
```

The current client only authenticates and reads `/data-fields`. Alpha creation
and simulation submission remain human-controlled until the official API
contract and account permissions are verified.

## Safety

- No real broker integration.
- No automatic BRAIN submission.
- No credentials in source, SQLite results, or logs.
- No claims that a mock score predicts a Gold alpha.
- All generated formulas and evaluation inputs must remain reproducible.

## TODO: Continue Tomorrow

当前项目是可运行 MVP。下面的任务按优先级排列，完成前不把任何 Alpha
标记为高质量或 Gold candidate。

### P0: Real BRAIN Evaluation

- [ ] 用本地环境变量完成 BRAIN 只读认证测试
- [ ] 验证 `/data-fields` 返回结构和字段类型
- [ ] 实现官方 Alpha simulation adapter，默认仍关闭写操作
- [ ] 解析真实 `Sharpe`、`Fitness`、`Returns`、`Turnover`、`Drawdown`
- [ ] 解析 `Long-Count`、`Short-Count` 和 `Coverage`
- [ ] 加入请求超时、重试、限流和结果持久化

### P0: Current Alpha Investigation

- [ ] 记录 `d5ZdrL0E` 的原始公式、设置和四年结果
- [ ] 分解国内 EBIT、海外 EBIT、资产公允价值的单独贡献
- [ ] 测试 `TOP500`、`TOP1000`、`TOP3000`
- [ ] 测试 `INDUSTRY`、`SUBINDUSTRY`、`MARKET` 中性化
- [ ] 测试平滑阈值版本，避免 `alpha * 2` 的硬跳变
- [ ] 测试“高资产公允价值 + 低 EBIT”交互公式

### P1: Robustness Gates

- [ ] 增加多时间段和样本外测试
- [ ] 增加 sub-universe 稳健性测试
- [ ] 增加因子间相关性矩阵和重复因子淘汰
- [ ] 增加字段更新频率测试：`d=5, 22, 66, 132, 252`
- [ ] 增加缺失值、Coverage 和 Long/Short 偏斜门槛
- [ ] 增加新闻/情绪字段搜索和替换实验

### P1: Learning Loop

- [ ] 将真实 BRAIN 结果写入 SQLite
- [ ] 按因子家族、字段、operator 和 market regime 统计成功率
- [ ] 将 `revenue_agent` 的学习知识转换为 Alpha generation prior
- [ ] 采用时间衰减和样本量门槛，防止旧结果污染新研究
- [ ] 只让人工确认后的结果进入长期知识库

### P2: Controlled Submission

- [ ] 设计人工确认页面/REPL 确认步骤
- [ ] 增加每日请求和提交预算
- [ ] 增加幂等键，防止重复 Alpha
- [ ] 记录 Alpha ID、公式、设置、结果和提交时间
- [ ] 在真实回测闭环稳定前，禁止自动提交

## Tests

```powershell
py -3 -m pytest
```
