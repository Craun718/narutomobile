import os

from .logger import logger


def _is_android() -> bool:
    if "ANDROID_ROOT" in os.environ:
        logger.info("当前正在安卓环境中运行")
        return True
    return False


is_android = _is_android()
