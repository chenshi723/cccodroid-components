---
name: haskell
description: Haskell GHC 编译器与 cabal（cccodroid 组件）：编译和运行 Haskell 程序、REPL 求值、管理 Haskell 包。用户提到 Haskell、GHC、cabal、函数式编程时使用。
---

# Haskell（GHC + cabal）

本机已安装 Termux 官方打包的 GHC 9.12（`ghc`、`ghci`、`runghc`）与 cabal（`cabal`）。

## 运行链路

```
ghc / ghci / runghc / cabal（$PREFIX/bin/*，Termux 官方原生 arm64 bionic 程序）
  ├─ 标准库    随 GHC 二进制，无需额外运行时目录
  └─ 临时文件  遵循 $TMPDIR（避免使用系统根下的临时目录）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| `ghc` / `ghci` / `runghc` | Termux `ghc` 包 | `$PREFIX/bin/` |
| `cabal` | Termux `cabal-install` 包 | `$PREFIX/bin/cabal` |

## 常用

```sh
ghc -o prog Main.hs && ./prog          # 编译并运行
runghc script.hs                       # 直接跑脚本（不落产物）
ghc -e 'print (6*7)'                   # 一行求值，无需文件
ghci                                  # 交互式 REPL（:q 退出）
cabal update && cabal build           # 取包索引并构建 cabal 项目
```

## 注意

- 装后约 2.8 GB，装之前先跟用户说清楚体积。
- 首次 `cabal update` 要联网拉 Hackage 索引（体积不小），跑之前告知用户。
- GHC 编译较慢，别拿它做高频热编译循环；一次性编译用 `ghc -O0` 足够。
