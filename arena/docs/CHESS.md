# 国际象棋：共享引擎、前端与 RL

本次将原来内部保留的 `chess` 身份接到新的共享环境。公开游戏 ID 仍为 `chess`，白方为席位 0、黑方为席位 1；属于回合制。已有实时游戏的时钟机制不变。

## 与 StartLux 的关系

参考 [StartLux-Decision](https://github.com/StartLuxLabs/Startlux-Decision) 的国际象棋决策组织：规则库生成合法着法，模型看到棋盘、子力、棋谱和可观察后果，再通过一次 Choice 选择着法。本版使用现有依赖 `python-chess` 处理规则，在 BlinkArena 的标准 Environment 中实现接线，没有复制一套训练专用棋局。

候选使用 UCI 作稳定 ID，SAN 作可读标签。每个合法着法均保留，候选附带吃子、易位、吃过路兵、升变、将军、将死、自动和棋与落点几何攻击事实。所有事实由当前公开棋盘和历史的一步规则执行计算。几何攻击明确注明可能来自被牵制棋子，不等同于必然能吃子；没有搜索排名、Stockfish 估分或教师答案。

模型负责选棋步、决定继续或申和；引擎负责合法性、机械落子和终局。规则对手是单独选择的公开一步启发式，不在模型报错时接管。

## 规则和种子

- 支持标准棋步、将军与将死、王车易位、吃过路兵，以及升后、车、象、马。
- 逼和、子力不足、五次重复和七十五回合按原生规则自动结束。三次重复、五十回合需要明确申和。
- 每个申和原因只有一个语义动作。需要预告走法时，候选事实列出合法证书并绑定确定的见证 UCI；执行只验真并结束，不执行这个预告棋步。避免同一申和结果重复占用许多候选，普通合法 UCI 均不删减。
- `seed=0` 是标准初始棋局；非零种子生成 4、6、8、10 或 12 半回合的合法公开开局前缀。前缀属于初始化，不计学生动作或模型成绩。相同种子可复现完整起点，JSON 中保存完整历史以验证重复局面和特殊规则。
- 显式 FEN 只允许测试接口明确 `allow_custom_fen=True`，RL 创建请求不接受注入 FEN。正式对照应分别报告标准开局和种子开局条件。
- 默认总预算为 256 半回合；RL 还可限制学生决策次数。达到预算记 `budget_exhausted`，不按子力或估分裁胜，也不冒充和棋。

## 调用链与接口

| 位置 | 接线 |
| --- | --- |
| 规则与观察 | `blink_arena/engines/jev_chess.py`：`ChessEnvironment` 六方法 |
| 共享注册 | `jev_engine_registry.py`：`family=strategy`、`renderer=chess`、两个席位与两种对手 |
| 前端 | `web/playground/chess.js`、`chess.css`，只消费后端公开棋盘与合法 UCI |
| 对局采样和回放 | `jev_chess_rl.py`：`play/verify`，由 `EngineEpisodeRunner` 和 `/api/v1/rollouts` 使用 |
| 评测 | `play_evaluation/verify_evaluation` 复用同一循环，显式禁止训练导出 |

```python
from blink_arena.engine import get_engine

engine = get_engine("chess")
state = engine.reset(0)
record = engine.observe(state)       # 原始 TrainingRecord，只有 decision Choice
state = engine.step(state, "e2e4", controller="human")
```

前端通过 `POST /api/v1/sessions` 创建 `{"game":"chess","seed":0}`。对局步进仍用 `POST /api/v1/sessions/{id}/steps`，带当前 `revision`，以下三种选择互斥：

```json
{"revision":0,"action":"e2e4"}
```

```json
{"revision":0,"model_id":"my-connected-model"}
```

```json
{"revision":0,"reference":true}
```

UI 提供白黑双方的人类、当前模型、规则控制，默认不自动调用模型。棋盘起终点选择、升变、申和、翻转和按席位连玩都提交同一组后端动作。候选概率显示实际返回分布；来源区区分动作前规范决策上下文与支持最终动作的真实代表请求。非实时试玩保留原有三次选项顺序扰动机制；真实请求顺序和代表输入单独展示，不将其解释为训练行为概率。

响应附 `controller`、`forced`、`previous_decision` 和 `previous_input`。输入取自动作前快照；模型错误不改棋局。为兼容私有信息游戏，这些动作前字段在私有换座场景隐藏，公开 replay 不泄露先前玩家手牌或未揭晓选择，服务器内部审计仍保留完整记录。

## RL 与奖励

创建 rollout 时使用 `game=chess`、`side=0/1`、`mode=rule_engine/qwen3.8-max`。外部模型对手需要调用方配置 callback；规则对手无需模型调用。其余 ticket 身份与应答字段沿用 [标准在线训练接口](ROLLOUT.md)。

```json
{
  "episode_id": "chess-condition1-trial0",
  "game": "chess",
  "seed": 963700000,
  "mode": "rule_engine",
  "side": 0,
  "group_id": "chess-condition1",
  "trial": 0,
  "policy_version": "student-checkpoint",
  "request_token": "start-chess-condition1-trial0"
}
```

只有实际学生策略选择进入 PG trace。唯一合法动作是确定性执行 B，不调用模型、不伪造概率；对手动作独立记录；没有学生失败后规则代走。每个学生动作的 credit interval 延伸至下一次学生决策前，包含期间实际发生的对手与强制动作，最终一项覆盖真实终局。即时 `after_state` 与用于归因的 `credit_after_state` 分开保存。

终局胜 +1、负 −1、和 0、预算耗尽 −1。`config/chess-rewards.json` 明确沿用终局奖励，不给吃子、子力增长或规则建议额外分数。过程没有目标价值被近似估分替代。训练复用现有逐步回报、冻结状态基线、Choice formatter、mask 和损失模块。

正式加入新轮次须显式配置 `game/chess` 权重，并先用独立历史窗口的真实学生轨迹建立 Chess 状态基线。现有冻结 V 没有 Chess 覆盖时会拒绝更新；不能用当前组奖励拟合自身基线，也不能用测试 fixture 顶替学生轨迹。当前旧训练目录、checkpoint 和冻结计划均未修改，训练仍暂停。

训练 `play/verify` 要求 `student_model` 和完整真实行为分布。评测使用 `evaluation_model`，回执为 `evaluation_only=True`、`on_policy=False`、`reward_export_prohibited=True`；两类回放互相拒绝。评测完整保留双方事件及核心状态用于重建，终局由同一棋引擎裁定。

## 验证与复现

CPU 回归覆盖特殊规则、65 个可复现且不同的种子起点、全部合法候选、重复申和证书合并、非法动作拒绝、旧 `_moves` 归档兼容、前端/API 与评测回放、双方奖励归属。实际浏览器测试覆盖棋盘操作、四种升变、模型概率与输入、双席位、页面切换时的迟到响应和终局显示。

```bash
python -m pytest tests/test_chess_core.py tests/test_chess_sessions.py \
  tests/test_chess_legacy_showcase.py tests/test_chess_evaluation.py
python tests/chess_browser.py
python tests/chess_browser_boundaries.py
```

浏览器脚本只启本机服务，证据位置可用 `JEV_CHESS_TEST_OUT` 指定。另有 CuES/ProjectZ CPU 集成验证，使用真实 tokenizer、formatter、rollout ticket、训练样本和 padding/mask，检查行为分布不变及显式 `game/chess` 权重。这些均为明确标记的 fixture，不是模型棋力成绩；本次没有 GPU 更新、真实模型胜率或正式 RL 提升结论。

原内部棋状态保留 archived 路径，已有成绩不改写。公开部署按项目当前停机约定保持关闭；源码可按 README 在本机启动。
