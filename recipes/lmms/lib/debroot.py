#!/usr/bin/env python3
"""给 cccodroid 的创作组件装 Debian arm64 运行根。

包清单钉在同目录的 debs.json 里（包名、版本、文件名、SHA256 都来自 Debian 官方
dists/<套件>/<组件>/binary-arm64/Packages 索引，安装时不联网解析索引，只按清单下载）。
glibc 运行时用 Termux 的（$PREFIX/glibc）：安卓上唯一能跑的那份，所以清单里没有 libc6。

安全：
  · 每个 .deb 下载后核对 debs.json 里的 SHA256，不符就失败，不写进缓存。
  · 解包只许落在目标目录里：成员名带 ..、软链 / 硬链指到目录外、经已有软链绕出去的，一律跳过。
  · 不在系统分区写任何东西；Debian 根放在组件自己的数据目录（$HOME/.cccodroid/<id>/debroot）。

用法: debroot.py --root <目标目录> --lock <debs.json> [--dry-run] [--jobs N] [--mirror URL]
  --dry-run   只算体积，不下载
  --jobs N    并发下载线程数（默认 4）
环境变量:
  CCODROID_DEB_MIRROR  只用一个镜像（默认按 debs.json 的 mirrors 顺序回退）
"""
import gzip
import hashlib
import io
import json
import lzma
import os
import sys
import tarfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LOCK = threading.Lock()
DEFAULT_MIRRORS = [
    "https://deb.debian.org/debian/",
    "https://ftp.debian.org/debian/",
    "https://mirrors.tuna.tsinghua.edu.cn/debian/",
    "https://mirrors.ustc.edu.cn/debian/",
]


