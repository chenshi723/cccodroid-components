---
name: gimp
description: 用 GIMP 3 的 Python-Fu 无头批量修图（图层、选区、滤镜、加字、导出）时用。
---

# GIMP 3.2（无头 Python-Fu）

## 自检

```sh
gimp-batch --selftest
```

最后一行应为 `===== 总结 ===== gimp=OK python-fu=OK png=OK 版本=3.2.8`。

## 运行链路

```
gimp-batch（$PREFIX/bin 下的包装脚本）
  → $PREFIX/bin/gimp -i -d -f -c --quit --batch-interpreter=python-fu-eval -b - < 脚本
      → GIMP 3.2.8（x11 仓库，bionic）
      → python-eval 插件（$PREFIX/lib/gimp/3.0/plug-ins/python-eval）
      → $PREFIX/bin/python3（工具包的 Python 3.14）+ PyGObject / Gimp 3 GI 绑定
```

- GIMP、Python-Fu 插件、PyGObject 都由**本组件**提供（x11 仓库）；Python 解释器由
  **工具包**提供。缺 python3 时 python-fu-eval 启动失败并明确报错。
- `-i -d -f` 跳过界面、画笔/渐变、字体加载；`--quit` 让批处理跑完退出。
  **不要**去掉 `--quit`：GIMP 会留在后台，Bash 命令永远不返回。
- 没有显示服务器也能跑：`-i` 不建窗口，不需要 Xvfb。

## 用法

`gimp-batch` 收一个 Python 脚本路径（或 `-` 从 stdin 读），其余参数原样交给 GIMP。

```sh
cat > /data/user/0/cc.codroid/files/home/workspace/edit.py <<'PY'
import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl, Gio

SRC = "/data/user/0/cc.codroid/files/home/workspace/in.jpg"
OUT = "/data/user/0/cc.codroid/files/home/workspace/out.png"

img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(SRC))
img.scale(800, 800)                       # 等比缩到长边 800
layer = img.get_active_layer()
Gimp.context_set_foreground(Gegl.Color.new("#ffffff"))
layer.edit_fill(Gimp.FillType.FOREGROUND) # 这里只是示例；真实脚本按需操作
Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, Gio.File.new_for_path(OUT), None)
print("DONE")
PY
gimp-batch /data/user/0/cc.codroid/files/home/workspace/edit.py
```

从零画图（自检就是这么做的）：

```python
img = Gimp.Image.new(128, 96, Gimp.ImageBaseType.RGB)
layer = Gimp.Layer.new(img, "bg", 128, 96, Gimp.ImageType.RGBA_IMAGE,
                       100.0, Gimp.LayerMode.NORMAL)
img.insert_layer(layer, None, 0)
Gimp.context_set_foreground(Gegl.Color.new("#3380e6"))
layer.edit_fill(Gimp.FillType.FOREGROUND)
Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img,
               Gio.File.new_for_path("/data/…/out.png"), None)
```

常用：

- `Gimp.file_load(run_mode, Gio.File)` —— 打开图片；返回 `Gimp.Image`。
- `img.scale(w, h)` / `img.crop(w, h, offx, offy)` / `img.flip(orientation)`。
- `img.get_layers()`、`img.insert_layer(layer, parent, position)`、`layer.set_opacity()`。
- `Gimp.context_set_foreground(Gegl.Color.new("#rrggbb"))`，`layer.edit_fill(...)`。
- `Gimp.file_save(run_mode, image, Gio.File, options)` —— 按扩展名选导出插件；
  `options=None` 用默认参数。
- 滤镜：`Gimp.get_pdb().run_procedure("gimp-drawable-brightness-contrast", [...])`，
  参数用 `Gimp.ValueArray` 拼。

## 常见坑

- **模块名是 `Gimp`（大写）**；GIMP 2 教程里的 `import gimp`、`pdb.gimp_image_new` 在 3.x 全不适用。
- **不要在脚本里调 `Gimp.quit()`**：批处理解释器会报 `Procedure 'python-fu-eval' returned no
  return values`，退出码不可靠。退出交给命令行的 `--quit`（`gimp-batch` 已经加了）。
- `Gegl.RGBA(...)` 没有暴露给 Python；用 `Gegl.Color.new("#3380e6")`。
- 直接调 `gimp` 时要自己带 `-i -d -f -c --quit --batch-interpreter=python-fu-eval -b -`；
  少一个就可能卡住。用 `gimp-batch` 更稳。
- GIMP 启动时会打印 `The catalog directory does not exist: …/share/locale` 和
  `Localization disabled` —— 无头环境下正常，不影响导出。
- 输出文件已存在时 `file_save` 默认覆盖；批量时先删旧文件或改名字。
- GIMP 的配置写到 `$HOME/.cccodroid/gimp/home`，不和用户的 GIMP 配置混在一起。

## 首次运行

组件已把 GIMP 和 Python-Fu 打进包，首次运行不下载东西，直接可用。
