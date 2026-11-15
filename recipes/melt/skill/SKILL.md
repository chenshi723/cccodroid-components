---
name: melt
description: 用 MLT 的 melt 把 .mlt XML 工程渲染成视频/音频（图片序列、多轨、文字、转场、滤镜）时用。
---

# MLT / melt（.mlt XML → 视频）

## 自检

```sh
melt-run --selftest
```

最后一行应为 `===== 总结 ===== melt=OK qimage=OK mp4=OK 版本=7.42.0`。

## 运行链路

```
melt-run（$PREFIX/bin 下的包装脚本）
  → 组件安装时已带好 ICU 79：$PREFIX/lib/cccodroid/icu79
      （从 Termux 官方 libicu 79.1 包提取；来源与 SHA256 见 NOTICE）
  → LD_LIBRARY_PATH 优先指向该目录（底座已有 79 时改用底座的）
  → 在 $TMPDIR 里找空闲显示号，起 $PREFIX/bin/Xvfb :N
  → $PREFIX/bin/melt（x11 仓库 7.42.0，Qt6 模块 + ffmpeg/avformat）
  → 关掉 Xvfb
```

- melt / MLT / Qt 模块由**本组件**提供（x11 仓库）；ffmpeg 的库由底座提供
  （avformat consumer 走它）。ICU 79 也随组件安装，运行时不联网。
- 缺 ICU 79 时 Qt producer 会 **dlopen 失败**（`libmltqt6.so` 加载不了），
  color / avformat 仍能跑 —— 看着像「qimage 没反应」，实际是 ICU。包装脚本会明确报。
- `libmltplacebo.so` 在本机还会报 `cannot locate symbol "pl_log_create_360"`：
  底座 libplacebo 和 mlt 的构建不一致，**只影响 placebo 滤镜**，不影响 color /
  qimage / qtext / avformat。
- 没有屏幕也能跑：Xvfb 是内存里的假显示，Qt 模块不需要用户真的有显示器。

## .mlt 工程的最小结构

```xml
<?xml version="1.0" standalone="no"?>
<mlt LC_NUMERIC="C" version="7.0.0" title="demo" producer="main_bin">
  <profile description="HD 1280x720 30 fps" width="1280" height="720" progressive="1"
           sample_aspect_num="1" sample_aspect_den="1" display_aspect_num="16"
           display_aspect_den="9" frame_rate_num="30" frame_rate_den="1" colorspace="709"/>

  <producer id="p_img" in="0" out="89">
    <property name="resource">/data/…/frame.png</property>
    <property name="mlt_service">qimage</property>
    <property name="ttl">90</property>
    <property name="aspect_ratio">1</property>
  </producer>

  <producer id="p_color" in="0" out="89">
    <property name="resource">#101828</property>
    <property name="mlt_service">color</property>
  </producer>

  <playlist id="bg">
    <entry producer="p_color" in="0" out="89"/>
  </playlist>
  <playlist id="fg">
    <blank length="30"/>
    <entry producer="p_img" in="0" out="59"/>
  </playlist>

  <tractor id="tractor0" in="0" out="89">
    <track producer="bg"/>
    <track producer="fg"/>
    <transition>
      <property name="a_track">0</property>
      <property name="b_track">1</property>
      <property name="mlt_service">mix</property>
      <property name="sum">1</property>
    </transition>
  </tractor>
</mlt>
```

渲染：

```sh
melt-run project.mlt -consumer avformat:out.mp4 vcodec=libx264 crf=23 an=1
melt-run project.mlt -consumer avformat:out.webm vcodec=libvpx-vp9
melt-run project.mlt -consumer avformat:out.wav acodec=pcm_s16le
```

## 常用 producer / filter

- `color`：纯色背景（`resource` 写 `#rrggbb`）。
- `qimage`：读 PNG/JPEG（`ttl` 是显示帧数；`resource` 是绝对路径）。
- `qtext`：文字（`argument` 是文本，`fgcolour` / `bgcolour` / `olcolour`、`size`、`family`）。
- `avformat`：读视频/音频文件。
- `qtblend` / `mix`：图层叠加；`affine`：缩放/平移/旋转关键帧。
- `brightness`、`volume`、`fadein` / `fadeout`：调色、音量、淡入淡出。
- 每个 producer 的 `in`/`out` 是帧号；`<blank length="N"/>` 插空白。
- 关键帧用 `keyframe` 属性，例如 `<property name="transition.geometry">0=0/0:100%x100%;45=10%/10%:80%x80%</property>`。

## 常见坑

- **时间单位是帧**，不是秒；30 fps 下 1 秒 = 30 帧。profile 不写会和素材不匹配，花屏/拉伸。
- `qimage` 的路径必须是**绝对路径**；相对路径按 melt 的当前目录解析，容易找不到。
- 直接调 `melt` 时 ICU 79 没补，Qt 模块会静默 dlopen 失败；用 `melt-run`。
- `-consumer avformat:out.mp4` 不带 `vcodec` 时可能用默认编码器，兼容性差；显式写 `vcodec=libx264`。
- 输出目录必须先存在；melt 不会替你建多级目录。
- 检查成品用 `ffprobe`：`ffprobe -v error -show_entries stream=codec_name,width,height -of default=nw=1 out.mp4`。

## 首次运行

组件安装时已把 ICU 79 一起装好，第一次执行 `melt-run` 不联网。
