import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import Rect
from numpy import ndarray
from utils.logger import logger

# 商店配置
SHOP_CONFIGS: dict[str, dict] = {
    "jade_child_shop": {
        "total_roi": [1019, 17, 128, 37],
        "slot_1_anchor": "jade_child_shop_slot_1",
        "slot_2_anchor": "jade_child_shop_slot_2",
        "node_data_key_1": "jade_good_slot_1_set",
        "node_data_key_2": "jade_good_slot_2_set",
        "check_count_pipeline": "shop_jade_child_check_shopping_count",
        "shopping": "shop_jade_child_shopping",
        "shopping_interface": "shop_jade_child_shopping_interface",
        "follow_up_shopping": "shop_jade_child_follow_up_shopping",
    },
    "survival_child_shop": {
        "total_roi": [1019, 17, 128, 37],
        "slot_1_anchor": "survival_child_shop_slot_1",
        "slot_2_anchor": "survival_child_shop_slot_2",
        "node_data_key_1": "survival_good_slot_1_set",
        "node_data_key_2": "survival_good_slot_2_set",
        "check_count_pipeline": "shop_survival_child_check_shopping_count",
        "shopping": "shop_survival_child_shopping",
        "shopping_interface": "shop_survival_child_shopping_interface",
        "follow_up_shopping": "shop_survival_child_follow_up_shopping",
    },
    "point_race_child_shop": {
        "total_roi": [1019, 17, 128, 37],
        "slot_1_anchor": "point_race_child_shop_slot_1",
        "slot_2_anchor": "point_race_child_shop_slot_2",
        "node_data_key_1": "point_race_good_slot_1_set",
        "node_data_key_2": "point_race_good_slot_2_set",
        "check_count_pipeline": "shop_point_race_child_check_shopping_count",
        "shopping": "shop_point_race_child_shopping",
        "shopping_interface": "shop_point_race_child_shopping_interface",
        "follow_up_shopping": "shop_point_race_child_follow_up_shopping",
    },
    "group_child_shop": {
        "total_roi": [646, 16, 130, 37],
        "slot_1_anchor": "group_child_shop_slot_1",
        "slot_2_anchor": "group_child_shop_slot_2",
        "node_data_key_1": "group_good_slot_1_set",
        "node_data_key_2": "group_good_slot_2_set",
        "check_count_pipeline": "shop_group_child_check_shopping_count",
        "shopping": "shop_group_child_shopping",
        "shopping_interface": "shop_group_child_shopping_interface",
        "follow_up_shopping": "shop_group_child_follow_up_shopping",
    },
}


