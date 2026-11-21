#!/usr/bin/env python3
"""跨仓库 scope_key 平价检查：reli-lims ↔ cnas-workbench（只读）。

不要修改 cnas-workbench：本脚本用 ``git show <ref>:server/testing_bridge.py``
把对端实现取到临时目录再 import，工作树与索引都不动。

用法：
    CNAS_WORKBENCH=/path/to/cnas-workbench python3 tools/check_cnas_scope_key_parity.py
    python3 tools/check_cnas_scope_key_parity.py --repo /path --ref feat/p0-hardening-20261114
    python3 tools/check_cnas_scope_key_parity.py --repo /path --write-vectors   # 重算向量

退出码：0 全部一致；1 实现不一致或向量过期；2 环境问题（仓库/分支取不到）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import atexit
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reli_lims.cnas_scope import normalize_identity, scope_key  # noqa: E402

# 默认值只作提示：真实路径/分支用 --repo / --ref 或环境变量给，避免把个人
# 机器路径与临时特性分支写死进仓库。
DEFAULT_REPO = os.environ.get("CNAS_WORKBENCH", "")
DEFAULT_REF = os.environ.get("CNAS_WORKBENCH_REF", "main")

EXIT_OK, EXIT_MISMATCH, EXIT_ENV = 0, 1, 2
VECTOR_FILE = os.path.join(ROOT, "tests", "fixtures", "cnas_scope_key_vectors.json")


def _git(repo, *args):
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{result.stderr.strip()}")
    return result.stdout


def load_bridge(repo, ref):
    source = _git(repo, "show", f"{ref}:server/testing_bridge.py")
    commit = _git(repo, "rev-parse", ref).strip()
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    directory = tempfile.mkdtemp(prefix="cnas-parity-")
    atexit.register(shutil.rmtree, directory, True)
    path = os.path.join(directory, "testing_bridge.py")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(source)
    spec = importlib.util.spec_from_file_location("cnas_bridge_for_parity", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cnas_bridge_for_parity"] = module
    spec.loader.exec_module(module)
    return module, commit, digest


def load_vectors():
    with open(VECTOR_FILE, encoding="utf-8") as stream:
        return json.load(stream)


def write_vectors(bridge, ref, commit, digest):
    """只更新 ref/commit/file_sha256 与期望键；source.repo 保持不变，避免把
    本地绝对路径写进 fixture 破坏溯源信息。"""
    fixture = load_vectors()
    for item in fixture["vectors"]:
        item["expected_scope_key"] = bridge.scope_key(item["laboratory"], item["row"])
    fixture["source"].update(ref=ref, commit=commit, file_sha256=digest)
    with open(VECTOR_FILE, "w", encoding="utf-8") as stream:
        json.dump(fixture, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"已重写 {os.path.relpath(VECTOR_FILE, ROOT)}：{len(fixture['vectors'])} 条向量")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("CNAS_WORKBENCH", DEFAULT_REPO))
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--write-vectors", action="store_true")
    args = parser.parse_args(argv)

    if not args.repo:
        print("需要 --repo，或设置环境变量 CNAS_WORKBENCH=<cnas-workbench 路径>",
              file=sys.stderr)
        return EXIT_ENV
    if not os.path.isdir(os.path.join(args.repo, ".git")):
        print(f"环境问题：{args.repo} 不是 git 仓库", file=sys.stderr)
        return EXIT_ENV

    try:
        bridge, commit, digest = load_bridge(args.repo, args.ref)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ENV
    if not hasattr(bridge, "scope_key"):
        print(f"环境问题：{args.ref} 的 testing_bridge.py 还没有 scope_key()",
              file=sys.stderr)
        return EXIT_ENV

    if args.write_vectors:
        return write_vectors(bridge, args.ref, commit, digest)

    fixture = load_vectors()
    name_width = max(len(item["name"]) for item in fixture["vectors"]) + 2
    print(f"cnas-workbench {args.ref} @ {commit[:7]}  bridge sha256 {digest[:12]}")
    print(f"{'vector'.ljust(name_width)} {'cnas':12} {'reli-lims':12} 结果  说明")
    print("-" * (name_width + 60))
    failures = []
    stale = []
    for item in fixture["vectors"]:
        theirs = bridge.scope_key(item["laboratory"], item["row"])
        ours = scope_key(item["laboratory"], item["row"])
        same = theirs == ours
        recorded = item.get("expected_scope_key")
        if not same:
            failures.append((item["name"], theirs, ours))
            status = "DIFF"
        elif recorded and recorded != theirs:
            stale.append((item["name"], recorded, theirs))
            status = "STALE"
        else:
            status = "ok"
        print(f"{item['name'].ljust(name_width)} {theirs[:12]:12} {ours[:12]:12} "
              f"{status:6} {item['note']}")
    print("-" * (name_width + 60))
    print(f"合计 {len(fixture['vectors'])} 条，实现不一致 {len(failures)} 条，"
          f"向量过期 {len(stale)} 条")
    for name, theirs, ours in failures:
        print(f"  ✗ DIFF  {name}: cnas={theirs} reli-lims={ours}")
    for name, recorded, theirs in stale:
        print(f"  ✗ STALE {name}: fixture={recorded} cnas={theirs}"
              "（对端实现变了，需 --write-vectors 并人工确认）")
    if failures or stale:
        return EXIT_MISMATCH
    identity = normalize_identity("LAB-L11464", fixture["vectors"][0]["row"])
    print(f"身份向量示例：{identity}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
