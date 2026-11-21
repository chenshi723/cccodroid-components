---
name: lua
description: Lua 5.4 与 LuaJIT 运行时（cccodroid 组件）：运行和检查 Lua 脚本、编字节码（luac5.4）、用 LuaJIT 跑高性能脚本。用户提到 Lua、LuaJIT、游戏脚本或 Neovim/嵌入脚本调试时使用。
---

# Lua 与 LuaJIT

本机已安装官方 Termux 打包的 Lua 5.4（`lua5.4`、`luac5.4`）与 LuaJIT（`luajit`）。

## 运行链路

```
lua5.4 / luac5.4 / luajit（$PREFIX/bin/*，Termux 官方原生 arm64 bionic 程序，无包装脚本）
  ├─ 标准库    内置于二进制，无需额外运行时目录
  └─ 临时文件  遵循 `$TMPDIR`（避免使用系统根下的临时目录）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| `lua5.4` / `luac5.4` | Termux `lua54` 包 | `$PREFIX/bin/lua5.4`、`$PREFIX/bin/luac5.4` |
| `luajit` | Termux `luajit` 包 | `$PREFIX/bin/luajit` |

## 常用

```sh
lua5.4 script.lua                     # 运行 Lua 5.4 脚本
luac5.4 -p script.lua                 # 仅语法检查（不产出 luac.out）
luajit script.lua                     # 用 LuaJIT 运行（兼容 Lua 5.1 + FFI）
lua5.4 -e 'print(_VERSION)'           # 一行求值
```

- 注意：Termux 的 `lua54` 可执行文件名是 `lua5.4`（不是 `lua`），命令里直接写 `lua5.4` 或 `luajit`。
- LuaJIT 语法基于 Lua 5.1 扩展，若脚本使用了 Lua 5.3/5.4 整数除法 `//` 或位运算符，请用 `lua5.4`。