@AgentServer.custom_recognition("Shopping")
class Shopping(CustomRecognition):
    """商店兑换"""

    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg) -> CustomRecognition.AnalyzeResult:
        context.clear_hit_count("shop_swipe_back_for_good")
        param = json.loads(argv.custom_recognition_param)
        shop_type = param.get("shop_type", "root_shop")
        logger.info(f"商店类型: {shop_type}")

        config = SHOP_CONFIGS.get(shop_type)
        if not config:
            logger.error("暂不支持")
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        box = self.get_child_shop_info(context, argv.image, config)
        if box is None:
            return CustomRecognition.AnalyzeResult(box=None, detail={})

        x, y, w, h = box
        logger.debug(f"点击位置[{x},{y},{w},{h}]")
        return CustomRecognition.AnalyzeResult(box=Rect(x, y, w, h), detail={})

    def get_child_shop_info(
        self,
        context: Context,
        image: ndarray,
        config: dict,
    ) -> list[int] | None:
        """
        获取商店信息,返回可购买商品的价格区域坐标[x, y, w, h],否则返回 None;
        """
        # 获取需要的识别商品节点
        slot_1_anchor = config["slot_1_anchor"]
        slot_2_anchor = config["slot_2_anchor"]

        slot_1 = context.get_anchor(slot_1_anchor)
        slot_2 = context.get_anchor(slot_2_anchor) if slot_1 is None else None

        if slot_1 is not None:
            slot = slot_1
            node_data_key = config["node_data_key_1"]
        elif slot_2 is not None:
            slot = slot_2
            node_data_key = config["node_data_key_2"]
        else:
            logger.error("未找到商店锚点配置")
            return None

        # 获得购买数量
        node_data = context.get_node_data(node_data_key)
        if not node_data or "max_hit" not in node_data:
            logger.error(f"节点数据 {node_data_key} 缺失或无效")
            return None

        count = node_data["max_hit"]
        logger.info(f"购买数量: {count}")

        # 设置购买数量检查
        check_pipeline = config["check_count_pipeline"]
        context.override_pipeline({check_pipeline: {"expected": str(count)}})

        # 识别商品
        reco_detail = context.run_recognition(slot, image)
        if not reco_detail or not reco_detail.hit:
            logger.warning("商品图标识别未命中")
            return None

        best_box = reco_detail.best_result.box  # ty:ignore[unresolved-attribute]

        # 解析限购文本
        limit_roi = [best_box[0] + 10, best_box[1] + 87, 192, 138]
        limit_detail = context.run_recognition("custom_ocr", image, {"custom_ocr": {"roi": limit_roi}})
        limit_text = (
            str(
                limit_detail.best_result.text  # ty:ignore[unresolved-attribute]
            ).strip()
            if limit_detail and limit_detail.hit
            else ""
        )
        logger.info(f"限购文本: '{limit_text}'")
        if not self.parse_limit_text(limit_text, count):
            logger.info("限购条件不满足，不可购买")
            return None

        # 解析货币数量
        total_roi = config["total_roi"]
        total_detail = context.run_recognition("custom_ocr", image, {"custom_ocr": {"roi": total_roi}})
        total_text = (
            str(
                total_detail.best_result.text  # ty:ignore[unresolved-attribute]
            ).strip()
            if total_detail and total_detail.hit
            else ""
        )
        w = 1  # 挣w
        if "万" in total_text:
            w = 10000
        total_value = self.extract_number(total_text)
        if total_value is not None:
            total_value *= w
        # 价格解析
        price_roi = [best_box[0] + 42, best_box[1] + 179, 123, 54]
        price_detail = context.run_recognition("custom_ocr", image, {"custom_ocr": {"roi": price_roi}})
        if price_detail and price_detail.hit:
            best = max(
                price_detail.all_results,
                key=lambda r: r.score,  # ty:ignore[unresolved-attribute]
            )
            price_text = best.text.strip()  # ty:ignore[unresolved-attribute]
        else:
            price_text = ""

        price_value = self.extract_number(price_text)
        if total_value is None or price_value is None:
            logger.error("货币总数或价格解析失败")
            return None

        if price_value <= 40:
            logger.warning(f"价格识别出错,跳过购买;原始文本:'{price_detail}'")
            return None

        # 可否购买
        if total_value < price_value * count:
            return None
        logger.info(f"需要{price_value * count},拥有{total_value}")
        # 多次购买事务
        if count > 1:
            repeat_count = count - 1
            context.override_next(
                config["shopping"],
                [
                    config["shopping_interface"],
                    "[JumpBack]shop_confirm_exchange",
                    config["follow_up_shopping"],
                    "shop_swipe_back_for_good",
                ],
            )
            context.override_pipeline(
                {
                    config["follow_up_shopping"]: {
                        "target": price_roi,
                        "repeat": repeat_count,
                    }
                }
            )

        return price_roi

    def parse_limit_text(self, limit_text: str, buy_count: int) -> bool:
        """根据限购文本判断是否可以购买"""
        if not limit_text:
            logger.warning("限购文本为空,拒绝购买")
            return False
        if any(kw in limit_text for kw in ["已拥有", "售罄", "售馨", "开启"]):
            return False

        nums = re.findall(r"\d+", limit_text)
        if len(nums) >= 2:
            try:
                bought = int(nums[0])
                total = int(nums[1])
            except ValueError:
                return False
            if bought + buy_count > total:
                logger.info(f"限购不足:已购{bought}/{total},需要购买{buy_count}")
                return False
            return True
        logger.warning(f"限购文本格式无法明确判断: '{limit_text}'")
        return False

    def extract_number(self, text: str) -> int | None:
        """从文本中提取第一个连续数字并返回整数，失败返回 None"""
        if not text:
            return None
        nums = re.findall(r"\d+", text)
        if nums:
            try:
                return int(nums[0])
            except ValueError:
                pass
        return None
