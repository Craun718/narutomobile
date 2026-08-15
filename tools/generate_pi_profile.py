#!/usr/bin/env python3
"""Generate pi-profile.yaml from pi-profile.sample.yaml with absolute paths."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def absolute_path(value: str, repository: Path) -> Path:
    """Resolve a command-line path relative to the repository root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


def yaml_path(path: Path) -> str:
    """Return a YAML-friendly absolute path (also works on Windows)."""
    return path.as_posix()


def replace_field(content: str, field: str, value: Path) -> str:
    pattern = rf"(?m)^(\s*{re.escape(field)}:\s*).*$"
    updated, count = re.subn(pattern, rf"\g<1>{yaml_path(value)}", content, count=1)
    if count != 1:
        raise ValueError(f"示例配置中未找到字段: {field}")
    return updated


def agent_abis(content: str) -> list[str]:
    """Read the simple inline agent ABI list used by the profile template."""
    match = re.search(r"(?m)^\s*abi:\s*\[([^]]*)]\s*$", content)
    if match is None:
        return []
    abis = [item.strip().strip("'\"") for item in match.group(1).split(",")]
    return [abi for abi in abis if abi]


def replace_agent_abis(content: str, abis: list[str]) -> str:
    """Replace the template's simple inline agent ABI list."""
    pattern = r"(?m)^(\s*abi:\s*)\[[^]]*](\s*)$"
    value = ", ".join(abis)
    updated, count = re.subn(pattern, rf"\g<1>[{value}]\g<2>", content, count=1)
    if count != 1:
        raise ValueError("示例配置中未找到 agent.abi")
    return updated


def missing_agent_abis(agent_source: Path, abis: list[str]) -> list[str]:
    """Return ABIs whose minimum runnable CPython bundle is absent."""
    required = ("bundle/bin/python3", "bundle/agent-core.json")
    return [
        abi
        for abi in abis
        if any(not (agent_source / abi / item).is_file() for item in required)
    ]


def check_android_agent(repository: Path, agent_source: Path, abis: list[str]) -> None:
    """Stop with an actionable reminder when an Android agent runtime is absent."""
    missing = missing_agent_abis(agent_source, abis)
    if not missing:
        if abis:
            print(f"Android agent runtime 已存在: {', '.join(abis)}")
        return

    launcher = repository / "tools" / "build_android_agent.py"
    if not launcher.is_file():
        raise FileNotFoundError(f"找不到 Android agent 构建脚本: {launcher}")

    command = [sys.executable, str(launcher), "--out", str(agent_source)]
    for abi in missing:
        command.extend(("--abi", abi))
    raise SystemExit(
        f"缺少 Android agent runtime: {', '.join(missing)}\n"
        "请先执行以下命令，完成后再重新生成 profile：\n"
        f"  {subprocess.list2cmdline(command)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="复制 pi-profile.sample.yaml 并自动填写绝对路径。"
    )
    parser.add_argument("--assets", default="assets", help="PI 资源根目录（默认: assets）")
    parser.add_argument(
        "--agent-source",
        default=".android-build/agent-dist",
        help="Agent 运行时产物目录（默认: .android-build/agent-dist）",
    )
    parser.add_argument(
        "--icon", default="docs/imgs/logo.png", help="应用图标（默认: docs/imgs/logo.png）"
    )
    parser.add_argument(
        "--abi",
        action="append",
        choices=("arm64-v8a", "x86_64"),
        help="Agent ABI，可重复指定；默认沿用模板",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已经存在的 pi-profile.yaml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = Path(__file__).resolve().parent.parent
    source = repository / "pi-profile.sample.yaml"
    destination = repository / "pi-profile.yaml"

    if not source.is_file():
        raise FileNotFoundError(f"找不到示例配置: {source}")
    if destination.exists() and not args.force:
        raise FileExistsError(f"目标文件已存在: {destination}（如需覆盖，请添加 --force）")

    template = source.read_text(encoding="utf-8")
    agent_source = absolute_path(args.agent_source, repository)
    selected_abis = args.abi or agent_abis(template)
    check_android_agent(repository, agent_source, selected_abis)

    # Copy first so file metadata and the requested copy semantics are preserved.
    shutil.copy2(source, destination)
    content = destination.read_text(encoding="utf-8")
    content = replace_field(content, "assets", absolute_path(args.assets, repository))
    content = replace_field(content, "sourceDir", agent_source)
    content = replace_field(content, "icon", absolute_path(args.icon, repository))
    content = replace_agent_abis(content, selected_abis)
    destination.write_text(content, encoding="utf-8", newline="\n")

    print(f"已生成: {destination}")


if __name__ == "__main__":
    main()
