---
name: octave
description: GNU Octave（cccodroid 组件）：MATLAB 兼容的命令行数值计算——矩阵运算、解线性方程、特征值、无头画 PNG/SVG 图。用户要跑 .m 脚本、做数值计算、或让 Octave/gnuplot 出图时使用。
---

# GNU Octave

本机装了 GNU Octave 11.3.0（Termux 官方包，CLI 版）和 gnuplot 6.0.5。没有图形界面；画图走 gnuplot 的无头终端。

## 先自检

```sh
octave-selftest
```

真机最后一行是 `===== 总结 ===== octave=OK matrix=OK plot=OK fonts=CJK`；没有系统 CJK 字体的环境（如 CI）是 `fonts=ASCII`。约 2 秒。

## 运行链路

```
octave-cli / octave    $PREFIX/bin/octave-cli → octave-cli-11.3.0（本组件，Termux 包）
  ├─ 数学库    libopenblas、suitesparse、arpack-ng、qrupdate-ng…（本组件的依赖，随组件安装）
  ├─ 画图      graphics_toolkit('gnuplot') → $PREFIX/bin/gnuplot（本组件）
  │              └─ print -dpngcairo / -dsvg → cairo + fontconfig → /system/fonts（真机）
  └─ 包系统    pkg install -forge → 下载源码现场编译（需要 make / clang / Fortran）
```

| 这一环 | 由谁提供 | 缺了会怎样 |
|---|---|---|
| `octave-cli` 本体 | 本组件 | 命令不存在 |
| gnuplot | 本组件（root） | Octave 只有 gnuplot 一个后端；没有它 `print` 直接报错，不会出图 |
| cairo 终端 | gnuplot 自身（编译时带 cairo） | `-dpngcairo` 报 unknown terminal；`-dpng` 还能用，但**中文会静默丢失** |
| 中文字体 | 底座 fontconfig 读 `/system/fonts` | 没有字体时中文缺字；`-dpngcairo` 不会报错，只能看图确认 |

- 没有 X11 / 显示服务：**不要**开 `figure` 等窗口，一律 `figure('visible','off')` + `print`。
- `-dpng` 走 libgd，不走 fontconfig：中文标题会整个消失，xlabel 的「轴」也只剩 `x`。**中文一律 `-dpngcairo`（位图）或 `-dsvg`（矢量）**。
- Octave 启动会提示 gnuplot toolkit "discouraged"；这是唯一可用的后端，忽略即可。

## 常用

### 非交互跑脚本

```sh
octave-cli --quiet --no-gui --norc calc.m
octave-cli --quiet --no-gui --norc --eval "disp(version)"
```

- `--norc` 不读 `~/.octaverc`，结果可复现。需要用户装的包时，在脚本里 `pkg load <包名>`。
- 出错时退出码非 0（实测 `error('boom')` → 1），但别用管道判断成败（管道会吞掉退出码）。
- **脚本不要叫 `plot.m` / `disp.m` 这类核心函数名**：实测 `plot.m` 会 shadow 内置 `plot`，脚本一调用自己就报 `invalid call to script`。

### 矩阵与解方程（实测）

```sh
octave-cli --quiet --no-gui --norc --eval "A=[1 2;3 4]; b=[5;11]; x=A\b; disp(x); disp(det(A)); disp(eig(A))"
```

输出 `x = 1, 2`、`det = -2`、`eig = -0.3723, 5.3723`。一次启动约 0.35 s；跑上面的 `calc.m` 脚本约 0.36 s。

### 无头出图（实测）

写 `demo_plot.m`：

```matlab
graphics_toolkit('gnuplot');
f = figure('visible', 'off');
plot(1:10, (1:10).^2);
title('中文标题：苹果香蕉');
xlabel('x 轴');
print(f, '-dpngcairo', '-r150', '/绝对路径/plot.png');
print(f, '-dsvg', '-r150', '/绝对路径/plot.svg');
close(f);
```

```sh
octave-cli --quiet --no-gui --norc demo_plot.m
```

- 实测（真机，有 Noto CJK）：PNG 418×314、13,069 字节；SVG 10,530 字节，里面能直接 grep 到「中文标题」；耗时约 1.7 s。
- 同一张图把 `-dpngcairo` 换成 `-dpng`：标题整个不见，xlabel 只剩 `x` —— 不要用。
- 输出写绝对路径，相对路径会落在当前工作目录。
- 会打印 `WARNING: linker: Warning: unable to normalize "11.3.0"`（Termux 包的 epoch 进了 rpath）和 `text_renderer: skipping missing glyph`（pngcairo 的字体回退先试了缺字字体）。两者都无害，**以生成的图片为准**。

### forge 包：signal / control 不可用

`pkg install -forge` 会从 packages.octave.org 下载源码现场编译。本机实测：

- `signal`：直接失败，`signal needs control >= 2.4`。
- `control`：下载 control 4.2.3 后，在 slicot 的 Fortran 编译处失败——`mkoctfile` 调 `flang-new`，本机没有这个命令（`sh: flang-new: inaccessible or not found`，make 退出）。
- `mkoctfile -p` 显示 `F77=flang-new`、`FC=`；仓库没有 gfortran。`flang` 包能提供 `flang-new`，但下载 62 MB / **解开 920 MB**，本组件不带。
- 结论：**本组件不支持 control / signal**。用户真要，得自己 `pkg install flang` 后重试；体积很大，本组件没有验证那条路。不要把 `pkg install -forge` 说成「装上就能用」。

## 常见坑

- 用 `octave-cli`，或至少给 `octave` 加 `--no-gui`；这个构建没有 GUI。
- 启动的 linker 警告是 Termux 包装配时 rpath 带 epoch 造成的，不是组件坏了；不想看就重定向 stderr。
- `pkg install -forge` 会往当前目录下载源码包，构建临时目录在 `$TMPDIR/oct-*`；失败后可能留下，记得清。
- MATLAB 专有工具箱（Simulink、Image Processing Toolbox 等）的代码跑不了；Octave 只兼容语言和核心函数。
- 大矩阵先从小规模试，注意手机内存。
