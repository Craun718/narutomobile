import os
import platform
import sys

from .logger import logger


def _is_android() -> bool:
    if (
        sys.platform == "android"
        or "ANDROID_ROOT" in os.environ
        or os.path.exists("/system/build.prop")
        or "android" in platform.platform().lower()
    ):
        logger.info("当前正在安卓环境中运行")
        return True
    return False


is_android = _is_android()
