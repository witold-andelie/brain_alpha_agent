# Brain Alpha Agent 使用说明

这是一份面向真实 WorldQuant BRAIN 研究流程的操作说明。请严格按顺序执行。

## 0. 先了解边界

本 agent 可以：

- 生成和校验 Alpha 候选公式。
- 使用你的 BRAIN 账号查询字段。
- 提交你明确触发的 simulation 并轮询结果。
- 保存真实 simulation 指标到 SQLite。
- 跨多个 region、universe、delay 和 neutralization 场景比较 Alpha。
- 用硬门槛筛选候选，供人工复核。

本 agent 不会：

- 自动提交 Alpha 到生产账户。
- 连接券商或执行交易。
- 把 mock 分数当成真实表现。
- 保证任何 Alpha 盈利或达到 Gold 标准。

## 1. 安装

在项目目录 `D:\1\making_money\brain_alpha_agent` 打开 PowerShell：

```powershell
py -3 -m pip install -e ".[test,brain,research]"
```

确认程序可以启动：

```powershell
py -3 -m brain_alpha_agent --help
```

运行自动测试：

```powershell
py -3 -m pytest
```

如果不执行 editable 安装，则每次运行前设置：

```powershell
$env:PYTHONPATH="src"
```

## 2. 设置真实 BRAIN 账号

只在本机当前 PowerShell 会话设置环境变量。不要把真实密码发到聊天，不要写入代码、JSON、SQLite 或日志。

```powershell
$env:BRAIN_USERNAME="你的 WorldQuant BRAIN 登录账号"
$env:BRAIN_PASSWORD="你的 WorldQuant BRAIN 登录密码"
$env:BRAIN_BASE_URL="https://api.worldquantbrain.com"
```

程序只从这三个环境变量读取配置。不会要求你把密码输入到 Alpha payload 中。

## 3. 先验证账号和字段权限

先执行只读字段查询：

```powershell
py -3 -m brain_alpha_agent fields --search roic --limit 20
```

成功时会返回字段 ID、描述和数据集。失败时先检查：

- `requests` 是否安装。
- 账号密码是否正确。
- 账号是否有 BRAIN API 权限。
- 网络是否可以访问 `https://api.worldquantbrain.com`。

不要在字段查询成功前批量提交 simulation。

## 4. 生成 Alpha 候选

使用真实研究数据库：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db generate `
  --region USA `
  --universe TOP3000 `
  --delay 1 `
  --neutralization SUBINDUSTRY `
  --profile robust
```

命令会输出候选 Alpha ID。先记下需要研究的 ID，例如：

```text
ALPHA_ID=输出中的某个ID
```

默认 `robust` profile 生成 8 个受控候选，包括基础 value/quality、growth/quality、
mean reversion、volume confirmation、low volatility，以及 smoothed reversion、
slow momentum defensive 和 fundamental anchor。`baseline` 保留原始 5 个候选，
`whipsaw` 只生成 4 个甩尾/压力候选。格式化重复公式会自动去重。

## 5. 校验候选公式

```powershell
py -3 -m brain_alpha_agent validate "rank(zscore(roic))"
```

公式必须使用项目允许的字段和算子。未知字段、未知算子、非法字符和过深表达式会被拒绝。

## 6. 准备真实 simulation payload

真实 BRAIN simulation 的请求格式必须以你的账号当前官方 API 合同为准。项目不会擅自猜测、修改或伪造该格式。

创建本地文件 `payload-template.json`。模板中可以使用以下变量：

```text
{{formula}}
{{alpha_id}}
{{region}}
{{universe}}
{{delay}}
{{neutralization}}
{{scenario.region}}
{{scenario.universe}}
{{scenario.delay}}
{{scenario.neutralization}}
```

模板示例，实际字段和结构请先与官方 API 文档核对：

```json
{
  "type": "REGULAR",
  "regular": {
    "expression": "{{formula}}"
  },
  "settings": {
    "region": "{{scenario.region}}",
    "universe": "{{scenario.universe}}",
    "delay": "{{scenario.delay}}",
    "neutralization": "{{scenario.neutralization}}"
  }
}
```

不要把账号密码放入这个文件。

## 7. 先做单个真实 simulation

准备最小的 `simulation.json`，内容必须是你确认过的官方请求体，然后执行：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db simulate `
  ALPHA_ID `
  --payload simulation.json `
  --regime baseline `
  --timeout 600 `
  --poll-interval 5
```

成功流程为：

```text
读取 SQLite 中的 Alpha
-> 读取本地 JSON
-> 确认 payload 包含该 Alpha 的精确公式
-> BRAIN 认证
-> POST /simulations
-> 轮询状态
-> 解析结果
-> 追加保存候选快照、请求、场景、来源、原始响应和标准化指标
```

第一次真实调用只使用一个 Alpha、一个小范围场景，并人工确认返回结果。确认请求格式和响应字段正确后，再进行批量研究。

## 8. 批量多场景研究

创建 `scenarios.json`：

