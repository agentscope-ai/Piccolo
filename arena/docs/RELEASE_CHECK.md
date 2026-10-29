# Piccolo Arena 发行检查

本目录从现有前端整理而来。此次验证结果与已知历史失败统一记录在 [Piccolo 验证记录](../../docs/VERIFICATION.md)；上游旧版本的测试数字不作为当前版本的验收结论。

## 可重复运行

在 `arena/` 下安装测试依赖，再执行：

```bash
python -m pip install -e '.[test]'
python -m pytest -q
node --test tests/test_connections_transport.cjs
python scripts/build_release.py --check-only
```

需要独立服务的测试须按测试说明设置 `JEV_TEST_URL`，未设置时会显式跳过。当前完整测试仍有已复现的上游旧断言失败，详见验证记录。

在 Piccolo 仓库根目录运行新的浏览器检查：

```bash
python scripts/verify_frontend.py --server-python arena/.venv/bin/python
```

执行检查的 Python 需安装 Playwright 和 Chromium。脚本在随机回环端口启动临时服务，检查双语、桌面与手机视口、榜单和归档回放，并在退出时关闭服务；证据写入忽略的 `var/verification/`。

## 可选源码发行包

```bash
python scripts/build_release.py --output-dir ../dist
```

此命令在 `arena/` 下执行，仅打包 Arena 组件。它使用发行文件清单并排除虚拟环境、运行数据、日志、凭据、缓存和内部交接文档；拒绝覆盖同名归档。完整 Piccolo 项目另含根目录 README、Showcase 素材及安全审批 Skill。

本次没有构建 Docker 镜像、公开部署、调用真实模型或接通 QwenPaw 服务。历史轨迹展示不构成未来模型的能力验证。
