# Piccolo 仓库范围

## v1.0.0

本次正式源码发布包含三种尺寸模型的公开下载入口、固定权重 revision、参考推理、发布成绩、QwenPaw 原生接入文档、交互 Arena 与归档回放。入口为 [Decision](https://decisionplayground.agentscope.io/)、[GitHub](https://github.com/agentscope-ai/Piccolo) 和 [Hugging Face](MODELS.md)。ModelScope 镜像尚未发布。

- [README](../README_zh.md) 为使用入口；[发布 Blog](piccolo-blog.md) 为公众号／小红书母稿，旧 `blog.md` 仅保留跳转。
- [models/](../models/README.md) 固定 12 个模型仓库的权重版本；完整 Safetensors、BF16、Q8_0、Q4_K_M 均已发布。
- [inference/](../inference/README.md) 与 [examples/](../examples/README.md) 提供候选概率参考推理与最小请求。
- [evaluation/](../evaluation/README.md) 记录发布权重成绩与来源口径；精选历史回放仍保留自身 checkpoint 身份。
- [training/](../training/README.md) 与 [data/](../data/README.md) 仍为 Coming soon，未公开实现不计入本次交付。

旧 Skill、下载助手、自定义审核客户端与 Guardian 已移除，原生下载、决策选择、审批和 ReMe 压缩由 [QwenPaw Draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463) 承接，使用双向 prompt attention 和候选 token 评分。配套 llama.cpp 尚需补丁；并非所有上游正式版本已支持。

自有代码采用 [Apache-2.0](../LICENSE)，第三方许可与署名见 [NOTICE](../NOTICE) 和 [组件来源](../arena/docs/THIRD_PARTY.md)。历史协议、Python 包 `blink_arena`、轨迹身份和提交作者元数据保留；没有为本次发布重写历史。

## 迁入与验证

Arena 来源于 JevArena，保留共享引擎、HTTP 接口、公共榜单与真实回放。源码与官网部署是不同产物，应分别核对；[网页同步记录](GITLAB_SYNC.md) 和 [验证记录](VERIFICATION.md)保留历史范围。本次变更说明见 [CHANGELOG](../CHANGELOG.md)。
