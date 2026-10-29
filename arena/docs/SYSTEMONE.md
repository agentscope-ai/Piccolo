# 在 Piccolo Arena 连接 System One 服务

Piccolo 的模型版本尚未确定。本页仅说明现有前端的外部服务兼容入口。

页面的结构化接口使用 `jev.decision.v1`，已有 System One 服务使用 `state/questions`。随包桥接器转换请求及响应，保留选项 ID、顺序、模型身份和实际概率；不加载模型，也不提供推理或训练实现。

```bash
python -m blink_arena.systemone --help
```

按命令帮助填写自己的服务地址和精确模型名，桥接器只在本机启动。前端连接需要可访问的完整 `/decide` URL，并满足浏览器的 CORS 要求。不要将内部地址或凭据写入仓库。

通用连接流程及协议见 [API 文档](API.md)。历史评测脚本 `scripts/evaluate_systemone.py` 保留供已有服务使用，不会在启动前端时自动运行。
