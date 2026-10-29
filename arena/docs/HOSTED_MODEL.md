# Blink 托管模型与双人对战

## 使用方式

页面默认选择本站提供的 **Blink**，公开连接 ID 为 `oneshot-hosted`。模型名默认 `pre-fin_service_2`。

- 12 个对战游戏：黑白棋 6×6、六角棋、点格棋、国际象棋、西洋跳棋、中国象棋、UNO、吹牛骰子、斗地主、德州扑克、地产大亨、炸金花。每个席位独立选择“我”、规则引擎、Blink 或已连接的外接模型。点击“开始”后，真人回合等待手动操作，模型与规则席位自动接招；也可执行当前席位单步。
- 斗地主显示地主、农民一、农民二三个独立选择框，两个农民不再共用控制器。每席只使用自己的手牌和公开信息，农民按团队结算。其他双人游戏显示两个选择框。
- 其余 10 个单人游戏保留玩法，使用当前选中的 Blink 或外接模型，也可手动操作。21 点庄家遵守原生规则，不改成可自由选择动作的第二名玩家。
- 实时游戏继续使用现有真实时钟，模型等待期间世界继续运行。
- 暂停停止后续请求；已经发出的本步请求可能完成。新开局、离开游戏或模型错误会停止连玩。

牌桌标签显示每个席位的控制者，`▶` 和高亮标出当前行动者。私有手牌视角固定在第一个选择“我”的席位；没有真人时固定第一席。回合切换不旋转座位。多个真人席位通过“切换到此席位”手动交接；公开棋盘保持原有朝向。展示视角与模型决策观测独立，后者仍只使用当前行动席位的原生观测。

多个席位都选 Blink 时，各自的当前席位观测分别构造独立请求，共用服务并发上限。规则席位使用已有原生策略，不发起模型请求；西洋跳棋、中国象棋和 UNO 沿用已有的合法动作随机基线。用户外接模型仍走浏览器直连；填写接口地址、模型名和 API Key，接口需允许页面来源的 CORS。用户 Key 只存当前页面内存，不上传给 PiccoloArena。

## 服务端配置

转发集成在现有 `blink_arena` 后端，无需额外公开端口。生产入口仍为 `python -m blink_arena` / `scripts/run.sh`。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 空 | 仅服务端读取的百炼长期 API Key；每次决策用它换取临时 Jev Token |
| `JEV_HOSTED_MODEL` | `pre-fin_service_2` | 上游模型名 |
| `JEV_HOSTED_ENDPOINT` | `https://poc-dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation` | 运维固定配置的 HTTPS 上游，浏览器不能修改 |
| `JEV_HOSTED_CONCURRENCY` | `5` | 托管模型请求并发，范围 1–32 |
| `JEV_HOSTED_TIMEOUT` | `60` | 换取 Token 和推理合计超时秒数，范围 1–600 |

把百炼 API Key 配置到实际服务管理器的环境或仓库外受限的凭据文件，确保自动部署的新进程也继承。配置后重启 PiccoloArena 服务。示例文件 `.env.example` 的 Key 为空；不要提交填有密钥的文件。直接运行 Python 不会自动加载 `.env`，需要由服务管理器注入；Compose 已声明上述变量映射。不再读取静态 `JEV_TOKEN`。

未配置 API Key 时网页仍可启动，Blink 标记为“等待服务端配置”，请求返回 `hosted_model_not_configured`；用户外接模型和单人手动操作仍可使用。`ready` 只代表配置存在；真实服务连通性需做一次实际决策验收。

每次调用严格执行两步（依据用户提供的 `jev-api-examples.zip`）：

1. 获得并发名额后，向 `https://dashscope.aliyuncs.com/api/v1/tokens?expire_in_seconds=60` 发空正文 POST，使用 `Authorization: Bearer <DASHSCOPE_API_KEY>`，取响应的 `token`。
2. 立即使用该临时 Token 请求下方推理网关。Token 只在本次调用内使用，不缓存、不落盘；下一步游戏决策重新换取。长期 Key 不发给推理网关。鉴权失败返回明确错误，不回退使用长期 Key 直接推理。

临时 Token 有效期为 60 秒；排队在换取之前发生，避免消耗它的有效期。换取和推理均禁止跟随重定向，并受同一总超时约束。前端显示的决策耗时包含排队、换取 Token 和推理。

转发的上游请求为：

