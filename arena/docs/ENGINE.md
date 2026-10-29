# 共享游戏引擎与 RL 接入

公共 Python 入口是 `blink_arena.engine`。引擎提供规则、公开观测、候选动作、状态推进、终局，以及实时游戏的 rollout runner 和重演 verifier；本仓库不包含完整训练框架、优化器或 checkpoint 管理。

前端试玩、Arena 和 RL 应从同一 registry 获取游戏，保留相同种子、规则版本与时钟合同。导入公共引擎入口不依赖 FastAPI 或模型服务；具体游戏按需加载自己的运行依赖，例如 OpenSpiel、python-chess 或 Node.js 22。Playwright 仅供旧浏览器插件或前端回归。

本应用的模型请求由浏览器直接发出：完整端点与密钥只保留在页面内存中，密钥只发送给所填模型服务，Jev 后端只调度公开观测和结构化结果。下面的 RL 示例将策略表示为调用方提供的 `policy` / `sampler` 回调，引擎入口没有端点或密钥配置；策略元信息与轨迹不得夹带凭据。网页版调用需要模型服务允许 CORS，HTTPS 页面连接 HTTPS 模型接口。

## 发现与环境合同

```python
from blink_arena.engine import get_engine, list_engines

for engine in list_engines(include_internal=False):
    print(engine.kind, engine.backend, engine.clock)

engine = get_engine("sokoban_puzzle")
descriptor = engine.descriptor()
```

HTTP 客户端通过 `GET /api/v1/games` 获取同一份可公开的 descriptor。`internal=True` 的兼容或内部任务不自动出现在试玩列表，部署的游戏范围也会继续过滤可创建的会话。

| 方法 | 输入 / 返回 | 用途 |
| --- | --- | --- |
| `reset(seed, options=None)` | 种子与该引擎支持的选项 → 原生状态 | 创建对局 |
| `legal_actions(state)` | 状态 → 动作 ID 与描述的字典 | 引擎合法动作集合 |
| `observe(state)` / `as_record(state)` | 状态 → 完整公开 `jev.training.v1` 记录 | 原始输入、历史兼容与严格回放 |
| `model_input(state, input_format="selected-v1")` | 状态 → 当前模型决策输入 | 与前端相同的意图/预测视图 |
| `step(state, action, **kwargs)` | 状态与动作 → 推进结果 | 回合游戏推进；浏览器引擎委托给 driver |
| `public(state)` | 状态 → 前端展示快照 | UI / 调试展示 |
| `outcome(state, side=None)` | 状态与可选席位 → 终局结果或 `None` | 判断是否结束 |

新策略输入使用 `model_input`；复现旧输入可使用 `observe` 或 `model_input(..., input_format="original")`，不能把完整原生状态或 UI 用的 `public` 快照直接发给模型。原生状态可能含暗牌、随机数状态或其他私有字段。候选顺序来自 `questions.decision.option_order`；不存在该字段时使用 `criteria` 的顺序。部分游戏提供合法动作的受限候选子集，策略必须从本次观测的 `criteria` 中选择，不能用更大的 `legal_actions` 集合替换它。

意图投影只读取完整公开观测，不读取隐藏状态；动作 ID、候选顺序和物理规则保持不变。已有 rollout runner 为严格回放保留原始观测；策略回调可用 `blink_arena.model_inputs.project_record(record, "selected-v1")` 取得与网页一致的输入，并另存实际发送记录。压缩字段与前后评测见 [模型输入优化](MODEL_INPUT_INTENT_20261021.md)。

种子通常是 uint32；仅特定棋盘起局支持 `None`。`reset` 的附加选项由具体适配器验证，不接受未定义选项。

## 纯回合游戏示例

下面用推箱子演示一次观测与手动动作，不请求模型：

