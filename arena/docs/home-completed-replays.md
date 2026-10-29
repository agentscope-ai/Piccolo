# Home 完整通关回放

Home 的游戏演示使用 `web/playground/data/home-decision.json`，由
`scripts/export_home_decision.py` 导出，`web/playground/home-demo.js` 播放。
四个版本各展示一局精选的成功对局：SFT、RL R6 iter19、GRPO N3 iter6、RL R9 iter31。
游戏覆盖 2048、推箱子、6×6 黑白棋和俄罗斯方块；每局都保留从评测初态到获胜终态的全部记录。
2048 使用引擎的短局目标 **128**，游戏名中会明确显示。

页面显示游戏、模型版本、种子和完成状态，支持逐步播放、进度拖动、倍速与直接查看结局。
黑白棋包含固定对手的落子；俄罗斯方块包含模型等待期间的下落、锁定和消行。
唯一合法动作、固定对手和机械执行区间均有明确标识，不计作模型决策。
这些是精选通关样例；总体表现请查看正式评测结果。

## 离线验证

在 `PiccoloArena` 根目录使用已安装项目依赖的 Python：

```bash
python scripts/export_home_decision.py --check
python -m unittest tests.test_home_decision -v
```

校验会通过仓库内的游戏引擎重放动作、核对每个候选和后继局面，并检查真实获胜与预算状态。
俄罗斯方块还会按原时钟记录重建动画帧。修改动作、方块或把预算耗尽标成成功都会被拒绝。
检查只需要仓库内的公共回放，不需要训练目录、模型服务或 API key。

## 更新数据

在四个 checkpoint 的 176 局评测全部完成后，准备一个仓库外的私有 JSON：

```json
{"run_id":"a-new-showcase","clips":[
  {"episode":"<完整原始 episode 的本地路径>","model_id":"<episode 中的精确 model>",
   "name":"Blink · RL iter19","checkpoint":"RL R6 / iter_0000019"}
]}
```

`clips` 需要四项，每个游戏和 checkpoint 各一项。导出命令：

```bash
python scripts/export_home_decision.py --selection <私有选择文件.json>
```

导出器检查来源评测完整、模型身份一致、自然终局获胜，并用现有引擎核对完整轨迹。
私有选择文件及原始轨迹留在评测目录；公开资产只包含播放所需的状态、动作、时钟、版本和种子。
更新回放不会修改 Arena 原始评测、Elo 结果或其他基准数据。

浏览器验收可运行：

```bash
python tests/browser_home_replays.py --url <运行中的网页地址> --out <截图和报告目录>
```

该检查覆盖桌面/手机、中英文、四局终态、拖动和重置、真实重力动画、快速切换、减少动态效果偏好，
并确认整个播放过程没有模型请求。
