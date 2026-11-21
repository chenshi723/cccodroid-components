// 批量 CI 实跑 selftest（arm64 + termux-docker）：新底座打包完后，自动为所有不依赖手机硬件
// （无 GPU / 屏幕 / Shizuku 需求）且尚未有验证记录的组件跑一遍安装 + first-run + selftest，
// 产出 ci-verified 片段供 build-index.mjs 合并进签名索引（kind: "ci-arm64"）。
//
// 用法：
//   node tools/ci-verify-base.mjs [--base <devkit-tag>] [--only <id>] [--shard <i/N>]
//                                 [--ci-verified <existing.json>] [--out <result.json>]
//                                 [--strict]
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { ROOT, REPO, APP_REPO, recipes, bases, run, asset } from "./lib.mjs";

const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : undefined; };
const STRICT = args.includes("--strict");
const ONLY = opt("only") || "";
const SHARD = opt("shard") || "0/1";
const OUT = path.resolve(opt("out") || path.join(ROOT, "work", "ci-verified-shard.json"));
const WORK = path.resolve(process.env.WORK || path.join(ROOT, "work"));
const IMAGE = process.env.TERMUX_DOCKER_IMAGE || "termux/termux-docker:aarch64";
const LIVE = "/data/data/cc.codroid", SNAP = "/opt/cc-base", USR = `${LIVE}/files/usr`;
const ST = path.join(WORK, "ci-verify");
fs.mkdirSync(ST, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

const [shardIdx, shardTotal] = SHARD.split("/").map((x) => Number(x));
if (!Number.isInteger(shardIdx) || !Number.isInteger(shardTotal) || shardIdx < 0 || shardIdx >= shardTotal) {
  console.error(`✗ --shard 格式应为 0/4 这种，收到：${SHARD}`);
  process.exit(2);
}

const gh = (...a) => run("gh", a);
const sudo = (...a) => execFileSync("sudo", a, { stdio: ["ignore", "pipe", "inherit"], maxBuffer: 1 << 26 });
const needsHardware = (r) => {
  const n = r.needs || {};
  return !!(n.gpu === "adreno" || n.gpu === "mali" || n.gpu === true || n.display || n.shizuku);
};

function loadExistingCiVerified() {
  const p = opt("ci-verified");
  if (p && fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, "utf8"));
  const dl = path.join(ST, "existing-ci-verified.json");
  try {
    gh("release", "download", "index", "-R", REPO, "-p", "ci-verified.json", "-O", dl, "--clobber");
    return JSON.parse(fs.readFileSync(dl, "utf8"));
  } catch {
    return {};
  }
}

function inContainer(script, timeoutSec) {
  const f = path.join(ST, "in.sh");
  fs.writeFileSync(f, [
    `export PREFIX=${USR} HOME=${LIVE}/files/home LANG=en_US.UTF-8 TERM=xterm-256color`,
    `export TMPDIR=$PREFIX/tmp PATH=$PREFIX/bin:/system/bin SHELL=$PREFIX/bin/bash`,
    `mkdir -p "$TMPDIR" "$HOME"`,
    `[ -f $PREFIX/lib/libtermux-exec-ld-preload.so ] && export LD_PRELOAD=$PREFIX/lib/libtermux-exec-ld-preload.so`,
    script,
  ].join("\n") + "\n");
  const r = spawnSync("docker", ["run", "--rm", "-v", `${LIVE}:${LIVE}`, "-v", `${ST}:/st`, "--entrypoint", "/system/bin/sh", IMAGE, "/st/in.sh"],
    { encoding: "utf8", timeout: (timeoutSec + 60) * 1000, maxBuffer: 1 << 26 });
  return { code: r.status ?? -1, out: ((r.stdout || "") + (r.stderr || "")).trim() };
}

const tag = opt("base") || bases()[0]?.tag;
if (!tag) { console.error("✗ bases.json 里没有底座"); process.exit(1); }

const baseDir = path.join(WORK, "bases", tag);
fs.mkdirSync(baseDir, { recursive: true });
const lockFile = path.join(baseDir, "devkit.lock.json");
if (!fs.existsSync(lockFile)) {
  gh("release", "download", tag, "-R", APP_REPO, "-p", "devkit.lock.json", "-D", baseDir, "--clobber");
}
const lock = JSON.parse(fs.readFileSync(lockFile, "utf8"));
const baseSha = lock.gz.sha256;
const base12 = baseSha.slice(0, 12);

const verified = JSON.parse(fs.readFileSync(path.join(ROOT, "verified.json"), "utf8"));
const existingCi = loadExistingCiVerified();

