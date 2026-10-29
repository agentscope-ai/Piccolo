# 部署与迁移

## 运行结构

前端文件在 `web/`，后端在 `blink_arena/`，共享规则在 `blink_arena/engines/`。默认一个 Python 进程同时提供静态页面和 HTTP API；这不要求两者部署在同一台机器，外部分发前端时需把 `/api/` 请求路由到同一后端，并保留会话 Cookie。

连接与游戏会话在进程内存中，因此当前部署使用单个 Uvicorn worker。对局与决策队列使用异步并发；不要通过 `--workers` 横向复制进程，否则同一浏览器的连接或会话可能落到另一个内存空间。浏览器直接调用模型服务，后端只提供游戏观测、决策队列和接收结构化结果。

## Docker 本地部署

```bash
docker compose up --build -d
docker compose ps
```

默认访问 <http://127.0.0.1:8080/>。服务以非 root 用户运行；Docker 中已安装 Chromium 和系统库。Compose 给浏览器保留 1 GiB 共享内存，评测大量 Mario/Terraria 对局时还需按实际并发分配主机内存。Playwright 的 Python 包版本和安装的浏览器版本应保持配套；构建时由同一版本的 `playwright install` 完成安装。[Playwright Docker 文档](https://playwright.dev/python/docs/docker)

需要安装支持 `docker compose` 的 Compose 插件。服务端口默认仅发布到主机回环地址，Compose 允许同网络 Caddy 的转发头，以正确识别 HTTPS 和同源请求。如果调整为直接公开后端端口，应将 `FORWARDED_ALLOW_IPS` 限定为实际反向代理地址。

用户自带模型的地址按用户浏览器能访问的地址填写。浏览器里的 `127.0.0.1` 指用户浏览器所在机器，不是 Docker 容器或网站服务器。

## DSW 反向代理

DSW 页面使用 HTTPS，转发给应用的请求可能仍显示为内部 HTTP 地址。部署时把浏览器地址栏中的来源（协议、域名和可选端口，不含路径）设置为 `JEV_PUBLIC_ORIGIN`，再启动服务。它只允许这个精确来源写入，不开放通配跨域。

```bash
JEV_PUBLIC_ORIGIN=https://your-instance-proxy-8080.dsw-gateway-cn-beijing.data.aliyun.com \
JEV_HOST=0.0.0.0 JEV_PORT=8080 bash scripts/run.sh
```

直接本地访问时无需设置。子路径部署仍用来源地址配合单独的 `JEV_PREFIX`。

## 固定域名与 HTTPS

将域名的 DNS 记录指向部署服务器，确保公网可访问 TCP 80/443。使用实际域名启动 Caddy 服务，默认不要求额外配置网站登录：

```bash
DOMAIN=games.example.com docker compose --profile domain up --build -d
```

随后访问 `https://games.example.com/`。模型地址、模型名和 API key 在前端填写，后端连接接口不接受模型端点或密钥。

`deploy/Caddyfile` 将请求保留原路径转发到 `jev:8080`。域名解析和端口满足条件时，Caddy 自动申请并续期 HTTPS 证书；证书保存在独立数据卷。[Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)

## 本站 Blink

在服务环境设置 `DASHSCOPE_API_KEY` 后重启现有后端即可。Git 内不包含真实 Key 或临时 Token；配置必须随自动部署保留，且不能进入静态资源。具体环境变量、验收命令与服务器 agent prompt 见 [HOSTED_MODEL.md](HOSTED_MODEL.md)。

## 浏览器模型连接

模型服务须使用与 Jev 页面不同的 origin，并允许页面 origin 的 CORS 请求，包括实际使用的 `Content-Type`、`Authorization`、`X-Request-ID` 请求头，以及 POST / OPTIONS。HTTPS 页面应连接 HTTPS 模型服务，避免被浏览器作为混合内容拦截；具体网络可达性以用户浏览器为准。

模型端点和密钥只保留在页面内存中，密钥只作为鉴权信息发送给填写的模型服务，不发送给 Jev 后端，也不写入浏览器持久存储、榜单或评测记录。关闭或刷新连接页面后需要重新连接；评测期间保持该页面打开。

浏览器 Cookie 的 owner 隔离用于区分连接和会话。若部署者需要限制整个网站的访问，可单独启用下节的可选登录。

## 可选网站登录

默认部署不启用 BasicAuth。需要网站入口密码时，交互生成 bcrypt hash，然后显式叠加可选配置；这与模型服务的 API key 无关：

```bash
docker run --rm -it caddy:2-alpine caddy hash-password
read -r -p 'Site username: ' JEV_SITE_USER
read -r -s -p 'Paste generated bcrypt hash: ' JEV_SITE_PASSWORD_HASH
printf '\n'
export JEV_SITE_USER JEV_SITE_PASSWORD_HASH
DOMAIN=games.example.com docker compose -f compose.yaml -f deploy/compose.auth.example.yaml --profile domain up -d
```

