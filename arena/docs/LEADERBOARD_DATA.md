# 统一榜单数据目录

正式前端的已发布成绩统一从仓库根目录 `leaderboard/` 读取。该目录随仓库、容器镜像和源码包分发，不依赖旧机器的训练目录或运行日志。

```text
leaderboard/
├── jevbench.json
├── decisionindex.json
├── harnessjevbench.json
├── datajevbench.json
├── arena.json
├── arena-replays.json
├── arena-ratings.json   # 可选：通过标准接口导入的 Arena ratings
└── history/             # 导入时保留旧版本；不提交到 Git
```

当前文件保存已发布的真实成绩；具体模型数、覆盖及赛程以文件内容为准。更新显示名或过滤旧 checkpoint 前必须归档原件，不能修改已结算指标、模型身份、比赛或真实回放。

## 配置与读取

默认位置为当前仓库的 `leaderboard/`。设置 `JEV_LEADERBOARD_DIR` 可以指向另一个完整榜单目录；Python 集成可用 `create_app(leaderboard_dir=...)` 显式指定。优先级为显式参数、环境变量、仓库默认目录。

`JEV_DATA_DIR` 只管理临时会话和评测运行产物，不再决定公开榜单目录。旧的 `data/seed/leaderboards/` 和 `var/leaderboards/` 不作为隐藏回退源，避免更新后继续显示另一个位置的旧版本。正在运行或已完成的本机 Arena 任务仍按评测接口提供状态；随包发布的历史榜单和回放来自统一目录。

三个 benchmark 的标准 JSON 由 `/api/v1/leaderboards/{benchmark}` 读取，页面投影由 `/api/leaderboard` 读取；Arena 与历史回放分别由 `/api/elo` 和 `/playground/visible-control.js` 读取。后端每次请求读取当前文件，完整原子替换后无需重启即可更新已发布数据。

## 更新 benchmark 成绩

准备符合 `jev.leaderboard.v1` 的完整 JSON，包含公开模型 ID、显示名称、指标以及雷达轴的 `label_en` / `label_zh`。导入会先验证合同，再保存旧版到同目录 `history/`，最后原子替换对应文件。

```bash
python scripts/import_leaderboard.py /path/to/new-results.json
python scripts/import_leaderboard.py /path/to/new-results.json --leaderboard-dir ./leaderboard
```

前端上传或标准 PUT 接口同样写入这个目录；管理员鉴权要求保持不变。只更新公开成绩，不需要模型服务。

`benchmark_id="arena"` 的标准导入文件保存为 `arena-ratings.json`。该格式与包含赛程、稳定性和最近对局的原生 `arena.json` 快照不同，因此使用独立文件名；导入 ratings 不覆盖原生快照或回放。存在 ratings 导入时优先展示该导入榜。

## 可选模型 Logo

各 benchmark 的 `rows` 条目支持可选 `logo` 字段。例如：

```json
{
  "model_id": "qwen3.8-27b-base",
  "model_name": "Qwen3.8 27B",
  "logo": "./playground/logos/qwen.png",
  "score": 0.85
}
```

上例得分仅示意格式，不是已登记成绩。将自己的图片放入 `web/playground/logos/`，使用相对页面的路径；也支持公开 HTTP(S) 图片 URL。本地资源会随独立包发布，推荐使用相对路径以适配 DSW 路径前缀。字段省略、设为 `null` 或空字符串时只显示模型名；图片加载失败也回退为纯文字。图例、模型选择器、柱状图及成绩表使用同一字段，图标大小为 20–25 px，柱图中的图标与模型名位于色条内部。

原生 `arena.json` 可在 `overall`、`by_game` 对应模型条目中填写 `logo`；标准 `arena-ratings.json` 导入也支持同一字段。品牌不按模型名称自动推断。JevBench、DecisionIndex、HarnessJevBench 和原生 Arena 已按明确模型 ID 配置可确认的图标；第三方图标来自官网，来源记录在 `web/playground/logos/README.md`；成绩、模型 ID 和原始来源保持不变。

检查线上图标时，先核对运行实例实际的 `JEV_LEADERBOARD_DIR`，再检查该实例 API 返回的 `logo` 和图片请求。只修改仓库默认 JSON 不会更新指定了外部榜单目录的实例。Qwen3.8 Max、Qwen3.6 使用 Qwen 图标，仍以明确模型 ID 登记；补充图标前归档原文件，只更新显示元数据。

