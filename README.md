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
py -3 -m brain_alpha_agent generate --region USA --universe TOP3000 --delay 1 --profile robust
py -3 -m brain_alpha_agent validate "rank(zscore(roic))"
py -3 -m brain_alpha_agent rank
py -3 -m brain_alpha_agent import-revenue --revenue-db ../revenue_agent/data/paper.db
py -3 -m brain_alpha_agent import-reference --reference-path "D:\CS_materials\量化\101_Alphas_项目"
py -3 -m brain_alpha_agent simulate ALPHA_ID --payload simulation.json --regime baseline
py -3 -m brain_alpha_agent simulate ALPHA_ID --payload simulation.json --regime baseline --offline
```

`simulate` and `research` call the BRAIN simulation endpoint. They require
`BRAIN_USERNAME` and `BRAIN_PASSWORD` in the local environment. Every request
must contain the exact formula of the selected candidate. The append-only run
record stores the candidate snapshot, request, scenario, verified evaluator
source, raw response, and normalized metrics. Use `--offline` to test the flow
without credentials or network access. Verify the request schema against the
official account API before using real credentials.

## Architecture

```text
financial hypothesis
-> controlled baseline / robust / whipsaw candidate profile
-> parsed and allowlisted formula validation
-> formula-bound BRAIN payload
-> append-only request/scenario/result provenance (SQLite)
-> real multi-regime BRAIN evaluation
-> fail-closed robustness gates and real-result ranking
-> human review and explicit submission outside this MVP
```

The mock evaluator is deterministic and exists only for pipeline tests. The
real adapter authenticates, submits simulations, follows only same-origin HTTPS
polling locations, backs off on transient responses, and stores provenance.
Mock scores are always labeled and never replace a real assessment. Alpha
submission remains outside this project.

## Shared Learning

`import-revenue` reads only aggregate learning state from `revenue_agent`:
paper attack/defense weights, observations, return, and drawdown. It does not
copy positions or orders. Imported knowledge is a weak research prior, never a
formula or trading instruction.

## Quality Gates

An alpha can pass only after at least three different material scenarios,
including `baseline` and `whipsaw`, have verified BRAIN provenance. Metrics
must be finite and internally valid. Gates check Sharpe, Fitness, Turnover,
Drawdown, Coverage, cross-scenario dispersion, whipsaw degradation, and any
available correlation to existing alphas. Labels alone do not make scenarios
distinct: their actual settings must differ.

See [STRATEGY.md](STRATEGY.md) for the candidate profiles and whipsaw workflow.

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
current BRAIN dataset. The catalog is persisted for controlled review; it is
not automatically promoted into simulation candidates.

## Course2 Reference

The local Course2 material is also imported as a controlled batch reference:

```powershell
py -3 -m brain_alpha_agent import-course --course-path "D:\CS_materials\量化\Course2_作业答案\src\必做4_批量生成Alpha.py"
```

It imports 25 template variations as reference records. They remain separate
from generated candidates until manually reviewed. The original course code
stores credentials in `config.py`; this agent does not. Use `BRAIN_USERNAME`
and `BRAIN_PASSWORD` environment variables instead.

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
- [x] 实现显式触发的官方 Alpha simulation adapter
- [x] 解析真实 `Sharpe`、`Fitness`、`Returns`、`Turnover`、`Drawdown`
- [x] 解析 `Long-Count`、`Short-Count` 和带分母验证的 `Coverage`
- [x] 加入超时、同源校验、轮询退避和追加式结果持久化

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

- [x] 将真实 BRAIN 请求、场景、结果和评估写入 SQLite
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
