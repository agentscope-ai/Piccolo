# 标准在线训练接口

同一个 BlinkArena 服务提供前端试玩和在线训练后端。运行 `python -m blink_arena` 即挂载 `/api/v1/rollouts`；服务不需要训练框架、checkpoint、模型地址或模型密钥。训练器自行调用当前策略，再把选中的动作及真实采样概率交回引擎。

## 调用顺序

使用一个保留 cookie 的 HTTP client，先请求 `GET /api/engines` 建立会话，再并发创建对局。子路径部署时所有路径加上部署前缀；更换会话 cookie 后不能读取原会话的记录。

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| POST | `/api/v1/rollouts` | 创建对局，固定环境条件和策略版本 |
| GET | `/api/v1/rollouts/{id}/next-decision?after=-1&timeout=25` | 原始 TrainingRecord、完整候选及决策 ticket |
| POST | `/api/v1/rollouts/{id}/answers` | ticket 身份、动作、实际行为分布 |
| GET | `/api/v1/rollouts/{id}/result` | 完整终局回执；未完成时 HTTP 202 |
| POST | `/api/v1/rollouts/{id}/cancel` | 中止且保留失败分母 |
| GET | `/api/v1/rollouts?cursor=0&limit=50` | 当前会话的分页摘要，最多 100 条 |

创建请求示例：

```json
{
  "episode_id": "round1-jump-condition1-trial0",
  "game": "jump_jump",
  "seed": 973610000,
  "mode": "environment",
  "group_id": "round1-jump-condition1",
  "trial": 0,
  "policy_version": "policy-0",
  "request_token": "start-round1-jump-condition1-trial0"
}
```

`game`、对手模式、席位和时钟机制以引擎清单为准。收到 ticket 后使用它的独立 `request_token`，不要使用创建请求的 token。答复的 `policy` 包含 `candidate_values`、`old_probabilities`、`selected_index`、`origin` 和 `forced`；完整分布必须对应实际抽样，不能用教师答案或文本自报概率代替。训练器可附同次推理的输入 token、候选 token、温度及探索比例。

同一 `episode_id` 的原样创建、同一 ticket 的原样答复可以重传；修改条件、改答、过期或错误策略版本会被拒绝。客户端不能提交 reward 或 advantage。训练端收到过期答复应继续查询结算，不能重新选择动作覆盖失败。

## 真实引擎与训练边界

`jev_engine_episode_runner.py` 是前端同源环境和旧采样器共用的完整对局执行与回放实现。原有棋盘和实时世界的规则、实时机制、终局条件均保留。Mario、Terraria 直接通过 Node.js 22 运行与网页相同的 `mario-core.js` / `terraria-core.js`，不加载页面、字体、Canvas 或 Chromium。实时游戏在等待模型时继续推进，回复到达时检查动作期限。

### Mario 种子地图与历史回放

`mario-map-v2-curriculum` 在前端与 RL 共用的独立核心中生成地图。种子现在同时决定地图长度、坑数量和宽度、管道数量、敌人数量、砖组位置与长度、蘑菇数量以及植物周期。`seed % 4` 依次对应 easy、medium、hard、legacy；后三者不代表新的胜利定义，通关仍要求活着抵达本地图旗杆。legacy 保留原来的 96 列布局，显式 `reset(seed, {generator_revision: 'world-seed-v1'})` 可恢复任意旧种子的旧地图。

| 档位 | 地图列数 | 坑数 | 管道数 | 敌人数 | 蘑菇数 |
|---|---:|---:|---:|---:|---:|
| easy | 48–64 | 1–2 | 1–2 | 1–3 | 3–5 |
| medium | 72–88 | 2–3 | 2–3 | 3–5 | 2–4 |
| hard | 96–128 | 3–4 | 4–5 | 5–8 | 1–2 |
| legacy | 96 | 3 | 4 | 5 | 2 |

各参数在安全几何约束内联合采样，范围不是所有组合都可取。新档位为坑、管道和砖组保留落脚及起跳空间；敌人巡逻限于有支撑的地面，出生区域无敌人。跳跃物理、碰撞、植物伤害、实时等待及动作到达检查沿用共享引擎，不提供通关接管。

原生回执新增 `environment_generation: {seed, generator_revision, profile}`，用于复现环境；它不进入模型的状态观测或候选题目。新回放按该版本复现，缺少该字段的旧 Mario 回执按 `world-seed-v1` 复现，并继续校验完整事件、输入、动作与奖励。前端和 RL 使用同一个 `world-seed.js` 与 `mario-core.js`；`mario.js` 只负责页面绘制和人类输入。回执顶层的 `engine_runtime` 和 `engine_viewport` 记录运行时与观察视口，不加入模型输入。默认正式视口为 Mario 896×448、Terra 888×480，与原现场一致。

