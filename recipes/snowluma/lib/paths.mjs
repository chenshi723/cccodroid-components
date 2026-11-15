import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

// $PREFIX/share/cccodroid/components/snowluma/lib -> $PREFIX
export const PREFIX =
  process.env.PREFIX ||
  path.resolve(HERE, "..", "..", "..", "..", "..");

export const HOME = process.env.HOME || os.homedir();
export const ROOT =
  process.env.CCCODROID_SNOWLUMA_DATA || path.join(HOME, ".cccodroid", "snowluma");

export const DATA = path.join(ROOT, "data");
export const DEBROOT = path.join(DATA, "debroot");
export const QQ_DIR = path.join(DEBROOT, "opt", "QQ");
export const QQ_BIN = path.join(QQ_DIR, "qq");
export const SL_DIR = path.join(DATA, "snowluma");
export const SL_BIN = path.join(SL_DIR, "node");
export const SL_INDEX = path.join(SL_DIR, "index.mjs");
export const SL_CONFIG = path.join(SL_DIR, "config");
export const ONE_BOT_CONFIG = path.join(SL_CONFIG, "onebot.json");
export const SL_RUNTIME_CONFIG = path.join(SL_CONFIG, "runtime.json");
export const SL_WEBUI_AUTH = path.join(SL_CONFIG, "webui.json");
export const SL_LICENSE = path.join(SL_DIR, "LICENSE");
export const SL_SHIM = path.join(SL_DIR, "lib");
export const QR_FILE = path.join(DATA, "cache", "qr.png");

export const CONFIG_FILE = path.join(ROOT, "config.json");
export const API_KEY_FILE = path.join(ROOT, "model-key.txt");
export const STATE_FILE = path.join(ROOT, "state.json");
export const SETUP_FILE = path.join(DATA, "setup.json");
export const LOG_DIR = path.join(ROOT, "logs");
export const HOME_DIR = path.join(DATA, "home");
export const TMP_DIR = path.join(DATA, "tmp");
export const RUN_DIR = path.join(DATA, "run");
export const CACHE_DIR = path.join(DATA, "cache");
export const LIB_DIR = path.join(DATA, "snowluma-libpath.txt");

export const LIB_INSTALLER = path.join(
  PREFIX,
  "share",
  "cccodroid",
  "components",
  "snowluma",
  "lib",
  "install.py",
);
export const LIB_SELFTEST = path.join(HERE, "selftest.mjs");
export const LIB_SUPERVISOR = path.join(HERE, "supervisor.mjs");

export function ensureLayout() {
  for (const d of [ROOT, DATA, LOG_DIR, HOME_DIR, TMP_DIR, RUN_DIR, CACHE_DIR]) {
    fs.mkdirSync(d, { recursive: true, mode: 0o700 });
  }
  try {
    fs.chmodSync(RUN_DIR, 0o700);
  } catch {}
}

export function nodeBin() {
  return process.execPath;
}

export function pythonBin() {
  return process.env.PYTHON || "python3";
}
