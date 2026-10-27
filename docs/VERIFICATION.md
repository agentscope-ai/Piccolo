# Blink 验证记录

本文保留分次验证结果。验证均使用本机 `127.0.0.1` 服务，不调用真实模型；仓库同步不等于官网部署。

## 2026-10-27：完整动画、候选框与自有模型贪吃蛇通关

- 八个场景统一为左侧游戏、右侧候选动作与执行反馈；保留正文四行两列和无额外图注，导出的画面不含旧的顶部切换栏。
- 贪吃蛇改为自有 `formal-sft310-20261016-v5/policy-0` 的历史 student rollout（seed `1194410000`）：51 次决策、49 次移动、6 个苹果、胜利，`on_policy=true`、`rule_takeover_count=0`。初态、各次观测/到达/执行后状态和终态共 155 处公开状态与共享引擎逐项相等。没有采用外部基线或改写失败终局。
- 完整时间线覆盖 210 次记录转换。马里奥重建第 0–2083 个物理帧并严格核对边界；贪吃蛇保留全部 49 次身体移动；推箱子保留 14 次实际移动；Tetris 展开原始时钟帧。八张 GIF 共 2805 帧，已用 ffprobe 逐项核对编码帧数；所有步骤按原顺序输出，取消 24 个状态的均匀抽样。2× 播放并增加阅读停留，GIF 为 12 fps。
- `scripts/test_full_showcase.py`：4 项通过，覆盖拒绝失败/少食物/篡改身体的 Snake 记录、完整移动/物理帧覆盖、推箱子逐格路径与障碍、来源摘要和完整步骤。马里奥原严格回放检查与 Snake 离线检查均通过。
- `scripts/verify_showcase.py`：8 游戏 × 1440px / 390px 共 16 组通过。遍历每步候选及选中项，检查游戏画布完整显示、真实滑块到终态、重播像素还原、播放推进、无横向溢出。JS 异常和站外请求均为 0。导出时额外逐帧断言画布没有被裁切。
- 中英文 README 与 Blog 共 6 组排版检查通过：8 张 GIF 全部加载，无额外图注、无横向溢出。来源文件的本地路径/配置扫描、本地文档链接、语法和 diff 检查通过。发行检查覆盖 281 个 Arena 文件。

当前证据保存在 `var/full-showcase-check/` 和 `var/gallery-snake-check/`。下面保留旧版本的验证历史，其中失败 Snake 与 24 帧 GIF 已被本轮替换。

## 2026-10-27：替换贪吃蛇并移除重复图注

- 中英文 README 与 Blog 改为四行两列、8 张动图：五子棋换为贪吃蛇，正文不再显示黑白棋，所有图片外的游戏名称与图例均移除；画面内名称和图片 alt 文本保留。
- 三份文档 × 1440px / 390px 共 6 组检查通过：8 张 GIF 均加载、合集没有额外可见文字、无横向溢出。
- 贪吃蛇采用 SFT v9-a17 / seed 43 的历史记录：41 次调用与事件、39 个执行动作，吃到 3 个食物后碰撞结束。`scripts/export_snake_showcase.py --check` 对全部事件的输入、实时推进与后继状态复演通过；终局公开投影与原始终局相等。
- 原字段与公开导出逐项相等，原始文件摘要保留；仅生成新增贪吃蛇 GIF 与 PNG，24 个采样画面。渲染器新增 `--game`，可重建单项并保留其他素材清单。
- 贪吃蛇播放器在两个视口下通过实际拖动、末态、游戏像素变化与重播检查，无 JS 异常或站外请求。本地链接、Python 语法和 `git diff --check` 通过；发行检查 272 个 Arena 文件通过。

预览证据位于忽略目录 `var/gallery-snake-check/`。本轮只复核新增回放与文档排版，下面保留此前验证结果。

## 2026-10-27：动图合集与马里奥增补

