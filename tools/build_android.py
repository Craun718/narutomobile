#!/usr/bin/env python3
"""Build a MaaAutoNaruto Android APK from the repository's PI and Python agent."""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DEBUG_ABIS = ("arm64-v8a",)
RELEASE_ABIS = ("arm64-v8a", "x86_64")
FRAMEWORK_LIBS = ("libMaaFramework.so", "libMaaAgentClient.so")
SDK_PLATFORM = "android-37.0"
BUILD_TOOLS = "37.0.0"
CMAKE_VERSION = "3.22.1"
SIGNING_ENV = ("KEYSTORE_PATH", "KEYSTORE_PASSWORD", "KEY_ALIAS", "KEY_PASSWORD")


class BuildError(RuntimeError):
    """An actionable build preparation or validation error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="准备 PI、Python agent 和 MaaFramework，并构建 MaaAutoNaruto Android APK。"
    )
    parser.add_argument("--release", action="store_true", help="构建 arm64-v8a + x86_64 Release")
    parser.add_argument("--install", action="store_true", help="构建并安装 Debug APK")
    parser.add_argument("--clean", action="store_true", help="构建前执行 Gradle clean")
    parser.add_argument("--refresh-framework", action="store_true", help="重新下载并铺 MaaFramework")
    parser.add_argument("--refresh-agent", action="store_true", help="重新构建 Python agent runtime")
    parser.add_argument("--unsigned", action="store_true", help="允许构建未签名 Release")
    parser.add_argument("--dry-run", action="store_true", help="只预检并打印计划，不生成文件")
    args = parser.parse_args(argv)
    if args.release and args.install:
        parser.error("--install 只能用于 Debug，不能与 --release 同时使用")
    if args.unsigned and not args.release:
        parser.error("--unsigned 只能与 --release 同时使用")
    return args


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("执行:", subprocess.list2cmdline(command))
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=capture,
    )


def git_output(repository: Path, *args: str) -> str:
    try:
        result = run(["git", "-C", str(repository), *args], cwd=repository, capture=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise BuildError(f"Git 校验失败: {' '.join(args)}") from exc
    return result.stdout.strip()


def validate_submodule(repository: Path, android: Path) -> None:
    gitmodules = repository / ".gitmodules"
    if not gitmodules.is_file():
        raise BuildError("缺少 .gitmodules，无法确认 android submodule")
    declaration = gitmodules.read_text(encoding="utf-8")
    if re.search(r"(?m)^\s*path\s*=\s*android\s*$", declaration) is None:
        raise BuildError(".gitmodules 没有声明 path = android")
    if not android.is_dir() or not (android / ".git").exists():
        raise BuildError("android submodule 尚未初始化；请运行: git submodule update --init --recursive android")
    if git_output(android, "rev-parse", "--is-inside-work-tree") != "true":
        raise BuildError("android 目录不是有效 Git 工作树")
    if not git_output(android, "rev-parse", "HEAD"):
        raise BuildError("android submodule 没有有效 HEAD")
    for relative in ("gradlew.bat", "settings.gradle.kts", "app"):
        if not (android / relative).exists():
            raise BuildError(f"android submodule 不完整，缺少: {relative}")


def read_properties(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    properties: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        properties[key.strip()] = value.strip().replace(r"\:", ":").replace(r"\\", "\\")
    return properties


def sdk_path(android: Path) -> Path:
    configured = read_properties(android / "local.properties").get("sdk.dir")
    configured = configured or os.environ.get("ANDROID_HOME")
    if not configured:
        raise BuildError("未配置 Android SDK；请设置 local.properties 的 sdk.dir 或 ANDROID_HOME")
    sdk = Path(configured).expanduser().resolve()
    if not sdk.is_dir():
        raise BuildError(f"Android SDK 目录不存在: {sdk}")
    return sdk


def validate_toolchain(repository: Path, android: Path) -> Path:
    try:
        java = run(["java", "-version"], cwd=repository, capture=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise BuildError("找不到可用的 JDK 17") from exc
    version_text = java.stderr + java.stdout
    if re.search(r'version "17(?:\.|\")', version_text) is None:
        raise BuildError("Android 构建要求 JDK 17；java -version 未报告版本 17")
    sdk = sdk_path(android)
    required = (
        sdk / "platforms" / SDK_PLATFORM,
        sdk / "build-tools" / BUILD_TOOLS,
        sdk / "cmake" / CMAKE_VERSION,
    )
    missing = [str(path) for path in required if not path.is_dir()]
    if missing:
        raise BuildError(
            "Android SDK 缺少构建组件:\n  "
            + "\n  ".join(missing)
            + "\n请在 Android Studio 的 SDK Manager > SDK Tools 中安装对应版本。"
        )
    return sdk


def validate_sources(repository: Path) -> None:
    interface = repository / "assets" / "interface.json"
    entrypoint = repository / "agent" / "main.py"
    requirements = repository / "requirements.txt"
    if not interface.is_file():
        raise BuildError(f"缺少 PI interface: {interface}")
    if re.search(r'"interface_version"\s*:\s*2\b', interface.read_text(encoding="utf-8")) is None:
        raise BuildError("assets/interface.json 不是 Project Interface V2")
    for path in (entrypoint, requirements):
        if not path.is_file():
            raise BuildError(f"缺少构建输入: {path}")


def framework_ready(android: Path, abis: tuple[str, ...]) -> bool:
    if not (android / ".maafwversion").is_file():
        return False
    root = android / "app" / "src" / "main" / "jniLibs"
    return all((root / abi / library).is_file() for abi in abis for library in FRAMEWORK_LIBS)


def agent_ready(repository: Path, abis: tuple[str, ...]) -> bool:
    root = repository / ".android-build" / "agent-dist"
    required = ("bundle/bin/python3", "bundle/agent-core.json")
    return all((root / abi / item).is_file() for abi in abis for item in required)


def copy_pi_staging(repository: Path) -> Path:
    build_root = repository / ".android-build"
    staging = build_root / "pi"
    temporary = build_root / "pi.tmp"
    backup = build_root / "pi.old"
    build_root.mkdir(parents=True, exist_ok=True)
    for path in (temporary, backup):
        if path.exists():
            shutil.rmtree(path)

    ignored = shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc")
    shutil.copytree(repository / "assets", temporary, ignore=ignored)
    shutil.copytree(repository / "agent", temporary / "agent", ignore=ignored)
    for name in ("CONTACT", "LICENSE"):
        source = repository / name
        if source.is_file():
            shutil.copy2(source, temporary / name)

    try:
        if staging.exists():
            staging.rename(backup)
        temporary.rename(staging)
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if not staging.exists() and backup.exists():
            backup.rename(staging)
        raise
    return staging


def validate_release_signing(unsigned: bool) -> None:
    if unsigned:
        return
    missing = [name for name in SIGNING_ENV if not os.environ.get(name)]
    if missing:
        raise BuildError("Release 缺少签名环境变量: " + ", ".join(missing) + "；或显式使用 --unsigned")
    keystore = Path(os.environ["KEYSTORE_PATH"]).expanduser()
    if not keystore.is_file():
        raise BuildError(f"KEYSTORE_PATH 指向的文件不存在: {keystore}")


def find_apk(android: Path, release: bool) -> Path:
    variant = "release" if release else "debug"
    output = android / "app" / "build" / "outputs" / "apk" / variant
    candidates = sorted(output.glob("*.apk"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise BuildError(f"Gradle 成功但未找到 {variant} APK: {output}")
    return candidates[0]


def validate_apk(apk: Path, abis: tuple[str, ...]) -> None:
    required = {
        "assets/pi.zip",
        "assets/pi.manifest",
        "assets/agent/bundle.zip",
        "assets/agent/agent-runtime.json",
        "assets/agent.fingerprint",
    }
    with zipfile.ZipFile(apk) as archive:
        names = set(archive.namelist())
        missing = sorted(required - names)
        if missing:
            raise BuildError("APK 缺少内容: " + ", ".join(missing))
        with zipfile.ZipFile(io.BytesIO(archive.read("assets/pi.zip"))) as pi_archive:
            pi_names = set(pi_archive.namelist())
            pi_missing = sorted({"interface.json", "agent/main.py"} - pi_names)
            if pi_missing:
                raise BuildError("APK 的 pi.zip 缺少内容: " + ", ".join(pi_missing))
        with zipfile.ZipFile(io.BytesIO(archive.read("assets/agent/bundle.zip"))) as bundle:
            bundle_names = set(bundle.namelist())
            runtime_missing = [
                f"{abi}/bin/python3" for abi in abis if f"{abi}/bin/python3" not in bundle_names
            ]
            if runtime_missing:
                raise BuildError("APK 的 agent bundle 缺少内容: " + ", ".join(runtime_missing))
        native_missing = [
            f"lib/{abi}/libMaaFramework.so"
            for abi in abis
            if f"lib/{abi}/libMaaFramework.so" not in names
        ]
        if native_missing:
            raise BuildError("APK 缺少目标 ABI 原生库: " + ", ".join(native_missing))


def planned_commands(repository: Path, android: Path, args: argparse.Namespace) -> list[list[str]]:
    abis = RELEASE_ABIS if args.release else DEBUG_ABIS
    commands: list[list[str]] = []
    if args.refresh_framework or not framework_ready(android, abis):
        commands.append(
            [
                sys.executable,
                str(android / "scripts" / "setup_maa_framework.py"),
                "--abi",
                "all" if args.release else "arm64-v8a",
            ]
        )
    if args.refresh_agent or not agent_ready(repository, abis):
        command = [
            sys.executable,
            str(repository / "tools" / "build_android_agent.py"),
            "--out",
            str(repository / ".android-build" / "agent-dist"),
        ]
        for abi in abis:
            command.extend(("--abi", abi))
        commands.append(command)
    profile = [
        sys.executable,
        str(repository / "tools" / "generate_pi_profile.py"),
        "--assets",
        str(repository / ".android-build" / "pi"),
        "--agent-source",
        str(repository / ".android-build" / "agent-dist"),
        "--force",
    ]
    for abi in abis:
        profile.extend(("--abi", abi))
    commands.append(profile)
    gradle = [str(android / "gradlew.bat")]
    if args.clean:
        gradle.append("clean")
    gradle.append(
        ":app:assembleRelease" if args.release else ":app:installDebug" if args.install else ":app:assembleDebug"
    )
    commands.append(gradle)
    return commands


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repository = Path(__file__).resolve().parent.parent
    android = repository / "android"
    abis = RELEASE_ABIS if args.release else DEBUG_ABIS
    try:
        print("[1/8] 校验 android submodule")
        validate_submodule(repository, android)
        print("[2/8] 校验工具链")
        validate_toolchain(repository, android)
        print("[3/8] 校验 PI 与 agent 源码")
        validate_sources(repository)
        if args.release:
            validate_release_signing(args.unsigned)

        commands = planned_commands(repository, android, args)
        if args.dry_run:
            print("Dry-run 计划:")
            for command in commands:
                print("  ", subprocess.list2cmdline(command))
            return 0

        index = 0
        if args.refresh_framework or not framework_ready(android, abis):
            print("[4/8] 准备 MaaFramework")
            run(commands[index], cwd=android)
            index += 1
        else:
            print("[4/8] MaaFramework 已就绪，跳过")

        print("[5/8] 建立 PI staging")
        staging = copy_pi_staging(repository)

        if args.refresh_agent or not agent_ready(repository, abis):
            print("[6/8] 构建 Python agent runtime")
            run(commands[index], cwd=repository)
            index += 1
        else:
            print("[6/8] Python agent runtime 已就绪，跳过")

        print("[7/8] 生成 PI profile")
        profile_command = commands[index]
        index += 1
        run(profile_command, cwd=repository)
        profile = repository / "pi-profile.yaml"
        if not profile.is_file() or not (staging / "agent" / "main.py").is_file():
            raise BuildError("PI staging 或 profile 生成不完整")

        print("[8/8] 执行 Gradle 并校验 APK")
        gradle_env = os.environ.copy()
        gradle_env["PI_PROFILE"] = str(profile)
        run(commands[index], cwd=android, env=gradle_env)
        apk = find_apk(android, args.release)
        validate_apk(apk, abis)
        print(f"构建完成: {apk}")
        print(f"类型: {'Release' if args.release else 'Debug'}；ABI: {', '.join(abis)}")
        return 0
    except BuildError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] 子命令失败，退出码 {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
    except OSError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
