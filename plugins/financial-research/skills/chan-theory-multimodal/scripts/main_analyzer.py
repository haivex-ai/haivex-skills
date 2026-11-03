"""缠论粗略版 - 调度引擎（对应 DS3 v2.4 chanlun_engine.py）

ChanlunEngine 类编排 M0-M12 全部模块，输出 TradeSignal。
"""

from typing import List, Optional
from dataclasses import asdict
from data_structures import KLine, TradeSignal, MACrossState, MACDData
from config import ChanlunConfig
from kline_processing import process_inclusion
from ma_system import calc_ma, get_ma_state
from fractal_detector import detect_fractals, build_pens, get_current_pen_state
from segment import identify_segments
from macd_analyzer import compute_macd, segment_macd_area, check_plate_divergence
from same_level_decomposition import compare_ai_ai2
from bollinger_zhongyin import calc_boll, is_zhongyin
from surface_relation import diagnose
from position_manager import calc_position
from boundary_handler import check_traps

class ChanlunEngine:
    """缠论调度引擎"""

    def __init__(self, config: Optional[ChanlunConfig] = None):
        self.config = config or ChanlunConfig()

    def analyze(
        self,
        klines: List[KLine],
        sub_klines: Optional[List[KLine]] = None,
    ) -> TradeSignal:
        """全流程分析（DS3对齐）

        流程: M1预处理 → M2均线 → M3/M4分型笔 → M0段识别
              → M6背驰 → M7表里关系 → M8同级别分解 → M9中阴 → M12陷阱
              → 综合决策
        """
        # 0. 数据不足检查
        if len(klines) < 20:
            return TradeSignal(
                action="hold", signal_type="hold", source="integrated",
                confidence=0.0, position_ratio=0,
                stop_loss=0, take_profit=0, description="数据不足",
            )

        # 1. 预处理 (M1)
        std_klines = process_inclusion(klines)

        # 2. 均线系统 (M2)
        close_series = [k.close for k in klines]
        ma5 = calc_ma(klines, self.config.SHORT_MA)
        ma10 = calc_ma(klines, self.config.LONG_MA)
        ma_state = get_ma_state(klines, len(close_series) - 1)

        # 3. 分型和笔 (M3 → M4)
        fractals = detect_fractals(std_klines, klines)
        pens = build_pens(fractals)
        pen_state = get_current_pen_state(pens, fractals[-1] if fractals else None)

        # 4. 段识别 (M0)
        segments = identify_segments(klines, ma5, ma10, self.config)
        for seg in segments:
            seg.macd_area = segment_macd_area(klines, seg)

        # 5. 盘整背驰 (M6)
        divergence = None
        if len(segments) >= 3:
            divergence = check_plate_divergence(
                segments[-3], segments[-1], klines,
            )

        # 6. 表里关系 (M7)
        disease = "未知"
        if sub_klines:
            sub_std = process_inclusion(sub_klines)
            sub_fractals = detect_fractals(sub_std, sub_klines)
            sub_pens = build_pens(sub_fractals)
            sub_state = get_current_pen_state(
                sub_pens, sub_fractals[-1] if sub_fractals else None,
            )
            disease, _ = diagnose(pen_state, sub_state)

        # 7. 同级别分解 (M8)
        same_signal = None
        if len(segments) >= 3:
            same_action = compare_ai_ai2(
                [asdict(seg) for seg in segments], len(segments) - 1, None, klines,
            )
            if same_action in ("buy", "sell"):
                # M8保留原买卖判断；仅适配为引擎约定的信号对象。
                same_signal = TradeSignal(
                    action=same_action,
                    signal_type="first_buy" if same_action == "buy" else "first_sell",
                    source="same_level", confidence=self.config.CONFIDENCE_MEDIUM,
                    position_ratio=(self.config.POSITION_MEDIUM_CONFIDENCE
                                    if same_action == "buy" else 0),
                    stop_loss=0, take_profit=0, description="同级别分解信号",
                )

        # 8. 中阴 (M9)
        _, upper, lower = calc_boll(std_klines, self.config.BOLL_PERIOD, self.config.BOLL_STD_MULT)
        current_price = klines[-1].close
        prev_high = std_klines[-2].high if len(std_klines) >= 2 else current_price
        zhongyin = (
            is_zhongyin(current_price, upper[-1], lower[-1], prev_high)
            if upper and lower else False
        )

        # 9. 陷阱检查 (M12)
        traps = check_traps(
            current_bar=klines[-1], prev_bars=klines[:-1], ma_state=ma_state,
            current_time=klines[-1].time,
            is_major_signal=bool(same_signal and same_signal.action in ("buy", "sell")),
        )

        # 10. 综合决策
        final = self._integrate(ma_state, fractals, divergence, disease, same_signal, zhongyin)
        # 卖出/观望信号保留自身仓位，避免置信度换算覆盖退出意图。
        if final.action == "buy":
            final.position_ratio = calc_position(final)
        return final

    def _integrate(
        self,
        ma_state: MACrossState,
        fractals: List,
        divergence,
        disease: str,
        same_signal,
        zhongyin: bool,
    ) -> TradeSignal:
        """综合决策（DS3 _integrate 优先级排列）"""
        # 第一类买点：男上位 + 底分型(strongest/strong) + 背驰
        if (ma_state.position == "男上位" and len(fractals) >= 2 and
            fractals[-1].type == "bottom" and
            fractals[-1].strength in ("strongest", "strong") and
            divergence and divergence.is_divergence):
            return TradeSignal(
                action="buy", signal_type="first_buy", source="integrated",
                confidence=self.config.CONFIDENCE_HIGH,
                position_ratio=self.config.POSITION_HIGH_CONFIDENCE,
                stop_loss=min(fractals[-1].low, fractals[-2].low),
                take_profit=0, description="第一类买点",
            )

        # 第二类买点：女上位 + 第1次缠绕 + 底分型
        if (ma_state.position == "女上位" and ma_state.kiss_count == 1 and
            fractals and fractals[-1].type == "bottom"):
            return TradeSignal(
                action="buy", signal_type="second_buy", source="integrated",
                confidence=self.config.CONFIDENCE_MEDIUM,
                position_ratio=self.config.POSITION_MEDIUM_CONFIDENCE,
                stop_loss=fractals[-1].low,
                take_profit=0, description="第二类买点",
            )

        # 同级别分解信号
        if same_signal:
            return same_signal

        # 中阴预警 + 已病 → 减仓
        if zhongyin and disease == "已病":
            return TradeSignal(
                action="sell", signal_type="first_sell", source="integrated",
                confidence=self.config.CONFIDENCE_MEDIUM,
                position_ratio=0, stop_loss=0, take_profit=0,
                description="中阴阶段+已病，减仓",
            )

        return TradeSignal(
            action="hold", signal_type="hold", source="integrated",
            confidence=self.config.CONFIDENCE_LOW,
            position_ratio=0, stop_loss=0, take_profit=0,
            description="无明确信号",
        )