## 更新原生 Arena 与回放

`arena.json` 和 `arena-replays.json` 应来自同一评测轮次；不要将不同 `run_id` 的结果拼在一起。保留原生比赛身份、协议、种子及真实结算数值。回放中缺少实际画面快照的记录保留缺帧标记，不能用摘要补成虚构动画。

只读导出已有公开成绩：

```bash
python scripts/export_public_results.py --api-root https://example.com/api --leaderboard-dir ./leaderboard
python scripts/export_public_results.py --check --leaderboard-dir ./leaderboard
```

导出脚本只读取成绩 API，不运行模型或补测。独立回放文件由评测归档导出；如果目标目录已有回放，脚本会检查其轮次、赛程身份和结算结果是否与 Arena 快照一致。`--output` 是 `--leaderboard-dir` 的兼容别名。

## 部署与校验

容器部署可挂载 `./leaderboard:/app/leaderboard`，目录需对容器运行用户可读，使用上传或 CLI 导入时还需可写。完整移动仓库时一并移动 `leaderboard/`；不要提交密钥、服务地址、内部 checkpoint 路径或模型请求报文。

```bash
python scripts/export_public_results.py --check
python -m pytest tests/test_leaderboard_directory.py tests/test_import_leaderboard_cli.py -q
```

目录回归覆盖三个 benchmark、Arena 与完整回放同源读取、环境变量覆盖、外部更新即时读取、ratings 导入不覆盖原生数据，以及不再读取旧目录的行为。

## 当前自有 checkpoint 保留名单

后续导入和刷新公开表时，`jev27b-` 前缀的自有 checkpoint 仅保留以下三个精确 ID；其他外部参照模型（例如 `access-`、原版 base）不受此名单影响。显示名称不能用于身份匹配。

| 精确模型 ID | 统一显示名 |
| --- | --- |
| `oneshot27b-control-reviewed-sft-iter310` | Blink 27B SFT-1015 |
| `oneshot27b-gameplay-terminal-rl4` | Blink 27B RL-1012 |
| `oneshot27b-game-rl-native-iter17` | Blink 27B RL-1019-iter17 |

每次更新先归档完整旧表，再按名单整理公开行并统一显示名；原始评测和精确模型路径绑定保存在评测产物中，不复制到公共榜单。这里是数据维护约定，接口不会自动替操作者过滤导入文件。

DecisionIndex full 与 quick 必须分开。仓库 `decisionindex.json` 继续保留 0.3 全量公开集口径；`decisionindex-quick.json` 保存 `0.3-quick-20261014` 的 3,818 records / 7,809 subquestions 同协议成绩。部署可将 quick 文件作为其独立榜单目录中的 `decisionindex.json`；便携发布包默认使用 quick，并将全量表另存 `decisionindex-full.json`，不得混入同一表。RL-1012 quick 来自已完成的历史原生评测，按精确身份和版本核验后复用官方得分；ACC、Brier、ECE 由该次真实分布计算，本次未重测。

当前 Blink Arena 为同一引擎、seed 42 的五模型共同锚点快速对照：保留 SFT-1015 与 RL-1019-iter17 的原 33 场结果，新增 Qwen3.8 27B、Qwen3.8 Max、Qwen3.6 35B-A3B 三个 DashScope API 参照对 SFT-1015 的 99 场，合计 21 游戏、132 场。协议标记为 `common-anchor-star-v1`；各挑战者 33 场、1 个对手，SFT 锚点 132 场、4 个对手，直接对战均交换席位。原始结算不改，新榜按完整登记赛程重新计算 Elo；旧表先归档。这是单种子快速检查，不能当作多独立条件的正式能力结论。

API 模型与本地 checkpoint 分开登记；各服务的真实时延保留在实时游戏时钟中，不能把响应速度差异当作训练收益。公开 `snapshot.control_audit` 单列可证实的规则接管 C 次数、审计缺失及目标完成数；接管次数只是有记录的下界，缺失不能记成零，自然目标完成与辅助完成分开。RL-1012 未参与该同引擎队列，因此不拼入其旧引擎成绩。完整 132 场回放与 45 个独立环境记录同属新 `run_id`，原始缺帧标记保留，不补造画面。


