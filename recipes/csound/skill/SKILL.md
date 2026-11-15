---
name: csound
description: 用 Csound 写文本乐谱（.csd）并渲染成 WAV —— 合成音色、算法作曲、生成音效时用。
---

# Csound（.csd → WAV）

## 自检

```sh
csound --selftest
```

最后一行应为 `===== 总结 ===== csound=OK wav=OK 版本=6.18`。失败时先看首次安装有没有报错。

## 运行链路

```
csound（$PREFIX/bin 下的包装脚本）
  → 首次运行：python3 debroot.py 从 Debian 官方仓库下载 34 个包（约 15 MB，解开约 35 MB）
      装到 $HOME/.cccodroid/csound/debroot，逐个核对 debs.json 里的 SHA256
  → 每次运行：拼 LD_LIBRARY_PATH（Debian 库 + $PREFIX/glibc/lib）
      → $PREFIX/glibc/lib/ld-linux-aarch64.so.1（工具包的 glibc 2.44）
      → debroot/usr/bin/csound（Debian 6.18.1）
```

- Csound 本体和 opcode 插件由**本组件**提供（首次运行下载）；glibc 运行时由**工具包**
  提供（`$PREFIX/glibc`）。缺 glibc 时包装脚本直接报「找不到 glibc 加载器」，不会静默降级。
- 缺 opcode 插件时 Csound 不一定立刻报错：`--version` 照样 0，复杂 .csd 才报
  `unknown opcode`。包装脚本已经设好 `OPCODE6DIR64`，不要自己覆盖。
- 实时播放（`-odac`）在手机上没有可用的声卡路由，通常静默失败或走 null 设备；
  **只承诺写文件**（`-o out.wav`）。

## 用法

AI 写 .csd，Csound 出 WAV：

```sh
cat > /data/user/0/cc.codroid/files/home/workspace/score.csd <<'CSD'
<CsoundSynthesizer>
<CsOptions>
-o out.wav
</CsOptions>
<CsInstruments>
sr = 44100
ksmps = 32
nchnls = 2
0dbfs = 1

instr 1
  ; 两个正弦叠成五度，1 秒，指数衰减
  a1 oscil 0.25, 440, 1
  a2 oscil 0.15, 660, 1
  aenv expseg 1, 1, 0.001
  outs a1 * aenv, a2 * aenv
endin
</CsInstruments>
<CsScore>
f 1 0 4096 10 1
i 1 0 1
</CsScore>
</CsoundSynthesizer>
CSD

csound -o out.wav score.csd
```

常用开关：

- `-o out.wav` / `-o out.aiff` —— 输出文件；不写就只检查不渲染。
- `--format=wav` / `--format=flac` —— 输出格式。
- `-W` —— 输出 WAV 而不是 AIFF（老版本习惯；新版看扩展名）。
- `-m 128` —— 降低零振幅错误信息的级别。
- `-d` —— 不显示波形图。

## 常见坑

- **.csd 是 XML 外壳**：`<CsInstruments>` 里定义乐器，`<CsScore>` 里放事件；两段都不能少。
- 采样率、声道数写在 `sr` / `nchnls`，音频函数按这些值算；`0dbfs = 1` 表示幅度以 1.0 为满刻度。
- 渲染完看退出码和 WAV 头，不要只看「文件在不在」：`head -c 4 out.wav` 应为 `RIFF`。
- 默认输出时长由谱面最后一条事件决定；要固定长度就在最后加 `e 2`（2 秒后结束）。
- 不要用 `-odac` 做「试听」；手机没有声卡输出路由，成品写 WAV 后用应用内播放器听。

## 首次运行

第一次执行 `csound` 会下载约 15 MB 并解开约 35 MB。**先告诉用户**下载多大、从哪下、
装到哪，得到同意再跑；之后不再联网。
