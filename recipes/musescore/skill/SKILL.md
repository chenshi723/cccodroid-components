---
name: musescore
description: 用 MuseScore 无头排版乐谱（MusicXML/MSCX → PDF/PNG/SVG/MIDI），需要所见即所得版式时用。
---

# MuseScore 4.7（制谱）

## 自检

```sh
musescore-run --selftest
```

最后一行应为 `===== 总结 ===== musescore=OK pdf=OK midi=OK png=OK 版本=MuseScore4Development 4.7.7`
（版本号跟仓库当前的 x11 包走，可能是 4.7.7 而不是计划里的 4.7.6）。

## 运行链路

```
musescore-run（$PREFIX/bin 下的包装脚本）
  → 首次运行：从 Termux 官方仓库取 libicu 79.1（约 10 MB，SHA256 核对）
      解到 $HOME/.cccodroid/musescore/libicu，只放 libicu*.so.79*
  → LD_LIBRARY_PATH 优先指向该目录（底座已有 79 时跳过）
  → 在 $TMPDIR 里找空闲显示号，起 $PREFIX/bin/Xvfb :N（1280×800）
  → $PREFIX/bin/musescore（x11 仓库的 bionic 4.7.x，Qt6）
      → xcb 平台插件连 :N → 排版 → 导出文件
  → 关掉 Xvfb；单页 PNG/SVG 的 -1 后缀改回原名
```

- MuseScore / Qt / Xvfb 由**本组件**提供（x11 仓库）；ICU 79 是首次运行下载到
  私有目录的一份；底座以后自带 79 时跳过。
- 缺 ICU 79：明确报 `libicuuc.so.79 not found`。缺 Xvfb：`✗ 找不到 …/Xvfb`。
- **不要**自己设 `QT_QPA_PLATFORM=offscreen` —— 实测被 MuseScore 的平台选择忽略，
  它仍然去加载 xcb；包装脚本的 Xvfb 才是能用的路。
- 没有屏幕也能跑：Xvfb 是内存里的假显示，不需要 termux-x11 应用。

## 用法

```sh
# MusicXML → PDF
musescore-run -o /data/…/out.pdf /data/…/score.musicxml

# MusicXML → PNG（单页直接是 out.png；多页是 out-1.png、out-2.png…）
musescore-run -o /data/…/out.png /data/…/score.musicxml

# → MIDI（给 music 组件用 fluidsynth 渲染成音频）
musescore-run -o /data/…/out.mid /data/…/score.musicxml

# 一次出多个格式（MuseScore 一次只认一个 -o，循环调用）
for ext in pdf png mid; do musescore-run -o "/data/…/out.$ext" score.musicxml; done
```

MuseScore 的 `-o` 靠扩展名决定格式：`.pdf` / `.png` / `.svg` / `.mid` / `.musicxml` /
`.mscx` / `.mp3` / `.wav`（后两个需要音频导出配置，手机上没有声卡，建议只出 MIDI）。

## 写乐谱

- **MusicXML** 是跨软件的标准格式，AI 生成最稳；最小骨架：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
 <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
 <part id="P1">
  <measure number="1">
   <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
     <time><beats>4</beats><beat-type>4</beat-type></time>
     <clef><sign>G</sign><line>2</line></clef></attributes>
   <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
  </measure>
 </part>
</score-partwise>
```

- **MSCX** 是 MuseScore 自己的文本工程（未压缩的 .mscx；.mscz 是 zip）。从 MuseScore
  导出的 .mscx 改音高/时值最直接，但结构比 MusicXML 复杂；AI 从零生成优先 MusicXML。
- 多声部、和弦、歌词、连音线在 MusicXML 里分别用 `<backup>`/`<chord>`/`<lyric>`/`<tied>`；
  先出单声部验证，再加。
- 中文字体：系统字体通常够；标题/歌词缺字时换字体或转成路径（MuseScore 不直接转曲）。

## 常见坑

- PNG/SVG 多页时文件名带页码；包装脚本只在**单页**时改回原名，多页会打印实际文件名。
- `-o out.pdf` 已存在时 MuseScore 覆盖；批量时注意别把不同曲子写到同一个名字。
- 输入扩展名决定解析器；`.musicxml` / `.xml` 走 MusicXML，`.mscx` 走 MuseScore 工程，
  `.mid`/`.midi` 也能导入但排版信息会丢。
- 首次运行会打印一些 Qt 的 `QCoreApplication::applicationDirPath` 警告，不影响导出。
- 导出大谱（几十页）时等几秒到几十秒；包装脚本没有加超时，卡住时用 `timeout 120` 包一层。
- 检查成品：PDF 看 `%PDF-`，MIDI 看 `MThd`，PNG 看 `\x89PNG`。

## 首次运行

第一次执行 `musescore-run` 会从 Termux 官方仓库下载约 10 MB 的 libicu 79.1。
**先告诉用户**下载多大、从哪下、装到哪，得到同意再跑；之后不再联网。