```python
from blink_arena.engine import get_engine

engine = get_engine("sokoban_puzzle")
assert engine.backend == "native" and engine.clock == "turn"
state = engine.reset(42)
record = engine.model_input(state)
question = record["questions"]["decision"]
candidate_ids = question.get("option_order") or list(question["criteria"])
action = candidate_ids[0]  # 示例选择；真实策略读取 record 后返回动作 ID。
state = engine.step(state, action)
result = engine.outcome(state)
print({"game": engine.kind, "action": action, "outcome": result})
```

RL rollout 可以重复这个循环，直到 `outcome` 非空或达到显式预算；训练框架负责模型调用与张量处理。每次都保存实际执行的动作、公开观测和对应结果，不能用参考答案替代模型动作。

## 原生实时游戏

贪吃蛇、俄罗斯方块和赛车的 `clock` 为 `realtime`，`engine.runtime` 提供统一时钟方法。正常交互要使用这些方法；连续调用普通 `step` 不能模拟模型等待期间的真实流逝时间。

| Runtime 方法 | 语义 |
| --- | --- |
| `start(session, now=None)` | 为包含 `world` 的会话建立单调时钟基点；不替代游戏本身的首次输入启动条件 |
| `tick(session, now=None)` | 补齐上次时钟以来的真实物理推进，更新 `session["world"]` |
| `capture(session)` | 先补齐物理，再返回冻结的请求时状态与公开记录；终局可返回空记录 |
| `commit(session, action, controller="model", observed=None)` | 再次补齐等待期间物理，校验到达时状态，返回 `applied`、`arrival_state` 和 `reason` |
| `fail(session, reason)` | 按原生运行时记录请求失败的终局 |

一次模型决策的接法如下。`policy(record)` 由调用者实现，只返回动作 ID。真实调用遵守 runtime 给出的超时与最短决策间隔：

```python
import asyncio
import time
from blink_arena.engine import get_engine

engine = get_engine("snake_navigation")
runtime = engine.runtime
session = {"world": engine.reset(42)}
runtime.start(session)

async def decision_once(policy):
    captured_at = time.monotonic()
    observed, record = runtime.capture(session)
    if record is None:
        return None
    action = await asyncio.wait_for(
        policy(record), timeout=runtime.MODEL_TIMEOUT_SECONDS
    )
    if action not in record["questions"]["decision"]["criteria"]:
        raise ValueError("action outside captured candidates")
    receipt = runtime.commit(session, action, observed=observed)
    if receipt["applied"]:
        await asyncio.sleep(max(0, runtime.MIN_DECISION_SECONDS -
                                  (time.monotonic() - captured_at)))
    runtime.tick(session)
    return receipt
```

正式 rollout 使用下节自带的 runner 来统一处理错误、超时、预算及轨迹。模型等待不会暂停物理；`capture`、UI 轮询或 `commit` 都按同一时钟补齐推进。俄罗斯方块需把 `observed` 传给 `commit`，防止旧方块的模型回复误操作新方块。返回 `applied=False` 时保留丢弃原因，不要静默替换动作或将其记作已执行动作。

游戏启动条件由规则决定：赛车首次踩油门后才开始赛时，贪吃蛇与俄罗斯方块遵循各自的首次有效输入条件。启动之后，推理等待、无新输入和动作过期都继续按真实规则处理。终局时间及最终得分使用相同运行时产生的数据。

## 实时 rollout 与重演校验

`EngineSpec.rl_runner` 和 `rl_verify` 是 `module:function` 形式的显式入口。原生实时游戏已注册对应 runner 与 verifier；Mario/Terra 注册独立 JS 核心 runner 与逐帧重演校验，`backend="worker"`；旧浏览器插件仍可注册 browser runner。不要仅依据 `clock` 猜测函数名。

