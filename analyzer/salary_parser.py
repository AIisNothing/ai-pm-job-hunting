"""薪资文本解析与格式化模块"""

import logging
import re

from models.schemas import SalaryRange

logger = logging.getLogger(__name__)

# Boss直聘常见薪资格式正则
# 匹配: "15-25K", "15-25K·14薪", "15-25k", "15K-25K", "1.5-2.5万", "1.5-2.5万·13薪"
_PATTERN_K = re.compile(
    r"^(\d+(?:\.\d+)?)\s*[Kk]?\s*[-~—]\s*(\d+(?:\.\d+)?)\s*[Kk]"
    r"(?:\s*[·.]\s*(\d+)\s*薪)?$"
)

_PATTERN_WAN = re.compile(
    r"^(\d+(?:\.\d+)?)\s*[-~—]\s*(\d+(?:\.\d+)?)\s*万"
    r"(?:\s*[·.]\s*(\d+)\s*薪)?$"
)


class SalaryParser:
    """Boss直聘薪资文本解析器"""

    def parse(self, salary_text: str) -> SalaryRange | None:
        """解析薪资文本为 SalaryRange 对象。

        支持格式:
          - "15-25K" / "15-25k"  → min=15, max=25, months=12
          - "15K-25K"            → min=15, max=25, months=12
          - "15-25K·14薪"       → min=15, max=25, months=14
          - "1.5-2.5万"         → min=15, max=25, months=12
          - "1.5-2.5万·13薪"   → min=15, max=25, months=13

        无法识别的格式（含"面议"、空字符串、None）返回 None。
        """
        if salary_text is None:
            logger.debug("薪资文本为 None，跳过解析")
            return None

        text = salary_text.strip()
        if not text or text == "面议":
            logger.debug("薪资文本无法解析: %r", salary_text)
            return None

        # 尝试 K 格式
        m = _PATTERN_K.match(text)
        if m:
            min_val = float(m.group(1))
            max_val = float(m.group(2))
            months = int(m.group(3)) if m.group(3) else 12
            return SalaryRange(
                min_monthly=min_val,
                max_monthly=max_val,
                months_per_year=months,
            )

        # 尝试 万 格式 (万 → 千元 ×10)
        m = _PATTERN_WAN.match(text)
        if m:
            min_val = float(m.group(1)) * 10
            max_val = float(m.group(2)) * 10
            months = int(m.group(3)) if m.group(3) else 12
            return SalaryRange(
                min_monthly=min_val,
                max_monthly=max_val,
                months_per_year=months,
            )

        logger.warning("无法识别的薪资格式: %r", salary_text)
        return None

    def format(self, salary_range: SalaryRange) -> str:
        """将 SalaryRange 格式化回文本。

        规则:
          - months_per_year == 12 → "15-25K"
          - months_per_year != 12 → "15-25K·14薪"
          - 整数值省略小数点 (15.0 → "15")
        """
        min_str = _format_number(salary_range.min_monthly)
        max_str = _format_number(salary_range.max_monthly)
        base = f"{min_str}-{max_str}K"
        if salary_range.months_per_year != 12:
            base += f"·{salary_range.months_per_year}薪"
        return base


def _format_number(value: float) -> str:
    """格式化数字：整数去掉小数点，浮点保留必要精度。"""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"
