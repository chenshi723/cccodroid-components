---
name: lmms
description: 用 LMMS 的无头命令行把 .mmp 工程渲染成 WAV/OGG/MP3（写曲子、合成器、鼓机、采样、效果链）时用。
---

# LMMS 1.2.2（.mmp 工程 → 音频）

## 自检

```sh
lmms --selftest
```

最后一行应为 `===== 总结 ===== lmms=OK wav=OK 版本=LMMS 1.2.2`。
自检会真渲染一小段 TripleOscillator 旋律，并用 ffmpeg 确认不是静音。

## 运行链路

```
lmms（$PREFIX/bin 下的包装脚本）
  → 首次运行：python3 debroot.py 从 Debian 官方仓库下载 183 个包
      （约 109 MB，解开约 417 MB）到 $HOME/.cccodroid/lmms/debroot，
      逐个核对 debs.json 里的 SHA256
  → 每次运行：拼 LD_LIBRARY_PATH（Debian 库 + $PREFIX/glibc/lib）
      设 LMMS_PLUGIN_DIR=debroot/usr/lib/aarch64-linux-gnu/lmms
        （Debian 多架构插件目录；不设的话乐器插件全不加载，渲染全静音）
      设 LMMS_DATA_DIR=debroot/usr/share/lmms、LADSPA_PATH、QT_QPA_PLATFORM=offscreen
      → $PREFIX/glibc/lib/ld-linux-aarch64.so.1（工具包的 glibc）
      → debroot/usr/bin/lmms（Debian lmms 1.2.2）
```

- LMMS 本体和它的依赖由**本组件**提供（首次运行下载）；glibc 由**工具包**提供。
- 渲染不需要声卡：LMMS 的 render-only 模式用 dummy 音频设备驱动混音器，
  再把缓冲写进文件。**也不需要 X / Xvfb**，Qt 走 offscreen。
- 直接用 `debroot/usr/bin/lmms` 或在别处另起一套环境，插件目录会丢 ——
  表现是「渲染成功但全静音」。一律用包装命令。

## 用法

```sh
lmms -r /data/user/0/cc.codroid/files/home/workspace/song.mmp -o /data/user/0/cc.codroid/files/home/workspace/song.wav
lmms -r song.mmp -o song.ogg          # 按扩展名选格式
lmms -r song.mmp -o song.mp3
lmms -r song.mmp -o song.wav -s 48000 # 输出采样率
```

其他参数原样交给 LMMS（`lmms --help` 是本包装脚本的说明；LMMS 自己的选项
见 `lmms -h` 不拦截时同理，常用就是 `-r` 渲染、`-o` 输出、`-f` 格式、`-s` 采样率）。

### 最小 .mmp 工程

LMMS 工程就是 XML；手写时用**未压缩的 `.mmp`**（`.mmpz` 是 gzip，不适合手改）。
最小可渲染骨架：

```xml
<?xml version="1.0"?>
<!DOCTYPE lmms-project>
<lmms-project type="song" version="1.0" creator="LMMS" creatorversion="1.2.2">
  <head timesig_numerator="4" timesig_denominator="4" bpm="120" mastervol="100" masterpitch="0"/>
  <song>
    <trackcontainer visible="1" width="600" height="300" type="song" x="6" y="5" maximized="0" minimized="0">
      <track type="0" muted="0" name="Lead" solo="0">
        <instrumenttrack pitch="0" fxch="0" basenote="57" usemasterpitch="1" pitchrange="1" vol="100" pan="0">
          <instrument name="tripleoscillator">
            <tripleoscillator wavetype0="0" vol0="200" vol1="0" vol2="0" .../>
          </instrument>
          <eldata .../>
          <midiport .../>
          <fxchain numofeffects="0" enabled="0"/>
        </instrumenttrack>
        <pattern len="192" muted="0" name="Lead" steps="16" pos="0" type="1">
          <note len="48" key="60" vol="100" pos="0" pan="0"/>
          <note len="48" key="64" vol="100" pos="48" pan="0"/>
        </pattern>
      </track>
    </trackcontainer>
    <fxmixer ...><fxchannel num="0" muted="0" volume="1" name="Master" soloed="0"><fxchain numofeffects="0" enabled="0"/></fxchannel></fxmixer>
    <timeline lp0pos="0" lp1pos="192" lpstate="0"/>
  </song>
</lmms-project>
```

- `key` 是 MIDI 音符号（60 = C4）；`pos`/`len` 单位是 tick，**192 tick = 1 小节**。
- 一个音轨可以有多个 `<pattern>`；音轨和 pattern 的 `muted="1"` 都会让它不出声。
- 完整可跑的例子就是 `lmms --selftest` 里内联的那份，可以直接抄。
- 更省事的做法：在桌面 LMMS 里存一个模板工程，手机上只改 `<note>` 和 `<head>`。
- 采样类乐器（`audiofileprocessor`）的样本路径**相对于 .mmp 所在目录**；
  把样本和工程放同一目录，换设备也不会丢。

## 常用乐器 / 效果

- `tripleoscillator`：三振荡器，`wavetype` 0=正弦 1=三角 2=锯齿 3=方波；`vol0..2` 0–200。
- `monstro`：FM/加法合成器；`kicker`：底鼓合成器；`audiofileprocessor`：采样器。
- `fxchain` 里放 `delay`、`reverb`（`ladspa` 也行），`numofeffects` 与子元素对应。
- 鼓机用 `type="1"` 的 pattern + `kicker`/采样音轨；每个 pattern 一个 `pos`。

## 常见坑

- **渲染成功但全静音**：99% 是插件目录没指对（直接调 debroot 里的 lmms），或
  音轨/pattern `muted="1"`，或引用的采样文件不存在。用包装命令，先 `--selftest`。
- 输出文件名建议直接带 `.wav`/`.ogg`/`.mp3`，LMMS 按扩展名选编码器；不认识的
  扩展名会退回 WAV。
- 渲染完**必须验证**：`ffmpeg -hide_banner -i out.wav -af volumedetect -f null -`
  看 `mean_volume`，-91 dB 就是全零。
- 工程时长看 `<timeline lp1pos>` 和最后音符；导出会跑到工程末尾，太长的空尾很占空间。
- 采样率不一致时 LMMS 会重采样；`-s 44100` 最稳。
- 别把 `PYTHONHOME` / `LD_PRELOAD` 带进来：包装脚本会清 termux-exec（bionic），
  glibc 加载器不认。

## 首次运行

第一次执行 `lmms` 会从 Debian 官方仓库下载约 109 MB、解开约 417 MB。
**先告诉用户**下载多大、从哪下、装到哪，得到同意再跑；之后不再联网。
