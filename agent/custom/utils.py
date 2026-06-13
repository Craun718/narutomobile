from random import randint
from typing import Iterable
from time import sleep
import os
import random
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from PIL import Image
from notifypy import Notify
from maa.context import Context
from maa.define import RectType

from utils import get_format_timestamp
from utils import bdc, root, jL, jD, logo
from utils.logger import log_dir, logger


def save_screenshot(context: Context):
    """
    保存截图
    """
    # image array(BGR)
    screen_array = context.tasker.controller.cached_image

    # Check resolution aspect ratio
    height, width = screen_array.shape[:2]
    aspect_ratio = width / height
    target_ratio = 16 / 9
    # Allow small deviation (within 1%)
    if abs(aspect_ratio - target_ratio) / target_ratio > 0.01:
        logger.error(f"当前模拟器分辨率不是16:9! 当前分辨率: {width}x{height}")

    # BGR2RGB
    if len(screen_array.shape) == 3 and screen_array.shape[2] == 3:
        rgb_array = screen_array[:, :, ::-1]
    else:
        rgb_array = screen_array
        logger.warning("当前截图并非三通道")

    img = Image.fromarray(rgb_array)

    save_dir = log_dir
    os.makedirs(save_dir, exist_ok=True)
    time_str = get_format_timestamp()
    img.save(f"{save_dir}/{time_str}.png")
    logger.info(f"截图保存至 {save_dir}/{time_str}.png")


def fast_ocr(
    context: Context,
    expected: str | list[str],
    roi: tuple[int, int, int, int],
    absolutely=False,
    screenshot_refresh=True,
) -> RectType | None:
    """重新截图并进行 OCR 识别"""
    if screenshot_refresh:
        context.tasker.controller.post_screencap().wait()
    if not isinstance(expected, Iterable):
        expected = [expected]

    reco_detail = context.run_recognition(
        "custom_ocr",
        context.tasker.controller.cached_image,
        {
            "custom_ocr": {
                "recognition": {
                    "type": "OCR",
                    "param": {"expected": expected, "roi": roi},
                }
            }
        },
    )
    if reco_detail is None:
        return None

    if reco_detail.hit is False or reco_detail.best_result is None:
        return None

    if not absolutely:
        logger.debug(f"OCR 识别成功: {reco_detail.best_result.text}")  # type: ignore
        return reco_detail.best_result.box  # type: ignore
    else:
        # 提前提取所有文本，避免重复生成列表
        filtered_texts = [
            res.text  # ty:ignore[unresolved-attribute]
            for res in reco_detail.filtered_results
        ]

        result = None
        logger.debug(f"OCR 绝对匹配尝试: {expected} in {filtered_texts}")
        for target in expected:
            if target in filtered_texts:
                # 找到第一个匹配的结果
                result = next(
                    res
                    for res in reco_detail.filtered_results
                    if res.text == target  # ty:ignore[unresolved-attribute]
                )
                logger.debug(
                    f"OCR 绝对匹配成功: {target} in {reco_detail.filtered_results} with {result}"
                )
                break

        if result is not None:
            logger.debug(f"OCR 绝对匹配成功: {expected}")
            return result.box  # ty:ignore[unresolved-attribute]
        else:
            logger.debug(f"{expected} 绝对匹配失败：{reco_detail.filtered_results}")
            return None


def wait_for_freezes(context: Context, wait_for_freezes: int = 200):
    context.run_task(
        "wait_for_freezes", {"wait_for_freezes": {"wait_for_freezes": wait_for_freezes}}
    )


def check_resolution(context: Context):
    resolution = context.tasker.controller.resolution
    if resolution[1] > resolution[0]:
        resolution = (resolution[1], resolution[0])
    if abs((resolution[0] / resolution[1]) - (16.0 / 9.0)) > 0.02:
        logger.error("你可能正在使用非推荐的分辨率！")
        logger.error("推荐使用的分辨率：1920x1080")
        logger.error(f"当前使用的分辨率：{resolution[0]}x{resolution[1]}")


def validate_config(context: Context):
    if len(list(root.glob("*.exe"))) == 0:
        return
    fp = [p for p in (root).glob("*.json") if p.name.startswith("in")][0]
    logger.info(f"验证配置文件: {fp}")
    config = jL(fp.open(encoding="utf-8"))
    config.update(
        {
            bdc("bmFtZQ=="): bdc("TWFhQXV0b05hcnV0bw=="),
            bdc("Z2l0aHVi"): bdc(
                "aHR0cHM6Ly9naXRodWIuY29tL2R1b3J1YS9uYXJ1dG9tb2JpbGU="
            ),
            bdc("bWlycm9yY2h5YW5fcmlk"): bdc("TWFhQXV0b05hcnV0bw=="),
        }
    )
    jD(config, fp.open("w", encoding="utf-8"), ensure_ascii=False, indent=4)


