# Jev HTTP API v1

新客户端使用 `/api/v1`；挂载在 `/jev` 等前缀下时将前缀加在所有路径前。机器可读合同由 `/api/openapi.json` 提供。本文路由已按服务实现核对；完整请求约束以对应版本的 OpenAPI 为准，实际验证范围见 [发布检查记录](RELEASE_CHECK.md)。

请求和响应使用 JSON。版本字段是精确字符串；未定义字段、非有限数字和非法动作会被拒绝。不要把模型服务地址或密钥放入 URL 查询参数。

## 资源

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/games` | 游戏 ID、规则和可用引擎信息 |
| GET | `/api/v1/models` | 当前浏览器的模型连接公开信息 |
| GET / POST | `/api/v1/connections` | 列举 / 创建临时连接 |
| DELETE | `/api/v1/connections/{model_id}` | 释放临时连接 |
| GET | `/api/v1/connections/{model_id}/requests` | 浏览器直连的长轮询队列 |
| POST | `/api/v1/connections/{model_id}/results` | 浏览器直连回传模型响应 |
| POST | `/api/v1/decisions` | 标准公开观测上的单次模型决策 |
| POST | `/api/v1/sessions` | 创建游戏会话 |
| GET / DELETE | `/api/v1/sessions/{session_id}` | 观察 / 释放会话 |
| POST | `/api/v1/sessions/{session_id}/steps` | 提交动作、模型决策或时间推进 |
| GET | `/api/v1/sessions/{session_id}/replay` | 导出当前会话动作追踪 |
| GET / POST | `/api/v1/evaluations` | 列举 / 创建 Arena 评测 |
| GET | `/api/v1/evaluations/{evaluation_id}` | 查询进度与成绩 |
| POST | `/api/v1/evaluations/{evaluation_id}/pause` | 暂停评测 |
| POST | `/api/v1/evaluations/{evaluation_id}/resume` | 恢复评测 |
| POST | `/api/v1/evaluations/{evaluation_id}/models/{model_id}` | 增量加入模型，保留已完成对局 |
| GET | `/api/v1/evaluations/{evaluation_id}/export` | 导出成绩与重演记录 |
| GET / PUT | `/api/v1/leaderboards/{benchmark}` | 读取 / 替换 Benchmark 榜单 |

连接和游戏会话属于创建它们的浏览器会话。编程客户端需要在后续请求中保留服务设置的 Cookie；owner 隔离用于资源归属。默认域名部署不要求网站登录，也可单独启用可选 BasicAuth。榜单默认只读；配置 `JEV_ADMIN_TOKEN` 后，写入使用 `X-Jev-Admin-Token: <admin-token>`，并兼容 `Authorization: Bearer <admin-token>`。启用可选网站 BasicAuth 时使用前者，避免 Authorization 头冲突。管理令牌与模型服务密钥用途不同。每个写入请求体最大 4 MiB。

## curl 客户端与 Cookie

下面用 Cookie jar 保留连接所有权；每次调用都带 `-b` / `-c`，不要为每个请求创建新的 Cookie jar。示例不连接真实付费模型。

```bash
jev_api=http://127.0.0.1:8080
jev_cookie_jar=$(mktemp)
curl --fail-with-body -sS -c "$jev_cookie_jar" -b "$jev_cookie_jar" \
  "$jev_api/api/v1/games"

curl --fail-with-body -sS -c "$jev_cookie_jar" -b "$jev_cookie_jar" \
  -H 'Content-Type: application/json' \
  --data '{"model_id":"my-model","name":"My Model","served_model":"my-served-model","adapter":"decision","transport":"browser"}' \
  "$jev_api/api/v1/connections"

curl --fail-with-body -sS -c "$jev_cookie_jar" -b "$jev_cookie_jar" \
  "$jev_api/api/v1/models"
```

上述模型注册只提交公开元信息；执行模型决策还需浏览器持续处理该连接的请求队列。通常由页面负责完整链路。手动试玩无需模型连接，将游戏 ID 替换为清单中的真实 ID 后创建会话，后续使用返回的 `session_id`、`revision` 和候选动作：

```bash
curl --fail-with-body -sS -c "$jev_cookie_jar" -b "$jev_cookie_jar" \
  -H 'Content-Type: application/json' \
  --data '{"game":"GAME_ID","seed":42}' \
  "$jev_api/api/v1/sessions"

curl --fail-with-body -sS -c "$jev_cookie_jar" -b "$jev_cookie_jar" \
  -H 'Content-Type: application/json' \
  --data '{"revision":0,"action":"ACTION_ID"}' \
  "$jev_api/api/v1/sessions/SESSION_ID/steps"
