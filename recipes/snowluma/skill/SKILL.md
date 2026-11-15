---
name: snowluma
description: 在 cccodroid 上原生运行 Linux QQ + SnowLuma 的 OneBot 机器人：首次安装、扫码登录、白名单、模型后端与排错。用户要部署/维护 QQ 机器人时使用。
---

# QQ 机器人（原生 SnowLuma）

在手机上**原生**跑 Linux 版 QQ + SnowLuma，不使用 proot、不需要 root。QQ 跑在组件自带的
Xvfb 虚拟显示里，SnowLuma 作为独立进程注入 QQ 后提供 OneBot v11，本组件附一个只应答
白名单会话的桥。所有运行数据在 `~/.cccodroid/snowluma`（`$HOME` 下），不写系统分区。

## 免责声明（下载前必须原文转告用户）

第一次 `setup` 之前，把下面这段**原样**告诉用户，用户明确表示「同意」后才能继续；用户没表态或拒绝，就停下，不要换个说法再劝。

> 1. 本组件是社区作品，与腾讯、QQ、SnowLuma 均无关联，未获任何官方授权或认可。
> 2. 它通过非官方框架（SnowLuma）接入 Linux 版 QQ 客户端，可能违反《腾讯 QQ 软件许可及服务协议》。登录的 QQ 号可能被限制功能、冻结或封禁，由此造成的损失（包括账号、好友、群、聊天记录）由使用者自行承担。**建议用不重要的小号。**
> 3. 机器人的回复由 AI 生成，可能有错误或不当内容。使用者对机器人在私聊和群里发出的全部内容负责，须遵守法律法规、平台规则和群规；把机器人拉进群前，应征得群主或管理员同意。
> 4. 不得用于批量注册、养号、刷屏、营销群发、冒充真人、收集他人信息等用途。
> 5. SnowLuma 官方仓库已因律师函消失；本组件从公共档案镜像下载官方原包。SnowLuma 的许可证限非商业使用，其 EULA 规定「通过自动化脚本部署须事先取得书面授权」——本组件未获该授权，仅在你明确同意后替你下载官方原包；是否合规由使用者自行评估，需要严格合规请自行联系 SnowLumaDevs。QQ 客户端受腾讯服务条款约束。
> 6. 组件按「现状」提供，不作任何担保；cccodroid 与组件作者不对使用后果承担责任。

## 先问用户，再下载

`snowluma setup --check` 只报体积，不下载。用户同意上面的免责声明之后，再把下面这些告诉用户，得到明确同意后再加 `--yes`：

- Debian trixie 运行库（GTK3/NSS/ALSA/GBM 等）：约 74 MB 下载 / 334 MB 解开
- Linux QQ 3.2.34（腾讯官方 CDN）：198 MB 下载 / 646 MB 解开
- SnowLuma 2.4.2 full 版（公共档案镜像 ×3）：50 MB 下载 / 约 262 MB 解开
- 合计约 322 MB 下载、1.2 GB 占用；安装时间取决于网速，可能十几分钟

来源、版本、SHA256 都写在组件的 `NOTICE` 里；安装器逐个核对。QQ 是腾讯的闭源客户端，
SnowLuma 官方发行包受其 EULA 约束，两者都不随组件包分发，只在用户确认后下载。

## 安装与登录

1. `snowluma setup --yes`（用户同意后）。可加 `--jobs 4`。失败重跑会续用缓存。
2. `snowluma start`。它会起 Xvfb、X 代理、SnowLuma、QQ 和桥；输出扫码地址。
3. 让用户在应用内浏览器打开 `http://127.0.0.1:8787/` 扫码（端口占用时看
   `snowluma status` 的实际端口）。页面是 QQ 登录窗口的实时截图（每 2 秒刷新），
   二维码 60–90 秒过期，扫完要在手机上立刻点「确认登录」。
4. `snowluma status` 或 `snowluma whoami` 直到显示已登录。没登录时 OneBot 的 3000/3001
   不会监听，这是正常的（SnowLuma 登录后才会起 OneBot 会话）。
5. 放行会话：`snowluma allow add <用户自己的 QQ 号>`。群聊用
   `snowluma allow add-group <群号>`；默认只在有人 **@ 机器人** 时回复。

白名单默认为空，空的时候不响应任何人。不要为了“先跑起来”把 `groupTrigger` 改成 `any`，
也不要把机器人拉进用户没有明确同意的群。

SnowLuma 自带 WebUI（`http://127.0.0.1:5099`）：账号状态、日志、OneBot 连接配置、进程
注入状态都在里面。首次启动时组件生成登录密码，用 `snowluma webui` 查看；用户在 WebUI 里
改过密码后以新密码为准。忘记密码：`snowluma stop` 后删掉
`~/.cccodroid/snowluma/data/snowluma/config/webui.json` 再 start，会重新生成。

## 模型后端

桥走 OpenAI 兼容的 `/chat/completions`。默认是 DeepSeek：

```
snowluma config set backend.baseUrl https://api.deepseek.com/v1
snowluma config set backend.model deepseek-chat
```