### DecisionIndex API 参照与历史失败

当前 quick 表也可展示已授权的 DashScope API 参照，模型 ID 使用 `dashscope-` 前缀，显示名显式包含 API 和 top-k 估计；与本地同名模型分开，不能视为同一个 checkpoint。当前已复用 Qwen3.8 Max 和 Qwen3.6 35B-A3B 的完整历史 quick 结果，本次没有新增 API 调用。

API 协议为 `native-naive-empty-prefix-v1+dashscope-first-token-top5-v1+candidate-topk-estimate-v1`。截断候选缺失量按独立估计协议置零后归一化；真实返回与估计分别保存。两项最终均覆盖 3,818 records / 7,809 subquestions，计分零错误；Max 136 子题和 35B-A3B 5 子题依赖这一显式估计。真实完整候选概率分别只有 3,946 和 6,014 子题；其余还包含仅 argmax 可证明的硬答案。完整计分覆盖不能当作完整概率观测，校准指标包含单列的估计分布数。

Max 的 quick 指数从原始 53.17、失败补测后 53.66 到估计版 59.06，35B-A3B 从 35.46、42.71 到 42.98，来自故障与概率覆盖修复，不是模型训练改善。strict 重试后仍有 Max 67 条、35B-A3B 3 条记录因部分子题概率不足而整条无法计分；旧缺失始终保留在完整分母中。历史错误、strict 原件与估计代际均保留，不以最终零错误抹去早期失败。

这些结果一直是 quick 子集。另一个 140,620 请求的 full-public 表有自己的 pending/error/complete 状态，不代表所有参照模型都已完整测完；不能用 full 的某个模型得分补 quick 缺行。

## 图表展示与交互

- 图表默认打开 JevBench，并选中当前榜单的全部模型，不设六个默认项或十个比较上限，也不显示图表选择数量。缺失总分保留为 `—`，缺失雷达维度保留断线，不补零。
- 模型选择器支持搜索、逐项勾选、全选、清空、仅显示一个及恢复默认全选。手动选择按榜单在当前页面会话内保留；新加入的模型默认选中。所有已导入模型仍保留在成绩表中。
- 成绩表移除 Errors / Record 两列，Arena 同步移除独立失败列；错误数、来源、模型 ID 和原始记录继续保存在 JSON 与 API 中，计分分母不变。自有模型统一显示为 Blink，旧模型 ID 继续使用。
- 柱图从高到低排列，logo 与模型名在色条内，右侧显示分数，不显示排名序号。短柱中的名称截断后可悬停或键盘聚焦查看全名。没有得分时保留 `—`，真实零分不显示正长度的色条。
- 柱图同时作为雷达图图例：悬停、聚焦可突出对应曲线，点击或 Enter 可固定，再次点击或 Escape 可解除。只有点击雷达维度或修改下拉菜单才切换比较指标，鼠标路过不会改掉正在看的指标。
- 模型采用固定的橙、蓝、青绿、紫等点缀色，同一模型跨榜单及排序保持同色；雷达线条提高对比度、填充保持轻量，不为 Blink 单独加深背景。所有图表、数据和控件采用本地 Inter 字体及统一中文无衬线回退。维度名称使用统一双语表；模型名称和模型 ID 不做词语替换翻译。
- 页面使用低饱和雾蓝、深青灰和浅色像素网格。陶土橙 `#B96E50` 集中用于选中下划线、重点标记和粒子亮点。主标题为 34 px（手机 30 px），正文及数据为 13–14 px，次级文字约 11–12 px；中文标题单独处理字距，避免直接沿用英文的紧字距。
- 装饰由 `leaderboard-effects.js` 独立提供。背景网络为桌面 42 / 手机 22 个节点，约 30 fps；鼠标尾迹粒子最多 36 个，尾迹限频 85 ms，仅限页头、导航和标题区。画布、输入框和游戏操作区不产生尾迹，后台暂停。
- 首次品牌使用逐字遮罩；Blog 的整块可见内容采用颗粒聚合，包括文章标题、摘要、已展开正文和装饰图块。Leaderboard 和 Playground 的可见文字也随页面整体切换，不局限于标题。切换页面时捕获旧内容的真实文字轮廓，让其顺风飘落消散；新内容再聚合显现。导航文字始终清晰，玻璃滑块保留掠光及少量顺向粒子。文字布局、可访问名称及按钮点击范围始终保留。整块内容最多 1800 / 手机 1000 颗粒，小标题最多 600 / 手机 360 颗粒，同时最多 4 项，动画约 820–880 ms；结束后停止沙化画布绘制。快速切换、滚动、缩放、语言变化和后台切换都清理动画并恢复文字。系统开启“减少动态效果”时直接显示静态内容。按钮裂开效果已移除。

