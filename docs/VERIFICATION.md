# Blink 验证记录

验证日期：2026-10-26。仅启动临时 `127.0.0.1` 服务，检查完成后关闭。未调用真实模型、使用 GPU、公开部署或推送远端。

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
