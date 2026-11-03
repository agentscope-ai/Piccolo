# Piccolo 仓库范围

## 当前源码

本次正式源码发布包含三种尺寸模型的公开下载入口、固定权重 revision、参考推理、发布成绩、QwenPaw 原生接入文档、交互 Arena 与归档回放。入口为 [Decision](https://decisionplayground.agentscope.io/)、[GitHub](https://github.com/agentscope-ai/Piccolo) 和 [模型下载目录](MODELS.md)。

- [README](../README_zh.md) 为使用入口；[发布 Blog](piccolo-blog.md) 为公众号／小红书母稿，旧 `blog.md` 仅保留跳转。
- [官网源码](../arena/docs/WEBSITE.md)包含双语文章、Method 图示、完整回放与 [12 个工作流案例](../examples/workflows/README.md)。
- [models/](../models/README.md) 固定 12 个模型仓库的权重版本；完整 Safetensors、BF16、Q8_0、Q4_K_M 均已发布。
- [inference/](../inference/README.md) 与 [examples/](../examples/README.md) 提供候选概率参考推理与最小请求。
- [evaluation/](../evaluation/README.md) 提供基准成绩和一键复现脚本；精选历史回放仍保留自身 checkpoint 身份。

原生下载、决策选择、审批和 ReMe 压缩已集成到 [QwenPaw 主分支](https://github.com/agentscope-ai/QwenPaw/blob/main/docs/local-piccolo.md)，使用双向 prompt attention 和候选 token 评分。源码安装与配套运行时配置见 [QwenPaw 指南](QWENPAW.md)。

自有代码采用 [Apache-2.0](../LICENSE)，第三方许可与署名见 [NOTICE](../NOTICE) 和 [组件来源](../arena/docs/THIRD_PARTY.md)。历史协议、Python 包 `blink_arena`、轨迹身份和提交作者元数据保留；没有为本次发布重写历史。

## 迁入与验证

Arena 来源于 JevArena，保留共享引擎、HTTP 接口、公共榜单与真实回放。源码与官网部署是不同产物，应分别核对；[网页同步记录](GITLAB_SYNC.md) 和 [验证记录](VERIFICATION.md)保留历史范围。本次变更说明见 [CHANGELOG](../CHANGELOG.md)。

## 持续集成

[GitHub Actions](../.github/workflows/ci.yml) 在主分支更新和 PR 中自动运行 Python、前端与浏览器测试，检查本地链接和生成文件，并打包完整源码。构建产物保存在 Actions 中，不创建 GitHub Release。