- 中英文 README 与 Blog 各有同一组 9 张 GIF：马里奥横跨一行，其余八项双列排列；Blog 删除独立游戏介绍与开头重复动图。通过本机 Markdown 预览检查三份文档 × 1440px / 390px，共 6 组，图片均加载且无横向溢出。
- 完整 Showcase 的 4 张 GIF 已移除 `COMPLETED GAME`、序号箭头与游戏切换栏；捕获前断言两处导航不可见。原交互页面保留导航。归档动图也移除了通用标题徽标。
- 五子棋、Hex、点格棋从旧归档直接导出；七条旧 stream 共 193 步与原字段逐项相等。原始归档未修改。
- 马里奥选用 SFT v9-a17 / seed 44 的完整历史通关记录：12 次调用与执行事件、11 次动作执行、1 次敌人方向变化导致的回复拒绝。公开字段与原始文件相等；原始文件 SHA-256、时钟、地图版本和参与者随公开轨迹保留。
- `python scripts/export_mario_showcase.py --check` 通过：初态、每次观测、到达检查、后继与终态共 38 次严格状态比较，未放宽容差。该检查只运行共享引擎，不请求模型。
- 归档播放器 8 项 × 2 个视口，共 16 组通过：实际滑块跳到末态、游戏区域像素变化、重播、无横向溢出与错误；马里奥拒绝的动作显示 `Discarded action`。浏览器无 JS 异常、无站外请求。
- 重新导出 4 张完整 Showcase GIF（88 帧，含终局停留）和 8 张归档 GIF（137 个采样画面），各附 PNG 与采样清单。9 个不同游戏用于正文，其余历史素材继续保留。
- 本地 Markdown / HTML 链接、JS / Python 语法、`git diff --check` 通过。发行检查覆盖 271 个 Arena 文件并通过；马里奥公开文件未发现私有路径、服务地址或凭据字段。

本次使用 Python 3.12、Node.js 25.9.0、Playwright 1.63 与本机 Chrome。预览报告和截图保存在忽略目录 `var/gallery-check/`。这里只复核本次变更相关的素材、导出与播放器；下面较早的整页与全量测试记录保留各自原始范围。

## 2026-10-27：完整 Showcase 与文档更新

- 完整归档与 JevArena 来源提交中的文件逐字节相等，SHA-256 为 `75895e17ec9c1bda1309d9b1a865f3a7c577c176ef16eb0e32363bf957570ad2`。
- `arena/scripts/export_home_decision.py --check`：4 局、4 个 checkpoint、116 次转换的动作、终局与时钟校验通过。
- `python -m unittest tests.test_home_decision -v`：4 项通过，包括拒绝改动方块/动作、拒绝把预算耗尽标为获胜、区分模型与自动步骤。
- 新独立播放器：1440px / 390px × 中英文 × 4 游戏，共 16 组通过；无 JS 异常、无横向溢出、无模型请求。终局、准确拖动、重置、Tetris 重力、快速切换、键盘、滑动和减少动态效果检查通过。
- Arena 内嵌播放器：相同 16 组检查通过，另验证切换页面标签后暂停播放；两个入口合计 32 组，模型请求数为 0。
- 旧整页回归：桌面/手机 × 中英文的 3 个标签与 5 个榜单、8 组早期 Showcase，以及榜单中的原始归档回放通过，无 JS 异常。
- 新素材：从交互播放器生成 4 张 GIF、4 张终局 PNG；76 个不同采样状态，含终局停留共 88 帧。记录见 `assets/showcase/completed/render-manifest.json`。
- 修复迁入播放器的进度条读取顺序：暂停刷新控件前保存目标位置；新增断言检查实际步号与拖到终局。补齐 Tetris v1–v4 的渲染识别和按记录时间插值。
- 中英文 README、Blog、来源说明及占位 README 的本地 Markdown 链接检查通过；JS / Python 语法与 `git diff --check` 通过。
- 发行范围检查通过：267 个 Arena 文件，私密内容规则未发现匹配。

本次使用 Python 3.12、Playwright 1.63、本机 Chrome；服务依赖使用仓库要求的 FastAPI、Uvicorn、HTTPX、Pydantic、python-chess 与 OpenSpiel 版本，未安装或验证本次未用到的 TextArena / RLCard 插件。报告和截图保存在忽略目录 `var/completed-replay-check/`、`var/verification/`。

本次没有重跑完整 Arena 测试，也没有验证新模型、训练或公开部署。下文全量测试的历史失败记录仍然有效。

