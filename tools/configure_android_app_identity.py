#!/usr/bin/env python3

import argparse
from pathlib import Path

PUBLIC_ID = "man"
PUBLIC_LABEL = "MAN"
INTERNAL_ID = "man.ci"
INTERNAL_LABEL = "MAN 内测版"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure the Android app identity")
    parser.add_argument(
        "--distribution",
        choices=("public", "internal"),
        required=True,
        help="artifact distribution",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("Android/profile.yaml"),
        help="Android profile path",
    )
    return parser.parse_args()


def has_identity(text: str, app_id: str, label: str) -> bool:
    return text.count(f"  id: {app_id}\n") == 1 and text.count(f"  label: {label}\n") == 1


def configure(profile: Path, distribution: str) -> None:
    text = profile.read_text(encoding="utf-8")
    original_text = text
    has_public_identity = has_identity(text, PUBLIC_ID, PUBLIC_LABEL)
    has_internal_identity = has_identity(text, INTERNAL_ID, INTERNAL_LABEL)
    if distribution == "internal":
        if has_public_identity and has_internal_identity:
            raise SystemExit(f"found both public and internal app identities in {profile}")
        if has_public_identity:
            text = text.replace(f"  id: {PUBLIC_ID}\n", f"  id: {INTERNAL_ID}\n")
            text = text.replace(
                f"  label: {PUBLIC_LABEL}\n",
                f"  label: {INTERNAL_LABEL}\n",
            )
        elif not has_internal_identity:
            raise SystemExit(
                f"could not identify public or internal app identity in {profile}",
            )
    else:
        if not has_public_identity or has_internal_identity:
            raise SystemExit(f"could not identify public app identity in {profile}")
    if text != original_text:
        profile.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    configure(args.profile, args.distribution)


if __name__ == "__main__":
    main()
