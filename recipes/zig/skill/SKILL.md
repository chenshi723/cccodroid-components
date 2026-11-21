---
name: zig
description: Zig 编译器与构建系统（cccodroid 组件）：编写、测试、编译 Zig 项目，以及用 zig cc / zig c++ 做原生或交叉 C/C++ 编译。用户提到 Zig、build.zig 或 zig cc 时使用。
---

# Zig

本机已安装官方 Termux 打包的 Zig 编译器与标准库。

## 运行链路

```
zig（$PREFIX/bin/zig，Termux 官方原生 arm64 bionic 程序）
  ├─ 标准库与内置 libc 头文件  $PREFIX/lib/zig/
  ├─ 全局缓存                  ~/.cache/zig（可通过 ZIG_GLOBAL_CACHE_DIR 覆盖）
  └─ 临时目录                  遵循 $TMPDIR（不要用系统根下的临时目录）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| `zig` 本体与标准库 | Termux `zig` 包 | `$PREFIX/bin/zig`、`$PREFIX/lib/zig/` |
| `zig-selftest` | 本组件自检脚本 | `$PREFIX/bin/zig-selftest` |

## 常用

```sh
zig version                           # 查看版本
zig build                             # 构建 build.zig 工程
zig build test                        # 运行工程测试
zig test foo.zig                      # 运行单文件测试
zig cc -O2 main.c -o main             # 用内置 clang 编译 C 程序
zig build-exe main.zig                # 编译单文件可执行程序
```

- Zig 会在项目目录下创建 `.zig-cache/` 与 `zig-out/`，并在 `~/.cache/zig` 缓存编译产物。
- 若遇到权限或路径问题，确保 `TMPDIR` 指向 `$PREFIX/tmp`。
