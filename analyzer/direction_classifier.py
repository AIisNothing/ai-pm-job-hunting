"""方向分类器模块 - 根据岗位名称和描述将记录归类到细分方向"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.schemas import JobRecord

logger = logging.getLogger(__name__)

_DEFAULT_RULES_PATH = str(
    Path(__file__).resolve().parent / "direction_rules.json"
)


class DirectionClassifier:
    """根据岗位名称和描述中的关键词将 JobRecord 归类到一个或多个方向。"""

    def __init__(self, rules_path: str | None = None):
        """加载方向分类规则。

        Args:
            rules_path: 规则 JSON 文件路径。
                默认为 ``analyzer/direction_rules.json``。
        """
        path = Path(rules_path if rules_path is not None else _DEFAULT_RULES_PATH)
        with path.open("r", encoding="utf-8") as f:
            self._rules: dict[str, dict[str, list[str]]] = json.load(f)

        logger.info(
            "方向分类规则加载完成，共 %d 个类别", len(self._rules)
        )

    def classify(self, record: JobRecord, category: str) -> list[str]:
        """将岗位记录归类到一个或多个方向。

        检查 title 和 description 中是否包含各方向的关键词，
        大小写不敏感匹配。若无匹配则返回 ``["通用"]``。

        Args:
            record: 岗位记录
            category: 岗位类别（如 "产品经理"）

        Returns:
            匹配到的方向名称列表，至少包含一个元素
        """
        category_rules = self._rules.get(category, {})
        if not category_rules:
            return ["通用"]

        text = f"{record.title} {record.description}"
        matched: list[str] = []

        for direction, keywords in category_rules.items():
            for kw in keywords:
                if self._match_keyword(kw, text):
                    matched.append(direction)
                    break

        return matched if matched else ["通用"]

    def get_directions(self, category: str) -> list[str]:
        """返回某个类别的所有已知方向名称。

        Args:
            category: 岗位类别

        Returns:
            方向名称列表；若类别无规则则返回空列表
        """
        return list(self._rules.get(category, {}).keys())

    def update_rules(self, category: str, rules: dict) -> None:
        """更新某个类别的分类规则。

        Args:
            category: 岗位类别
            rules: 方向规则字典，格式 ``{"direction_name": ["kw1", "kw2"]}``
        """
        self._rules[category] = rules
        logger.info("已更新类别 '%s' 的分类规则，共 %d 个方向", category, len(rules))

    @staticmethod
    def _match_keyword(keyword: str, text: str) -> bool:
        """检查关键词是否在文本中出现（大小写不敏感）。

        对含中文的关键词使用子串匹配；
        对纯 ASCII 关键词使用单词边界匹配以避免部分匹配。
        """
        if re.search(r"[\u4e00-\u9fff]", keyword):
            return keyword in text

        escaped = re.escape(keyword)
        pattern = r"(?<![a-zA-Z0-9_.])" + escaped + r"(?![a-zA-Z0-9_])"
        return bool(re.search(pattern, text, re.IGNORECASE))
