# QwenPaw 接入

## 导入技能

在 QwenPaw 控制台的 **工作区 → 技能 → ZIP 导入** 中导入 `blink-safety-review.zip`。也可以先导入技能池再广播至目标工作区；只进入技能池不会使工作区运行它。导入后按界面确认技能已启用。

QwenPaw 当前工作区目录约定为 `$QWENPAW_WORKING_DIR/workspaces/{agent_id}/skills/`，默认根目录为 `~/.qwenpaw`。通过界面导入可同时维护 `skill.json`；不要只复制共享池后假定已生效。

本技能可在对话中被 Agent 调用。**导入技能不等于所有工具调用都会被强制审查。** 宿主层的覆盖需要下面的 ToolGuard 注册。

## 模型发布后的配置

维护者将 `assets/release.json` 更新为正式发布信息：`status=released`、Hugging Face 模型仓库、固定 revision、允许下载文件、精确 `served_model` 和完成安全评测后的 `allow_threshold`。不得用当前历史游戏 checkpoint 自动代替安全审批模型。

下载器通过 [Hugging Face 官方 snapshot_download](https://huggingface.co/docs/huggingface_hub/guides/download) 按固定 revision 下载到调用方指定目录。它不加载模型、不执行下载文件、不自动写入 QwenPaw 配置。下载完成不代表审批服务已启动或模型已验证。

服务需要接受 `jev.decision.v1`，返回与请求相同的 `request_id` 和精确 `model`、`action` 以及 `allow / ask_user / deny` 三项完整概率。该接口是现有 Arena 的兼容接入合同；模型内部的推理框架及启动命令待模型确定后提供。文本自报置信度不能代替模型候选概率。

## 宿主 ToolGuard 接入

已按本地 QwenPaw 源码核对以下接口：

- `qwenpaw.security.tool_guard.guardians.BaseToolGuardian.guard(tool_name, params)`。
- `qwenpaw.security.tool_guard.engine.get_guard_engine().register_guardian(...)`。
- `qwenpaw.security.tool_guard.models.GuardFinding`。

在 **QwenPaw 服务进程内** 的受信任启动扩展中加载 `scripts/qwenpaw_guardian.py` 并注册。另起一个 Python 进程调用 `register_guardian` 不会改变正在运行的服务。当前配置没有 `approval_model` 这类模型字段，不要编造配置键。

```python
# skill_scripts 为已安装技能的 scripts 目录。
# 在宿主受信任启动代码中设置 import 路径，并只注册一次。
import sys
sys.path.insert(0, str(skill_scripts))
from qwenpaw_guardian import BlinkGuardian
from qwenpaw.security.tool_guard.engine import get_guard_engine

engine = get_guard_engine()
if 'blink-safety-review' not in engine.guardian_names:
    engine.register_guardian(BlinkGuardian(
        endpoint=local_decision_endpoint,
        model=release['served_model'],
        threshold=release['allow_threshold'],
        context_provider=current_request_authorization,
    ))
```

`current_request_authorization()` 必须从宿主当前请求上下文返回 `user_request`、`authorized_scope` 两个字符串。使用请求局部状态，不把不同用户的授权放在同一个全局变量中。缺少上下文时检查器产生 HIGH finding，进入已有审批流程。

检查器是附加层：不会注销默认 guardians，也不改变 `denied_tools`、`guarded_tools`、approval level、文件保护或 session 审批。`allow` 只表示本检查器未新增 finding；`ask_user` 与 `deny` 都产生 HIGH finding，交给宿主现有审批流程。**此适配器不实现不可被用户覆盖的硬拒绝**，也不会代发批准。强制拒绝需由宿主拒绝规则或执行边界实现。

模型建议的作用范围只覆盖当前工具与参数。框架禁用 ToolGuard、显式预批准或其他执行入口可能绕过 guardian；启用前应按实际运行版本验收覆盖面。本次未修改或启动 QwenPaw 服务，未接通真实模型。

## 接通前验收

先用已授权只读动作、越权动作、缺失授权上下文、错误模型身份、缺失概率、超时和服务不可达进行验证。再评估审批模型的漏拦与误拦，确定阈值后才启用自动 allow 建议；导入技能或接口通过不等于模型安全能力通过。