用户可以换成任何 OpenAI 兼容服务（包括本机的 llama-server）。只允许 https，或
`http://127.0.0.1`/`localhost`；不要把带密钥的明文 http 指到外网。

密钥：**绝不要让用户把密钥贴进对话，也不要读取或打印它**。让用户自己在终端里创建：

```
printf '%s' '你的密钥' > ~/.cccodroid/snowluma/model-key.txt
chmod 600 ~/.cccodroid/snowluma/model-key.txt
```

路径可以用 `snowluma config set backend.apiKeyFile <路径>` 改；`snowluma config` 会打码。
没配置密钥时桥会重试并在 `bridge.log` 记一条（每分钟最多一条），不会把密钥写进日志。

## 运行链路（动手前先读，别猜）

`snowluma start` 不是直接跑 QQ，它起一层 supervisor，把下面几段接起来：

```
snowluma（Node，$PREFIX/bin/snowluma）
  └─ supervisor.mjs（Node，bionic）
       ├─ $PREFIX/bin/Xvfb :99（bionic，x11 仓库，-extension MIT-SHM 关掉共享内存）
       ├─ X 代理 127.0.0.1:6099（Node）→ $PREFIX/tmp/.X11-unix/X99
       ├─ QQ（glibc，debroot/opt/QQ/qq，解释器已改成 $PREFIX/glibc/lib/ld-linux-aarch64.so.1）
       ├─ SnowLuma（glibc，data/snowluma/node → index.mjs，独立进程）
       │     └─ 原生附加组件把 snowluma-linux-arm64.so 注入 QQ 进程（同 uid）
       │          └─ OneBot HTTP/WS 127.0.0.1:3000 / 3001（登录后才有）
       │          └─ WebUI http://127.0.0.1:5099（首次启动播种密码）
       ├─ bridge.mjs（Node，bionic）—— OneBot → OpenAI 兼容接口
       ├─ scrot（bionic，x11 仓库）—— 每 2 秒截一张 X 显示图当登录二维码
       └─ 扫码页 http://127.0.0.1:8787/（读 data/cache/qr.png）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| CLI、supervisor、桥、扫码页 | 本组件脚本 | `$PREFIX/share/cccodroid/components/snowluma/lib/` |
| Xvfb、xauth、scrot 与 X 工具 | Termux x11 仓库（组件依赖） | `$PREFIX/bin/Xvfb`、`$PREFIX/bin/scrot`、`$PREFIX/tmp/.X11-unix/` |
| GTK3 / NSS / ALSA / GBM 等 | `snowluma setup` 从 Debian trixie arm64 取 | `~/.cccodroid/snowluma/data/debroot/` |
| QQ 本体 | `snowluma setup` 从腾讯官方 CDN 取（198 MB，核 SHA256） | `debroot/opt/QQ/` |
| SnowLuma 运行时（含自带 node 24.22.1） | `snowluma setup` 从公共档案镜像取（50 MB，核 SHA256） | `~/.cccodroid/snowluma/data/snowluma/` |
| glibc 运行时 | base 的 glibc 包；Debian 的 libc6 故意跳过 | `$PREFIX/glibc/lib/` |

几条由此而来的事实：

- **SnowLuma 不是 NapCat 那种注入**：它是独立 Node 进程，用原生附加组件把
  `snowluma-linux-arm64.so` 手动映射进**同 uid 的 QQ 进程**，钩子经
  `SNOWLUMA_HOOK_RUNTIME_DIR`（supervisor 设成 `data/run`）下的管道回连。不要去找
  `app_launcher`、`package.json main` 或 `loadNapCat.js`——snowluma 没有这些。
- **SnowLuma 的 node 必须直接执行**：它的解释器被 patchelf 成
  `$PREFIX/glibc/lib/ld-linux-aarch64.so.1`。不要用 `ld-linux ./node` 形式启动——SnowLuma
  启动时会用 `process.execPath` 自 spawn 更新守护子进程，execPath 若是加载器，子进程会把
  `index.mjs` 当 ELF 加载报 invalid ELF header。库路径只能来自
  `data/snowluma-libpath.txt`（libc.so 垫片 + debroot 库 + `$PREFIX/glibc/lib`），绝不能有
  `$PREFIX/lib`（bionic 的 libc）。垫片是 `data/snowluma/lib/libc.so → $PREFIX/glibc/lib/libc.so.6`
  的软链：自带 node 的 DT_NEEDED 里有裸名 libc.so，而 glibc 的 libc.so 是 ld 链接脚本。
- **二维码靠截图**：SnowLuma 不像 NapCat 有 cache/qrcode.png，登录二维码在 QQ 窗口里。
  扫码页由 supervisor 每 2 秒用 scrot 截一张 `data/cache/qr.png`。Xvfb 必须带
  `-extension MIT-SHM`：安卓 bionic 没有 SYSV 共享内存，scrot/imlib2 走 XShm 会永远挂在
  ShmGetImage 上（实测踩过）。scrot 是 bionic 程序，走 `$PREFIX/tmp/.X11-unix` 的 Unix
  socket（DISPLAY=:N），QQ 的 Debian libxcb 走 TCP 代理，两者不冲突。
- **登录前 OneBot 不监听**：SnowLuma 登录后才有账号会话，3000/3001 那时才开；扫码页不
  依赖 OneBot。`snowluma status` 显示“等待扫码登录”是正常的。账号识别靠 QQ 登录数据库
  （`data/home/.config/QQ`）文件变化 + 进程事件，QQ 重启后 SnowLuma 会自动重新注入。
- **注入是进程注入**：SnowLuma 对 QQ 的注入走同 uid 的进程内存操作。QQ 与 SnowLuma 都由
  supervisor 以同一个应用 uid 启动，安卓允许同 uid 互相 ptrace/读 /proc；跨 uid 不行。
  不要用 shizuku/root 去跑其中任何一个，也不要改它们的 uid。
- **模型后端在桥里**：QQ ↔ SnowLuma ↔ bridge 之间只走 `127.0.0.1`。配置见
  `snowluma config`；SnowLuma 自己的 OneBot 配置在
  `data/snowluma/config/onebot.json`（http 3000 / ws 3001，token 与桥的
  `config.json` 一致），runtime 配置在 `config/runtime.json`（webuiHost 127.0.0.1、
  hookAutoLoad true）。SnowLuma 的内置 #sl 状态命令已关闭，避免绕过白名单自动回话。

确认走的是哪条路：

```sh
snowluma status                 # supervisor / QQ / SnowLuma / 桥 / 登录状态 / 扫码端口
snowluma doctor                 # 安装、node 解释器、密钥权限、3000/3001/5099、扫码页
readelf -l ~/.cccodroid/snowluma/data/snowluma/node | grep -A1 INTERP
# 应指向 $PREFIX/glibc/lib/ld-linux-aarch64.so.1
ps -ef | grep -E 'Xvfb :99|/opt/QQ/qq|snowluma/index.mjs|bridge.mjs|scrot'
```

## 排查

- **QQ 起不来/扫码页没有二维码**：`snowluma logs 120`（先问用户，日志可能含聊天内容）。
  看 `qq.log` 是否有 `GPU process launch failed`。启动参数已固定为
  `--no-sandbox --disable-dev-shm-usage --disable-gpu`，不要加
  `--in-process-gpu`、`--single-process`、`--disable-gpu-compositing`。
- **扫码页一直黑/没有图**：确认 `snowluma doctor` 里 scrot 存在、Xvfb 在跑；确认
  `$PREFIX/tmp/.X11-unix` 可写。scrot 挂住的话看 Xvfb 是否带了 `-extension MIT-SHM`
  （supervisor 固定带，不要去掉）。
- **反复崩**：`snowluma stop`，删掉
  `~/.cccodroid/snowluma/data/home/.config/QQ/Crashpad` 和 `crash_files` 里的内容
  （不要删整个 `.config/QQ`，那会丢登录态），再 `snowluma start`。
- **扫码后很快又回二维码**：确认这个 QQ 没有在别的设备登录；等 10 分钟风控冷却。
- **SnowLuma 起来了但 QQ 没被注入**：看 `snowluma.log` 里 hook 相关行；确认 QQ 和
  SnowLuma 都是 supervisor 起的（同 uid）；`ps -ef | grep '/opt/QQ/qq'` 确认 QQ 主进程在
  （Electron 子进程带 `--type=`，会被自动跳过，属正常）。
- **OneBot 连不上**：先确认已登录；`snowluma doctor` 会检查 3000/3001。OneBot 的 token
  在 `config.json` 与 `data/snowluma/config/onebot.json` 两处，重装后自动对齐，不要手改单边。
- **WebUI 进不去/忘记密码**：`snowluma webui` 看密码；改过密码以新密码为准。重置：
  停掉后删 `data/snowluma/config/webui.json` 再 start（只丢 WebUI 凭据，不丢登录态）。
- **模型报错**：`bridge.log` 里有 HTTP 状态和响应片段；不要打印密钥。检查
  `baseUrl` 是否包含 `/v1`、模型名是否存在、余额是否足够。
- **端口占用**：OneBot 3000/3001、WebUI 5099、扫码页 8787–8789。用 `snowluma doctor`
  看是哪一项。

## 数据与卸载

- 登录态/缓存：`~/.cccodroid/snowluma/data/home/.config/QQ`
- SnowLuma 运行时与配置：`~/.cccodroid/snowluma/data/snowluma/`（含 `config/`、
  `LICENSE`、`EULA.md`、`PRIVACY.md` 与消息存储）
- 桥配置：`~/.cccodroid/snowluma/config.json`；密钥：同目录 `model-key.txt`
- 日志：`~/.cccodroid/snowluma/logs`
- 卸载组件不会自动删这些数据。要彻底删除，先 `snowluma stop`，再让用户确认后删
  `~/.cccodroid/snowluma`（会丢登录态、SnowLuma 消息存储和配置）。
- 不要把 `config.json`、`model-key.txt`、`onebot.json`、`webui.json` 或登录态拷到共享存储/仓库。
