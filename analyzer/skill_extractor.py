"""技能标签提取与归一化模块"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.schemas import JobRecord

logger = logging.getLogger(__name__)

# Default dictionary path relative to backend/
_DEFAULT_DICT_PATH = str(
    Path(__file__).resolve().parent / "skill_dictionary.json"
)


class SkillExtractor:
    """从岗位描述中提取、归一化技能标签，并检测候选新技能。"""

    def __init__(self, dictionary_path: str | None = None):
        """加载技能关键词词典。

        Args:
            dictionary_path: 技能词典 JSON 文件路径。
                默认为 ``analyzer/skill_dictionary.json``（相对于 backend/）。
        """
        path = Path(dictionary_path if dictionary_path is not None else _DEFAULT_DICT_PATH)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._skills: list[dict] = data.get("skills", [])

        # 构建同义词 → 标准名称的映射（小写 key）
        self._synonym_map: dict[str, str] = {}
        # 所有可匹配的词条（标准名 + 同义词），按长度降序排列以优先匹配长词
        self._all_terms: list[tuple[str, str]] = []  # (term, standard_name)

        for skill in self._skills:
            name = skill["name"]
            # 标准名称自身也可匹配
            self._synonym_map[name.lower()] = name
            self._all_terms.append((name, name))
            for syn in skill.get("synonyms", []):
                self._synonym_map[syn.lower()] = name
                self._all_terms.append((syn, name))

        # 按词条长度降序排列，优先匹配更长的词条
        self._all_terms.sort(key=lambda t: len(t[0]), reverse=True)

        # 收集所有已知词条（小写），用于 detect_new_skills 排除
        self._known_terms_lower: set[str] = set(self._synonym_map.keys())

        logger.info("技能词典加载完成，共 %d 个标准技能，%d 个词条",
                     len(self._skills), len(self._all_terms))

    def extract(self, description: str) -> list[str]:
        """从岗位描述中提取归一化的技能标签列表。

        匹配规则：
        - 大小写不敏感
        - 对纯英文/数字词条使用单词边界匹配，避免部分匹配
          （如 "AI" 不会匹配 "MAIL"）
        - 对含中文的词条使用子串匹配
        - 返回去重后的标准技能名称列表

        Args:
            description: 岗位描述文本

        Returns:
            归一化后的技能名称列表（去重）
        """
        if not description:
            return []

        found: dict[str, None] = {}  # 保持插入顺序的去重集合

        for term, standard_name in self._all_terms:
            if standard_name in found:
                continue
            if self._match_term(term, description):
                found[standard_name] = None

        return list(found.keys())

    def normalize(self, raw_skill: str) -> str:
        """将技能名称归一化为标准名称。

        - 若输入匹配某个同义词，返回对应的标准名称
        - 若已是标准名称，返回自身
        - 若未找到，返回原始输入

        Args:
            raw_skill: 原始技能名称

        Returns:
            归一化后的标准技能名称
        """
        return self._synonym_map.get(raw_skill.lower(), raw_skill)

    def detect_new_skills(
        self, records: list[JobRecord] | list[str], threshold: float = 0.05
    ) -> list[str]:
        """检测候选新技能：在岗位描述中高频出现但不在词典中的词汇。

        使用简单的正则分词（中文按连续汉字切分，英文按单词切分），
        统计各词汇出现在多少条记录中，超过 *threshold* 比例且不在词典中的
        词汇作为候选新技能返回。

        Args:
            records: ``JobRecord`` 列表（取 ``description`` 字段），
                也兼容直接传入字符串列表以方便测试。
            threshold: 出现频率阈值（默认 0.05，即 5%）

        Returns:
            候选新技能词汇列表
        """
        if not records:
            return []

        # 兼容 list[str] 和 list[JobRecord]
        descriptions: list[str] = []
        for item in records:
            if isinstance(item, str):
                descriptions.append(item)
            else:
                descriptions.append(item.description)

        total = len(descriptions)
        min_count = total * threshold

        # 统计每个词汇出现在多少条描述中
        doc_freq: Counter[str] = Counter()

        for desc in descriptions:
            tokens = self._tokenize(desc)
            # 每条描述中去重
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        candidates: list[str] = []
        for token, count in doc_freq.most_common():
            if count <= min_count:
                continue
            # 排除已在词典中的词条
            if token.lower() in self._known_terms_lower:
                continue
            # 排除过短的词（单个汉字或单个英文字母）
            if len(token) <= 1:
                continue
            candidates.append(token)

        return candidates

    # ─── 内部方法 ───────────────────────────────────────────────

    @staticmethod
    def _match_term(term: str, text: str) -> bool:
        """检查 term 是否在 text 中出现，避免部分匹配。

        对纯 ASCII 词条（英文/数字/符号）使用单词边界或特殊字符边界匹配；
        对含中文的词条使用简单子串匹配（中文天然以字为边界）。
        """
        # 含中文字符 → 子串匹配（大小写不敏感）
        if re.search(r"[\u4e00-\u9fff]", term):
            return term in text

        # 纯 ASCII 词条 → 使用边界匹配
        escaped = re.escape(term)
        # 对于像 C++, C#, Node.js 这类含特殊字符的词条，
        # 使用前后非字母数字字符或字符串边界作为边界
        pattern = r"(?<![a-zA-Z0-9_.])" + escaped + r"(?![a-zA-Z0-9_])"
        return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词：提取连续中文字符串和英文单词。

        不依赖 jieba，使用正则提取：
        - 连续2个及以上汉字组成的词
        - 英文单词（含数字和常见连接符）
        """
        # 匹配：连续汉字（2+）或 英文单词（含数字、点、+、#）
        tokens = re.findall(
            r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9+#.]*[a-zA-Z0-9+#]|[a-zA-Z]",
            text,
        )
        return tokens
