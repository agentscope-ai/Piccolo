# 来源与第三方组件

前端页脚的 **Source & credits / 来源与致谢** 指向随仓库提供的 `web/credits.html`。本页区分改编的前端代码、玩法与绘制参考、实际加载的规则库和字体。上游地址依据当前文件的来源元信息及公开仓库核对，不把场景中的链接自动解释为复制了整个上游项目。

## 前端改编

| 本地内容 | 上游 | 使用关系 |
| --- | --- | --- |
| `web/playground/terraria.js` | [Xinji-Mai / Terramai · tasty-world.js](https://github.com/Xinji-Mai/Xinji-Mai.github.io/blob/master/assets/js/tasty-world.js) | 沿用 Terramai 像素沙盒的世界、物理和绘制基础，在此之上接入 Jev 公开观测、模型动作、种子、终局和重演控制。不是原商业游戏 Terraria 的代码或素材包。 |

Terramai 的来源在 `jev_demo_showcases.py` 的 `terraria_survival` 元信息中明确记录，本地文件保留了原 Terramai 文件头及引擎骨架。上游仓库的 [LICENSE](https://github.com/Xinji-Mai/Xinji-Mai.github.io/blob/master/LICENSE) 是带站点模板版权声明的 MIT 文本；所引用的游戏文件未单独声明许可。这里保留精确代码与许可链接，不把模板的版权作者改写为游戏作者，也不据此给整个 PiccoloArena 仓库指定统一许可证。

## 玩法、交互与绘制参考

| 本版区域 | 引用的项目 | 当前证据与使用范围 |
| --- | --- | --- |
| 国际象棋 | [StartLuxLabs / Startlux-Decision](https://github.com/StartLuxLabs/Startlux-Decision) | 参考合法候选、公开棋盘与棋谱、单次 Choice 的决策组织。本版由共享 `jev_chess.py`、现有 python-chess 依赖与本地棋盘 renderer 实现；不使用上游预算估分判胜或错误后随机代走。 |
| 俄罗斯方块 | [thelau / jev-tetris](https://github.com/thelau/jev-tetris) · [上游 MIT 许可](https://github.com/thelau/jev-tetris/blob/main/LICENSE) | 原场景元信息列出的玩法与决策展示参考。本版由 `jev_tetris_realtime.py` 和本地 renderer 实现实时下落。未取得逐文件移植清单，因此不标为整套上游前端的复制。 |
| 贪吃蛇 | [sorrycc / typesafe-snake](https://github.com/sorrycc/typesafe-snake) | 原场景元信息列出的实时决策玩法参考。本版由 `jev_snake_realtime.py` 与本地渲染器运行。核对的仓库根目录未提供独立 LICENSE，不能将其标成 MIT。 |
| 赛车 | [jakesgordon / JavaScript Racer](https://github.com/jakesgordon/javascript-racer) · [上游 MIT 许可](https://github.com/jakesgordon/javascript-racer/blob/master/LICENSE) | `jev_racing_game.py` 明确将其标为绘制参考；本版车辆动力学、碰撞和计分由 Jev 共享实时赛车引擎负责。当前资产目录不包含上游音乐或图片资源。 |
| 掷骰猪 | [OpenSpiel 游戏目录](https://github.com/google-deepmind/open_spiel/blob/master/docs/games.md) | 场景说明的规则参考；该玩法在 `jev_probability_games.py` 中本地实现，不由 OpenSpiel 的运行时执行。 |

参考项目的许可只说明该项目自身，不能用来替代实际采用文件的版权与许可记录。新增上游代码或资产时，应记录具体文件、版本及改动，并保留它自带的声明。

## 实际使用的游戏规则库

| 组件 | 本版用途 | 上游与许可 |
| --- | --- | --- |
| OpenSpiel / `pyspiel` | 兵卒突围、播棋、吹牛骰子、竞价夺牌和 21 点的状态与规则，由 `jev_agent_games.py` 调用；新增西洋跳棋、9×9围棋和中国象棋由 `jev_selected_games.py` 调用 | [代码仓库](https://github.com/google-deepmind/open_spiel) · [Apache-2.0](https://github.com/google-deepmind/open_spiel/blob/master/LICENSE) |
| TextArena 0.7.3 | 猜数字、扫雷和数独的原生状态与规则；数独只增加公开的选格阶段 | [代码仓库](https://github.com/TextArena/TextArena) · [MIT](https://github.com/TextArena/TextArena/blob/main/LICENSE) |
| RLCard 1.2.0 | 双人UNO的原生牌堆、合法动作和结算；适配层拒绝非法动作，避免上游随机替换 | [代码仓库](https://github.com/datamllab/rlcard) · [MIT](https://github.com/datamllab/rlcard/blob/master/LICENSE) |
| python-chess / `chess` | 国际象棋合法着、棋局状态和终局规则 | [代码仓库](https://github.com/niklasf/python-chess) · [GPL-3.0-or-later 说明](https://github.com/niklasf/python-chess#license) · [许可全文](https://github.com/niklasf/python-chess/blob/master/LICENSE.txt) |

这些组件通过 Python 依赖安装；版本见 `requirements.txt`。它们与前端样式参考是不同的依赖关系。

## 字体

全站界面与图表采用 **Inter 4.1**，由 Rasmus Andersson 设计，文件为 `web/playground/fonts/InterVariable.woff2`。来源：[rsms/inter v4.1](https://github.com/rsms/inter/tree/v4.1)，许可为 **SIL Open Font License 1.1**，全文随包保留在 [Inter-OFL.txt](../web/playground/fonts/Inter-OFL.txt)。字体本地加载，页面不会请求第三方字体服务。中文统一使用平台无衬线回退（苹方、微软雅黑或 Noto Sans CJK SC）。

既有 canvas 渲染器里的 `Jev Comic` 名称保留为兼容别名，当前同样映射到 Inter。旧版 **ZCOOL KuaiLe / 站酷快乐体** 文件和 [ZCOOLKuaiLe-OFL.txt](../web/playground/fonts/ZCOOLKuaiLe-OFL.txt) 保留在包中，当前主题不加载它；旧字体来源为 [googlefonts/zcool-kuaile](https://github.com/googlefonts/zcool-kuaile)。

## 服务与浏览器运行依赖

以下为安装或部署时使用的组件，不是复制来的前端模板。直接依赖的版本见 `requirements.txt`，完整依赖与许可由对应安装包随附。

| 组件 | 用途 | 上游 |
| --- | --- | --- |
| FastAPI | 版本化 HTTP API | [fastapi / fastapi](https://github.com/fastapi/fastapi) |
| Uvicorn | ASGI 服务 | [Kludex / uvicorn](https://github.com/Kludex/uvicorn) |
| HTTPX | HTTP 接口测试客户端 | [encode / httpx](https://github.com/encode/httpx) |
| Pydantic | 请求及导入文件合同校验 | [pydantic / pydantic](https://github.com/pydantic/pydantic) |
| Playwright Python | 运行同一套浏览器世界，用于试玩会话和评测 | [microsoft / playwright-python](https://github.com/microsoft/playwright-python) |
| Caddy | 可选域名反向代理与 HTTPS | [caddyserver / caddy](https://github.com/caddyserver/caddy) |

Jensen–Shannon 距离的方法链接指向 [SciPy 官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jensenshannon.html)，用于解释统计定义；这不表示项目运行时依赖 SciPy。

## 隐私与分发边界

来源页只列公共项目、公共许可与本仓库的相对路径。页脚不链接旧部署主机、数据审计或样式实验室。模型端点、凭据、私人机器目录、运行日志与 checkpoint 不属于来源信息，不放入来源页或发行说明。外部链接只在点击后打开，并设置不发送来源页 referrer。

开发过程的内部交接文件不进入发行包；源码包仍包含本说明、前端来源页和本地字体许可。