```json
[
  {
    "regime": "baseline",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": "SUBINDUSTRY"
  },
  {
    "regime": "whipsaw",
    "region": "USA",
    "universe": "TOP1000",
    "delay": 1,
    "neutralization": "INDUSTRY"
  },
  {
    "regime": "stress",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 0,
    "neutralization": "SUBINDUSTRY"
  }
]
```

`regime` 是审计标签，不会自动改变 BRAIN 的回测窗口。`whipsaw` 场景必须在已核对的
官方 payload 模板中映射到真实不同的快速反转日期窗口或设置。仅复制同一场景并更改
标签会被 material scenario fingerprint 拒绝。

批量研究一个 Alpha：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db research `
  --alpha-id ALPHA_ID `
  --payload-template payload-template.json `
  --scenarios scenarios.json `
  --max-runs 50 `
  --timeout 600 `
  --poll-interval 5
```

批量研究多个 Alpha：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db research `
  --alpha-id ALPHA_ID_1 `
  --alpha-id ALPHA_ID_2 `
  --alpha-id ALPHA_ID_3 `
  --payload-template payload-template.json `
  --scenarios scenarios.json `
  --timeout 600 `
  --poll-interval 5
```

注意：每个 Alpha 和每个场景都会产生一次 BRAIN simulation，会消耗账号请求预算。

## 9. 评估质量门槛

批量结果保存完成后：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db assess ALPHA_ID
```

默认要求至少 3 个真实、有效且实质不同的完成场景，并检查：

- 场景必须包含 `baseline` 和 `whipsaw` 状态；
- result provenance 必须由真实 `brain` adapter 写入；
- 每个场景都有 Sharpe、Fitness、Turnover、Drawdown 和 Coverage。
- 所有指标必须为有限数，Coverage 必须有有效 universe 分母且位于 0-1；
- Sharpe 不低于 `1.0`。
- Fitness 不低于 `0.5`。
- Turnover 不高于 `0.8`。
- Drawdown 不高于 `0.25`。
- Coverage 不低于 `0.5`。
- 多场景 Sharpe 波动不能过大。
- baseline 到 whipsaw 的 Sharpe 下降和 whipsaw Turnover 不能过大。
- 若平台返回与已有 Alpha 的相关性，绝对值不能高于 `0.8`。
- mock/offline 结果永远不能通过。

调整最少场景数：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db assess ALPHA_ID --min-scenarios 5
```

每次 assessment 都会持久化，并成为 `rank` 的正式数据源。mock 分数会明确标记，
不会覆盖真实排名。`passed: true` 只表示通过当前硬门槛，不等于 Gold 或可交易。
仍必须人工检查经济逻辑、数据更新频率、行业暴露、样本外表现和平台完整结果。

## 10. 查看结果和数据库状态

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db status
py -3 -m brain_alpha_agent --db data/brain_alpha.db rank
```

默认数据库是 `data/brain_alpha.db`，可以用 `--db` 指定其他 SQLite 文件。

## 11. 导入研究参考资料

这些资料只产生研究线索，不会自动提交 Alpha：

```powershell
py -3 -m brain_alpha_agent --db data/brain_alpha.db import-reference --reference-path "D:\CS_materials\量化\101_Alphas_项目"
py -3 -m brain_alpha_agent --db data/brain_alpha.db import-course --course-path "D:\CS_materials\量化\Course2_作业答案\src\必做4_批量生成Alpha.py"
py -3 -m brain_alpha_agent --db data/brain_alpha.db import-revenue --revenue-db ..\revenue_agent\data\paper.db
```

公开研究方法记录见 [RESEARCH_METHODS.md](RESEARCH_METHODS.md)。

## 12. Moltbook 只读研究线索

只有在需要导入公开讨论时才设置：

```powershell
$env:MOLTBOOK_API_KEY="你的Moltbook API key"
py -3 -m brain_alpha_agent --db data/brain_alpha.db import-moltbook `
  --query "factor robustness volatility regime" `
  --limit 20
Remove-Item Env:MOLTBOOK_API_KEY
```

Moltbook 接入只调用官方 GET 搜索接口。不会发帖、评论、点赞或关注，API key 只发送到 `www.moltbook.com`。讨论内容默认低置信度，只能生成研究问题，不能直接成为 Alpha。

## 13. 结束工作并清除凭据

```powershell
Remove-Item Env:BRAIN_USERNAME
Remove-Item Env:BRAIN_PASSWORD
Remove-Item Env:BRAIN_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:MOLTBOOK_API_KEY -ErrorAction SilentlyContinue
```

不要把包含凭据的 PowerShell 命令保存到脚本、README 或日志中。

## 附录：开发离线测试

离线模式只用于验证代码，不访问 BRAIN，也不会读取账号密码。离线结果会标记为 `offline`，不能通过质量门槛。

```powershell
py -3 -m brain_alpha_agent --db data/mock.db generate --region USA --universe TOP3000 --delay 1
py -3 -m brain_alpha_agent --db data/mock.db simulate ALPHA_ID --payload simulation.json --regime baseline --offline
py -3 -m brain_alpha_agent --db data/mock.db evaluate ALPHA_ID
py -3 -m brain_alpha_agent --db data/mock.db rank
```

运行全套测试：

```powershell
py -3 -m pytest
```