后端返回 `jev.rollout.receipt.v1`，包含实际执行轨迹、环境过程奖励、终局效用、回放验证、策略来源、规则接管次数和失败类型。错误、超时、取消及中断全部保留分母；完整隐藏状态只进入服务端审计。规则接管不能算成学生模型的 on-policy 成绩。

训练端负责与 SFT 一致的 PromptTemplate/tokenizer、候选概率、逐步 advantage、mask 和显式任务权重。单一 `decision` Choice 表示完整动作；多个问题的单项概率不能作为联合动作概率。

需要模型对手时，宿主通过 `create_app(rollout_opponent=callback)` 注入异步 `(kind, seed, ordinal, record) -> (action, metadata)` 回调。缺少指定对手会明确失败。浏览器模型连接仍遵循原有隐私边界，训练 RPC 不接收模型地址或凭据。

## 缓存、恢复与运行目录

数据写入 `JEV_DATA_DIR/rollouts`。同一目录仅允许一个服务进程写入；使用单 worker。元信息、journal 和回执持久化到私有文件，SQLite 维护身份与分页索引。已完成记录可淘汰出内存，再按需读盘；淘汰不会删除审计或取消幂等性。

| 环境变量 | 默认值 | 含义 |
| --- | ---: | --- |
| `JEV_ROLLOUT_MAX_ACTIVE` | 16 | 同时运行上限 |
| `JEV_ROLLOUT_DECISION_TIMEOUT` | 90 | 单个策略请求期限，秒 |
| `JEV_ROLLOUT_CACHE_SIZE` | 32 | 已完成记录缓存条数上限 |
| `JEV_ROLLOUT_CACHE_BYTES` | 67108864 | 已完成缓存序列化字节上限 |

数量和字节上限同时生效，任一个设为 0 可使用无已完成缓存模式。普通页面访问不会打开 rollout 存储或启动引擎子进程。当前内置世界的每个活跃会话使用独立 Node 核心，结束或取消后退出。重启后保留终局和重复请求身份；运行中被中断的局记为 `error`，不会悄悄重跑。无法持久化审计时拒绝成功训练导出；失败文件及旧结果不覆盖、不删除。

序列化字节上限不等于整个 Python 进程的 RSS 上限；活跃局、核心运行时与返回响应还占用内存。扩容应结合活跃数、内存与实际吞吐调整。

## 验证

独立进程验收覆盖四次同条件完整对局、可见输入与实际动作一致、实时等待与过期拒绝、Mario/Terraria 的独立核心时钟、缓存淘汰、重启幂等和跨会话隔离。这些接口检查使用测试策略，不代表模型胜率或 GPU 训练已经通过。训练框架及真实模型更新由调用方单独验收。

## 独立核心与超时

`WorldCoreDriver` 通过受控 JSON RPC 调用 registry 注册的 `core_module`；新增同类游戏只需实现相同核心接口并注册模块及资源，不必修改 Node 宿主中的游戏分支。宿主拒绝任意脚本路径，模型仍只能提交本次 Choice 中的动作。核心需要 `snapshot/reset/prepare/act/release/activate/condition/tick/advanceTo/terminal`，终局时钟读取 `terminal()`，不通过额外 `snapshot()` 改变可见历史。

核心初始化默认 90 秒，单次 RPC 默认 120 秒；取消或超时会结束对应子进程，旧回复不能进入后续请求。策略 ticket 默认 90 秒，长轮询依然有界返回。完整回放调用同一核心按记录帧推进，逐项检查观察、候选、到达校验、实际动作与终态；不会通过放宽超时接受错状态或迟到动作。游戏动作预算、物理时间和胜利条件保持原定义。

贪吃蛇、俄罗斯方块和赛车的实时 runner 还会独立等待策略回调；这三处 `MODEL_TIMEOUT_SECONDS` 默认同为 90 秒，避免外层 ticket 尚未到期就被内层 30 秒限制取消。它只限制模型请求等待；赛车的控制意图期限、方块身份校验、重力和其他物理规则使用各自原合同。

Node 路径可设 `JEV_NODE_EXECUTABLE`；完整源码目录或发行包默认从相邻 `web/playground/` 读取核心资源，宿主也可用 `JEV_ENGINE_ASSET_DIRECTORY` 指定受控资源目录。前端一致性测试仍可运行 Chromium；它不参与正式 RL 环境执行。