这些变化不修改 benchmark 得分、样本分母、模型身份或评分协议，也不会触发模型请求。


## Blink 页面与更新时间

自有模型 ID 统一使用 `oneshot27b-…`；附件中自有模型使用 `oneshot-w22m05r02-v5best-avg50`，第三方模型 ID 保留原值。公开榜单和回放的参与者、席位、胜者、episode 标识及字典索引按同一映射迁移，来源 API 使用新 ID。该迁移不变更 checkpoint 精确路径、计分协议参数或任何评测数值，历史原件单独留存。

- 顶部顺序为 Blog、Leaderboard、Playground，首页打开 Blog；游戏在进入 Playground 后初始化。品牌为 Blink，副标题为“决策智能研究 / Decision Intelligence”。
- `site-theme.css` 统一浅色像素背景、卡片、控件、天梯与游戏外围界面。Blog 正文与全站统一字体，使用适合长文的行高和宽度，技术笔记内容来自实际环境接口与计分合同，不展示未完成实验的成绩。
- 顶部主导航采用液态玻璃滑块，benchmark 导航采用细线指示。按钮保持固定尺寸，指示层平移（主导航 360 ms、榜单 280 ms），内容使用 200 ms 透明度过渡，页面内容沙化使用独立装饰层，导航文字保持清晰，布局不改变几何尺寸。支持方向键、Home/End、可中断切换和系统减少动态效果；模型连接区位于 Playground 内容区，不再推动公共导航。
- Blink Arena 页面仅从后端读取榜单、进度及回放，移除当前模型、加入评测、暂停和恢复控件。评测管理继续由后端接口承担。
- 所有 benchmark 使用等宽的雷达/柱图两列、相同的雷达画布（820 × 780）、中心和半径，桌面图表高度统一为420 px；模型较多时柱图区内部滚动，避免数量改变卡片尺寸。Harness 保留全部具名维度，上下拥挤处使用引线。手机端所有榜单图表统一为495 px高，雷达使用相同的520 px宽画布，可横向滑动，避免把标签缩到不可读。模型选择器为浮层，不挤动图表；点击外部或 Escape 关闭。窄屏表格固定模型列，首项分数直接可见，其余指标横向滚动。
- `/api/leaderboard` 每个 benchmark 的 `updated_at` 使用对应 JSON 的实际文件 mtime，`source_file` 标明文件名；缺少文件时不伪造时间。三个标准榜单从同一打开的文件读取数据与时间。Blink Arena 使用 `arena.json`，有标准 ratings 导入时使用 `arena-ratings.json`。页面切换榜单时同步切换时间；刷新不会更新数据时间。
- 源码包保留文件的秒级 mtime，因此解包不会将榜单时间重置为 1970 年。JSON 内模型评测时间、真实成绩和历史归档保持原样。


## 用户提供的四份结果（2026-10-20）

当前 JevBench 1.2、DecisionIndex 0.3、HarnessJevBench V0.4 和新增 DataJevBench V0.5 均采用用户提供的完整13模型快照，覆盖旧公开表的对应版本。精确模型ID、显示名、得分、轴值、样本数、状态与原协议保留；不套用历史 checkpoint 保留名单筛掉附件中的模型。原表在导入前归档。

DecisionIndex 有6项可用得分及7项缺失，缺失保留为空；公开化仅脱敏5条来源备注中的私有路径，未修改指标。Harness 的 Hard主分使用原生 `score`，Task ACC 优先显示附件的 `strict_task_accuracy`，不把任务均分冒充整任务准确率；缺失Brier/ECE继续为空。DataJevBench 使用独立API、6个原始子集轴以及ACC/Brier/ECE展示。

Blink Arena的原生成绩、导入ratings和回放文件不随本次更新变动。此次仅展示现成结果，不运行新的模型评测。
