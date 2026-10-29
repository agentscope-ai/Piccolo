# 前端实时游戏与全游戏回归

本文中的 `${RUN_DATA}` 表示评测产物的父目录，按当前机器的挂载位置设置。

## 修复行为

本次修复在 `dev_xinji` 的 `c6a5d76` 发布，后续补充了公网测试的同步夹具和原生游戏终局检查。

- **俄罗斯方块重力不可见**：界面只把 `tetris-realtime-v1` 分派给实时渲染器，当前 v4 仍进入旧的回合制画法，忽略实际下落坐标。实时界面、绘制和回放现在共用渲染器的版本支持检查，覆盖 v1–v4；插值只展示服务器回传运动，不推进物理。
- **马里奥“世界观测过长”**：原接口把完整观测限制为 24,000 字符，正常对局中的可见候选、近期动作和动态历史会超过限制。真实观测样例为 24,428 字符，旧接口返回 413。网页的观测与决策入口统一改为最多 256 KiB UTF-8，完整保留观测；未截掉候选或历史，也未改模型输入合同。
- **马里奥死亡后卡住**：终局消息反复触发停止连玩，停止操作又发布终局消息，形成循环。现在只在进入终局时停止；取消当前网页请求后立即恢复控件；旧请求完成时不能覆盖新局或释放新局的动作。iframe 状态消息携带局代次，重开后忽略旧局消息。HUD 与状态通知使用轻量快照，模型判断仍使用完整快照。
- **私有手牌交接时报错**：Goofspiel 连玩在交接后继续请求下一步，服务器因此返回“本局已结束”。连玩现在在 `handoff` 处暂停，保留主动揭牌流程；同一检查覆盖诈唬骰、Goofspiel 和 UNO。
- **重开后残留旧错误**：场景游戏重开时清空上一局的错误提示。

## 引擎评测同时运行

这些改动没有修改 Mario/Terraria 共享核心、原生游戏物理、动作、计分、种子或正式评测策略。网页接收完整观测的大小限制不在直接调用引擎的离线评测路径中。

`http://10.29.240.38:30000/v1/systemone` 的独立评测持续运行：前端实际 28 个可玩游戏，每游戏 8 个不同种子，共 224 局；对局和实际 HTTP 请求并发上限都是 2。前端回归使用浏览器内的标记测试模型，不访问该推理服务，不混入正式成功率结果。

正式产物：`${RUN_DATA}/systemone-30000-frontend-c2-20261021/`。

## 验证范围与复跑

- 67 项 Python 检查通过，含实际 HTTP 会话；14 项 Node 检查通过。
- `browser_all_games_stress.py`：28 游戏 × 桌面/手机，合计 56 个案例。每案例使用种子 42、43，检查多步模型操作或自然终局、限流后同局重试、错误后重开、连玩暂停、私有交接、导航保留和种子 44 重新开局。实时游戏每种子检查 3 次模型操作，其他游戏最多 8 次；自然终局会提前结束。这是前端交互回归，不是成功率评测。
- `browser_realtime_recovery.py`：桌面/手机共 16 项公网检查。包括模型连玩和在途推理时的重力、真实大观测、马里奥死亡/重开与迟到消息隔离；另通过真实人工控制让俄罗斯方块、贪吃蛇、赛车进入原生终局，再从网页重新开局。马里奥死亡夹具在测试请求实际进入模型后才恢复物理，以避免公网延迟导致“请求发出前已死亡”的测试竞态。
- `browser_game_surfaces.py`：Canvas、DOM、iframe 的桌面/手机导航检查 6 项通过。
- 公网首页及 7 个相关资源与发布快照逐字节一致，真实大观测的公开 API 返回 200 且观测完整。

在 PiccoloArena 根目录执行：

```bash
JEV_TEST_URL=http://127.0.0.1:59881 .venv/bin/python -m pytest tests/test_sessions.py tests/test_api.py tests/test_world_observation_size.py tests/test_interactive_recovery.py tests/test_systemone.py -q
node --test tests/tetris_renderer.test.cjs tests/game_errors.test.cjs tests/test_connections_transport.cjs
.venv/bin/python tests/browser_all_games_stress.py --url http://127.0.0.1:59881/ --output /tmp/frontend-stress
.venv/bin/python tests/browser_realtime_recovery.py --url http://127.0.0.1:59881/ --output /tmp/realtime-recovery
```

当前环境复用了旧工作区的 Python 虚拟环境；新检出安装依赖后可使用自身 `.venv`。公网网页测试使用 `--url https://decisionplayground.agentscope.io/ --allow-local-network`，在独立测试浏览器中明确允许本地网络访问，以连接回环地址的测试模型；不关闭浏览器安全检查。

所有验收记录、截图、部署回执及最终结果在 `${RUN_DATA}/playground-realtime-debug-20261021/`；完整矩阵的最终状态以 `all-games-stress-final/report.json` 为准。测试模型只从当次公开合法候选中选择，不使用隐藏状态、规则接管或回填成功结果。
