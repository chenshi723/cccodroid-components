#!/usr/bin/env python3
"""snowluma 首次安装：原生 Linux QQ + SnowLuma + Debian GTK3 运行库。

不写系统分区，不使用 proot/root。所有下载都核对 SHA256；Debian 的
Packages.gz 先与 InRelease 里记的 SHA256 对齐，再逐个核对 .deb。

SnowLuma 官方仓库因律师函 404、Release 全没了：安装器按序回退到三个
公共档案镜像，任何一个源下载的内容 SHA256 不符都会被拒。

用法:
  install.py <组件数据目录> --check    只报体积和来源
  install.py <组件数据目录> --yes      真正下载并安装
选项:
  --jobs N    并发下载线程数（默认 4）
  --force     已装过也重装
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import lzma
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SUITE = os.environ.get("CCODROID_QQ_DEBIAN_SUITE", "trixie")
MIRRORS = [
    os.environ.get("CCODROID_QQ_DEBIAN_MIRROR", "https://deb.debian.org/debian/"),
    "https://ftp.debian.org/debian/",
]
ARCH = "arm64"
COMPS = ["main", "contrib", "non-free"]
# QQ deb 的 Depends（去掉 xdg-utils：无头运行用不到桌面集成脚本）。
ROOTS = [
    "libgtk-3-0t64",
    "libnss3",
    "libnotify4",
    "libatspi2.0-0t64",
    "libsecret-1-0",
    "libgbm1",
    "libasound2t64",
    "libxss1",
    "libxtst6",
    "libuuid1",
    "fonts-dejavu-core",
]
SKIP = {"libc6"}  # 用组件的 glibc 2.44

QQ = {
    "version": "3.2.34-53644",
    "url": "https://qqdl.gtimg.cn/qqfile/QQNT/9.9.36/beta/9ee04bef/linuxqq_3.2.34-53644_arm64.deb",
    "sha256": "181b895cb573548e396e54bb0548cca92ffdc1b1a4b018fa4551bb062385fdca",
    "bytes": 207538924,
    "installed": 655698 * 1024,
}
SNOWLUMA = {
    "version": "2.4.2",
    # 官方仓库 SnowLuma/SnowLuma 2026-11 因律师函 404，Release 全部消失：不列官方 URL。
    # 三个公共档案镜像按序回退，同一 SHA256 校验所有源，任何源内容不符都被拒。
    # 用 full 不用 lite：lite 不带 node（要系统有 glibc Node 24.22.1+/26.12.1+，
    # cccodroid 的 nodejs 是 bionic 的），且 SnowLuma 的原生附加组件都是 glibc ELF，
    # 加载不进 bionic node。full 自带 glibc 版 node 24.22.1。
    "urls": [
        "https://github.com/XingYunStar/snowluma/releases/download/v2.4.2/SnowLuma-v2.4.2-linux-arm64.tar.gz",
        "https://github.com/venti1112/snowluma/releases/download/v2.4.2/SnowLuma-v2.4.2-linux-arm64.tar.gz",
        "https://github.com/TomyJan/SnowLuma/releases/download/v2.4.2/SnowLuma-v2.4.2-linux-arm64.tar.gz",
    ],
    "sha256": "c4bcff22828fb465d6fbd8caa375e82432fd3af684b297c43f2c428a2de2200c",
    "bytes": 52545976,
    "installed": 268 * 1024 * 1024,
}
# 官方包里只有 EULA.md 和 PRIVACY.md；源码许可 LICENSE 不在包里，
# 从档案镜像的 raw 拉取（三个镜像内容一致，sha256 与官方仓库 v2.4.2 的 LICENSE 比对过）。
SNOWLUMA_LICENSE = {
    "urls": [
        "https://raw.githubusercontent.com/XingYunStar/snowluma/main/LICENSE",
        "https://raw.githubusercontent.com/venti1112/snowluma/main/LICENSE",
        "https://raw.githubusercontent.com/TomyJan/SnowLuma/main/LICENSE",
    ],
    "sha256": "af26ab857dd2b1796a548bd132da23c4363476f85255856090187f3560445e08",
}

LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()


def say(*a):
    with PRINT_LOCK:
        print(*a, flush=True)


def mb(n):
    return f"{n / 1048576:.0f} MB"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http_bytes(urls, timeout=180, tries=4):
    if isinstance(urls, str):
        urls = [urls]
    last = None
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "cccodroid-snowluma/1"})
        for i in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read()
            except Exception as e:  # noqa: BLE001
                last = e
                if "CERTIFICATE" in str(e) or i == tries - 1:
                    break
                wait = 2 ** i
                say(f"    网络中断，{wait}s 后重试（{i + 1}/{tries - 1}）：{os.path.basename(url)} · {e}")
                time.sleep(wait)
    raise RuntimeError(f"下载失败（全部源都不可用）: {last}")


def download(urls, dest, want_sha, want_size=None, timeout=600):
    """下载到 dest，边下边算 SHA256；对不上就删掉并报错。已存在且正确则跳过。
    urls 可以是字符串或列表：列表按顺序回退（主源失效换镜像），每个源重试 4 次。"""
    if isinstance(urls, str):
        urls = [urls]
    if os.path.exists(dest) and sha256_file(dest) == want_sha:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last = None
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "cccodroid-snowluma/1"})
        for i in range(4):
            try:
                h = hashlib.sha256()
                got = 0
                tmp = dest + ".part"
                with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        h.update(b)
                        f.write(b)
                        got += len(b)
                if want_size and got != want_size:
                    raise ValueError(f"大小不符（应为 {want_size}，实得 {got}）")
                if h.hexdigest() != want_sha:
                    os.remove(tmp)
                    raise ValueError(f"SHA256 不符（应为 {want_sha[:16]}…，实得 {h.hexdigest()[:16]}…）")
                os.replace(tmp, dest)
                return dest
            except Exception as e:  # noqa: BLE001
                last = e
                if "CERTIFICATE" in str(e) or i == 3:
                    break
                wait = 2 ** i
                say(f"    下载中断，{wait}s 后重试（{i + 1}/3）：{e}")
                time.sleep(wait)
        say(f"    该源不可用，换下一个源：{os.path.basename(url)}")
    raise RuntimeError(f"下载失败（全部源都不可用）: {last}")


# ── Debian 索引 ────────────────────────────────────────────────────────
def parse_deb822(block):
    fields, last = {}, None
    for line in block.split("\n"):
        m = re.match(r"^([A-Za-z0-9-]+):\s?(.*)$", line)
        if m:
            last = m[1]
            fields[last] = m[2]
        elif last and line.startswith(" "):
            fields[last] += "\n" + line.strip()
    return fields


def ver_key(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.\-~+]", v)]


def release_sha256(mirror):
    text = http_bytes(f"{mirror}dists/{SUITE}/InRelease").decode("utf-8", "replace")
    sums, on = {}, False
    for line in text.split("\n"):
        if line.startswith("SHA256:"):
            on = True
            continue
        if on:
            if not line.startswith(" "):
                break
            p = line.split()
            if len(p) == 3:
                sums[p[2]] = (p[0].lower(), int(p[1]))
    if not sums:
        raise ValueError("InRelease 里没有 SHA256 一节")
    return sums


def load_index():
    for mirror in MIRRORS:
        try:
            sums = release_sha256(mirror)
            idx = {}
            for comp in COMPS:
                rel = f"{comp}/binary-{ARCH}/Packages.gz"
                gz = http_bytes(f"{mirror}dists/{SUITE}/{rel}")
                want = sums.get(rel)
                got = hashlib.sha256(gz).hexdigest()
                if not want or want[0] != got:
                    raise ValueError(f"{rel} 与 InRelease 对不上")
                raw = gzip.decompress(gz).decode("utf-8", "replace")
                for block in raw.split("\n\n"):
                    f = parse_deb822(block)
                    name = f.get("Package")
                    if not name:
                        continue
                    cur = idx.get(name)
                    if cur is None or ver_key(f.get("Version", "")) > ver_key(cur["version"]):
                        idx[name] = {
                            "version": f.get("Version", "?"),
                            "filename": f.get("Filename", ""),
                            "size": int(f.get("Size", 0) or 0),
                            "installed": int(f.get("Installed-Size", 0) or 0) * 1024,
                            "sha256": (f.get("SHA256", "") or "").lower(),
                            "deps": (f.get("Depends", "") or "") + "," + (f.get("Pre-Depends", "") or ""),
                        }
            say(f"  索引：Debian {SUITE}/{ARCH} · {len(idx)} 个包 · {mirror}")
            return mirror, idx
        except Exception as e:  # noqa: BLE001
            say(f"  镜像不可用 {mirror}: {e}")
    raise SystemExit("所有 Debian 镜像都拿不到索引")


def parse_deps(s):
    out = []
    for grp in s.split(","):
        first = grp.split("|")[0].strip()
        name = re.sub(r":.*$", "", re.sub(r"\(.*?\)", "", first)).strip()
        if name and not name.startswith("${"):
            out.append(name)
    return out


def closure(idx, roots):
    seen, missing, order = set(), [], []
    q = list(roots)
    dl = inst = 0
    while q:
        n = q.pop(0)
        if n in seen or n in SKIP:
            continue
        p = idx.get(n)
        if not p:
            missing.append(n)
            continue
        seen.add(n)
        order.append(n)
        dl += p["size"]
        inst += p["installed"]
        q.extend(parse_deps(p["deps"]))
    return order, missing, dl, inst


# ── 解包 ───────────────────────────────────────────────────────────────
def ar_entries(path):
    with open(path, "rb") as f:
        if f.read(8) != b"!<arch>\n":
            raise ValueError("不是 ar 归档")
        while True:
            hdr = f.read(60)
            if len(hdr) < 60:
                return
            name = hdr[:16].decode("utf-8", "replace").strip().rstrip("/")
            try:
                size = int(hdr[48:58].decode().strip())
            except ValueError:
                return
            off = f.tell()
            yield name, off, size
            f.seek(off + size + (size & 1))


def inside(root_real, p):
    rp = os.path.realpath(p)
    return rp == root_real or rp.startswith(root_real + os.sep)


def extract_tar(tf, root, stats):
    root_real = os.path.realpath(root)
    for m in tf:
        rel = m.name.lstrip("./").lstrip("/")
        if not rel:
            continue
        dst = os.path.join(root, rel)
        if ".." in rel.split("/") or not inside(root_real, os.path.dirname(dst) or root):
            stats["skipped"] += 1
            continue
        try:
            if m.isdir():
                os.makedirs(dst, exist_ok=True)
                continue
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if m.issym():
                target = m.linkname
                if target.startswith("/"):
                    target = os.path.join(root, target.lstrip("/"))
                resolved = os.path.normpath(os.path.join(os.path.dirname(dst), target))
                if not (resolved == root_real or resolved.startswith(root_real + os.sep)
                        or resolved == root or resolved.startswith(root + os.sep)):
                    raise OSError("软链指到根外")
                if os.path.lexists(dst):
                    os.remove(dst)
                os.symlink(target, dst)
                stats["links"] += 1
            elif m.islnk():
                src = os.path.join(root, m.linkname.lstrip("./").lstrip("/"))
                if ".." in m.linkname.split("/") or not inside(root_real, src) or not os.path.exists(src):
                    stats["skipped"] += 1
                    continue
                if os.path.lexists(dst):
                    os.remove(dst)
                os.link(src, dst)
                stats["links"] += 1
            elif m.isfile():
                if os.path.lexists(dst):
                    os.remove(dst)
                src = tf.extractfile(m)
                with open(dst, "wb") as out:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
                os.chmod(dst, m.mode & 0o7777)
                stats["files"] += 1
            else:
                stats["skipped"] += 1
        except (OSError, tarfile.TarError):
            stats["skipped"] += 1


def extract_deb(path, root, stats):
    entries = list(ar_entries(path))
    with open(path, "rb") as f:
        for name, off, size in entries:
            if not name.startswith("data.tar"):
                continue
            f.seek(off)
            blob = f.read(size)
            if name.endswith(".xz"):
                tf = tarfile.open(fileobj=lzma.LZMAFile(io.BytesIO(blob)), mode="r|")
            elif name.endswith(".gz"):
                tf = tarfile.open(fileobj=gzip.GzipFile(fileobj=io.BytesIO(blob)), mode="r|")
            elif name.endswith(".zst"):
                try:
                    from compression import zstd
                    raw = zstd.decompress(blob)
                except ImportError:
                    import zstandard
                    raw = zstandard.ZstdDecompressor().decompress(blob)
                tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r|")
            else:
                tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r|")
            try:
                extract_tar(tf, root, stats)
            finally:
                tf.close()
            return
    raise ValueError("deb 里没有 data.tar.*")


def extract_qq_deb(path, root, cache, stats):
    """QQ 的 data.tar.xz 有 198 MB，先落到缓存文件再流式解，避免整包进内存。"""
    entry = next((e for e in ar_entries(path) if e[0].startswith("data.tar")), None)
    if not entry:
        raise ValueError("QQ deb 里没有 data.tar.*")
    name, off, size = entry
    tmp = os.path.join(cache, "qq-data.tar.xz")
    with open(path, "rb") as src, open(tmp, "wb") as out:
        src.seek(off)
        left = size
        while left:
            b = src.read(min(1 << 20, left))
            if not b:
                break
            out.write(b)
            left -= len(b)
    try:
        with tarfile.open(tmp, mode="r|xz") as tf:
            extract_tar(tf, root, stats)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


# ── Debian 运行库 ─────────────────────────────────────────────────────
def install_debian(root, cache, jobs, plan_path):
    mirror, idx = load_index()
    order, missing, dl, inst = closure(idx, ROOTS)
    plan = {
        "suite": SUITE,
        "roots": ROOTS,
        "packages": [{"name": n, "version": idx[n]["version"], "sha256": idx[n]["sha256"]} for n in order],
    }
    say(f"  Debian 闭包：{len(order)} 个包 · 下载 {mb(dl)} · 解开约 {mb(inst)}")
    if missing:
        say(f"  ⚠️ 没解析到的虚包 {len(missing)} 个：{', '.join(missing[:6])}")
    gtk_marker = os.path.join(root, "usr/lib/aarch64-linux-gnu/libgtk-3.so.0")
    if os.path.isdir(root) and os.path.exists(plan_path) and os.path.exists(gtk_marker):
        try:
            if json.load(open(plan_path, encoding="utf-8")) == plan:
                say("  Debian 运行库已装且一致，跳过")
                return plan, inst
        except (OSError, ValueError):
            pass
    os.makedirs(root, exist_ok=True)
    os.makedirs(cache, exist_ok=True)

    errors = []
    done = {"n": 0}

    def fetch(name):
        p = idx[name]
        dest = os.path.join(cache, os.path.basename(p["filename"]))
        try:
            download(mirror + p["filename"], dest, p["sha256"], p["size"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            return None
        with LOCK:
            done["n"] += 1
            if done["n"] % 25 == 0 or done["n"] == len(order):
                say(f"    下载并核对 {done['n']}/{len(order)}")
        return dest

    say("  ▸ 下载 Debian 包并核对 SHA256 …")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        files = [x for x in ex.map(fetch, order) if x]
    if errors:
        raise RuntimeError("；".join(errors[:3]))

    say("  ▸ 解包 …")
    stats = {"files": 0, "links": 0, "skipped": 0}
    for i, path in enumerate(files, 1):
        extract_deb(path, root, stats)
        if i % 40 == 0 or i == len(files):
            say(f"    解包 {i}/{len(files)}")
    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    say(f"  Debian 运行库：{stats['files']} 个文件 · {stats['links']} 条链接")
    return plan, inst


def lib_path(debroot, prefix):
    dirs = []
    for base in ("usr/lib", "lib", "usr/lib/aarch64-linux-gnu", "lib/aarch64-linux-gnu"):
        d = os.path.join(debroot, base)
        if os.path.isdir(d):
            dirs.append(d)
    # 有些库在 blas/、pulseaudio/ 这类子目录里；扫一层
    for base in ("usr/lib", "lib"):
        top = os.path.join(debroot, base)
        if not os.path.isdir(top):
            continue
        for name in os.listdir(top):
            d = os.path.join(top, name)
            if os.path.isdir(d) and any(x.endswith(".so") or ".so." in x for x in os.listdir(d)):
                dirs.append(d)
    glibc_lib = os.path.join(prefix, "glibc", "lib")
    return ":".join(dict.fromkeys(dirs + [glibc_lib]))


def run_glibc(debroot, prefix, argv, env_extra=None, stdout=None):
    ldso = os.path.join(prefix, "glibc", "lib", "ld-linux-aarch64.so.1")
    env = dict(os.environ)
    env.pop("LD_PRELOAD", None)
    env.pop("LD_LIBRARY_PATH", None)
    if env_extra:
        env.update(env_extra)
    cmd = [ldso, "--library-path", lib_path(debroot, prefix)] + argv
    return subprocess.run(cmd, env=env, stdout=stdout or subprocess.PIPE,
                          stderr=subprocess.PIPE, text=False)


def post_install(debroot, prefix, root):
    # gdk-pixbuf 的 loaders.cache 与 GLib schemas 不会被自动生成（没跑 postinst），
    # 但 GTK 需要它们；这两步失败只警告，不影响 QQ 主体启动。
    loaders_dir = os.path.join(debroot, "usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders")
    query = os.path.join(debroot, "usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders")
    if os.path.isfile(query) and os.path.isdir(loaders_dir):
        out = os.path.join(debroot, "usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache")
        try:
            with open(out, "wb") as f:
                r = run_glibc(debroot, prefix, [query], {"GDK_PIXBUF_MODULEDIR": loaders_dir}, stdout=f)
            if r.returncode != 0:
                say(f"  ⚠️ gdk-pixbuf loaders.cache 生成失败：{r.stderr[-300:].decode('utf-8', 'replace')}")
        except Exception as e:  # noqa: BLE001
            say(f"  ⚠️ gdk-pixbuf loaders.cache 生成失败：{e}")
    schemas = os.path.join(debroot, "usr/share/glib-2.0/schemas")
    compiler = os.path.join(debroot, "usr/lib/aarch64-linux-gnu/glib-2.0/glib-compile-schemas")
    if os.path.isfile(compiler) and os.path.isdir(schemas):
        try:
            r = run_glibc(debroot, prefix, [compiler, schemas])
            if r.returncode != 0:
                say(f"  ⚠️ GLib schemas 编译失败：{r.stderr[-300:].decode('utf-8', 'replace')}")
        except Exception as e:  # noqa: BLE001
            say(f"  ⚠️ GLib schemas 编译失败：{e}")
    # 字体：Debian 的 fonts.conf 只认 /usr/share/fonts；补上安卓系统字体与可写缓存目录。
    etc = os.path.join(root, "etc")
    os.makedirs(etc, exist_ok=True)
    conf = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>{debroot}/usr/share/fonts</dir>
  <dir>/system/fonts</dir>
  <cachedir>{root}/cache/fontconfig</cachedir>
  <include ignore_missing="yes">{debroot}/etc/fonts/conf.d</include>
</fontconfig>
"""
    with open(os.path.join(etc, "fonts.conf"), "w", encoding="utf-8") as f:
        f.write(conf)
    os.makedirs(os.path.join(root, "cache", "fontconfig"), exist_ok=True)