const allRecipes = recipes().sort((a, b) => a.id.localeCompare(b.id));
const recipeById = new Map(allRecipes.map((r) => [r.id, r]));

// 拉取某个组件在当前底座上最新发布的构建清单 + 资产名
const metaCache = new Map();
function latestBuildForBase(id) {
  if (metaCache.has(id)) return metaCache.get(id);
  const vcmp = (a, b) => a.localeCompare(b, "en", { numeric: true });
  let assets;
  try { assets = JSON.parse(gh("release", "view", id, "-R", REPO, "--json", "assets")).assets.map((a) => a.name); }
  catch { metaCache.set(id, null); return null; }
  const assetSet = new Set(assets);
  const dl = path.join(ST, "meta", id);
  fs.rmSync(dl, { recursive: true, force: true });
  fs.mkdirSync(dl, { recursive: true });
  try { gh("release", "download", id, "-R", REPO, "-p", `*-for-${base12}.json`, "-D", dl); }
  catch { metaCache.set(id, null); return null; }
  let best = null;
  for (const f of fs.readdirSync(dl)) {
    const m = JSON.parse(fs.readFileSync(path.join(dl, f), "utf8"));
    const name = asset(m.id, m.version, m.base.gz);
    if (m.id !== id || m.base.gz !== baseSha || !assetSet.has(name + ".tar.gz")) continue;
    if (!best || vcmp(m.version, best.version) > 0) best = { ...m, asset: name + ".tar.gz" };
  }
  metaCache.set(id, best);
  return best;
}

const candidates = allRecipes.filter((r) => {
  if (ONLY && r.id !== ONLY) return false;
  if (needsHardware(r)) return false;
  if (!r.selftest) return false;
  return true;
});

const myCandidates = candidates.filter((_, idx) => idx % shardTotal === shardIdx);
const todo = [];
const rows = [];

for (const r of myCandidates) {
  const b = latestBuildForBase(r.id);
  if (!b) { rows.push([r.id, "—", `底座 ${base12} 尚无构建`]); continue; }
  if (verified[r.id]?.[b.version]?.[base12]) { rows.push([r.id, "✓", "已有真机验证，跳过"]); continue; }
  const prevCi = existingCi[r.id]?.[b.version]?.[base12];
  if (prevCi && prevCi.gzSha256 === b.gz.sha256) { rows.push([r.id, "✓", "已有同哈希 CI 验证，跳过"]); continue; }
  todo.push({ recipe: r, build: b });
}

console.log(`底座 ${tag}（${base12}）· shard ${shardIdx}/${shardTotal} · 待跑 ${todo.length} / ${myCandidates.length}`);

const passed = {};
let fails = 0;

