---
name: rclone
description: rclone（cccodroid 组件）：本地目录、WebDAV、S3、Google Drive 等云存储的 copy / sync / check / 备份。用户要同步、备份、比对文件，或配置网盘远程时使用。
---

# rclone

本机装了 rclone v1.75.2-termux（Termux 官方包，单文件 Go 程序）。本地目录不需要任何配置；WebDAV、S3、网盘需要先建 remote。

## 先自检

```sh
rclone-selftest
```

最后一行应为 `===== 总结 ===== rclone=OK copy=OK check=OK dryrun=OK webdav=present`，约 0.3 秒。用 `$TMPDIR` 里的空配置，不联网、不碰用户配置。

## 运行链路

```
rclone（$PREFIX/bin/rclone，本组件，无包装脚本）
  ├─ 配置文件   ~/.config/rclone/rclone.conf   ← 用户自己建，里面可能有令牌
  ├─ 后端       本地目录 / WebDAV / S3 / Google Drive …
  │             本地后端 = 直接读写文件系统，不联网
  │             WebDAV / 云后端 = 走用户网络（HTTP/HTTPS）
  └─ OAuth      需要 OAuth 的网盘：rclone 监听 127.0.0.1:53682 收授权码
```

| 这一环 | 由谁提供 | 缺了会怎样 |
|---|---|---|
| `rclone` 本体 | 本组件 | 命令不存在 |
| 本地后端 | rclone 内置 | 不需要配置，直接 `rclone copy /a /b` |
| WebDAV 后端 | rclone 内置 | 需要 URL；没配就报 remote not found |
| OAuth 网盘 | 用户自己在终端 `rclone config` 建 | 没建 remote 就没有令牌，命令直接报错；不会悄悄降级 |
| 配置文件 | 用户（`~/.config/rclone/rclone.conf`） | 本地后端不需要；云后端缺了就用不了 |

- 本地到本地是纯文件操作；WebDAV / 网盘才会发网络请求。
- 没有 FUSE 挂载环境（本机没有 `fusermount`），**不要用 `rclone mount`**；用 `copy` / `sync` 落地到目录。
- `rclone config` 是交互式 TUI，Claude 的终端没有 TTY，**让用户自己跑**。

## 安全：配置和令牌

- `rclone.conf` 里可能有网盘令牌、WebDAV 密码。**绝不读取、打印、复制、转述它的内容**：不要 `cat`，不要 `rclone config show`，不要把文件贴进对话或提交到仓库。
- 只读 remote 名字：`rclone listremotes`。要看目录用 `rclone lsd remote:` / `rclone ls remote:path`，这些不输出令牌。
- 不要向用户索要令牌或密码。需要密码时让用户在 `rclone config` 里输入；**不要把密码写进命令行参数**（会进 shell 历史/进程列表）。
- Claude 自己测试时用隔离配置：`rclone --config "$TMPDIR/empty.conf" ...`，不要指向用户的 `rclone.conf`。

## 常用

### 本地目录 copy / check / sync（实测）

```sh
rclone copy /path/src /path/dst -v          # 只增改，不删目标多余文件
rclone check /path/src /path/dst --checksum # 0 differences found 才算一致
rclone sync /path/src /path/dst --dry-run -v  # 先看会删什么
rclone sync /path/src /path/dst -v          # 真同步：目标多余文件会被删
rclone size /path/dst
```

实测：3 个文件、20 MiB，本地 `copy` 约 0.10 秒；`check --checksum` 输出 `0 differences found`；
删掉源端一个文件后 `sync --dry-run` 输出 `Skipped delete as --dry-run is set`，目标文件仍在。

### WebDAV（实测，回环）

建一个不需要账号的 WebDAV remote（URL 不是秘密；有账号密码时让用户用交互式 `rclone config`）：

```sh
rclone config create mywebdav webdav url=https://example.com/dav vendor=other
rclone listremotes
rclone lsd mywebdav:
rclone copy /path/src mywebdav:backup -v --dry-run
rclone copy /path/src mywebdav:backup -v
rclone check /path/src mywebdav:backup --size-only
```

- WebDAV 服务端通常不提供哈希，`rclone check` 会提示 `No common hash found`，只能按大小/修改时间比；用 `--size-only` 明确这一点。
- 本机自测可以用 `rclone serve webdav` 起一个只监听回环的服务：

```sh
rclone serve webdav --addr 127.0.0.1:8080 /path/to/share
RCLONE_WEBDAV_URL=http://127.0.0.1:8080 RCLONE_WEBDAV_VENDOR=other rclone lsd :webdav:
```

  不带 `--htpasswd` 时该服务**没有认证**；只绑 `127.0.0.1`，不要绑到局域网/公网。
  实测回环 `copy` / `check` / `ls` 都通过（2 个文件约 0.11 秒）。

### OAuth 网盘（Google Drive、OneDrive 等）

这一步必须用户自己做，Claude 不碰令牌：

1. 用户在 cccodroid 终端运行 `rclone config`，选 `n` 新建 remote，选 `drive` / `onedrive` 等；
2. 授权方式选自动（auto config），rclone 会打印 `http://127.0.0.1:53682/auth?...`；
3. 用户在 App 内浏览器打开这个地址（本机实测该本地页面可达，返回 307 跳转到 Google 登录），完成登录；
4. 回调回到 127.0.0.1:53682，rclone 把令牌写进 `rclone.conf`。

- **没有账号，未做完整授权**；只验证了监听端口能起、回环页面能打开。实际登录是否顺利取决于网络和浏览器。
- 回调端口固定 53682；如果被占用，先结束别的 `rclone authorize` / `rclone config`。
- 浏览器打不开时，让用户手动复制终端里的本地 URL，不要由 Claude 代开、代贴授权码。
- 建好后 Claude 只用 remote 名字，例如 `rclone lsd gdrive:`；仍然不许读配置。

### 备份工作区

```sh
rclone copy /data/user/0/cc.codroid/files/home/workspace backup:cccodroid/workspace --dry-run -P
rclone copy /data/user/0/cc.codroid/files/home/workspace backup:cccodroid/workspace -P
rclone check /data/user/0/cc.codroid/files/home/workspace backup:cccodroid/workspace --size-only
```

先 `--dry-run` 把要传/要删的清单给用户看，确认后再真跑。目标端已有旧版本时，`copy` 不会删除多余文件；要镜像才用 `sync`，并明确告诉用户它会删目标端多余文件。

## 常见坑

- `rclone sync` 会删除目标端源端没有的文件；**永远先 `--dry-run`**，尤其是网盘。
- `rclone check` 在 WebDAV/部分网盘上没有哈希，`--checksum` 会提示无法校验；改用 `--size-only`，并说明只是大小一致。
- `rclone config` 是交互式 TUI，不要在 Claude 的 Bash 里跑；没有 TTY 会卡住。
- 配置里的令牌过期后，命令会报 401；让用户自己重新运行 `rclone config` 修那个 remote，不要试图读取/修改配置文件。
- 不要把 WebDAV 密码写在命令行；用交互式配置。
- 本机没有 FUSE，`rclone mount` 不适用。