```python
from importlib import import_module
import inspect

def resolve(entry):
    module, function = entry.split(":", 1)
    return getattr(import_module(module), function)

async def run_verified(engine, sampler, seed, episode_id):
    job = {"kind": engine.kind, "seed": seed, "episode_id": episode_id}
    play = resolve(engine.rl_runner)
    verify = resolve(engine.rl_verify)
    initial, final, trace, outcome, extra = await play(sampler, job)
    if engine.backend == "browser":
        await verify(sampler, job, initial, final, extra, trace=trace)
    else:
        checked = verify(job, initial, final, extra)
        if inspect.isawaitable(checked):
            await checked
    return initial, final, trace, outcome, extra
```

上述签名适用于本包当前自带的实时 runner；自定义插件的 runner/verifier 应在插件合同中说明其签名。`sampler` 需实现：

- `async policy_action(record, episode_id, ordinal)`：返回 `(action_id, policy_metadata)`。
- 可选 `journal(job, event_name, event)`：记录事件。只保存需要的评测信息，不夹带模型密钥、鉴权头或私人端点。
- 内置 Mario/Terra 不要求 `browser` 或 `args.frontend`；Node 宿主从 registry 的 `core_module` 加载共享核心。只有显式注册的旧 browser 插件才需要真实 Playwright driver。

返回的 `trace` 包含实际应用的动作；`extra.replay_events` 还保留等待、未执行回复和终局等校验信息。原生 verifier 重放记录的时间间隔和动作；浏览器 verifier 在同一份 JavaScript 物理上推进到记录的帧边界。校验失败的轨迹不应直接当作有效训练样本。推理等待产生的效果归属由 runner 的 `credit_before_state`、`credit_after_state` 与 `credit_revision` 明确记录。

## 独立世界核心与 bind

Mario 和 Terramai 的 `backend="worker"`，其状态推进来自 `web/playground/` 下前端共用的独立 JavaScript 核心。`core_module` 与 `core_viewport` 描述执行资源；`browser_page`、`browser_bridge`、`browser_assets` 保留前端渲染元信息，不要求 RL 加载页面。未绑定 driver 时，`reset` / `step` 抛出 `DriverRequired`。

`engine.bind(driver)` 返回一个绑定后的 EngineSpec，不修改全局 registry。driver 实现 `reset(seed, options)` 和 `step(observed_state, action, **kwargs)`；异步 driver 可以返回 awaitable：

```python
from blink_arena.engine import get_engine
from blink_arena.engines.jev_world_core import WorldCoreDriver

async def decide_once(policy):
    engine = get_engine("mario_platformer")
    driver = WorldCoreDriver(engine.kind, 42)
    bound = engine.bind(driver)
    try:
        state = await bound.reset(42, {})
        record = bound.observe(state)
        selected_action = await policy(record)
        # Node 中的同一份游戏物理在等待模型时继续运行。
        return await bound.step(state, selected_action)
    finally:
        await driver.close()
```

`step` 的返回值包含到达快照、执行后快照及丢弃原因，调用方保留这些信息后再取执行后状态。driver 在同一核心任务中检查终局、世界变化与死亡/重生，再提交动作。标准 RL 接入优先复用已注册 runner，它同时负责 episode clock、动作到达检查和 verifier 所需记录。显式注册的旧 `backend="browser"` 插件仍须绑定真实 browser driver。

## 增加普通回合游戏

普通原生游戏实现 `Environment` 的六个方法后注册 `EngineSpec`。默认 `renderer="generic"` 可由前端通用场景面板展示公开状态与候选，不需要复制一份页面。以下是最小可运行插件，只用于展示合同：

