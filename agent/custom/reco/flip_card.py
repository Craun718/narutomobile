from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import Rect
from numpy import ndarray
from utils.logger import logger


@AgentServer.custom_recognition("FlipCard")
class FlipCard(CustomRecognition):
    """
    周年庆4x4翻牌游戏

    基于贪心算法

    规则：
    1. 胜利判定：仅统计紫色牌数量,连续4个判定胜利;
    2. 初始状态：优先选橙色不在的对角线牌，双对角线橙色则选横竖无橙色牌；
    3. 紫色生长：
       - 按“单一方向（行/列/对角线）的最高紫色数”评分；
       - 同最高分下，优先选该方向内的位置（比如行分数最高→优先选该行）；
       - 有橙色的方向（行/列/对角线),紫色数直接计0;
       - 同分数+同方向下，优先选对角线位置（双对角线橙色时忽略）；
    4.你违反了规则
    """

    # 地图
    CARD_4X4_ROI = [
        [
            [206, 94, 145, 109],
            [357, 94, 145, 111],
            [508, 94, 148, 111],
            [661, 94, 145, 111],
        ],
        [
            [206, 212, 145, 111],
            [360, 212, 143, 108],
            [510, 212, 143, 108],
            [661, 212, 145, 111],
        ],
        [
            [204, 328, 145, 111],
            [360, 328, 143, 111],
            [510, 328, 143, 111],
            [661, 328, 145, 111],
        ],
        [
            [206, 447, 143, 111],
            [357, 444, 145, 111],
            [510, 447, 143, 111],
            [661, 447, 145, 111],
        ],
    ]
    TIP_CLICK_ROI = [1035, 229, 103, 93]  # 识别失败点击ROI
    MAIN_DIAG = [(0, 0), (1, 1), (2, 2), (3, 3)]  # 主对角线（左上-右下）
    SUB_DIAG = [(0, 3), (1, 2), (2, 1), (3, 0)]  # 副对角线（右上-左下）
    ALL_DIAG = MAIN_DIAG + SUB_DIAG  # 所有对角线位置

    def get_orange_info(self, card_state_grid: list[list[int]]) -> dict[str, Any]:
        """提取橙色牌信息(只要有1个橙色就标记该对角线)"""
        orange_pos = []
        orange_rows = set()
        orange_cols = set()
        orange_diags = set()
        is_both_diag_orange = False

        # 遍历所有牌，标记橙色位置/行/列/对角线
        for row in range(4):
            for col in range(4):
                if card_state_grid[row][col] == 2:
                    orange_pos.append((row, col))
                    orange_rows.add(row)
                    orange_cols.add(col)
                    # 只要对角线有1个橙色，就标记该对角线为橙色
                    if (row, col) in self.MAIN_DIAG:
                        orange_diags.add("main")
                    if (row, col) in self.SUB_DIAG:
                        orange_diags.add("sub")

        # 判断是否双对角线都有橙色
        if "main" in orange_diags and "sub" in orange_diags:
            is_both_diag_orange = True
            logger.debug("检测到双对角线都有橙色，忽略对角线优先级")

        return {
            "orange_pos": orange_pos,
            "orange_rows": orange_rows,
            "orange_cols": orange_cols,
            "orange_diags": orange_diags,
            "is_both_diag_orange": is_both_diag_orange,
        }

    def _is_initial_state(self, card_state_grid: list[list[int]]) -> bool:
        """判断是否初始状态（除橙色外全未翻牌）"""
        for row in range(4):
            for col in range(4):
                if card_state_grid[row][col] not in [0, 2]:
                    return False
        return True

    def _get_valid_initial_pos(self, card_state_grid: list[list[int]], orange_info: dict) -> tuple[int, int]:
        """初始状态选最优翻牌位置"""
        all_unflip = [(r, c) for r in range(4) for c in range(4) if card_state_grid[r][c] == 0]
        if not all_unflip:
            return all_unflip[0]

        # 双对角线橙色 → 优先选横竖无橙色的未翻牌
        if orange_info["is_both_diag_orange"]:
            valid_unflip = [
                (r, c)
                for (r, c) in all_unflip
                if r not in orange_info["orange_rows"] and c not in orange_info["orange_cols"]
            ]
            if valid_unflip:
                logger.debug(f"双对角线橙色，选横竖无橙色的未翻牌：{valid_unflip[0]}")
                return valid_unflip[0]
            return all_unflip[0]

        # 单对角线橙色 → 优先选另一对角线无橙色的牌
        diag_unflip = [pos for pos in all_unflip if pos in self.ALL_DIAG]
        if not diag_unflip:
            return all_unflip[0]

        priority1 = []  # 不在橙色行/列+不在橙色对角线
        priority2 = []  # 不在橙色行/列
        priority3 = []  # 其他对角线牌

        for r, c in diag_unflip:
            in_orange_row_col = (r in orange_info["orange_rows"]) or (c in orange_info["orange_cols"])
            in_orange_diag = False
            if (r, c) in self.MAIN_DIAG and "main" in orange_info["orange_diags"]:
                in_orange_diag = True
            if (r, c) in self.SUB_DIAG and "sub" in orange_info["orange_diags"]:
                in_orange_diag = True

            if not in_orange_row_col and not in_orange_diag:
                priority1.append((r, c))
            elif not in_orange_row_col:
                priority2.append((r, c))
            else:
                priority3.append((r, c))

        if priority1:
            logger.debug(f"初始状态选优先级1对角线牌:{priority1[0]}")
            return priority1[0]
        elif priority2:
            logger.debug(f"初始状态选优先级2对角线牌:{priority2[0]}")
            return priority2[0]
        elif priority3:
            logger.debug(f"初始状态选优先级3对角线牌:{priority3[0]}")
            return priority3[0]
        return diag_unflip[0]

    def _calc_single_dir_score(
        self, pos: tuple[int, int], card_state_grid: list[list[int]], orange_info: dict
    ) -> dict[str, int | str]:
        """
        计算单一方向的分数（非叠加）：行/列/对角线各自的分数
        return: {"row_score": 行分数, "col_score": 列分数, "diag_score": 对角线分数, "max_score": 最高分}
        """
        r, c = pos
        orange_rows = orange_info["orange_rows"]
        orange_cols = orange_info["orange_cols"]
        orange_diags = orange_info["orange_diags"]

        # 1. 行分数：有橙色则0，否则该行紫色数
        row_score = 0
        if r not in orange_rows:
            row_score = sum(1 for col in range(4) if card_state_grid[r][col] == 1)

        # 2. 列分数：有橙色则0，否则该列紫色数
        col_score = 0
        if c not in orange_cols:
            col_score = sum(1 for row in range(4) if card_state_grid[row][c] == 1)

        # 3. 对角线分数：有橙色则0，否则所属对角线的紫色数
        diag_score = 0
        # 主对角线
        if (r, c) in self.MAIN_DIAG and "main" not in orange_diags:
            diag_score = sum(1 for (x, y) in self.MAIN_DIAG if card_state_grid[x][y] == 1)
        # 副对角线（若同时在两个对角线，取最大值,不过应该不会出现这种情况）
        if (r, c) in self.SUB_DIAG and "sub" not in orange_diags:
            sub_score = sum(1 for (x, y) in self.SUB_DIAG if card_state_grid[x][y] == 1)
            diag_score = max(diag_score, sub_score)

        # 4. 单一方向最高分
        max_score = max(row_score, col_score, diag_score)

        return {
            "row_score": row_score,
            "col_score": col_score,
            "diag_score": diag_score,
            "max_score": max_score,
            # 标记最高分所属方向（用于优先选同方向位置）
            "max_dir": ("row" if row_score == max_score else ("col" if col_score == max_score else "diag")),
        }

    def get_best_growth_pos_by_score(
        self, card_state_grid: list[list[int]], orange_info: dict
    ) -> tuple[int, int] | None:
        """
        优先同方向生长
        """
        all_unflip = [(r, c) for r in range(4) for c in range(4) if card_state_grid[r][c] == 0]
        if not all_unflip:
            return None

        # 计算每个未翻牌的单一方向分数
        pos_data = []
        for pos in all_unflip:
            dir_scores = self._calc_single_dir_score(pos, card_state_grid, orange_info)
            max_score: int = dir_scores["max_score"]  # type: ignore
            max_dir = dir_scores["max_dir"]
            # 排序权重：1. 最高分降序 → 2. 最高分方向（行>列>对角线）→ 3. 对角线优先 → 4. 行列号升序
            dir_priority = 0 if max_dir == "row" else (1 if max_dir == "col" else 2)
            is_diag = 1 if (pos in self.ALL_DIAG and not orange_info["is_both_diag_orange"]) else 0
            pos_data.append((-max_score, dir_priority, -is_diag, pos))

        # 排序规则：
        # 1. -max_score → 最高分降序；
        # 2. dir_priority → 行>列>对角线；
        # 3. -is_diag → 对角线优先；
        # 4. pos → 行列号升序；
        pos_data.sort()
        best_pos = pos_data[0][3]
        best_score = -pos_data[0][0]

        # 日志输出单一方向分数
        logger.debug("未翻牌评分详情（优先同方向生长，行>列>对角线）：")
        for idx, item in enumerate(pos_data[:3]):
            max_score = -item[0]
            dir_priority = item[1]
            max_dir = "行" if dir_priority == 0 else ("列" if dir_priority == 1 else "对角线")
            is_diag = "*" if -item[2] == 1 else " "
            pos = item[3]
            logger.debug(
                f"  候选{idx + 1}:({pos[0] + 1},{pos[1] + 1}) {is_diag} 最高分={max_score} 最高分方向={max_dir}"
            )
        logger.debug(f"最终选择：({best_pos[0] + 1},{best_pos[1] + 1}) 最高分={best_score}")

        return best_pos

    def check_victory(self, card_state_grid: list[list[int]]) -> bool:
        """胜利判定：仅统计紫色牌(1)数量,连续4个才胜利"""
        # 检查行
        for r in range(4):
            purple_count = sum(1 for col in range(4) if card_state_grid[r][col] == 1)
            if purple_count == 4:
                logger.debug(f"检测到第{r + 1}行4个紫色连成一线,胜利!")
                return True
        # 检查列
        for c in range(4):
            purple_count = sum(1 for row in range(4) if card_state_grid[row][c] == 1)
            if purple_count == 4:
                logger.debug(f"检测到第{c + 1}列4个紫色连成一线,胜利!")
                return True
        # 检查主对角线
        main_purple = sum(1 for i in range(4) if card_state_grid[i][i] == 1)
        if main_purple == 4:
            logger.debug("检测到主对角线4个紫色连成一线,胜利!")
            return True
        # 检查副对角线
        sub_purple = sum(1 for i in range(4) if card_state_grid[i][3 - i] == 1)
        if sub_purple == 4:
            logger.debug("检测到副对角线4个紫色连成一线,胜利!")
            return True
        return False

    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg) -> CustomRecognition.AnalyzeResult:
        logger.debug("===== 开始检测翻牌游戏状态=====")

        # 步骤1：识别卡牌状态
        card_state_grid = []
        has_recognize_fail = False
        for row in range(4):
            row_state = []
            for col in range(4):
                roi = self.CARD_4X4_ROI[row][col]
                card_type = self.get_card_type(context, argv.image, roi)
                row_state.append(card_type)
                if card_type == 3:
                    has_recognize_fail = True
            card_state_grid.append(row_state)
        logger.debug(f"当前卡牌状态网格：\n{card_state_grid}")

        # 步骤2：处理识别失败
        if has_recognize_fail:
            logger.debug(f"检测到识别失败,点击提示ROI:{self.TIP_CLICK_ROI}")
            tip_box = Rect(*self.TIP_CLICK_ROI)
            return CustomRecognition.AnalyzeResult(
                box=tip_box,
                detail={"action": "click_tip", "tip_roi": self.TIP_CLICK_ROI},
            )

        # 步骤3：检查胜利
        if self.check_victory(card_state_grid):
            invalid_box = Rect(0, 0, 1, 1)
            return CustomRecognition.AnalyzeResult(box=invalid_box, detail={"has_valid_target": False, "is_win": True})

        # 步骤4：提取橙色信息
        orange_info = self.get_orange_info(card_state_grid)
        logger.debug(
            f"橙色牌信息：位置{[(x + 1, y + 1) for x, y in orange_info['orange_pos']]}，阻挡行{orange_info['orange_rows']},"  # noqa: E501
            f"阻挡列{orange_info['orange_cols']}，阻挡对角线{orange_info['orange_diags']}，双对角线橙色：{orange_info['is_both_diag_orange']}"
        )

        # 步骤5：初始状态选牌
        if self._is_initial_state(card_state_grid):
            best_pos = self._get_valid_initial_pos(card_state_grid, orange_info)
            best_roi = self.CARD_4X4_ROI[best_pos[0]][best_pos[1]]
            logger.debug(f"初始状态选择翻牌位置：({best_pos[0] + 1},{best_pos[1] + 1}),ROI={best_roi}")
            flip_box = Rect(*best_roi)
            return CustomRecognition.AnalyzeResult(
                box=flip_box,
                detail={
                    "has_valid_target": False,
                    "action": "flip_initial",
                    "flip_pos": (best_pos[0] + 1, best_pos[1] + 1),
                    "flip_roi": best_roi,
                },
            )

        # 步骤6：按单一方向最高分选最优生长位置
        best_growth_pos = self.get_best_growth_pos_by_score(card_state_grid, orange_info)
        if not best_growth_pos:
            logger.warning("无未翻牌可翻")
            invalid_box = Rect(0, 0, 1, 1)
            return CustomRecognition.AnalyzeResult(
                box=invalid_box,
                detail={"has_valid_target": False, "reason": "no_unflip_card"},
            )

        best_roi = self.CARD_4X4_ROI[best_growth_pos[0]][best_growth_pos[1]]
        logger.debug(f"紫色生长选择翻牌位置：({best_growth_pos[0] + 1},{best_growth_pos[1] + 1}),ROI={best_roi}")
        flip_box = Rect(*best_roi)
        return CustomRecognition.AnalyzeResult(
            box=flip_box,
            detail={
                "has_valid_target": False,
                "action": "flip_growth",
                "flip_pos": (best_growth_pos[0] + 1, best_growth_pos[1] + 1),
                "flip_roi": best_roi,
            },
        )

    def get_card_type(self, context: Context, image: ndarray, roi: list[int]) -> int:
        """
        识别单张卡牌类型
        return: 0=未翻开 1=紫色牌 2=橙色牌 3=识别失败（如触发牌已经翻开的提示，或者被奖励遮盖）
        """
        # 识别紫色牌
        purple_reco = context.run_recognition("card_0", image, {"card_0": {"roi": roi}})
        if purple_reco and purple_reco.hit:
            return 1

        # 识别橙色牌
        orange_reco = context.run_recognition("card_1", image, {"card_1": {"roi": roi}})
        if orange_reco and orange_reco.hit:
            return 2

        # 识别未翻开牌
        wait_reco = context.run_recognition("card_wait", image, {"card_wait": {"roi": roi}})
        if wait_reco and wait_reco.hit:
            return 0

        # 识别失败
        logger.warning(f"卡牌ROI{roi} 识别失败,应该是触发提示，或者被奖励遮盖")
        return 3
