#!/usr/bin/env python3
"""检查仓库里是否写入了完整的客户免登录链接密钥。

规则：任何被跟踪的文件都不得包含 `web_form_request_key=<实际的 key>`。
占位写法（`<运行时生成>`、`${VAR}`、`{{ key }}`、`***`）允许。

用法：
    python tools/check_no_secrets.py                  # 检查工作区
    python tools/check_no_secrets.py --rev <sha>      # 检查某个提交（部署预检用）
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# 抓 `web_form_request_key=` 后面跟着看起来像真实密钥的串（长度 ≥ 16，且不是占位符）。
PATTERN = re.compile(r"web_form_request_key=([A-Za-z0-9_\-]{16,})")
PLACEHOLDER_HINTS = ("<", ">", "${", "{{", "***", "xxxx", "XXXX", "REDACTED", "运行时生成")

SKIP_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".pyc",
)


def tracked_files(repo: str, rev: str | None) -> list[str]:
    cmd = ["git", "-C", repo, "ls-tree", "-r", "--name-only", rev] if rev else \
          ["git", "-C", repo, "ls-files"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [name for name in out.splitlines() if name and not name.endswith(SKIP_SUFFIXES)]


def read(repo: str, rev: str | None, path: str) -> str:
    if rev:
        result = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"],
                                capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    try:
        with open(f"{repo}/{path}", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--rev", default=None, help="检查指定提交而非工作区")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    hits: list[tuple[str, int]] = []
    for path in tracked_files(args.repo, args.rev):
        content = read(args.repo, args.rev, path)
        if "web_form_request_key=" not in content:
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            for match in PATTERN.finditer(line):
                value = match.group(1)
                if any(hint in value for hint in PLACEHOLDER_HINTS):
                    continue
                hits.append((path, lineno))

    if not hits:
        if not args.quiet:
            print("未发现完整链接密钥")
        return 0

    print("发现完整客户链接密钥（禁止提交）：")
    for path, lineno in hits:
        print(f"  {path}:{lineno}")
    print("请改为占位写法，并用 tools/rotate_customer_links.py 撤销已泄露链接。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