# ── QQ / SnowLuma ──────────────────────────────────────────────────────
def patch_interpreter(path, ldso):
    try:
        cur = subprocess.run(["patchelf", "--print-interpreter", path],
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        cur = ""
    if cur == ldso:
        return False
    subprocess.run(["patchelf", "--set-interpreter", ldso, path], check=True)
    return True


def install_qq(debroot, cache, prefix):
    deb = os.path.join(cache, "linuxqq_3.2.34-53644_arm64.deb")
    say(f"  ▸ 下载 Linux QQ {QQ['version']}（{mb(QQ['bytes'])}，腾讯官方 CDN）…")
    download(QQ["url"], deb, QQ["sha256"], QQ["bytes"])
    qq_bin = os.path.join(debroot, "opt", "QQ", "qq")
    if os.path.exists(qq_bin) and os.path.getsize(qq_bin) > 100 * 1024 * 1024:
        say("  QQ 已解包，跳过")
    else:
        say("  ▸ 解包 QQ（约 646 MB）…")
        stats = {"files": 0, "links": 0, "skipped": 0}
        extract_qq_deb(deb, debroot, cache, stats)
        say(f"    解包：{stats['files']} 个文件 · {stats['links']} 条链接 · 跳过 {stats['skipped']}")
    ldso = os.path.join(prefix, "glibc", "lib", "ld-linux-aarch64.so.1")
    patched = patch_interpreter(qq_bin, ldso)
    # crashpad 不是必需的，但能补就补，避免崩溃处理进程反复报错
    crash = os.path.join(debroot, "opt", "QQ", "chrome_crashpad_handler")
    if os.path.exists(crash):
        try:
            patch_interpreter(crash, ldso)
        except Exception:
            pass
    say(f"  QQ 解释器：{'已改为 ' + ldso if patched else '已正确'}")
    return deb


def read_token(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        t = None
        for k in ("wsServers", "httpServers"):
            for srv in (d.get("networks", {}).get(k) or []):
                if isinstance(srv.get("accessToken"), str) and srv["accessToken"]:
                    t = srv["accessToken"]
                    break
            if t:
                break
        if t:
            return t
    except Exception:  # noqa: BLE001
        pass
    return secrets.token_urlsafe(24)


def write_json(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + f".tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def install_snowluma(root, data, cache, prefix):
    sl_dir = os.path.join(data, "snowluma")
    cfg_dir = os.path.join(sl_dir, "config")
    tar_path = os.path.join(cache, "SnowLuma-v2.4.2-linux-arm64.tar.gz")
    say(f"  ▸ 下载 SnowLuma {SNOWLUMA['version']} full 版（{mb(SNOWLUMA['bytes'])}，公共档案镜像 ×3）…")
    download(SNOWLUMA["urls"], tar_path, SNOWLUMA["sha256"], SNOWLUMA["bytes"])
    if not os.path.exists(os.path.join(sl_dir, "index.mjs")):
        say("  ▸ 解包 SnowLuma …")
        os.makedirs(sl_dir, exist_ok=True)
        stats = {"files": 0, "links": 0, "skipped": 0}
        with tarfile.open(tar_path, mode="r|gz") as tf:
            extract_tar(tf, sl_dir, stats)
        say(f"    解包：{stats['files']} 个文件 · {stats['links']} 条链接 · 跳过 {stats['skipped']}")

    ldso = os.path.join(prefix, "glibc", "lib", "ld-linux-aarch64.so.1")
    node_bin = os.path.join(sl_dir, "node")
    patch_interpreter(node_bin, ldso)
    say(f"  SnowLuma node 解释器：{ldso}")

    # 自带 node 的 DT_NEEDED 里有裸名 libc.so，组件 glibc 的 libc.so 是 ld 链接脚本，
    # 直接加载报 invalid ELF header：放一条指向 glibc libc.so.6 的软链并排进库路径首位。
    shim_dir = os.path.join(sl_dir, "lib")
    shim = os.path.join(shim_dir, "libc.so")
    if os.path.lexists(shim):
        os.remove(shim)
    os.makedirs(shim_dir, exist_ok=True)
    os.symlink(os.path.join(prefix, "glibc", "lib", "libc.so.6"), shim)

    # SnowLuma 运行时的库路径：libc.so 垫片 + Debian 闭包 + 组件 glibc（不含 bionic 前缀）
    with open(os.path.join(data, "snowluma-libpath.txt"), "w", encoding="utf-8") as f:
        f.write(shim_dir + ":" + lib_path(os.path.join(data, "debroot"), prefix) + "\n")

    # 装完立刻自检：node 必须能直接跑（解释器已改），否则后患无穷
    env = dict(os.environ)
    env.pop("LD_PRELOAD", None)
    env["LD_LIBRARY_PATH"] = shim_dir + ":" + lib_path(os.path.join(data, "debroot"), prefix)
    r = subprocess.run([node_bin, "--version"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
    if r.returncode != 0 or not r.stdout.startswith(b"v"):
        raise RuntimeError("SnowLuma node 自检失败：" + r.stderr[-300:].decode("utf-8", "replace"))
    say(f"  SnowLuma node 自检：{r.stdout.decode().strip()}")

    # 官方包里没有 LICENSE（源码许可），从档案镜像 raw 拉一份放在旁边（再分发要求带全文）
    lic = os.path.join(sl_dir, "LICENSE")
    if not os.path.exists(lic):
        try:
            blob = http_bytes(SNOWLUMA_LICENSE["urls"])
            got = hashlib.sha256(blob).hexdigest()
            if got != SNOWLUMA_LICENSE["sha256"]:
                raise ValueError(f"SHA256 不符（{got[:16]}…）")
            with open(lic, "wb") as f:
                f.write(blob)
        except Exception as e:  # noqa: BLE001
            say(f"  ⚠️ SnowLuma LICENSE 下载失败（不影响运行）：{e}")

    token = read_token(os.path.join(cfg_dir, "onebot.json"))

    # OneBot v11：http 3000（发动作）、ws 3001（收事件），token 同 NapCat 版桥的约定。
    # statusCommand 关掉：不要让 SnowLuma 内置的 #sl 状态命令绕过白名单在群里自动回话。
    onebot = {
        "networks": {
            "httpServers": [{
                "name": "http-default", "host": "127.0.0.1", "port": 3000, "path": "/",
                "enableWebSocket": False, "enableSse": False,
                "accessToken": token, "messageFormat": "array", "reportSelfMessage": False,
            }],
            "httpClients": [],
            "wsServers": [{
                "name": "ws-default", "host": "127.0.0.1", "port": 3001, "path": "/",
                "role": "Universal",
                "accessToken": token, "messageFormat": "array", "reportSelfMessage": False,
            }],
            "wsClients": [],
        },
        "statusCommand": {"enabled": False, "swallow": False, "cooldownSeconds": 5, "trigger": "#sl"},
        "historySync": {"enabled": False},
        "notifications": {"channelIds": []},
    }
    write_json(os.path.join(cfg_dir, "onebot.json"), onebot)

    # 运行时配置：WebUI 只监听 127.0.0.1:5099；自动注入新发现的 QQ 主进程。
    runtime = {
        "webuiPort": 5099,
        "webuiHost": "127.0.0.1",
        "webuiTls": {"enabled": False},
        "hookAutoLoad": True,
        "trustProxy": "",
        "logMaxTotalMb": 1024,
        "logRetainDays": 7,
        "logPerUin": False,
    }
    write_json(os.path.join(cfg_dir, "runtime.json"), runtime)
    return token


def write_component_config(root, token):
    path = os.path.join(root, "config.json")
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cfg = {}
    cfg.setdefault("version", 1)
    ob = cfg.setdefault("onebot", {})
    ob.setdefault("wsUrl", "ws://127.0.0.1:3001")
    ob.setdefault("httpUrl", "http://127.0.0.1:3000")
    if not ob.get("accessToken"):
        ob["accessToken"] = token
    cfg.setdefault("allow", {"private": [], "groups": []})
    cfg.setdefault("groupTrigger", "at")
    be = cfg.setdefault("backend", {})
    be.setdefault("type", "openai")
    be.setdefault("baseUrl", "https://api.deepseek.com/v1")
    be.setdefault("model", "deepseek-chat")
    be.setdefault("apiKeyFile", "")
    be.setdefault("maxTokens", 800)
    be.setdefault("temperature", 0.7)
    be.setdefault("timeoutMs", 120000)
    bh = cfg.setdefault("behavior", {})
    bh.setdefault("systemPrompt", "你是一个通过 QQ 提供帮助的 AI 助手。回答准确、简洁，默认使用中文。被问到身份时如实说明你是 AI，不要假装是人类。不要主动发起话题，不要模仿真人群聊语气，不要发送未经用户要求的内容。遇到不确定的信息直接说不确定。")
    bh.setdefault("groupPrefix", "")
    bh.setdefault("maxInputChars", 4000)
    bh.setdefault("contextMessages", 12)
    bh.setdefault("maxReplyChars", 600)
    bh.setdefault("cooldownMs", 3000)
    write_json(path, cfg)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    check = "--check" in argv
    yes = "--yes" in argv
    force = "--force" in argv
    jobs = 4
    if "--jobs" in argv:
        jobs = max(1, int(argv[argv.index("--jobs") + 1]))
    args = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    if len(args) != 1:
        print("用法: install.py <组件数据目录> [--check|--yes] [--jobs N] [--force]", file=sys.stderr)
        return 2
    root = os.path.abspath(args[0])
    data = os.path.join(root, "data")
    debroot = os.path.join(data, "debroot")
    cache = os.path.join(data, "cache")
    prefix = os.environ.get("PREFIX") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

    print(f"snowluma 首次安装 · 数据目录 {root}")
    mirror, idx = load_index()
    order, missing, dl, inst = closure(idx, ROOTS)
    total_dl = dl + QQ["bytes"] + SNOWLUMA["bytes"]
    total_inst = inst + QQ["installed"] + SNOWLUMA["installed"]
    print(f"  Debian {SUITE}/{ARCH}：{len(order)} 个包 · 下载 {mb(dl)} · 解开约 {mb(inst)}")
    if missing:
        print(f"  ⚠️ 虚包 {len(missing)} 个：{', '.join(missing[:6])}")
    print(f"  Linux QQ {QQ['version']}：下载 {mb(QQ['bytes'])} · 解开约 {mb(QQ['installed'])}（腾讯官方）")
    print(f"  SnowLuma {SNOWLUMA['version']} full：下载 {mb(SNOWLUMA['bytes'])} · 解开约 {mb(SNOWLUMA['installed'])}（公共档案镜像 ×3，SHA256 逐包校验）")
    print(f"  合计：下载约 {mb(total_dl)} · 装后约 {mb(total_inst)}")
    if check:
        print("  （--check：只报体积，没有下载）")
        return 0
    if not yes:
        print("  需要先征得用户同意，再加 --yes 安装。", file=sys.stderr)
        return 2

    os.makedirs(root, mode=0o700, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    st = os.statvfs(root)
    free = st.f_bavail * st.f_frsize
    need = total_inst * 1.35
    if free < need:
        print(f"  ✗ 空间不够：剩 {mb(free)}，需要约 {mb(need)}", file=sys.stderr)
        return 1

    ldso = os.path.join(prefix, "glibc", "lib", "ld-linux-aarch64.so.1")
    if not os.path.exists(ldso):
        print(f"  ✗ 找不到 glibc 加载器：{ldso}", file=sys.stderr)
        return 1
    if not shutil.which("patchelf"):
        print("  ✗ 找不到 patchelf（组件依赖里应有）", file=sys.stderr)
        return 1

    t0 = time.time()
    plan_path = os.path.join(data, "debian-plan.json")
    if force:
        for p in (os.path.join(data, "qq.json"), os.path.join(data, "snowluma.json")):
            try: os.remove(p)
            except OSError: pass
    if force or not os.path.exists(os.path.join(data, "qq.json")):
        install_debian(debroot, cache, jobs, plan_path)
        post_install(debroot, prefix, root)
    else:
        print("  Debian 运行库已装，跳过（--force 可重装）")
        if not os.path.exists(os.path.join(root, "etc", "fonts.conf")):
            post_install(debroot, prefix, root)

    if force or not os.path.exists(os.path.join(data, "qq.json")):
        install_qq(debroot, cache, prefix)
        write_json(os.path.join(data, "qq.json"), {"version": QQ["version"], "sha256": QQ["sha256"]})
    else:
        print("  QQ 已装，跳过（--force 可重装）")

    token = install_snowluma(root, data, cache, prefix)
    write_json(os.path.join(data, "snowluma.json"), {"version": SNOWLUMA["version"], "sha256": SNOWLUMA["sha256"]})
    write_component_config(root, token)

    with open(os.path.join(data, "setup.json"), "w", encoding="utf-8") as f:
        json.dump({
            "qq": QQ["version"], "qq_sha256": QQ["sha256"],
            "snowluma": SNOWLUMA["version"], "snowluma_sha256": SNOWLUMA["sha256"],
            "debian_suite": SUITE, "debian_packages": len(order),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\n完成 · {len(order)} 个 Debian 包 + QQ + SnowLuma · 用时 {time.time() - t0:.0f}s")
    print("下一步：snowluma start → 打开 http://127.0.0.1:8787/ 扫码；登录后 snowluma allow add <你的QQ号>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
