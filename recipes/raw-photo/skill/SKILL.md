---
name: raw-photo
description: 用 darktable-cli 或 RawTherapee 无头处理 RAW / 照片（批量转 JPEG、改尺寸、调色）时用。
---

# RAW 照片处理（darktable + RawTherapee）

## 自检

```sh
raw-photo --selftest
```

最后一行应为 `===== 总结 ===== darktable=OK rawtherapee=OK jpeg=OK …`。

## 运行链路

```
raw-photo（$PREFIX/bin 下的包装脚本）
  → raw-photo darktable：
      首次运行从 Termux 官方仓库取 libicu 79.1（约 10 MB，SHA256 核对）
        → 解到 $HOME/.cccodroid/raw-photo/libicu
        → LD_LIBRARY_PATH 优先指向它（底座已有 79 时跳过）
      → $PREFIX/bin/darktable-cli（x11 仓库 5.6.2，bionic）
  → raw-photo rawtherapee：
      → $PREFIX/bin/rawtherapee-cli（x11 仓库 5.13，bionic；不需要 ICU 79）
```

- 两个引擎由**本组件**提供（x11 仓库）；darktable 要的 ICU 79 是首次运行下载到私有目录
  的一份，不写 `$PREFIX`、不改底座。
- 直接调 `darktable-cli` 会报 `libicui18n.so.79 not found`；**用 `raw-photo darktable`**。
  `rawtherapee-cli` 直接调能用，但建议统一走 `raw-photo rawtherapee`。
- 两个引擎都**不需要显示服务器**，`-i` / `-cli` 路径不建窗口。

## 用法

### darktable

```sh
# 单张：RAW → JPEG（默认参数）
raw-photo darktable /data/…/IMG_0001.CR3 /data/…/out.jpg

# 一批：目录里所有 RAW → JPEG（darktable-cli 一次只收一张，用循环）
for f in /data/…/raw/*.CR3; do
  raw-photo darktable "$f" "/data/…/out/$(basename "${f%.*}").jpg"
done

# 用 XMP 调好的参数
raw-photo darktable --apply-custom-presets /data/…/style.xmp IMG.CR3 out.jpg
```

常用参数：`--width` / `--height`（输出尺寸）、`--hq 0|1`、`--core`（只跑 CPU 核心数）、
`--out-ext jpg|tif|png`。完整列表看 `raw-photo darktable --help`。

### RawTherapee

```sh
# 批量：目录 → 输出目录（默认参数）
raw-photo rawtherapee -o /data/…/out -c /data/…/raw

# 单张 + 指定输出名
raw-photo rawtherapee -o /data/…/out.jpg -c /data/…/IMG.CR3

# 用 PP3 参数
raw-photo rawtherapee -p /data/…/style.pp3 -o /data/…/out -c /data/…/raw
```

常用参数：`-j[1-100]`（JPEG 质量）、`-t[z]`（TIFF）、`-b8|16`（位深）、`-Y`（覆盖已存在文件）、
`-q`（安静）。`rawtherapee-cli -h` 有完整列表。

## 常见坑

- darktable 用默认参数导出时会打印 `no XMP sidecar file…` —— 正常，表示按默认设置出图。
- 输出文件**已存在**时 darktable 会拒绝覆盖；先删目标或换名字。RawTherapee 默认也不覆盖，加 `-Y`。
- 两个引擎的默认色彩/锐化不同，同一张 RAW 出来的 JPEG 不会完全一样；批量前先用一张对比。
- RAW 的相机型号支持取决于 libraw 版本；很新的相机可能要等上游更新。
- 检查成品：JPEG 头 `FF D8 FF`，TIFF 头 `49 49 2A 00` / `4D 4D 00 2A`。
- 首次用 `darktable` 子命令要下载约 10 MB，**先问用户**；之后不再联网。

## 首次运行

第一次执行 `raw-photo darktable`（或 `--selftest`）会从 Termux 官方仓库下载约 10 MB 的
libicu 79.1。**先告诉用户**下载多大、从哪下、装到哪，得到同意再跑。