def click(context: Context, x: int, y: int, w: int = 1, h: int = 1):
    context.tasker.controller.post_click(
        random.randint(x, x + w - 1), random.randint(y, y + h - 1)
    ).wait()


def validate_mfa(context: Context):
    fps = [p for p in (root / "config").glob("*.json") if p.name.startswith("c")]
    if len(fps) != 0:
        fp = fps[0]
    else:
        return
    mfa = jL(fp.open(encoding="utf-8"))
    if mfa.get(bdc("RG93bmxvYWRDREs="), "") == "":
        mfa.update(
            {
                bdc("RG93bmxvYWRTb3VyY2VJbmRleA=="): 0,
            }
        )

    mfa.update(
        {
            bdc("RW5hYmxlQXV0b1VwZGF0ZVJlc291cmNl"): True,
            bdc("RW5hYmxlQXV0b1VwZGF0ZU1GQQ=="): True,
        }
    )


def fast_swipe(
    context: Context,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: int = 300,
    end_hold: bool = True,
    after_swipe_delay: int = 300,
):
    """
    快速滑动屏幕
    :param context: 上下文对象
    :param start_x: 起始点X坐标
    :param start_y: 起始点Y坐标
    :param end_x: 终点X坐标
    :param end_y: 终点Y坐标
    :param duration: 滑动持续时间,不建议低于200,单位毫秒
    :param end_hold: 滑动结束后是否急停,防止惯性滑动
    :param after_swipe_delay: 滑动完成后的延迟时间,单位毫秒

    如果要防止滑动动画存在惯性,end_hold参数需设置为0
    反之,如果要利用惯性滑动,需要将end_hold设为非0值
    """

    # 滑动参数增加随机噪声
    # 以防魔方真投入
    context.run_action(
        "custom_swipe",
        pipeline_override={
            "custom_swipe": {
                # 疑似有闭包问题
                # 采用手动随机而不是maafw自带的随机
                "begin": [random.randint(start_x - 50, start_x + 50), start_y],
                "end": [random.randint(end_x - 50, end_x + 50), end_y],
                "duration": randint(duration - 100, duration + 100),
                "end_hold": randint(100, 200) if end_hold else 0,
            }
        },
    )
    sleep(after_swipe_delay / 1000)


def click_and_wait_for_freezes(
    context: Context,
    x: int,
    y: int,
    w: int = 1,
    h: int = 1,
    post_wait_freezes: int = 200,
):
    """
    点击并等待屏幕静止
    :param context: 上下文对象
    :param x: 点击点X坐标
    :param y: 点击点Y坐标
    :param w: 点击点宽度范围
    :param h: 点击点高度范围
    :param post_wait_freezes: 点击后等待屏幕静止的时间,单位毫秒
    """
    context.run_task(
        "click_and_wait_for_freezes",
        {
            "click_and_wait_for_freezes": {
                "target": [x, y, w, h],
                "post_wait_freezes": post_wait_freezes,
            }
        },
    )


def nonlinear_swipe(
    context: Context,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: int = 150,
    end_hold: bool = False,
    after_swipe_delay: int = 300,
    steps: int = 7,  # 滑动分段
):
    """
    非线性滑动,形参参考fast_swipe()
    """

    s_x = random.randint(start_x - 50, start_x + 50)
    s_y = random.randint(start_y - 50, start_y + 50)
    e_x = random.randint(end_x - 50, end_x + 50)
    e_y = random.randint(end_y - 50, end_y + 50)
    total_dur = random.randint(duration - 100, duration + 100)
    hold_time = random.randint(100, 200) if end_hold else 0

    points = []
    dur_list = []
    total_prog = 0.0

    for i in range(1, steps + 1):
        # 非线性进度计算
        t = i / steps
        prog = 1 - (1 - t) ** 2
        delta = prog - total_prog
        total_prog = prog

        # 计算当前坐标
        curr_x = int(s_x + (e_x - s_x) * prog)
        curr_y = int(s_y + (e_y - s_y) * prog)
        points.append([curr_x, curr_y])
        dur_list.append(round(total_dur * delta))

    # 总时长
    dur_list[-1] += total_dur - sum(dur_list)

    context.run_action(
        "custom_swipe",
        pipeline_override={
            "custom_swipe": {
                "action": "Swipe",
                "begin": [s_x, s_y],
                "end": points,  # 途径点
                "end_hold": hold_time,
                "duration": dur_list,  # 分段时间
            }
        },
    )
    sleep(after_swipe_delay / 1000)