```json
{
  "model": "pre-fin_service_2",
  "input": {
    "state": "引擎生成的当前席位观测 JSON 字符串",
    "questions": {
      "decision": {
        "type": "choice",
        "instructions": "引擎生成的决策要求",
        "criteria": {"hit": "要牌", "stand": "停牌"},
        "option_order": ["hit", "stand"]
      }
    }
  },
  "parameters": {}
}
```

游戏状态按 `json.dumps(state, ensure_ascii=False, sort_keys=True, allow_nan=False)` 转为字符串，保留空值及训练 formatter 的格式；`option_order` 保留引擎候选顺序，避免网关重排对象键。

浏览器通过现有 `/api/v1/decisions` 或游戏接口选择 `oneshot-hosted`。正式响应为 `output.answers.decision.choice` 和 `probabilities`；`output.model` 为 `jev-1026`，与请求的网关别名 `pre-fin_service_2` 不同，公共决策响应仍使用已登记的请求别名。适配器兼容根 `answers.decision` 及 chat JSON 包装；非法动作、不完整或非有限概率均拒绝，不伪造概率。上游错误正文、临时 Token 和鉴权头不会回传到网页。

## 服务器 agent 交接 prompt

```text
请为已同步的 PiccoloArena 配置 Blink 真实后端服务。

1. 先核对自动部署当前实际运行的 release 路径、Git 提交和服务管理器，读取该版本 PiccoloArena/docs/HOSTED_MODEL.md。不要只修改旧 checkout。
2. 使用我在本服务器授权提供的凭据位置，把真实 AK 注入现有 PiccoloArena 服务的 DASHSCOPE_API_KEY 环境变量。凭据保存在仓库外、权限受限的服务配置或 Secret 中；不写入 Git、前端、命令行参数、日志或对话。没有凭据位置时只向我询问位置。
3. 保持 JEV_HOSTED_MODEL=pre-fin_service_2，JEV_HOSTED_ENDPOINT=https://poc-dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation，JEV_HOSTED_CONCURRENCY=5，JEV_HOSTED_TIMEOUT=60。代码每次先使用长期 Key 换取 60 秒临时 Token，再请求推理；不要设置静态 JEV_TOKEN。服务位于反向代理后时，沿用正确的 JEV_PUBLIC_ORIGIN / JEV_PREFIX。确保后续自动部署仍能继承这些环境变量。
4. 重启实际 PiccoloArena 后端。转发已集成，无需另建公网代理、另开模型端口或改成浏览器持有本站 Token。不要启动 tests/hosted_fixture.py；它只返回模拟决策。
5. 执行 scripts/check_hosted_model.py --url <实际服务根地址>，再在网页验收 Blink 的 21 点或 2048 单步，以及 Blink vs Blink、Blink vs 真人、Blink vs 用户自带模型。检查双方使用各自的观测，真人行动后模型能自动接招，暂停/重开及报错后能恢复。
6. 间隔至少 65 秒再执行一次真实决策，确认后续请求重新获取 Token，且页面连玩不会因旧 Token 过期而失效。正式响应路径是 output.answers.decision，返回模型名 jev-1026 与请求别名不同属于正常行为。不要将接口错误替换为规则动作或伪造成功。
7. 最后只报告实际版本、服务状态、真实调用的合法动作与耗时和网页验收结果；不展示任何凭据。不要部署或恢复数据分布报告到公开 Playground。
```

## 本地验证

`tests/test_hosted_model.py` 用 MockTransport 检查每次重新换取 Token、两段鉴权隔离、请求序列化、正式响应结构、非法响应、超时与跨浏览器授权边界；`tests/test_social_duels.py` 对照已有原生对手执行器检查状态及结算。

浏览器 QA 专用入口与生产入口分开：

```bash
PYTHONPATH=.:tests .venv/bin/python -m uvicorn hosted_fixture:create --factory --host 127.0.0.1 --port 8893
PYTHONPATH=.:tests .venv/bin/python tests/browser_hosted_duels.py --url http://127.0.0.1:8893/ --output var/hosted-duels-qa
```

这里的 fixture 仅使用明显标注的假 Token 和本机模拟服务，不能作为真实上游已经联通的证据。

2026-10-26 本地回归：307 项 Python 测试及 2 个子测试、9 项 Node 测试通过。浏览器验证了 22 款游戏的模型单步、全部 12 款对战游戏的两模型连玩、外接模型席位和真人回合衔接，以及 1360 / 390 / 320 像素布局；无页面脚本错误。此验证使用模拟换取 Token 和推理接口，不是游戏成功率评测；生产凭据注入和真实网关调用按上方交接 prompt 验收。
