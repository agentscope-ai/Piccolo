# 统一榜单数据目录

正式前端的已发布成绩统一从仓库根目录 `leaderboard/` 读取。该目录随仓库、容器镜像和源码包分发，不依赖旧机器的训练目录或运行日志。

## 2026-10-29 本地待审阅快照

四个 Benchmark 当前使用 2026-10-28 评测汇总，统一保留 11 个模型：Piccolo-27B、Piccolo-9B、Piccolo-4B，加上原九个外部模型去掉 StartLux 后的八个。五个新增 P0 模型不进入此次网站名单。quick 子集和在线模型连接保持各自原有数据。

Piccolo 是三个 Blink-1028 checkpoint 的新显示名。公开模型 ID 继续使用 `blink-27b-1028`、`blink-9b-1028`、`blink-4b-1028`，以保留与已评测权重的身份绑定；不复用旧 OneShot 权重的 ID、分数或维度。

- Harness Hard 使用同轮 295 任务 / 303 问题，雷达轴从该轮逐题结果重新汇总。Luna 使用结构化 instructions 序列化后的完整 Hard 重跑结果；其旧 Soft 仍只有 46/60 有效，正式 Soft 指标保留为空，诊断值单列。
- DataJevBench 使用历史原生链路的 500 条记录，统一以概率和容差 `1e-3` 重评分，不归一化原始概率；无效记录仍保留在分母中。校准分布不完整时不发布完整集 Brier/ECE。
- JevBench Public 使用历史原生链路的 231 题；维度、校准与总分来自同轮评分文件。JEV 1.14 的三条归一化沿用原 Public 规则，与 Data 的概率校验规则分开。
- Decision Index 仅使用文本 Public。三个 Piccolo 复用训练侧已存的 140,178 请求结果；另外四个有效模型使用官方 Public 快照。其余四个模型没有找到公开成绩，分数与维度保留为空。官方逐请求错误数未知时，`errors` 允许为 `null`，不伪装成零错误。
- 表格默认将 Piccolo-27B 放在首行，并明确说明是置顶展示。名次仍按真实主分计算，并列采用竞赛排名；Harness 中 Piccolo-27B 为第 2、d3 为第 1。点击表头进入正常数值排序，缺失值始终排在末尾。柱图继续按实际数值排序。
- HarnessJevBench 首页卡片、比较面板与榜单介绍移除未发布提示，不额外添加发布徽标；项目地址为 `https://github.com/agentscope-ai/HarnessJevBench`。DataJevBench 的公开项目地址为 `https://github.com/datajuicer/DataJevBench`。

随本仓库提供的数据与页面可在本地预览。可运行 `python scripts/preview_leaderboard.py --port 18086` 预览静态页面和真实 Benchmark API；该轻量预览不启动模型服务或游戏引擎。

```text
leaderboard/
├── jevbench.json
├── decisionindex.json
├── harnessjevbench.json
├── datajevbench.json
```

当前文件保存已发布的真实成绩；具体模型数、覆盖及赛程以文件内容为准。更新显示名或过滤旧 checkpoint 前必须归档原件，不能修改已结算指标、模型身份、比赛或真实回放。

## 配置与读取

默认位置为当前仓库的 `leaderboard/`。设置 `JEV_LEADERBOARD_DIR` 可以指向另一个完整榜单目录；Python 集成可用 `create_app(leaderboard_dir=...)` 显式指定。优先级为显式参数、环境变量、仓库默认目录。

`JEV_DATA_DIR` 只管理临时会话和评测运行产物，不再决定公开榜单目录。旧的 `data/seed/leaderboards/` 和 `var/leaderboards/` 不作为隐藏回退源，避免更新后继续显示另一个位置的旧版本。

四个 benchmark 的标准 JSON 由 `/api/v1/leaderboards/{benchmark}` 读取，页面投影由 `/api/leaderboard` 读取。后端每次请求读取当前文件，完整原子替换后无需重启即可更新已发布数据。

## 更新 benchmark 成绩

准备符合 `jev.leaderboard.v1` 的完整 JSON，包含公开模型 ID、显示名称、指标以及雷达轴的 `label_en` / `label_zh`。导入会先验证合同，再保存旧版到同目录 `history/`，最后原子替换对应文件。

```bash
python scripts/import_leaderboard.py /path/to/new-results.json
python scripts/import_leaderboard.py /path/to/new-results.json --leaderboard-dir ./leaderboard
```

前端上传或标准 PUT 接口同样写入这个目录；管理员鉴权要求保持不变。只更新公开成绩，不需要模型服务。


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

品牌不按模型名称自动推断。图标来源记录在 `web/playground/logos/README.md`；成绩、模型 ID 和原始来源保持不变。

检查线上图标时，先核对运行实例实际的 `JEV_LEADERBOARD_DIR`，再检查该实例 API 返回的 `logo` 和图片请求。只修改仓库默认 JSON 不会更新指定了外部榜单目录的实例。Qwen3.8 Max、Qwen3.6 使用 Qwen 图标，仍以明确模型 ID 登记；补充图标前归档原文件，只更新显示元数据。


## 首页精选回放

首页独立使用 `web/playground/data/home-decision.json` 与 `home-demo.js`，共享游戏 renderer；精选通关与应用 Showcase 的素材清单见 `website-assets.json`。

```bash
python scripts/export_public_results.py --check
python scripts/export_home_decision.py --check
```