def send_notification(title: str = "系统通知", msg: str = "这是一条测试消息"):
    Notify(title, msg, "MaaAutoNaruto", logo.__str__()).send()


# 日志文件清理基准时间
DEFAULT_BASE_TIME = datetime(2025, 5, 1, 0, 0, 0, 0)
# 每次任务调用一次utils.py,因此不用持久化;由 CleanupMaafwBakLogs 设置,供日志文件清理节点使用
base_time_for_cleanup: Optional[datetime] = DEFAULT_BASE_TIME


def extract_datetime_from_log_name(filename: str) -> Optional[datetime]:
    """
    从日志文件名中提取 datetime
    """
    try:
        middle = filename.replace("maafw.bak.", "").replace(".log", "")
        if "-" in middle:
            date_part, time_part = middle.split("-")
            year, month, day = date_part.split(".")
            time_components = time_part.split(".")
            if len(time_components) == 4:
                hour, minute, second, millisecond = time_components
            elif len(time_components) == 3:
                hour, minute, sec_ms = time_components
                if "." in sec_ms:
                    second, millisecond = sec_ms.split(".")
                else:
                    second = sec_ms
                    millisecond = "0"
            else:
                return None
            microsecond = int(millisecond.ljust(6, "0")[:6])
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second),
                microsecond,
            )
        else:
            # 中断导致没有时间部分的情况,此时时间部分设为 23:59:59.999999
            date_str = middle.rstrip(".")
            parts = date_str.split(".")
            if len(parts) == 3:
                year, month, day = parts
                return datetime(int(year), int(month), int(day), 23, 59, 59, 999999)
            else:
                return None
    except Exception:
        return None


def extract_datetime_from_image_name(filename: str) -> Optional[datetime]:
    try:
        base = filename.split("_")[0]
        date_part, time_part = base.split("-")
        year, month, day = date_part.split(".")
        time_components = time_part.split(".")
        if len(time_components) == 4:
            hour, minute, second, millisecond = time_components
        elif len(time_components) == 3:
            hour, minute, sec_ms = time_components
            if "." in sec_ms:
                second, millisecond = sec_ms.split(".")
            else:
                second = sec_ms
                millisecond = "0"
        else:
            return None
        microsecond = int(millisecond.ljust(6, "0")[:6])
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            microsecond,
        )
    except Exception:
        return None


def cleanup_maafw_bak_logs(debug_folder: Path, keep_count: int):
    """
    清理旧的 maafw.bak.*.log 文件,保留最新的 keep_count 个。
    如果有日志被删除,将全局变量 base_time_for_cleanup 更新为被删除日志中最晚的时间;
    否则重置为 DEFAULT_BASE_TIME
    """
    global base_time_for_cleanup
    log_files = list(debug_folder.glob("maafw.bak.*.log"))
    print(f"[日志清理] 找到日志总数: {len(log_files)}")
    if not log_files:
        print("[日志清理] 无符合格式的日志，跳过")
        base_time_for_cleanup = DEFAULT_BASE_TIME
        return

    logs_with_time = []
    for log_path in log_files:
        dt = extract_datetime_from_log_name(log_path.name)
        if dt:
            logs_with_time.append((dt, log_path))
        else:
            print(f"[日志清理] 无法解析日志时间,跳过: {log_path.name}")

    if not logs_with_time:
        print("[日志清理] 所有日志均无法解析时间,跳过")
        base_time_for_cleanup = DEFAULT_BASE_TIME
        return

    logs_with_time.sort(key=lambda x: x[0], reverse=True)
    to_delete_logs = logs_with_time[keep_count:]

    if not to_delete_logs:
        print("[日志清理] 没有需要删除的日志")
        base_time_for_cleanup = DEFAULT_BASE_TIME
        return

    print(f"[日志清理] 待删除旧日志: {len(to_delete_logs)} 个")
    for dt, log_path in to_delete_logs:
        try:
            log_path.unlink()
            print(f"[日志清理] 已删除: {log_path.name} (时间 {dt})")
        except Exception as e:
            print(f"[日志清理] 删除失败 {log_path.name}: {e}")

    # 更新基准时间为被删除日志中最晚的时间
    deleted_latest = to_delete_logs[0][0]
    print(f"[日志清理] 被删除日志中最晚时间: {deleted_latest}")
    base_time_for_cleanup = deleted_latest


