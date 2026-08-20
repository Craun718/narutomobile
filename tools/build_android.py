#!/usr/bin/env python3
"""Build the Android debug APK locally using the same steps as CI."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANDROID_ROOT = REPO_ROOT / "Android" / "MaaFwApp"
AGENT_OUTPUT = REPO_ROOT / "Android" / "agent-dist"
DEFAULT_ABI = "arm64-v8a"
DEFAULT_MAAFW_TAG = "v5.12.3"


def run(*command: str | Path, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"+ {printable}", flush=True)
    subprocess.run([str(part) for part in command], cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Android debug APK (equivalent to android.yml).")
    parser.add_argument("--abi", default=DEFAULT_ABI)
    parser.add_argument("--maafw-tag", default=DEFAULT_MAAFW_TAG)
    parser.add_argument(
        "--skip-native-download",
        action="store_true",
        help="Reuse MaaFramework files already present in .maa-cache.",
    )
    parser.add_argument(
        "--skip-agent-bundle",
        action="store_true",
        help="Reuse the existing Android/agent-dist directory.",
    )
    return parser.parse_args()


def check_environment() -> Path:
    sdk_value = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if not sdk_value:
        raise RuntimeError("Set ANDROID_SDK_ROOT (or ANDROID_HOME) to the Android SDK.")

    sdk_root = Path(sdk_value).expanduser().resolve()
    if not sdk_root.is_dir():
        raise RuntimeError(f"Android SDK directory does not exist: {sdk_root}")

    if shutil.which("java") is None:
        raise RuntimeError("Java was not found in PATH. Install JDK 17 (matching CI).")

    java_version = subprocess.run(["java", "-version"], capture_output=True, text=True, check=True)
    version_text = java_version.stderr + java_version.stdout
    if not re.search(r'version "17(?:\.|\")', version_text):
        print(f"WARNING: CI uses JDK 17; current Java is:\n{version_text.strip()}")

    gradle_wrapper = ANDROID_ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradle_wrapper.is_file():
        raise RuntimeError(f"Gradle wrapper not found: {gradle_wrapper}")
    return sdk_root


def write_local_properties(sdk_root: Path, abi: str) -> None:
    # Java properties require ':' to be escaped; forward slashes work cross-platform.
    sdk_property = sdk_root.as_posix().replace(":", r"\:")
    content = f"sdk.dir={sdk_property}\npi.profile=../profile.yaml\nbuild.debugAbi={abi}\n"
    (ANDROID_ROOT / "local.properties").write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    sdk_root = check_environment()
    write_local_properties(sdk_root, args.abi)

    print("[1/4] Preparing Android PI tree...")
    run(sys.executable, "tools/prepare_android_pi.py")

    print(f"[2/4] Preparing MaaFramework ({args.maafw_tag}, {args.abi})...")
    native_command: list[str | Path] = [
        sys.executable,
        "Android/MaaFwApp/scripts/setup_maa_framework.py",
        "--abi",
        args.abi,
        "--tag",
        args.maafw_tag,
    ]
    if args.skip_native_download:
        native_command.append("--skip-download")
    run(*native_command)

    if args.skip_agent_bundle:
        print("[3/4] Reusing existing agent bundle...")
        if not AGENT_OUTPUT.is_dir():
            raise RuntimeError(f"Agent bundle does not exist: {AGENT_OUTPUT}. Run again without --skip-agent-bundle.")
    else:
        print("[3/4] Packing agent runtime...")
        run(
            sys.executable,
            "Android/MaaFwApp/scripts/build_agent_bundle.py",
            "--out",
            AGENT_OUTPUT,
            "--requirements",
            REPO_ROOT / "requirements.txt",
            "--exclude",
            "pillow",
            "--exclude",
            "win32-setctime",
            "--exclude",
            "colorama",
            "--exclude",
            "jeepney",
            "--require",
            "pillow==11.0.0",
            "--extra-index-url",
            "https://chaquo.com/pypi-13.1/",
        )

    print("[4/4] Assembling debug APK...")
    # cwd does not participate in CreateProcess executable lookup on Windows,
    # so pass the wrapper's resolved path instead of only "gradlew.bat".
    wrapper = ANDROID_ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew")
    run(wrapper, "--no-daemon", ":app:assembleDebug", cwd=ANDROID_ROOT)

    apk = ANDROID_ROOT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if not apk.is_file():
        raise RuntimeError(f"Gradle completed, but the APK was not found: {apk}")
    print(f"Build completed: {apk}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
