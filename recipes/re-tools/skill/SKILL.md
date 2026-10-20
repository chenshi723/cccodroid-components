---
name: re-tools
description: 二进制分析工具（rizin + binwalk，cccodroid 组件）：看 ELF/.so 架构与节区、反汇编函数、扫描固件里的 zip/gzip/文件系统签名。CTF、分析自己编译的程序或安卓 .so 时使用。
---

# 逆向工具：rizin + binwalk

本机装了 rizin 0.9.1（含 `rz-bin`）和 binwalk 3.1.0（Rust 版）。都没有图形界面，不联网。

## 先自检

```sh
re-tools-selftest
```

最后一行应为 `===== 总结 ===== rizin=OK binwalk=OK scan=OK`，约 0.3 秒。它用 `rz-bin -I` 读自己、`rizin` 反汇编入口、`binwalk` 扫一个自造的 gzip 样本。

## 运行链路

```
rizin / rz-bin        $PREFIX/bin（本组件，Termux 包）
  ├─ 反汇编/分析       capstone（本组件的依赖）
  ├─ 解析辅助          tree-sitter、xxhash、openssl、zlib 等（本组件的依赖）
  └─ 读文件            ELF / .so / 固件；只读，不改被分析文件

binwalk               $PREFIX/bin/binwalk（本组件，Rust 单文件）
  ├─ 签名库            内置 85 种签名（zip、gzip、squashfs、uImage…）
  └─ 提取 -e           只有部分格式内置；zip/文件系统要外部工具（7z、unsquashfs…），本组件不带
```

| 这一环 | 由谁提供 | 缺了会怎样 |
|---|---|---|
| `rizin` / `rz-bin` | 本组件 | 命令不存在 |
| capstone | 本组件的依赖 | rizin 起不来或反汇编失败（不会悄悄换后端） |
| `binwalk` | 本组件 | 命令不存在 |
| binwalk 的外部解压工具 | 不在本组件 | `-e` 对 zip 等格式报 `Failed to spawn external extractor`，但**退出码仍可能是 0**；必须看输出里的 `Extraction ... failed/completed` |
| 网络 | 不需要 | 全程离线 |

- 只读分析：`rizin` 默认不会修改目标文件；不要在分析时加 patch/write 参数。
- `binwalk -e` 会往当前目录写 `extractions/`，并解开不可信内容；先 `cd $TMPDIR`，且不要执行解出来的文件。

## 常用

### 看 ELF / .so 信息（实测）

```sh
rz-bin -I ./hello 2>/dev/null
rz-bin -I /apex/com.android.runtime/lib64/bionic/libc.so 2>/dev/null
```

输出里有 `arch arm`、`bits 64`、`bintype elf`、`machine ARM aarch64`、`os android` 等。
对 clang 编出来的 PIE，stderr 可能提示 `Neither hash nor gnu_hash exist. Falling back to heuristics...`；
这是 rizin 在猜动态符号数量，不影响信息读取。实测 `rz-bin -I` 约 0.06 秒。

### 反汇编一个函数（实测）

```sh
rizin -q -e scr.color=0 -c 'aa; pdf @ main; q' ./hello
rizin -q -e scr.color=0 -c 'aa; afl~main; q' ./hello
```

`pdf @ main` 打出 main 的汇编（实测能看到 `sub sp, sp, 0x20`、`bl sym.add`、`ret`）；
`afl~main` 列出地址。`-e scr.color=0` 去掉颜色，`q` 让它在命令结束后退出。
实测一次反汇编约 0.07 秒。

### 扫描固件样本（实测）

自己拼一个，不要下载来路不明的固件：

```sh
cd "$TMPDIR"
printf 'FIRMWARE HEADER v1\n' > fw.bin
printf 'payload\n' > payload.txt
zip -q payload.zip payload.txt
cat payload.zip >> fw.bin
gzip -c payload.txt >> fw.bin
binwalk fw.bin
```

实测输出：

```
19    0x13   ZIP archive, file count: 1, total size: 264 bytes
283   0x11B  gzip compressed data, original file name: "payload.txt", ...
Analyzed 1 file for 85 file signatures (187 magic patterns) in 15.0 milliseconds
```

只想找某类签名时用 `binwalk -y gzip -- fw.bin` 或 `binwalk --include=gzip fw.bin`。
**`-y` 后面的 `--` 不能省**：实测 `binwalk -y gzip fw.bin` 会把文件名也当成 include 值，直接 panic
（`No target file name specified!`，退出码 101）。`-e` 提取前先看上面的 `Extraction` 行，
zip 在本机没有外部解压器时失败但退出码仍是 0，gzip 能成功。

### 安卓 .so

```sh
rz-bin -I /data/app/.../lib/arm64-v8a/libxxx.so 2>/dev/null
rizin -q -e scr.color=0 -c 'aa; afl~JNI; q' /data/app/.../lib/arm64-v8a/libxxx.so
```

- `.so` 可能是 stripped，函数名只剩 `sym.imp.*` / 地址；这时按字符串或调用点找。
- 读其他应用的文件可能被 Android 权限挡住；先确认路径可读。

## 常见坑

- `binwalk -e` 的退出码不代表提取成功：外部解压器缺失时它打 `failed` 但返回 0。看 `Extraction ... completed/failed`。
- 本组件不带 7z、unsquashfs 等外部解压器；需要时另行安装，不要假设 `-e` 全能解。
- rizin 的 `pdf`/`afl` 输出带颜色和终端控制字符；脚本里用 `-e scr.color=0`，需要纯文本时再过滤。
- `aa` 只是基本分析；复杂二进制用 `aaa` 会更慢，但能识别更多函数。
- 不要对不可信固件直接执行解出来的程序；只在 `$TMPDIR` 里静态分析。
- 反汇编结果依赖架构；aarch64 的 `.so` 不要用 x86 的 objdump 思路硬套。
