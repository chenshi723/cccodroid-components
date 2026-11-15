---
name: kicad
description: 用 kicad-cli 无头处理 KiCad 工程：Gerber、钻孔、SVG/PDF/DXF、网表、BOM、ERC/DRC 时用。
---

# KiCad 9.0（kicad-cli：PCB → Gerber / 钻孔 / 图纸）

## 自检

```sh
kicad-cli --selftest
```

最后一行应为 `===== 总结 ===== kicad-cli=OK gerber=OK drill=OK 版本=9.0.2`。
自检手写一块最小 `.kicad_pcb`，导出 Gerber 和 Excellon 钻孔，核对文件与 M48 头。

## 运行链路

```
kicad-cli（$PREFIX/bin 下的包装脚本）
  → 首次运行：python3 debroot.py 从 Debian 官方仓库下载 264 个包
      （约 181 MB，解开约 817 MB）到 $HOME/.cccodroid/kicad/debroot，
      逐个核对 debs.json 里的 SHA256
  → 每次运行：复制 debroot/usr/bin/kicad-cli 为 kicad-cli-cccmd，
      patchelf 把解释器改成 $PREFIX/glibc/lib/ld-linux-aarch64.so.1，直接执行
      （让 /proc/self/exe 指回 debroot/usr/bin，旁边的 _pcbnew.kiface 才能加载）
      设 KICAD_STOCK_DATA_HOME=debroot/usr/share/kicad（schemas 等数据）
  → LD_LIBRARY_PATH 只在 exec 时给 KiCad，不 export
```

- KiCad 本体和依赖由**本组件**提供（首次运行下载）；glibc 由**工具包**提供。
- 首次运行还需要工具包里的 **patchelf**；缺了包装脚本会提示 `pkg install patchelf`。
- 不需要屏幕：全部走 `kicad-cli`，不加载 GUI、不用 Xvfb。
- **不含符号库 / 封装库 / 3D 模型库**（kicad-symbols、kicad-footprints、
  kicad-packages3d 太大）。出 Gerber/钻孔/图纸不需要它们。

## 用法

```sh
# Gerber：-o 是目录，输出文件名由板子文件名派生
kicad-cli pcb export gerbers -o /data/user/0/cc.codroid/files/home/workspace/gerbers /data/user/0/cc.codroid/files/home/workspace/board.kicad_pcb

# Excellon 钻孔：-o 目录，带结尾斜杠更明确
kicad-cli pcb export drill -o /data/user/0/cc.codroid/files/home/workspace/drills/ /data/user/0/cc.codroid/files/home/workspace/board.kicad_pcb

# 图纸（SVG / PDF / DXF），--layers 逗号分隔
kicad-cli pcb export svg -o /abs/board.svg --layers F.Cu,B.Cu,Edge.Cuts /abs/board.kicad_pcb
kicad-cli pcb export pdf -o /abs/board.pdf --layers F.Cu,Edge.Cuts /abs/board.kicad_pcb
kicad-cli pcb export dxf -o /abs/outline.dxf --layers Edge.Cuts /abs/board.kicad_pcb

# 贴片坐标（pick & place）
kicad-cli pcb export pos -o /abs/pos.csv /abs/board.kicad_pcb

# DRC 报告
kicad-cli pcb drc -o /abs/drc.rpt /abs/board.kicad_pcb

# 原理图：网表 / BOM / ERC
kicad-cli sch export netlist -o /abs/out.net /abs/schematic.kicad_sch
kicad-cli sch export bom -o /abs/bom.csv /abs/schematic.kicad_sch
kicad-cli sch erc -o /abs/erc.rpt /abs/schematic.kicad_sch
```

`kicad-cli --version` 打印 `9.0.2`；子命令帮助用 `kicad-cli pcb export --help`。

### 最小 .kicad_pcb（手写板子）

```scheme
(kicad_pcb (version 20240108) (generator pcbnew)
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
  (setup (pad_to_mask_clearance 0))
  (gr_rect (start 10 10) (end 60 40)
    (stroke (width 0.1) (type solid)) (fill none) (layer "Edge.Cuts"))
  (footprint "Test:Test" (layer "F.Cu") (at 30 25)
    (fp_rect (start -5 -5) (end 5 5)
      (stroke (width 0.1) (type solid)) (fill none) (layer "F.CrtYd"))
    (pad "1" thru_hole circle (at 0 0) (size 2 2) (drill 1) (layers "*.Cu" "*.Mask"))
  )
)
```

- 单位是 mm；`Edge.Cuts` 上的图形定义板框，没有板框也能出 Gerber 但没有外形。
- 层号：0 = F.Cu，31 = B.Cu，44 = Edge.Cuts（还有 F.SilkS 37、B.SilkS 38 等）。
- `footprint` 可以内嵌全部图形和焊盘，不依赖外部封装库。
- 出 Gerber 时默认按板子实际用到的层；要固定层用 `--layers`。

## 需要官方符号库 / 封装库时

本组件没打包（体积以 GB 计）。需要时从 KiCad 官方库取（GitHub 的
`KiCad/kicad-symbols`、`KiCad/kicad-footprints`、`KiCad/kicad-packages3d`），
解到一个目录，然后给 kicad-cli 指路（KiCad 9 的前缀是 `KICAD9_`）：

```sh
export KICAD9_SYMBOL_DIR=/abs/kicad-symbols
export KICAD9_FOOTPRINT_DIR=/abs/kicad-footprints
export KICAD9_3DMODEL_DIR=/abs/kicad-packages3d
```

这些是 KiCad 的「路径变量」，导出网表/封装/3D STEP 时会读。**不要覆盖
`KICAD_STOCK_DATA_HOME`** —— 那是包装脚本用来指 debroot 的自带数据的。

## 常见坑

- **`Failed to load kiface library '/…/glibc/lib/_pcbnew.kiface'`**：说明绕过包装命令、
  直接用 glibc 加载器跑了 Debian 的 kicad-cli。KiCad 按 `/proc/self/exe` 的目录找 kiface，
  经加载器启动时看到的是 ld-linux。用 `kicad-cli` 包装命令。
- **`schema file '/usr/share/kicad/schemas/…' not found`**：同上，绕过包装脚本后
  `KICAD_STOCK_DATA_HOME` 没设。用包装命令。
- 输出目录要先建好；Gerber 的 `-o` 是**目录**，不是文件名。
- 文件名派生：输入 `board.kicad_pcb` → `board-F_Cu.gtl`、`board-B_Cu.gbl`、
  `board-Edge_Cuts.gm1`、`board.drl`、`board-job.gbrjob`。
- 板子里引用了不存在的封装库只会在加载时警告，内嵌图形和焊盘照常出图；
  但如果封装根本没内嵌，Gerber 里就是空的 —— 检查输出文件大小。
- `pcb export step` 需要 3D 模型库（kicad-packages3d），没装时只有板基/焊盘。
- DRC/ERC 的报告文件名用 `-o` 指定；报告里 `** Found N DRC violations **` 可 grep。
- 首次安装占 **817 MB** 左右；运行根和缓存都在应用私有目录。

## 首次运行

第一次执行 `kicad-cli` 会从 Debian 官方仓库下载约 181 MB、解开约 817 MB。
**先告诉用户**下载多大、从哪下、装到哪、占多少空间，得到同意再跑；之后不再联网。
