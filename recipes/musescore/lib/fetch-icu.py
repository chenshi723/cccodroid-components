#!/usr/bin/env python3
"""取 Termux 官方的 libicu 79.1，只解出 libicu*.so.79* 放进组件私有目录。

背景：底座（devkit-2026.10.28）里的 ICU 是 78.3，而 x11 仓库这批二进制
（Qt / GTK 那一串）是按 ICU 79 构建的。组件不会覆盖底座里的包，所以 78 会
一直留在原位；这里把 79 取到组件自己的目录，运行时用 LD_LIBRARY_PATH 优先。
底座以后升到 79 时，包装脚本会直接跳过，不再下载。

用法: fetch-icu.py <目标目录>
  已经取过（目标目录里有 libicuuc.so.79）就直接退出 0。
"""
import gzip
import hashlib
import io
import lzma
import os
import sys
import tarfile
import time
import urllib.request

VERSION = "79.1"
DEB = f"libicu_{VERSION}_aarch64.deb"
SHA256 = "83c980a010e957738e3567127801d66a1b9bd7e404a4fda98788048ee57d606c"
SIZE = 10312036
MIRRORS = [
    "https://packages-cf.termux.dev/apt/termux-main/",
    "https://packages.termux.dev/apt/termux-main/",
    "https://grimler.se/termux/termux-main/",
]
SUBDIR = "pool/main/libi/libicu/"


def http_get(url, timeout=120, tries=4):
    req = urllib.request.Request(url, headers={"User-Agent": "cccodroid-creative/1"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                                     # noqa: BLE001
            if "CERTIFICATE" in str(e) or i == tries - 1:
                raise
            print(f"    网络中断，{2 ** i}s 后重试：{e}", file=sys.stderr)
            time.sleep(2 ** i)


def ar_members(buf):
    if buf[:8] != b"!<arch>\n":
        raise ValueError("不是 ar 归档")
    off = 8
    while off + 60 <= len(buf):
        hdr = buf[off:off + 60]
        name = hdr[:16].decode("utf-8", "replace").strip().rstrip("/")
        try:
            size = int(hdr[48:58].decode().strip())
        except ValueError:
            break
        yield name, buf[off + 60:off + 60 + size]
        off += 60 + size + (size % 2)


def tar_stream(name, blob):
    if name.endswith(".xz"):
        return lzma.LZMAFile(io.BytesIO(blob))
    if name.endswith(".gz"):
        return gzip.GzipFile(fileobj=io.BytesIO(blob))
    if name.endswith(".zst"):
        try:
            from compression import zstd                       # Python 3.14+
            return io.BytesIO(zstd.decompress(blob))
        except ImportError:
            import zstandard
            return io.BytesIO(zstandard.ZstdDecompressor().decompress(blob))
    return io.BytesIO(blob)


def main():
    if len(sys.argv) != 2:
        print("用法: fetch-icu.py <目标目录>", file=sys.stderr)
        return 2
    dest = os.path.abspath(sys.argv[1])
    if os.path.exists(os.path.join(dest, "libicuuc.so.79")):
        print(f"  libicu {VERSION}：已有，跳过下载")
        return 0
    os.makedirs(dest, exist_ok=True)
    print(f"  libicu {VERSION}：首次运行需要下载 {SIZE / 1048576:.0f} MB（Termux 官方仓库），逐个核对 SHA256")
    blob = None
    for mirror in MIRRORS:
        try:
            blob = http_get(mirror + SUBDIR + DEB)
            break
        except Exception as e:                                     # noqa: BLE001
            print(f"    镜像不可用 {mirror}: {e}", file=sys.stderr)
    if blob is None:
        print("  ✗ 所有镜像都下载失败", file=sys.stderr)
        return 1
    got = hashlib.sha256(blob).hexdigest()
    if got != SHA256:
        print(f"  ✗ SHA256 不符（应为 {SHA256[:16]}… / 实得 {got[:16]}…）", file=sys.stderr)
        return 1
    n = 0
    for name, data in ar_members(blob):
        if not name.startswith("data.tar"):
            continue
        tf = tarfile.open(fileobj=tar_stream(name, data), mode="r|")
        for m in tf:
            rel = m.name.lstrip("./").lstrip("/")
            base = os.path.basename(rel)
            if "/lib/" not in "/" + rel or not (base.startswith("libicu") and ".so.79" in base):
                continue
            if ".." in rel.split("/"):
                continue
            dst = os.path.join(dest, base)
            if m.issym():
                if os.path.lexists(dst):
                    os.remove(dst)
                os.symlink(m.linkname, dst)                        # 包里的软链是相对名（libicuuc.so.79 → .79.1）
                continue
            if not m.isfile():
                continue
            with open(dst, "wb") as out:
                src = tf.extractfile(m)
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
            os.chmod(os.path.join(dest, base), 0o755)
            n += 1
        tf.close()
        break
    if not os.path.exists(os.path.join(dest, "libicuuc.so.79")):
        print("  ✗ 解包后没有 libicuuc.so.79", file=sys.stderr)
        return 1
    print(f"  libicu {VERSION}：已就绪（{n} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