可选配置要求 `JEV_SITE_USER` 与 `JEV_SITE_PASSWORD_HASH`；默认 `compose.yaml` 不读取这两个参数。明文密码不写进命令参数、配置或日志。Caddy 的密码 hash 格式见 [BasicAuth 官方说明](https://caddyserver.com/docs/caddyfile/directives/basic_auth)。

## 挂载到子路径

例如使用 `https://games.example.com/jev/`：

```bash
DOMAIN=games.example.com JEV_PREFIX=/jev docker compose --profile domain up --build -d
```

原生启动方式：

```bash
JEV_PREFIX=/jev bash scripts/run.sh
```

反向代理必须保留 `/jev` 前缀，不使用会剥离路径的 `handle_path`。此时首页是 `/jev/`，健康检查为 `/jev/api/health`，OpenAPI 为 `/jev/api/openapi.json`。前缀不要写成完整 URL。

## 配置

| 配置 | 默认值 | 作用 |
| --- | --- | --- |
| `JEV_DATA_DIR` | 仓库内 `var/`；Docker 为 `/data` | 本地评测任务与运行记录 |
| `JEV_LEADERBOARD_DIR` | 仓库内 `leaderboard/`；Docker 为 `/app/leaderboard` | 统一榜单文件与随附回放目录 |
| `JEV_PREFIX` | 空 | 同一域名下的路径前缀 |
| `JEV_PUBLIC_ORIGIN` | 空 | 反向代理外部页面的精确来源，例如 `https://434426-proxy-8080.dsw-gateway-cn-beijing.data.aliyun.com`；代理未保留 HTTPS/Host 时仍允许这个来源的同站写入，不接受通配符或路径 |
| `JEV_CONFIG` | `config/app.json` | 服务运行参数文件 |
| `JEV_ENGINE_PLUGINS` | 空 | 显式载入的游戏插件模块，用逗号分隔；详见 ENGINE.md |
| `JEV_ADMIN_TOKEN` | 空 | 设置后才开放榜单写入；与模型 API key 无关 |
| `JEV_HTTP_PORT` | `8080` | Compose 发布到本机的端口 |
| `JEV_HOST` / `JEV_PORT` | `127.0.0.1` / `8080` | `scripts/run.sh` 的监听地址与端口 |
| `JEV_PYTHON` | 优先 `.venv/bin/python` | `scripts/run.sh` 使用的 Python 可执行文件 |
| `DOMAIN` | `localhost` | Caddy 的域名；正式部署填实际域名 |
| `FORWARDED_ALLOW_IPS` | Uvicorn 默认信任回环地址；Compose 中为 `*` | 接受可信代理的 HTTPS 转发头 |

模型地址、模型名和密钥在页面连接对话框中填写。服务配置文件只提供运行参数，不保存模型连接。榜单默认只读；需要通过 HTTP 导入时由部署环境设置管理员令牌，不要将真实值提交到仓库。

若另行启用了网站 BasicAuth，榜单 HTTP 写入使用 `X-Jev-Admin-Token`，避免覆盖入口的 `Authorization` 头；本地导入 CLI 不需要 Web 管理令牌。运行时不要打印模型凭据或访问令牌。

## 更新统一榜单目录

源码启动直接读取根目录 `leaderboard/`。更新该目录的标准 JSON 后，页面重新读取即可看到结果；完整文件约定见 [榜单数据目录](LEADERBOARD_DATA.md)。本地 CLI 使用同一目录：

```bash
.venv/bin/python scripts/import_leaderboard.py results.json --leaderboard-dir ./leaderboard
```

Docker 默认把榜单放在 `jev-leaderboard` 命名卷，容器内路径统一为 `/app/leaderboard`。新卷首次启动时从镜像复制初始文件，已有卷在镜像更新后仍保留原数据。要把宿主机已更新的目录同步进去：

```bash
docker compose cp ./leaderboard/. jev:/app/leaderboard/
docker compose exec --user root jev chown -R 10001:10001 /app/leaderboard
```

`jev` 是 Compose 中实际服务名。第二条确保后端以 UID 10001 运行时仍能写入更新与历史归档。若只想用合同校验导入一个结果文件：

```bash
docker compose cp ./results.json jev:/tmp/jev-results.json
docker compose exec jev python scripts/import_leaderboard.py /tmp/jev-results.json
```

需要让宿主目录和容器直接共用同一份文件时，可叠加 `deploy/compose.leaderboard-bind.example.yaml`。先确保宿主 `leaderboard/` 目录对容器 UID 10001 可读写，例如按本机权限策略配置 ACL；避免更改日常编辑用户所需的权限。

```bash
docker compose -f compose.yaml -f deploy/compose.leaderboard-bind.example.yaml up -d
```

## 数据持久化与迁移

榜单及随附回放集中在 `JEV_LEADERBOARD_DIR`，活动评测记录写入 `JEV_DATA_DIR`；`data/seed/` 只保留最小公共目录元信息。Compose 分别使用 `jev-leaderboard` 与 `jev-data` 命名卷；迁移时既要迁移源码/镜像，也要迁移实际使用的这两个目录或卷。若只需要前端和随包初始成绩，复制完整仓库即可。

本地启动的迁移流程：

1. 等待正在进行的评测完成，或通过服务提供的暂停接口停在可恢复状态。
2. 备份完整源码目录、`JEV_DATA_DIR` 和 `JEV_LEADERBOARD_DIR`；模型凭据不在这些位置保存。
3. 在新机器安装依赖与 Chromium，保留 `web/`、`config/`、`data/seed/`、`leaderboard/` 和 `blink_arena/` 的相对位置。
4. 设置新机器的数据目录并启动，在页面重新连接模型。浏览器 Cookie 和内存连接不随数据目录迁移。

不要只搬 `web/` 或 Python wheel 并期待游戏服务仍能运行。当前交付单位是完整源码目录、包含资产的源码压缩包，或完整 Docker 镜像。首次安装依赖需联网；隔离环境部署应在可联网的机器完成镜像构建后转移镜像及运行数据。

## 验收范围

实际通过的测试、浏览器检查、子路径与迁移副本启动结果见 [发布检查记录](RELEASE_CHECK.md)。Docker 容器构建与真实域名 DNS/TLS 尚未实测；部署配置不能替代目标机器上的验收。