if (todo.length) {
  const gz = path.join(WORK, "base-gz", tag, `devkit-${lock.target || "cc.codroid"}.tar.gz`);
  if (!fs.existsSync(gz)) {
    fs.mkdirSync(path.dirname(gz), { recursive: true });
    execFileSync("gh", ["release", "download", tag, "-R", APP_REPO, "-p", path.basename(gz), "-O", gz], { stdio: "inherit" });
  }
  console.log(`解包底座 ${tag} 并跑首次运行…`);
  sudo("rm", "-rf", LIVE, SNAP);
  sudo("mkdir", "-p", `${LIVE}/files/home`);
  sudo("tar", "xzf", gz, "-C", `${LIVE}/files`);
  const fr = inContainer(`sh $PREFIX/libexec/devkit/first-run.sh >/st/base-first-run.log 2>&1; echo "rc=$?"`, 900);
  console.log("  base first-run: " + fr.out.split("\n").pop());
  sudo("cp", "-a", LIVE, SNAP);

  const downloadAsset = (id, assetName) => {
    const p = path.join(ST, "pkg", id, assetName);
    if (!fs.existsSync(p)) {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      gh("release", "download", id, "-R", REPO, "-p", assetName, "-O", p, "--clobber");
    }
    return p;
  };
  const downloadModule = (mid) => {
    const fname = `devkit-${mid}-${lock.target || "cc.codroid"}.tar.gz`;
    const p = path.join(ST, "mod", tag, fname);
    if (!fs.existsSync(p)) {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      gh("release", "download", tag, "-R", APP_REPO, "-p", fname, "-O", p, "--clobber");
    }
    return p;
  };

  // 解析组件依赖链（拓扑序：依赖在前，支持 requires 里的 module:<id>）
  const collectDeps = (id, seen = new Set(), compChain = [], modIds = new Set()) => {
    if (seen.has(id)) return { compChain, modIds, missing: null };
    seen.add(id);
    const r = recipeById.get(id);
    if (!r) return { compChain, modIds, missing: id };
    for (const req of r.requires || []) {
      if (req.startsWith("module:")) { modIds.add(req.slice(7)); continue; }
      const sub = collectDeps(req, seen, compChain, modIds);
      if (sub.missing) return sub;
    }
    const b = latestBuildForBase(id);
    if (!b) return { compChain, modIds, missing: `${id}@${base12}` };
    compChain.push({ id, build: b });
    return { compChain, modIds, missing: null };
  };

  for (const { recipe: r, build: b } of todo) {
    console.log(`\n══ [${r.id}] ${b.version}：${r.selftest}`);
    const deps = collectDeps(r.id);
    if (deps.missing) {
      fails++;
      rows.push([r.id, "❌", `依赖 ${deps.missing} 在底座 ${base12} 上缺构建`]);
      continue;
    }
    sudo("rm", "-rf", LIVE);
    sudo("cp", "-a", SNAP, LIVE);

    // 额外可选模块（full:false 的模块不在整包里，如 go/node/rust，按需叠加）
    const modFirstRuns = [];
    let depErr = null;
    for (const mid of deps.modIds) {
      try {
        const mtar = downloadModule(mid);
        sudo("tar", "xzf", mtar, "-C", `${LIVE}/files`);
        modFirstRuns.push(`f=$PREFIX/libexec/devkit/modules/${mid}/first-run.sh; [ -f "$f" ] && sh "$f"`);
      } catch (e) { depErr = `模块 ${mid} 下载失败：${e.message.split("\n")[0]}`; break; }
    }
    if (depErr) { fails++; rows.push([r.id, "❌", depErr]); continue; }

    for (const c of deps.compChain) {
      const tar = downloadAsset(c.id, c.build.asset);
      sudo("tar", "xzf", tar, "-C", `${LIVE}/files`);
    }
    const compFirstRuns = deps.compChain.map((c) => `f=$PREFIX/libexec/devkit/components/${c.id}/first-run.sh; [ -f "$f" ] && { PIP_NO_INDEX=1 sh "$f" || echo "（${c.id} first-run rc=$?）"; }`);
    fs.writeFileSync(path.join(ST, "cmd"), r.selftest + "\n");
    const runRes = inContainer([
      ...modFirstRuns,
      ...compFirstRuns,
      `cd "$HOME"; timeout 300 $PREFIX/bin/bash /st/cmd >/st/${r.id}.log 2>&1; echo "rc=$?"`,
    ].join("\n"), 900);
    const code = Number((/rc=(\d+)\s*$/.exec(runRes.out) || [])[1] ?? -1);
    let log = ""; try { log = fs.readFileSync(path.join(ST, `${r.id}.log`), "utf8").trim(); } catch {}
    const last = log.split("\n").filter(Boolean).slice(-1)[0] || "";
    console.log(log.split("\n").slice(-6).map((l) => "  | " + l).join("\n") + `\n  rc=${code}`);

    if (code === 0) {
      passed[r.id] = {
        [b.version]: {
          [base12]: {
            kind: "ci-arm64",
            date: new Date().toISOString().slice(0, 10),
            device: "GitHub Actions ubuntu-24.04-arm (termux-docker:aarch64)",
            app: `devkit ${tag}`,
            gzSha256: b.gz.sha256,
            checks: `ci-verify-base on ${tag}: installed on real base snapshot; first-run ok; selftest exit 0${last ? ": " + last.slice(0, 140) : ""}`,
            by: "github-actions[bot]",
          },
        },
      };
      rows.push([r.id, "✅", `selftest 0${last ? "；`" + last.slice(0, 80).replace(/`/g, "'") + "`" : ""}`]);
    } else {
      fails++;
      rows.push([r.id, "❌", `${code === 124 ? "超时（5 分钟）" : "退出码 " + code}${last ? "；`" + last.slice(0, 80).replace(/`/g, "'") + "`" : ""}`]);
    }
  }
  sudo("rm", "-rf", LIVE, SNAP);
}

fs.writeFileSync(OUT, JSON.stringify(passed, null, 2) + "\n");
const md = [
  `### CI 自动验证（底座 \`${tag}\` · shard ${shardIdx}/${shardTotal}）`,
  "",
  rows.length ? "| 组件 | 结果 | 说明 |\n|---|---|---|\n" + rows.map((r) => `| ${r.join(" | ")} |`).join("\n") : "本分片无待验证组件。",
  "",
  `通过 ${Object.keys(passed).length} 个，失败 ${fails} 个（硬件组件已跳过，仍须真机验证）。`,
  "",
].join("\n");
console.log("\n" + md);
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md);
if (STRICT && fails > 0) process.exit(1);
