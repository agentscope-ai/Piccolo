# 可移植公开成绩

`data/seed/leaderboards/` 保存发布前端当前展示的三个 benchmark 聚合结果，格式为 `jev.leaderboard.v1`。这些文件只包含公开模型 ID、显示名称、评测协议、最终成绩、校准指标和能力/场景得分；不包含模型地址、密钥、checkpoint 路径、原始题目、逐题输出或训练数据。

| 文件 | 版本 | 模型数 | 雷达维度 |
| --- | --- | ---: | ---: |
| `jevbench.json` | 1.2 | 8 | 18 |
| `decisionindex.json` | 0.3-quick-20261014 | 8 | 5 |
| `harnessjevbench.json` | V0.2 | 8 | 31 |

此次只读取当前 `display_rows`，不混入其他归档组。模型 ID 保持原值，前端继续使用已有显示名称映射。每个轴显式包含 `label_en` 与 `label_zh`，语言按钮切换时同步切换；自定义标签优先于内置缩写。

## 计分边界

- JevBench 的主分数是准确率，范围 0–1；雷达使用各能力准确率。
- DecisionIndex 保留原生 quick-subset 指数，范围 0–100，不将其改称 ACC。补充 ACC 是可分类子题的微平均准确率；Brier/ECE 仅纳入有概率分布的单标签分类子题。雷达保存随机基线校正后的领域分，范围 0–1。
- HarnessJevBench 主分数为 Hard 任务等权分，ACC 要求两个视图均全部答对。Soft 场景雷达轴使用 `1 − TV`，表示分布一致度，不并入 Hard 总分；轴的 `metric` 保留该区别。
- Brier/ECE 不从正确率推算。指标缺失保持缺失；校准覆盖数量保留在 `metrics` 的数值字段中。
- 源状态 `complete_with_errors` 转为合同的 `complete`，同时保留真实 `errors` 和说明。本次 SFT-1015 的 DecisionIndex 有 1 个失败请求，未将其抹除。
- 未完成的记录保留 `running`/`pending`/`error` 状态，`score` 及所有轴得分为 `null`，不导出部分校准成绩。

## 重新导出与校验

在仓库根目录执行；`--api-root` 指向实际部署前端的公开 API 根路径。导出只发出只读 GET 请求，不连接任何模型服务，也不启动评测。

```bash
python scripts/export_public_results.py --api-root https://example.com/api
python scripts/export_public_results.py --check
node --check web/playground/leaderboard.js
python tests/browser_leaderboards.py --url http://127.0.0.1:8092/
```

导出采用嵌套字段白名单，再验证合同、数值有限性、模型引用和私有路径/凭据字段。所有数据验证完成后才写入各个 JSON 文件。`--check` 完全离线。

此次验证包括：三个榜单全部主分数、维度分数和补充指标与只读 API 逐项相同；运行中记录不会发布最终分数；非白名单身份字段不会进入导出；公开字段出现私有路径会拒绝导出。JavaScript 运行检查覆盖三个榜单的导入指标/雷达映射、中英文显式标签和自定义标签换行。

实际 Chromium 检查覆盖 1440px 桌面与 390px 手机、中英文、4 个雷达和 3 张指标表，共 16 个页面视图。全部导入指标可见，雷达标签随语言切换，页面无横向溢出、无控制台错误；手机指标表可在自身容器内横向滚动。截图和结构化结果在 `var/browser/`，不随公开成绩提交。
