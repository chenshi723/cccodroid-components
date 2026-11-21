---
name: ruby
description: Ruby 语言运行时与工具链（cccodroid 组件）：运行 Ruby 脚本、rake 任务、bundler 工程管理。用户提到 Ruby、Gemfile、Rakefile 或 Ruby 脚本时使用。
---

# Ruby

本机已安装官方 Termux 打包的 Ruby 运行时及 `gem`、`bundle`、`rake`、`irb`。

## 运行链路

```
ruby / gem / bundle / rake（$PREFIX/bin/*，Termux 官方原生 arm64 bionic 程序）
  ├─ 标准库与默认 gem  $PREFIX/lib/ruby/
  ├─ 用户装的 gem      ~/.local/share/gem 或项目 vendor/bundle
  └─ C 扩展编译        若 gem 含原生扩展，需要工具包的「C/C++ 构建」模块（clang/make）
```

| 这一环 | 由谁提供 | 在哪 |
|---|---|---|
| `ruby` / `gem` / `bundle` / `rake` | Termux `ruby` 包 | `$PREFIX/bin/*` |
| OpenSSL / zlib / libffi 等共享库 | 底座工具包 | `$PREFIX/lib/` |

## 常用

```sh
ruby -v                               # 查看版本
ruby -c script.rb                     # 仅检查语法
ruby script.rb                        # 运行脚本
bundle exec rake                      # 在项目目录运行 Rake 任务
```

- 在无 TTY 环境下不要直接启动交互式 `irb`，改用 `ruby -e '...'` 执行单行表达式。
- 执行 `gem install` 或 `bundle install` 会联网下载三方包，执行前先确认用户意图；含原生 C 扩展的 gem 需要先在扩展页安装工具包的「C/C++ 构建」模块。
