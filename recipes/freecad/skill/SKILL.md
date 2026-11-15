---
name: freecad
description: 用 FreeCAD 的无头命令 freecadcmd 跑 Python 建模脚本，生成或修改 STEP/IGES/STL 模型时用。
---

# FreeCAD 1.0（freecadcmd：Python 建模 → STEP / STL）

## 自检

```sh
freecadcmd --selftest
```

最后一行应为 `===== 总结 ===== freecadcmd=OK step=OK stl=OK 版本=1.0.0`。
自检会 `Part.makeBox(12,8,5)` 造一个实体，导出 STEP 和 STL，再核对体积 480。

## 运行链路

```
freecadcmd（$PREFIX/bin 下的包装脚本）
  → 首次运行：python3 debroot.py 从 Debian 官方仓库下载 338 个包
      （约 367 MB，解开约 1.6 GB）到 $HOME/.cccodroid/freecad/debroot，
      逐个核对 debs.json 里的 SHA256
  → 每次运行：补 usr/lib/freecad/lib → ../freecad-python3/lib 的软链
  → 复制 freecadcmd-python3 为 freecadcmd-cccmd，patchelf 把解释器改成
      $PREFIX/glibc/lib/ld-linux-aarch64.so.1，直接执行（让 /proc/self/exe 指对）
  → LD_LIBRARY_PATH / PYTHONHOME($B/usr) / FREECAD_USER_HOME 只给 FreeCAD 进程
  → debroot/usr/lib/freecad/bin/freecadcmd-cccmd（Debian FreeCAD 1.0.0）
```

- FreeCAD 本体和依赖由**本组件**提供（首次运行下载）；glibc 由**工具包**提供。
- 首次运行还需要工具包里的 **patchelf**（用来改入口的解释器）。缺了包装脚本会
  明确提示 `pkg install patchelf`。
- 不需要屏幕：freecadcmd 是无头入口；包装脚本把 Qt 设成 offscreen，不用 Xvfb。

## 用法

```sh
cat > /data/user/0/cc.codroid/files/home/workspace/make_box.py <<'PY'
import FreeCAD, Part
box = Part.makeBox(12, 8, 5)                 # 长 宽 高，单位 mm
box.exportStep("/data/user/0/cc.codroid/files/home/workspace/box.step")
box.exportStl("/data/user/0/cc.codroid/files/home/workspace/box.stl")
print("VOLUME", box.Volume)
PY

freecadcmd /data/user/0/cc.codroid/files/home/workspace/make_box.py
```

命令行只收**一个 Python 脚本文件**（没有 `-c`）；脚本里的路径写绝对路径。

### 文档对象方式（贴近 GUI 的操作）

```python
import FreeCAD, Part
doc = FreeCAD.newDocument("demo")
obj = doc.addObject("Part::Box", "Box")
obj.Length, obj.Width, obj.Height = 20, 10, 4
obj.Placement.Base = FreeCAD.Vector(0, 0, 0)
doc.recompute()
Part.export([obj], "/abs/out.step")          # STEP
doc.saveAs("/abs/out.FCStd")                 # 存工程，下次 FreeCAD.openDocument()
```

### 常用几何

- `Part.makeBox(l, w, h)`、`Part.makeCylinder(r, h)`、`Part.makeSphere(r)`。
- 布尔：`a.cut(b)`、`a.fuse(b)`、`a.common(b)`；倒角：`shape.makeFillet(r, edges)`。
- 拉伸：`Part.Face(wire).extrude(FreeCAD.Vector(0, 0, h))`。
- 旋转体：`Part.makeRevolution(profile, angle, ...)`。
- 网格：`import Mesh`，`Mesh.Mesh(shape.tessellate(0.1))`，或 `MeshPart`。
- 读 STEP：`import Import; Import.insert("/abs/in.step", doc.Name)`。
- 版本：`FreeCAD.Version()[0:3]`；单位默认 mm。

## 常见坑

- **`No modules found in …/Mod`**：说明绕过包装命令、直接用加载器跑了 Debian 的
  `freecadcmd-python3`。FreeCAD 靠 `/proc/self/exe` 找根目录，经加载器启动时它看到
  的是 ld-linux。用 `freecadcmd` 包装命令。
- `import Part` 成功但 `Part.makeBox` 不存在（`Part.__file__` 是 None）：Python 扩展
  目录没进 `sys.path`。包装脚本用 `usr/lib/freecad/lib` 软链解决；别自己改 debroot。
- 脚本报 `ModuleNotFoundError`：只有 Debian 自带的 Python 3.13 包可见；Termux 的
  `pip install` 包不会出现在 FreeCAD 里。
- 输出目录必须已存在；`exportStep` 不会建多级目录。
- 生成 STEP 后验证：`head -c 14 out.step` 应为 `ISO-10303-21;`。
- FreeCAD 的日志带 ANSI 颜色码，写自己的标记（如 `print("VOLUME", …)`）再 grep。
- 不要 `import FreeCADGui` / `PartGui`：没有 X 显示，headless 入口不加载 GUI 模块。
- 首次安装占 **1.6 GB** 左右，先确认存储空间。

## 首次运行

第一次执行 `freecadcmd` 会从 Debian 官方仓库下载约 367 MB、解开约 1.6 GB。
**先告诉用户**下载多大、从哪下、装到哪、占多少空间，得到同意再跑；之后不再联网。