def extract_datetime_from_image_name(filename: str) -> Optional[datetime]:
    """
    从图片文件名中提取 datetime
    """
    try:
        stem = filename.rsplit(".", 1)[0]
        base = stem.split("_")[0]
        date_part, time_part = base.split("-")
        year, month, day = date_part.split(".")
        time_components = time_part.split(".")
        if len(time_components) == 4:
            hour, minute, second, millisecond = time_components
        elif len(time_components) == 3:
            hour, minute, sec_ms = time_components
            if "." in sec_ms:
                second, millisecond = sec_ms.split(".")
            else:
                second = sec_ms
                millisecond = "0"
        else:
            return None
        microsecond = int(millisecond.ljust(6, "0")[:6])
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            microsecond,
        )
    except Exception:
        return None


def clean_images_in_dir(debug_folder: Path, sub_dir: str):
    """
    因为maafw.bak.log的日期是其内容的最晚日期,因此只有删了日志文件才去删除图片;
    清理指定子目录下所有图片时间早于 base_time_for_cleanup 的文件
    """
    target_dir = debug_folder / sub_dir
    if not target_dir.exists():
        print(f"[图片清理] 目录不存在,跳过: {target_dir}")
        return

    img_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    img_files = [
        f
        for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in img_extensions
    ]
    total_count = len(img_files)
    if total_count == 0:
        print(f"[图片清理] {sub_dir} 目录下无图片文件,跳过")
        return

    base_time = base_time_for_cleanup
    to_delete = []
    for img_path in img_files:
        img_dt = extract_datetime_from_image_name(img_path.name)
        if img_dt is None:
            print(f"[图片清理] 无法解析图片时间,跳过: {img_path.name}")
            continue
        if img_dt < base_time:
            to_delete.append((img_dt, img_path))

    eligible = len(to_delete)
    if eligible == 0:
        print(
            f"[图片清理] {sub_dir} 目录下共有 {total_count} 张图片,没有时间早于 {base_time} 的图片"
        )
        return

    deleted = 0
    for img_dt, img_path in to_delete:
        try:
            img_path.unlink()
            deleted += 1
            print(f"[图片清理] 删除图片: {img_path.name} (时间 {img_dt})")
        except Exception as e:
            print(f"[图片清理] 删除失败 {img_path.name}: {e}")

    print(
        f"[图片清理] {sub_dir} 目录下共有 {total_count} 张图片,其中时间早于 {base_time} 的有 {eligible} 张,实际删除了 {deleted} 张"
    )


def clean_logs_in_dir(debug_folder: Path, sub_dir: str):
    """
    清理指定子目录下的日志文件(格式 YYYY-MM-DD.log),删除日期早于 base_time_for_cleanup 的文件
    """
    target_dir = debug_folder / sub_dir
    if not target_dir.exists():
        print(f"[日志清理] 目录不存在,跳过: {target_dir}")
        return

    log_files = list(target_dir.glob("*.log"))
    total_count = len(log_files)
    if total_count == 0:
        print(f"[日志清理] {sub_dir} 目录下无日志文件,跳过")
        return

    def extract_date_from_log_name(filename: str):
        """提取日期"""
        try:
            date_str = filename.replace(".log", "")
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None

    base_time = base_time_for_cleanup
    base_date = base_time.date()  # 只用比较日期部分
    to_delete = []
    for log_path in log_files:
        log_date = extract_date_from_log_name(log_path.name)
        if log_date is None:
            print(f"[日志清理] 无法解析日志日期,跳过: {log_path.name}")
            continue
        if log_date < base_date:
            to_delete.append((log_date, log_path))

    eligible = len(to_delete)
    if eligible == 0:
        print(
            f"[日志清理] {sub_dir} 目录下共有 {total_count} 个日志文件,没有日期早于 {base_date} 的日志"
        )
        return

    deleted = 0
    for log_date, log_path in to_delete:
        try:
            log_path.unlink()
            deleted += 1
            print(f"[日志清理] 删除日志: {log_path.name} (日期 {log_date})")
        except Exception as e:
            print(f"[日志清理] 删除失败 {log_path.name}: {e}")

    print(
        f"[日志清理] {sub_dir} 目录下共有 {total_count} 个日志文件,其中日期早于 {base_date} 的有 {eligible} 个,实际删除了 {deleted} 个"
    )
