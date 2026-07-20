import json
from base64 import b64decode
from datetime import datetime
from pathlib import Path

# 获取当前main.py路径并设置上级目录为工作目录
current_file_path = Path(__file__).resolve()  # 当前脚本的绝对路径
current_script_dir = current_file_path.parent  # 包含此脚本的目录
project_root_dir = current_script_dir.parent  # 假定的项目根目录
resource_base = project_root_dir / "resources" / "base"


def get_format_timestamp():
    now = datetime.now()
    date = now.strftime("%Y.%m.%d")
    time = now.strftime("%H.%M.%S")
    milliseconds = f"{now.microsecond // 1000:03d}"

    return f"{date}-{time}.{milliseconds}"


bdc = lambda s: b64decode(s).decode("utf-8")  # noqa: E731
jL = json.load
jD = json.dump
root = Path(__file__).resolve().parent.parent.parent

is_debug = any(root.glob("MFAAvalonia*"))
logo = (root / "docs" / "imgs" / "logo.png").absolute()
