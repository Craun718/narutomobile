#!/usr/bin/env python3
"""Build MaaAutoNaruto's Python agent runtime for the Android app."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="调用 Android runtime 构建器，生成 MaaAutoNaruto Python agent bundle。"
    )
    parser.add_argument(
        "--out",
        default=".android-build/agent-dist",
        help="输出目录，相对路径以仓库根目录为基准（默认: .android-build/agent-dist）",
    )
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="依赖文件，相对路径以仓库根目录为基准（默认: requirements.txt）",
    )
    parser.add_argument(
        "--abi",
        action="append",
        choices=("arm64-v8a", "x86_64"),
        help="目标 ABI，可重复指定（默认: arm64-v8a）",
    )
    parser.add_argument(
        "--pillow-version",
        default="11.0.0",
        help="Chaquopy Android wheel 中的 Pillow 版本（默认: 11.0.0）",
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="允许 pip 重新解析传递依赖；默认按锁定清单使用 --no-deps",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印底层命令，不下载或构建"
    )
    args, extra = parser.parse_known_args()
    return args, extra


def repository_path(value: str, repository: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


def main() -> int:
    args, extra = parse_args()
    repository = Path(__file__).resolve().parent.parent
    builder = repository / "android" / "scripts" / "build_agent_bundle.py"
    requirements = repository_path(args.requirements, repository)
    output = repository_path(args.out, repository)

    if not builder.is_file():
        raise FileNotFoundError(f"找不到 Android agent 构建器: {builder}")
    if not requirements.is_file():
        raise FileNotFoundError(f"找不到依赖文件: {requirements}")

    command = [
        sys.executable,
        str(builder),
        "--out",
        str(output),
        "--requirements",
        str(requirements),
        "--exclude",
        "pillow",
        "--require",
        f"pillow=={args.pillow_version}",
        "--extra-index-url",
        "https://chaquo.com/pypi-13.1/",
    ]
    if not args.with_deps:
        command.append("--no-deps")
    for abi in args.abi or ["arm64-v8a"]:
        command.extend(("--abi", abi))
    command.extend(extra)

    print("执行:", subprocess.list2cmdline(command))
    if args.dry_run:
        return 0
    subprocess.run(command, cwd=repository, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