```python
# 保存为 demo_game_plugin.py，确保该模块可被 Python 导入。
from blink_arena.engine import EngineSpec

class CounterGame:
    def reset(self, seed, options=None):
        return {"kind": "demo_counter", "seed": seed, "count": 0}

    def legal_actions(self, state):
        return {"finish": "Finish"} if not state["count"] else {}

    def observe(self, state):
        actions = self.legal_actions(state)
        return {"schema_version": "jev.training.v1", "state": self.public(state),
                "questions": {"decision": {"type": "choice",
                    "instructions": "Choose an action.", "criteria": actions,
                    "option_order": list(actions)}}, "labels": {},
                "metadata": {"domain": "game", "sub_domain": "demo_counter"}}

    def step(self, state, action, **kwargs):
        if action not in self.legal_actions(state):
            raise ValueError("Illegal action")
        return {**state, "count": state["count"] + 1}

    def public(self, state, **kwargs):
        return {"kind": "demo_counter", "count": state["count"]}

    def outcome(self, state, side=None):
        return "win" if state["count"] else None

def register_engines(register):
    register(EngineSpec(kind="demo_counter", name="Counter demo",
                        environment=CounterGame(), limit=1,
                        goal="Finish one move"))
```

```bash
JEV_ENGINE_PLUGINS=demo_game_plugin bash scripts/run.sh
```

多个模块用逗号分隔，前端服务与 RL 进程都需载入同一组模块。插件必须是可导入的 Python 模块；加载器不扫描任意目录。模块可在导入时注册，或提供 `register_engines(register)`，二者选择一种。插件不能覆盖已有内置游戏，注册失败会回滚该模块的 registry 变更。

注册约束包括：小写游戏 ID、正数决策预算、非空且不重复的对手模式、正数席位数，以及六个环境方法。普通插件注册可接入通用会话与前端；进入 Arena、多人对局、专用渲染器或训练奖励时仍须满足对应消费者的语义，不能仅靠添加一个名字获得这些能力。

新增原生实时游戏还必须提供 `runtime_module`、`rl_runner` 和 `rl_verify`；新增浏览器世界还必须提供真实 page/bridge、包内相对资产路径与 runner/verifier。自定义 RL runner 与 verifier 必须成对注册。不能把实时插件声明为回合游戏来绕开时间或重演合同。

## 历史兼容

正常新对局使用 `get_engine(kind)`。读取已知历史状态时可用 `get_engine(kind, state)`，按明确布局选择归档适配器；不能为了避开缺失 browser driver 而使用旧模拟规则。`get_archived_engine` 仅用于显式归档兼容。保留轨迹中的引擎、接口、时钟和计分版本；不同版本的历史结果不应伪装成同一规则重新计分。

## 共享 JS 核心

`mario-core.js` 与 `terraria-core.js` 是无 DOM、Canvas 或网络依赖的 factory。浏览器的 `mario.js` / `terraria.js` 是绘制、键盘、触屏和本地化适配器；Node 用同一个核心推进物理，结构化公开观测继续交给相同 Python TrainingRecord/Choice 合同。

注册 `EngineSpec(..., backend="worker", family="world", environment=WorkerEnvironment(...), core_module="my-game-core.js", core_viewport=(896,448), rl_runner=..., rl_verify=..., browser_assets=(...))`。可选 `browser_page` / `browser_bridge` 描述前端渲染入口，与执行后端类型分离。模块导出 `create(options)`，接受注入的 seed source、单调时钟和视口；实现 reset、snapshot、prepare、act、activate、release、condition、tick、advanceTo、terminal。`renderState()` 只给绘制器，不得作为模型输入。

`tick(timestamp)` 保留原固定步长与原生时序；`advanceTo(frame)` 仅用于相同物理的确定性重演。模型调用期间独立 Node 定时器继续工作。终局检测使用不带观察副作用的 `terminal()`；`world-arrival.js` 在前端与 Node 都校验当前状态，拒绝过期意图且不替模型另选动作。

## 新增七个原生游戏

西洋跳棋、围棋、中国象棋、猜数字、扫雷、数独和UNO默认注册。专用 renderer、私有席位交接、RL runner/verifier 与奖励配置见 [七个游戏接入说明](SELECTED_GAMES.md)。数独分为选格和填数两个公开决策阶段；规则对手为合法动作随机基线。