def http_get(url, timeout=180, tries=4):
    # 不关证书校验：下载文件的来源就是 https，关了的话下面「核对 SHA256」也保不住。
    # 手机网络会断流：退避重试，证书错误不重试。
    req = urllib.request.Request(url, headers={"User-Agent": "cccodroid-creative/1"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                                     # noqa: BLE001
            if "CERTIFICATE" in str(e) or i == tries - 1:
                raise
            print(f"    网络中断，{2 ** i}s 后重试（{i + 1}/{tries - 1}）：{os.path.basename(url)} · {e}")
            time.sleep(2 ** i)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def inside(root_real, path):
    rp = os.path.realpath(path)
    return rp == root_real or rp.startswith(root_real + os.sep)


def extract_tar(tf, root, stats):
    root_real = os.path.realpath(root)
    for m in tf:
        rel = m.name.lstrip("./").lstrip("/")
        if not rel:
            continue
        dst = os.path.join(root, rel)
        if ".." in rel.split("/") or not inside(root_real, os.path.dirname(dst) or root):
            with LOCK:
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
                    raise OSError("软链指到根外：" + m.linkname)
                if os.path.lexists(dst):
                    os.remove(dst)
                os.symlink(target, dst)
                key = "links"
            elif m.islnk():
                src = os.path.join(root, m.linkname.lstrip("./").lstrip("/"))
                if ".." in m.linkname.split("/") or not inside(root_real, src):
                    raise OSError("硬链指到根外：" + m.linkname)
                if not os.path.exists(src):
                    key = "skipped"
                else:
                    if os.path.lexists(dst):
                        os.remove(dst)
                    os.link(src, dst)
                    key = "links"
            elif m.isfile():
                if os.path.lexists(dst):
                    os.remove(dst)
                src_f = tf.extractfile(m)
                with open(dst, "wb") as out:
                    while True:
                        b = src_f.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
                os.chmod(dst, m.mode & 0o7777)
                key = "files"
            else:
                key = "skipped"
        except (OSError, tarfile.TarError):
            key = "skipped"
        with LOCK:
            stats[key] += 1


def extract_deb(deb, root, stats):
    for name, blob in ar_members(deb):
        if not name.startswith("data.tar"):
            continue
        tf = tarfile.open(fileobj=tar_stream(name, blob), mode="r|")
        extract_tar(tf, root, stats)
        tf.close()
        return
    raise ValueError("没有 data.tar.*")


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    jobs = 4
    if "--jobs" in argv:
        i = argv.index("--jobs")
        jobs = max(1, int(argv[i + 1]))
        del argv[i:i + 2]
    mirror = None
    if "--mirror" in argv:
        i = argv.index("--mirror")
        mirror = argv[i + 1]
        del argv[i:i + 2]
    opt = {}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            opt[a[2:]] = argv[i + 1]
    if not opt.get("root") or not opt.get("lock"):
        print("用法: debroot.py --root <目标目录> --lock <debs.json> [--dry-run] [--jobs N] [--mirror URL]", file=sys.stderr)
        return 2
    root = os.path.abspath(opt["root"])
    base = os.path.dirname(root.rstrip("/"))
    cache = os.path.join(base, "debcache")
    with open(opt["lock"], encoding="utf-8") as f:
        lock = json.load(f)
    pkgs = lock["packages"]
    stamp = hashlib.sha256(json.dumps(lock, sort_keys=True).encode()).hexdigest()[:16]
    marker = os.path.join(base, f"installed-{stamp}.json")
    dl = sum(p.get("size", 0) for p in pkgs)
    inst = sum(p.get("installed", 0) for p in pkgs)
    mirrors = [mirror] if mirror else (os.environ.get("CCODROID_DEB_MIRROR")
                                        and [os.environ["CCODROID_DEB_MIRROR"]] or lock.get("mirrors", DEFAULT_MIRRORS))

    print(f"Debian {lock.get('suite', 'trixie')}/{lock.get('arch', 'arm64')} 运行根"
          f"（{len(pkgs)} 个包 · 下载约 {dl / 1048576:.0f} MB · 解开约 {inst / 1048576:.0f} MB）")
    print(f"  装到：{root}")

    if os.path.isdir(root) and os.path.exists(marker):
        print(f"  已经装过，内容一致：{root}")
        return 0
    if dry:
        print(f"  （--dry-run：没下载。目标：{root}）")
        return 0

    probe = base
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    st = os.statvfs(probe or ".")
    free_mb = st.f_bavail * st.f_frsize / 1048576
    need_mb = inst / 1048576 * 1.3
    if free_mb < need_mb:
        print(f"  ✗ 空间不够：剩 {free_mb:.0f} MB，需要约 {need_mb:.0f} MB", file=sys.stderr)
        return 1

    os.makedirs(root, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    print(f"  缓存：{cache}（.deb 留着，重装/续传不用再下）")

    t0 = time.time()
    errors = []
    prog = {"n": 0}

    def fetch(p):
        dest = os.path.join(cache, os.path.basename(p["filename"]))
        if os.path.exists(dest) and sha256_file(dest) == p["sha256"]:
            with LOCK:
                prog["n"] += 1
            return p["name"], dest
        blob = None
        last = None
        for m in mirrors:
            try:
                blob = http_get(m + p["filename"], timeout=600)
                break
            except Exception as e:                                 # noqa: BLE001
                last = e
                print(f"    镜像不可用 {m}（{p['name']}）：{e}")
        if blob is None:
            errors.append(f"{p['name']}: 所有镜像都下载失败（{last}）")
            return None
        got = hashlib.sha256(blob).hexdigest()
        if got != p["sha256"]:
            errors.append(f"{p['name']}: SHA256 不符（清单 {p['sha256'][:16]}… / 实得 {got[:16]}…）")
            return None
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, dest)
        with LOCK:
            prog["n"] += 1
            if prog["n"] % 25 == 0 or prog["n"] == len(pkgs):
                print(f"    下载并核对 {prog['n']}/{len(pkgs)}（{time.time() - t0:.0f}s）")
        return p["name"], dest

    print("  ▸ 下载并核对 SHA256 …")
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        debs = [r for r in ex.map(fetch, pkgs) if r]
    if errors:
        for e in errors:
            print("  ✗ " + e, file=sys.stderr)
        return 1

    print("  ▸ 解包 …")
    t1 = time.time()
    stats = {"files": 0, "links": 0, "skipped": 0}
    prog2 = {"n": 0}

    def unpack(item):
        name, deb = item
        with open(deb, "rb") as f:
            blob = f.read()
        try:
            extract_deb(blob, root, stats)
        except Exception as e:                                     # noqa: BLE001
            errors.append(f"{name}: 解包失败 {e}")
        with LOCK:
            prog2["n"] += 1
            if prog2["n"] % 25 == 0 or prog2["n"] == len(debs):
                print(f"    解包 {prog2['n']}/{len(debs)}（{time.time() - t1:.0f}s）")

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(unpack, debs))
    if errors:
        for e in errors:
            print("  ✗ " + e, file=sys.stderr)
        return 1

    # 装好之前不写成功标记：半截装完的中断，下次会重新解一遍（下载走缓存，不重复下载）
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"lock": stamp, "packages": len(pkgs)}, f, ensure_ascii=False, indent=1)
    print(f"  完成：{len(debs)} 个包 · {stats['files']} 个文件 · {stats['links']} 条链接"
          f" · 跳过 {stats['skipped']} · 共 {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
