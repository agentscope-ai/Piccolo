# Blink 验证记录

本文保留分次验证结果。验证均使用本机 `127.0.0.1` 服务，不调用真实模型；仓库同步不等于官网部署。

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
