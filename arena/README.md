# Blink Arena

Blink 的交互与评测组件。访问 [Decision 官网](https://decisionplayground.agentscope.io/)，或按下文在本机运行。模型发布仍在准备中，随附榜单和轨迹属于历史实验。

新版完整对局 Showcase 已接入 Blog 页签，也可打开 `/completed-showcase.html` 独立查看：2048（目标 128）、推箱子、6×6 黑白棋和俄罗斯方块，支持逐步播放、拖动与终局查看。来源与离线验证见 [轨迹说明](../docs/SHOWCASE.md)，项目介绍见 [Blog](../docs/blog.md)。早期回放继续保留在 `/showcase.html`。

这里包含游戏试玩、Blink Arena 天梯、Benchmark Leaderboard 和 MBTI。前端、HTTP 服务和共享游戏引擎一起交付；模型服务在页面里填写，启动时不需要 checkpoint、模型地址或模型密钥。

验证范围见 [发布检查记录](docs/RELEASE_CHECK.md)。Docker 容器构建与真实域名 HTTPS 尚未实测。训练数据审计与 loss 看板不在本仓库范围内。

页面页脚提供 **Source & credits / 来源与致谢**，列出采用的前端代码、玩法参考、规则库及字体的上游链接。详细记录见 [来源与第三方组件](docs/THIRD_PARTY.md)，不同组件保留各自的许可说明。

新增西洋跳棋、9×9围棋、中国象棋、猜数字、扫雷、数独和UNO，前端与RL共享原生引擎、席位隐私及精确回放。规则、奖励和验证边界见 [七个游戏接入说明](docs/SELECTED_GAMES.md)。

国际象棋已接入同一前端和 RL 后端：完整合法着法、种子开局、双席位控制、候选后果和精确回放，决策组织参考 StartLux。见 [国际象棋接入说明](docs/CHESS.md)。

## 启动

需要 Python 3.12 和 Node.js 22。当前内置游戏的 RL 和服务端会话不需要 Chromium；浏览器回归及旧 browser 插件才需要它。首次安装 Python 依赖需要联网；前端字体、游戏素材、默认配置和已导入的成绩文件随源码提供。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
node --version  # 应为 v22.x；也可设置 JEV_NODE_EXECUTABLE 指向 Node 22
bash scripts/run.sh
```

打开 <http://127.0.0.1:8080/>。需要运行浏览器回归时，另执行 `.venv/bin/python -m playwright install --with-deps chromium`；Linux 的系统库安装可能需要管理员权限。Docker 配置已包含 Node 22。

```bash
docker compose up --build -d
```

固定域名、子路径、持久化和迁移见 [部署文档](docs/DEPLOYMENT.md)。此仓库按完整源码目录或 Docker 镜像分发；源码安装使用 `pip install -e .`，让服务可以找到相邻的静态资产。

本地和固定域名部署均可直接打开页面；如需限制网站访问，可另行启用可选登录配置，见部署文档。

## 连接模型

在页面的模型连接设置中填写显示名称、服务返回的模型名、完整请求 URL 和密钥，然后选择接口格式。模型请求统一由浏览器直接发送到所填模型服务。

| 接口 | 服务需要实现的内容 |
| --- | --- |
| 结构化决策接口 | 接受 `jev.decision.v1` 请求，返回合法选项 ID，可选返回完整概率分布 |
| OpenAI 兼容接口 | 接受 Chat Completions 请求，返回 `choices[0].message.content` 中的 `{"action":"选项 ID"}` |

端点与密钥只在浏览器内存中；密钥只发给填写的模型服务，不发送给 Arena 后端。模型接口须使用与游戏页面不同的 origin，并允许页面来源的 CORS 请求；HTTPS 页面应连接可用的 HTTPS 模型接口。评测期间保持连接页面打开，关闭或刷新页面后需要重新填写连接。

模型密钥不写入配置文件、榜单、浏览器持久存储或评测结果。模型显示名称可以自由取名，服务返回的模型身份必须和配置的 `served_model` 精确一致。接口字段和响应例子见 [API 文档](docs/API.md)。

## 组件与数据流

```text
web/                         游戏、榜单、MBTI、模型连接界面
  │ HTTP /api/v1/*
blink_arena/                   会话、决策队列、Arena、成绩读写
  │ 共享规则与观测合同
blink_arena/engines/           游戏规则、种子、候选动作、观测与终局计分
  └─ RL 调用共享 registry / environment；不经过网页点击

config/                      游戏范围、提示、服务运行参数
leaderboard/                 统一榜单 JSON 与随附回放，可直接更新
data/seed/                   最小公共目录元信息
var/                        运行中产生的评测记录，默认不入 Git
```

前端通过版本化 HTTP 接口操作，浏览器从后端领取决策任务并直接调用模型，再交回结构化结果；模型只获得引擎生成的公开观测与合法候选。Mario 与 Terraria 的物理、规则和意图执行位于无 DOM 的 `*-core.js`：网页适配器负责绘制/输入，服务端会话、Arena 和 RL 使用 Node 直接运行同一核心，无需加载 HTML、字体或浏览器。标准 HTTP 合同见 [API 文档](docs/API.md)。

RL 可通过 `/api/v1/rollouts` 请求完整对局，或通过 `blink_arena.engine` 直接复用规则。在线接口提供决策 ticket、实际执行反馈、奖励结算、有界缓存及重启恢复，见 [在线训练接口](docs/ROLLOUT.md)；时钟合同与插件注册见 [共享引擎文档](docs/ENGINE.md)。训练框架、策略模型和 checkpoint 管理由调用方负责。

## 排行榜与评测

Benchmark 榜单通过 `jev.leaderboard.v1` JSON 导入：JevBench、DecisionIndex、HarnessJevBench、DataJevBench 分别维护，分数范围、ACC/Brier/ECE、双语雷达轴和模型名称随数据文件明确给出。没有概率数据时应保留空值，不能用生成文本中的自报置信度补造 Brier/ECE。

同一合同也支持 `benchmark_id: "arena"` 的综合 / 分游戏 Elo 快照。导入榜供只读展示，不含原始对局回放，不参与新对战计分；已有本地评测任务的展示优先于导入榜。

本地运维可直接导入已准备的完整 JSON，无需启动服务或填写 Web 管理令牌：

```bash
.venv/bin/python scripts/import_leaderboard.py results.json
# 指定其他目录时，服务也应设置同一个 JEV_LEADERBOARD_DIR。
.venv/bin/python scripts/import_leaderboard.py results.json --leaderboard-dir ./leaderboard
```

Arena 使用共享游戏引擎：可双人对战的游戏直接对局，单人游戏比较同游戏、同种子的终局结果，展示综合与分游戏 Elo。评测请求显式指定模型、游戏、种子和并发；结果保存在运行目录中。导入的历史结果只负责展示，不会在启动时自动补跑模型。

榜单文件统一从根目录 `leaderboard/` 读取，部署时可用 `JEV_LEADERBOARD_DIR` 改位置。文件约定与更新方法见 [榜单数据目录](docs/LEADERBOARD_DATA.md)。

## 开发与验证

```bash
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

新客户端使用 `/api/v1/*`，机器可读合同为 `/api/openapi.json`。旧页面的 `/api/*` 兼容路由保留用于迁移。修改共享规则时同时验证试玩、Arena 与 RL 的动作、种子、终局及时间计分合同。
