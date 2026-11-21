---
name: gleam
description: Gleam 编程语言与 Erlang/BEAM 运行时（cccodroid 组件）：编写、格式化、编译和测试 Gleam 工程（支持 BEAM 与 JavaScript/Node.js 双目标）。用户提到 Gleam、gleam.toml 或 BEAM 函数式开发时使用。
---

# Gleam

本机已安装官方上游静态编译的 `gleam`（arm64 musl）与 Termux 官方打包的 Erlang/BEAM 运行时（`erl`、`escript`）。

## 运行链路

```
gleam（$PREFIX/bin/gleam → $PREFIX/lib/gleam/gleam，上游静态 arm64 musl 二进制）
  ├─ BEAM 目标运行    调用本组件自带的 $PREFIX/bin/erl / escript（Termux erlang 包）
  └─ JS 目标运行      调用底座的 $PREFIX/bin/node（--target javascript）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| `gleam` 编译器 | 上游 GitHub Release（`aarch64-unknown-linux-musl`，核过 SHA256） | `$PREFIX/lib/gleam/gleam`（经 `$PREFIX/bin/gleam` 调用） |
| `erl` / `escript` | Termux `erlang` 包 | `$PREFIX/bin/erl`、`$PREFIX/bin/escript` |
| `node`（JS 目标） | 底座工具包 | `$PREFIX/bin/node` |

## 常用

```sh
gleam --version                       # 查看版本
gleam new myapp                       # 创建新工程（离线只生成骨架）
gleam format --check src              # 检查代码格式
gleam build --no-print-progress       # 编译工程
gleam test --no-print-progress        # 运行测试
gleam run --target javascript         # 使用底座 Node.js 运行 JS 目标
```

- 拉取 Hex.pm 三方依赖（`gleam deps download` / 首次带依赖的 `gleam build`）需要联网，执行前先确认用户需求。
- `gleam` 是静态链接二进制，包装脚本已自动清除 `LD_PRELOAD`，直接调用 `gleam` 即可。