## 2026-10-26：初始迁入验证

以下是初次整理时的本机检查，不代表本次重跑结果。

## 此次通过的检查

| 范围 | 结果 |
| --- | --- |
| 品牌与页面 | 桌面 1440px、手机 390px × 中英文；每组检查 3 个主标签与 5 个榜单，无 JavaScript 异常或页面横向溢出 |
| Showcase | 4 个游戏 × 2 个视口，共 8 组；初态、终态、滑块跳转、重播通过 |
| 原对局回放 | 从 Blink Arena 榜单展开比赛记录、打开归档回放通过 |
| 数据一致性 | 132 场对局、45 条复用 episode 的 JSON 解析结果与迁入前完全相等；4 条展示 stream 与归档对应字段完全相等 |
| README 素材 | 原有渲染器生成 4 张 GIF 和 4 张封面；74 个采样画面，保留真实终局结果 |
| 浏览器模型传输 | `node --test arena/tests/test_connections_transport.cjs`，8 项通过 |
| 安全审批客户端与下载助手 | `python -m pytest -q tests/test_safety_review.py`，24 项通过；使用本机假服务和下载替身，不下载真实权重 |
| Skill 格式 | skill-creator 的 `quick_validate.py` 通过 |
| QwenPaw 附加检查器 | 使用本地 QwenPaw 实际 BaseToolGuardian 与 GuardFinding 类隔离检查 4 种行为：allow、ask_user、deny、缺少授权上下文 |
| 源码发行检查 | `arena/scripts/build_release.py --check-only` 通过；源码私密内容规则未发现匹配，单文件最大约 32.42 MiB，全部浏览器 JS 语法检查通过 |

新增浏览器检查可通过 `python scripts/verify_frontend.py --server-python arena/.venv/bin/python` 复现。执行脚本的 Python 需安装 Playwright，服务端 Python 需安装 Arena 依赖。此次复用原应用已有依赖环境，实际导入和服务源码来自新的 `arena/`。

本地浏览器报告、截图及 Python 测试输出位于忽略的 `var/verification/`，不纳入发行文件。

## 完整 Arena 测试的历史失败

`python -m pytest -q`：**161 passed、8 failed、28 skipped**。28 项跳过需要显式设置独立服务地址 `JEV_TEST_URL`，本次未运行这些在线会话测试。

下列 8 项失败已在原 JevArena 源码上对照复现。它们来自旧测试对当前游戏集合或榜单投影的假设；此次没有为通过旧断言重新启用已移除游戏或改变成绩。

- `test_api.py::test_board_standard_start_and_explicit_seed_remain_distinct`：`gomoku_19x19`、`othello_8x8` 两项。
- `test_chess_legacy_showcase.py::test_old_private_agent_handoff_and_redaction_survive[goofspiel]`。
- `test_leaderboard_directory.py::test_one_directory_serves_benchmarks_arena_and_replays`：过滤后的游戏范围与原全量成绩比较。
- `test_selected_games.py::test_no_additional_collected_games_are_registered`：旧数量断言。
- `test_selected_games.py::test_go_reaches_native_terminal_through_both_seats`。
- `test_selected_games.py::test_frontend_full_episode_evaluator_scores_selected_games`：包含已移除围棋。
- `test_sessions.py::test_current_games_include_eight_selected_games`：旧集合断言。

不能将本次验证描述为“完整测试全绿”。

## 尚未验证或提供的能力

- 模型未定：没有权重下载实测、模型推理/训练实现、真实审批能力评测或自动放行阈值。
- QwenPaw 全应用导入受当前环境缺少 `agentscope_runtime` 等完整依赖限制。上述隔离接口检查不等于宿主服务端到端验收；未安装/启用检查器，也未修改 QwenPaw 配置。
- Skill 导入与宿主工具审查注册是两个步骤；当前适配器把 ask_user / deny 交给已有人工审批，不能声称实现不可覆盖的硬拒绝。
- Docker 镜像、容器运行与公开域名部署未实测。
- 项目级许可证、正式模型权重许可和模型卡需在发布前确定；保留已有第三方来源声明。
