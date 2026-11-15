---
name: inkscape
description: 用 Inkscape 无头导出或精修 SVG（SVG → PNG/PDF/SVG），调整尺寸、导出选中对象时用。
---

# Inkscape（SVG → PNG / PDF）

## 自检

```sh
inkscape-run --selftest
```

最后一行应为 `===== 总结 ===== inkscape=OK png=OK pdf=OK 版本=Inkscape 1.4.4`。

## 运行链路

```
inkscape-run（$PREFIX/bin 下的包装脚本）
  → 组件安装时已带好 ICU 79：$PREFIX/lib/cccodroid/icu79
      （从 Termux 官方 libicu 79.1 包提取；来源与 SHA256 见 NOTICE）
  → LD_LIBRARY_PATH 优先指向该目录（底座已有 79 时改用底座的）
  → $PREFIX/bin/inkscape（x11 仓库的 bionic 1.4.4）
  → GTK / gspell / Pango / Cairo（x11 仓库，随组件安装）
```

- Inkscape 与 GTK 那一串由**本组件**提供（x11 仓库）；ICU 79 也随组件安装，
  **运行时不联网**。
- 缺 ICU 79 时 **明确报错**：`libicuuc.so.79 not found`，不会出空白图。
  带 `LD_LIBRARY_PATH` 的提示时不要自己拼，直接用 `inkscape-run`。
- 没有显示服务器也能导出：Inkscape 的 `--export-*` 路径不建窗口。**不要**设 `DISPLAY`
  去连一个不存在的 X 服务；连不上时会多刷一屏 GTK 警告，但通常不影响文件导出。

## 用法

```sh
# SVG → PNG（按画布大小）
inkscape-run --export-type=png --export-filename=out.png in.svg

# 指定宽度 / DPI
inkscape-run --export-type=png --export-filename=out.png --export-width=1024 in.svg
inkscape-run --export-type=png --export-filename=out.png --export-dpi=300 in.svg

# SVG → PDF
inkscape-run --export-type=pdf --export-filename=out.pdf in.svg

# 只导出某个对象（对象要有 id）
inkscape-run --export-type=png --export-id=logo --export-id-only --export-filename=logo.png in.svg

# 批量：对目录里每个 SVG 出一张 PNG
for f in *.svg; do inkscape-run --export-type=png --export-filename="${f%.svg}.png" "$f"; done
```

常用开关：

- `--export-area-page` / `--export-area-drawing` / `--export-area-snap` —— 导出范围。
- `--export-background=white` / `--export-background-opacity=255` —— 背景（默认透明）。
- `--export-text-to-path` —— PDF 里把文字转曲（换设备不缺字体）。
- `--query-width` / `--query-height` —— 只量尺寸，不导出。

## 常见坑

- `--export-filename` 不是 `-o` 的别名都能用；老教程里的 `-e` / `-z` 是 0.92 的旧参数，1.x 不认。
- 导出 PNG 默认透明背景；要看白底就加 `--export-background=white`。
- 中文文字要有 CJK 字体；工具包的系统字体（`/system/fonts`）通常够，缺字时先换成路径或换字体。
- 检查成品不要只看文件大小：PNG 看 `\x89PNG`，PDF 看 `%PDF-`。
- 大量导出时每个文件起一次进程，几秒一个；几百个图建议用 `--export-filename` 模板或分批。

## 首次运行

组件安装时已把 ICU 79 一起装好，第一次执行 `inkscape-run` 不联网。