```

`GAME_ID`、`SESSION_ID`、`ACTION_ID` 为占位符，`ACTION_ID` 使用当前 `decision.question.options` 返回的候选 ID。以上手动动作不调用模型。

上述示例针对本地回环地址。访问启用了入口登录的域名时，额外使用 `curl --user "$JEV_SITE_USER"`，由 curl 交互提示输入密码；不要把明文密码放入命令行参数或记录脚本。

### Playground 开局与种子

首次进入 Playground 默认选择精选第一项贪吃蛇；精选顺序与默认选择共用同一配置。页面间切换保留当前游戏和对局。

前端首次进入、切换游戏、Restart 和终局“再来一局”均开始完整新局，不沿用种子输入框中的局面。棋盘恢复标准摆法；需要发牌、生成地图或方块序列的游戏仍正常随机生成，但进度、得分和行动历史从初始值开始。只有底部“按种子重开 / 换一个种子”显式使用种子，下一次普通 Restart 会回到标准开局模式。

- 棋盘入口 `POST /api/game/new` 不传 `seed`（或传 `null`）表示标准开局。显式数字种子包括 `0` 仍用于合法预走的可复现局面。
- 国际象棋前端通过 `POST /api/v1/sessions` 传 `{"game":"chess","seed":0}` 创建标准 32 子开局；非零种子保留合法开局前缀。通用会话接口的默认种子及 RL 调用合同不变。
- 其他游戏的普通重开不提交输入框种子；世界游戏调用无种子的 `reset()`。显式样例回放仍使用样例自身初始状态，不叠加种子。
- 种子与开局模式属于界面和复现信息，不注入模型的隐藏信息。实时游戏继续沿用原有时钟机制。


## 模型连接

模型有三个不同字段：`model_id` 是本服务的稳定 ID，`name` 是榜单上的显示名称，`served_model` 是模型接口实际接受并返回的身份。重命名显示文字不改变模型身份。

创建请求只登记浏览器连接的公开元信息：

```json
{
  "model_id": "my-model",
  "name": "My Model",
  "served_model": "my-served-model",
  "adapter": "openai",
  "transport": "browser",
  "json_mode": true,
  "timeout_seconds": 120
}
```

`transport` 固定为 `browser`，后端连接接口**不接受** `endpoint` 或 `api_key`。完整请求地址与密钥在前端填写并只留在页面内存中，密钥仅发送给所填模型服务，不发送给 Jev 后端。页面轮询自己连接的决策队列，直接向模型服务发送请求，再把标准决策结果交回后端。关闭或刷新页面会中断此链路，需要重新连接。

页面中填写的请求地址应为完整 HTTP(S) URL，不能包含 URL 用户名、密码、查询或片段；例如 OpenAI 兼容接口包含完整 `/v1/chat/completions` 路径。模型接口须使用与 Jev 页面不同的 origin，避免密钥发送到游戏站点。模型服务必须允许当前页面来源的 CORS 请求，HTTPS 页面应连接 HTTPS 模型接口。Jev 后端没有代替浏览器发送模型请求的路径。

轮询 `GET /connections/{model_id}/requests` 每次最多等待 10 秒，返回 `{"requests":[...]}`，其中每项是 `jev.decision.v1` 请求。回传到 `POST /connections/{model_id}/results`，请求体为 `{"request_id":"...","result":{...标准响应...}}`；失败时用 `error` 代替 `result`，值只能是 `connection_failed`、`invalid_response`、`timeout` 或 `cancelled`。不要回传含密钥或上游敏感正文的错误内容。

`adapter` 为 `decision` 时使用下节的结构化合同，为 `openai` 时使用 Chat Completions JSON。接口返回的 `model` 必须与 `served_model` 相同；不同服务对模型别名的返回方式不同，应填写实际返回的名称。

## 结构化决策合同

自建模型服务接收以下 `jev.decision.v1` JSON。`observation` 只包含公开观测；请求中的 `question.options` 是本次全部合法候选，模型必须选择其中一个 ID。

```json
{
  "schema_version": "jev.decision.v1",
  "request_id": "decision-0001",
  "model": "my-served-model",
  "game": "example_game",
  "observation": {"turn": 3, "visible_board": [[0, 1], [0, 0]]},
  "question": {
    "id": "decision",
    "instructions": "Choose one legal action.",
    "options": [
      {"id": "left", "label": "Move left"},
      {"id": "right", "label": "Move right"}
    ]
  }
}
```

`example_game` 仅用于说明 JSON 结构。实际游戏 ID 从 `/api/v1/games` 读取，状态与动作由对应引擎生成。

响应：

```json
{
  "schema_version": "jev.decision.v1",
  "request_id": "decision-0001",
  "model": "my-served-model",
  "action": "right",
  "probabilities": {"left": 0.2, "right": 0.8},
  "usage": {"prompt_tokens": 82, "completion_tokens": 12}
}
```

`request_id` 与 `model` 必须与请求完全相同。`probabilities` 可省略或为 `null`；如果提供，必须覆盖全部且仅有合法候选，取值在 0–1 之间，总和与 1 的误差不超过 `1e-7`。返回概率应来自模型服务可测量的候选分布，不用生成文本的自报置信度代替。

向浏览器连接下发决策时，用 `POST /api/v1/decisions` 包裹上述请求；后端排队等待该浏览器返回结果，不会自行访问模型服务：

```json
{
  "model_id": "my-model",
  "input": {
    "schema_version": "jev.decision.v1",
    "request_id": "decision-0001",
    "model": "my-served-model",
    "game": "example_game",
    "observation": {"turn": 3},
    "question": {
      "instructions": "Choose one legal action.",
      "options": [{"id": "left", "label": "Move left"}, {"id": "right", "label": "Move right"}]
    }
  }
}
```

## OpenAI 兼容适配

请求使用 `model`、`messages`、`temperature`、`max_tokens`、`stream: false`。默认附带 `response_format: {"type":"json_object"}`；模型服务不支持该字段时关闭连接的 `json_mode`。

模型应在 `choices[0].message.content` 中返回可解析的 JSON 字符串，例如 `{"action":"right"}`。服务响应顶层需要返回匹配的 `model`。此适配器不把 JSON 中自报的 `probabilities` 转成真实候选概率；没有可测量概率时相应指标保持缺失。

## 游戏会话

创建请求：

```json
{"game": "实际游戏 ID", "seed": 42}
```

会话返回 `schema_version: "jev.session.v1"`、`session_id`、`game`、`seed`、`revision`、公开 `state`、`terminal` 和可决策时的 `decision`。调用方只能依照当前返回的候选提交动作。

动作请求形态：

```json
{"revision": 0, "action": "当前合法动作 ID"}
```

也可以让已连接模型决策：

```json
{"revision": 0, "model_id": "my-model"}
```

`action` 与 `model_id` 互斥。`revision` 使用上次观察到的版本，避免两个请求覆盖同一状态。实时游戏的无动作推进可使用 `ticks`（0–120）；具体时钟、终局和动作持续时间由共享引擎定义，不能通过省略动作冻结实时规则。

## Arena 评测

创建请求：

```json
{
  "model_ids": ["model-a", "model-b"],
  "games": ["实际游戏 ID"],
  "seeds": 1,
  "seed_base": 42,
  "concurrency": 32
}
```

模型需已连接并归当前浏览器所有。`model_ids` 为 2–16 个唯一 ID；省略 `games` 表示当前全部 Arena 游戏，显式列表为 1–128 个唯一 ID，仍须属于当前可评测引擎；`seeds` 为 1–3，`concurrency` 为 1–64，同时受服务总模型请求并发限制。不要把对局并发与实际发出的模型请求并发混为一谈。

可双人对战的游戏使用直接对局并交换席位；单人游戏以同游戏、同种子的最终结果配对。实时游戏使用单次模型决策；其他游戏的重复决策及选项换位遵循记录中的协议版本。终局、失败、超时与时间计分按共享引擎和评测协议记录，保留完整追踪来源。

导入的历史成绩不会触发重新评测，服务启动也不会自动调用模型。评测任务和回放数据与浏览器临时模型连接分开存储，服务重启后需重新连接模型再显式恢复任务。

增量加入模型使用 `POST /evaluations/{evaluation_id}/models/{model_id}`；原参赛模型连接仍需可用，服务只安排缺少的新对局。暂停、恢复或加入操作要求当前浏览器拥有该任务所需的模型连接。

## Benchmark 榜单导入

`benchmark` 支持 `jevbench`、`decisionindex`、`harnessjevbench`、`datajevbench` 和 `arena`。文件使用 `jev.leaderboard.v1`，每次导入是对应榜单的完整快照；保留需要显示的所有模型行。

```json
{
  "schema_version": "jev.leaderboard.v1",
  "benchmark_id": "jevbench",
  "title": "JevBench",
  "version": "my-evaluation-v1",
  "metric": "accuracy",
  "score_scale": [0, 1],
  "higher_is_better": true,
  "axis_scale": [0, 1],
  "rows": [
    {
      "model_id": "my-model",
      "model_name": "My Model",
      "score": 0.81,
      "status": "complete",
      "metrics": {"accuracy": 0.81, "brier": 0.18, "ece": 0.04},
      "samples": 100,
      "errors": 0,
      "evaluated_at": "2026-10-16T00:00:00Z",
      "protocol": "my-protocol-v1",
      "axes": [
        {"id": "planning", "label_en": "Planning", "label_zh": "规划", "score": 0.8, "samples": 40},
        {"id": "reasoning", "label_en": "Reasoning", "label_zh": "推理", "score": 0.82, "samples": 60}
      ]
    }
  ]
}
```

该例为格式示例，非真实模型成绩。`score_scale` 控制总分范围，`axis_scale` 控制雷达轴范围；每条记录必须符合对应范围。模型 ID 在同一榜单内唯一，轴 ID 在同一模型内唯一。`null` 表示没有指标，不应写成 0。双语切换使用 `label_zh` 与 `label_en`。

修改榜单会保留上一版 JSON 归档，不需要原始训练样本或模型 checkpoint。JevBench、DecisionIndex、HarnessJevBench 与 DataJevBench 的总分使用各自指标定义；Arena 则使用下节的 Elo 快照约定。Harness 的总分为 Hard mean task score，ACC 优先显示 `strict_task_accuracy`；DataJevBench 使用 ACC 总分及 D1–D6 雷达维度。

导入时对 `PUT /api/v1/leaderboards/jevbench` 发送上述完整 JSON，`benchmark_id` 必须与 URL 一致，并携带管理员认证。`GET` 同一地址可导出标准 JSON。Arena 原始逐局记录与重演使用 `/evaluations/{evaluation_id}/export`，与下面的榜单分数快照区分。

在服务器上运行 `python scripts/import_leaderboard.py results.json --leaderboard-dir ./leaderboard` 可使用同一合同和归档逻辑进行本地导入，无需 Web 管理令牌。该命令不调用模型服务，失败时不会把输入内容回显到错误消息中；默认目录遵循 `JEV_LEADERBOARD_DIR`，未配置时使用仓库 `leaderboard/`。它替换指定榜单的完整快照，已存在的上一版保留在目录内的 `history/`。具体文件约定见 [榜单数据目录](LEADERBOARD_DATA.md)。

## Arena Elo 快照导入

`GET /api/v1/leaderboards/arena` 和 `PUT /api/v1/leaderboards/arena` 使用同一个 `jev.leaderboard.v1` 合同。`score` 是综合 Elo，`axes` 保存分游戏 Elo，`metrics` 可包含 `wins`、`draws`、`losses`，`samples` 是已比较场次。请为 Elo 明确设置总分与轴范围，而不是保留概率分数默认的 `[0,1]`。

```json
{
  "schema_version": "jev.leaderboard.v1",
  "benchmark_id": "arena",
  "title": "Piccolo Arena",
  "version": "import-example-v1",
  "metric": "elo",
  "score_scale": [0, 3000],
  "axis_scale": [0, 3000],
  "higher_is_better": true,
  "rows": [
    {
      "model_id": "example-imported-model",
      "model_name": "Imported Model",
      "score": 1520,
      "status": "complete",
      "metrics": {"wins": 12, "draws": 3, "losses": 5},
      "samples": 20,
      "protocol": "example-elo-protocol-v1",
      "axes": [
        {"id": "snake_navigation", "label_en": "Snake", "label_zh": "贪吃蛇", "score": 1510},
        {"id": "racing_sprint", "label_en": "Racing", "label_zh": "赛车", "score": 1530}
      ]
    }
  ]
}
```

这是格式示例，不是真实成绩。导入的 Arena 榜单供只读展示，没有原始 match 或回放，也不能把导入的 Elo 数值当作新对战的计算起点。后续评测需要真实连接和对局记录，按该任务自己的协议计算。

前端展示优先级为：已有本地评测任务的成绩 → 导入的 `arena` 快照 → 随包历史成绩。因而本地已存在评测任务时，导入文件仍可通过标准 GET 接口读取，但不会覆盖当前任务在前端天梯中的展示。

标准 Arena Elo 导入写入统一目录的 `arena-ratings.json`；原生完整 `arena.json` 与 `arena-replays.json` 继续配套保留，不会被一个纯分数快照覆盖。

## 错误处理

| HTTP 状态 | 调用方处理 |
| --- | --- |
| `401` / `403` | 检查管理员认证、浏览器 Cookie 或连接所有权 |
| `404` | 资源不存在，重新查询游戏/连接/会话清单 |
| `409` | ID 冲突、会话版本冲突或任务状态不允许当前操作 |
| `422` | 修改请求字段或非法动作，勿原样无限重试 |
| `429` | 并发或连接数限制，降低并发并稍后重试 |
| `502` | 模型响应不符合合同或上游错误，核对模型名与返回结构 |
| `503` / `504` | 模型连接失效、超时或暂不可用，重新连接或恢复服务 |

上游响应文本和鉴权头不作为公共错误信息返回。客户端也不应把模型密钥写入自己的日志或评测数据。

## 私有游戏席位交接

UNO的版本化会话在 `state.handoff=true` 时不提供合法动作或模型观测。对 `POST /api/v1/sessions/{session_id}/steps` 发送当前 `revision` 和 `reveal: true` 可显示下一席位。交接请求不能同时包含 action、model_id 或 ticks。兼容页面继续使用 `/api/showcases/reveal`。
