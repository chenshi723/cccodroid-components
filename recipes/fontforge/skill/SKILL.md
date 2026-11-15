---
name: fontforge
description: 用 FontForge 脚本造字、改字、批量转换字体（SFD/TTF/OTF/WOFF）时用。
---

# FontForge（造字 / 改字）

## 自检

```sh
fontforge --selftest
```

最后一行应为 `===== 总结 ===== fontforge=OK ttf=OK 版本=20230101`。

## 运行链路

```
fontforge（$PREFIX/bin 下的包装脚本）
  → 首次运行：python3 debroot.py 从 Debian 官方仓库下载 48 个包
      （约 20 MB，解开约 72 MB）到 $HOME/.cccodroid/fontforge/debroot，
      逐个核对 debs.json 里的 SHA256
  → 每次运行：拼 LD_LIBRARY_PATH（Debian 库 + $PREFIX/glibc/lib）
      → $PREFIX/glibc/lib/ld-linux-aarch64.so.1（工具包的 glibc）
      → debroot/usr/bin/fontforge（Debian fontforge-nox 20230101）
```

- FontForge 本体由**本组件**提供（首次运行下载）；glibc 由**工具包**提供。
- 这是 **fontforge-nox**（无 GTK）：没有图形界面，只跑脚本。`-lang=py` 用的 Python
  是 Debian 自带的 3.13，包装脚本已经设好 `PYTHONHOME`；自己再 export 一个
  `PYTHONHOME` 会把它盖掉，报 `Failed to import encodings module`。
- 缺包/缺 glibc 都会**明确报错**；不会悄悄降级。

## 用法

### Python（推荐）

```sh
cat > /data/user/0/cc.codroid/files/home/workspace/make_font.py <<'PY'
import fontforge
f = fontforge.font()
f.fontname = "demo"
f.familyname = "Demo"
f.fullname = "Demo Regular"
f.em = 1000
g = f.createChar(0x41, "A")        # 画一个三角
g.width = 500
pen = g.glyphPen()
pen.moveTo((100, 0)); pen.lineTo((250, 700)); pen.lineTo((400, 0)); pen.closePath()
pen = None
f.generate("/data/user/0/cc.codroid/files/home/workspace/demo.ttf")
PY

fontforge -lang=py -script /data/user/0/cc.codroid/files/home/workspace/make_font.py
```

### FontForge 自己的脚本语言

```sh
fontforge -lang=ff -c 'Open("in.sfd"); SelectAll(); Scale(120, 80); Generate("out.ttf"); Quit(0)'
```

也可以把多行脚本写进 `.pe` 文件，用 `-script file.pe` 跑。

### 常用操作

- `f.generate("out.otf")` / `out.woff` / `out.woff2` —— 按扩展名出格式。
- `f.createChar(码位, "名字")` —— 新建字形；`g.width` 是前进宽度（以 `f.em` 为 1000 时按千分之一 em）。
- `f.fontname` / `f.familyname` / `f.fullname` —— 字体名，生成前至少设这三个。
- `fontforge -lang=ff -c 'Open("x.ttf"); Print(CharCnt()); Quit(0)'` —— 查字形数。
- 批量转换：`for f in *.sfd; do fontforge -lang=ff -c "Open(\"$f\"); Generate(\"${f%.sfd}.ttf\"); Quit(0)"; done`

## 常见坑

- `-script` 收的是**脚本文件**；一行命令用 `-c`。两者不要混。
- 忘记 `Quit(0)` 时脚本模式一般也会退出；但 `-c` 里抛错后退出码可能仍是 0，**要检查产物**。
- Python 模式启动时会打印 `Core python package 'pkg_resources' not found` —— 只是插件发现失败，造字/转换不受影响。
- 生成 TTF 后验证魔数：`head -c 4 out.ttf | od -An -tx1` 应为 `00 01 00 00`。
- 中文字形要在 `f.em = 1000` 的坐标系里画；从现成字体合并时用 `fontforge.open()` 后 `mergeFonts()`，注意先设目标字体的编码。

## 首次运行

第一次执行 `fontforge` 会下载约 20 MB 并解开约 72 MB。**先告诉用户**下载多大、从哪下、
装到哪，得到同意再跑；之后不再联网。
