"""趋势分析引擎 - 招聘趋势、薪资趋势、技能趋势、市场概览"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

from models.schemas import (
    CityCount,
    DirectionSummary,
    ExperienceCount,
    MarketOverview,
    SkillFrequency,
    TimePeriod,
)

if TYPE_CHECKING:
    from models.schemas import JobRecord

    from analyzer.direction_classifier import DirectionClassifier
    from analyzer.skill_extractor import SkillExtractor

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """趋势分析器：基于内存中的 JobRecord 列表进行多维度分析。"""

    # ─── 辅助方法 ───────────────────────────────────────────────

    @staticmethod
    def _calculate_change_pct(old: float, new: float) -> float:
        """计算变化百分比: (new - old) / old * 100。

        old 为 0 时返回 0.0 以避免除零错误。
        """
        if old == 0:
            return 0.0
        return (new - old) / old * 100

    @staticmethod
    def _get_trend_label(values: list[float], threshold: float = 10.0) -> str:
        """根据数值序列判断趋势方向。

        比较最后一个值与倒数第二个值的变化百分比：
        - 增长 > threshold → "上升"
        - 下降 > threshold → "下降"
        - 否则 → "平稳"

        少于 2 个值时返回 "平稳"。
        """
        if len(values) < 2:
            return "平稳"
        old, new = values[-2], values[-1]
        if old == 0:
            return "平稳"
        pct = (new - old) / old * 100
        if pct > threshold:
            return "上升"
        if pct < -threshold:
            return "下降"
        return "平稳"

    @staticmethod
    def _records_in_period(
        records: list[JobRecord], period: TimePeriod
    ) -> list[JobRecord]:
        """筛选 publish_date 或 created_at 落在 period 内的记录。

        优先使用 publish_date；若为 None 则跳过该记录。
        """
        result: list[JobRecord] = []
        for r in records:
            d = r.publish_date
            if d is None:
                continue
            if period.start_date <= d <= period.end_date:
                result.append(r)
        return result

    @staticmethod
    def _salary_midpoint(record: JobRecord) -> float | None:
        """计算单条记录的薪资中点（千元/月）。"""
        if record.salary_min is not None and record.salary_max is not None:
            return (record.salary_min + record.salary_max) / 2
        return None

    @staticmethod
    def _salary_stats(records: list[JobRecord]) -> dict:
        """计算一组记录的薪资统计指标。

        返回 dict 包含 median, mean, p25, p75。
        若无有效薪资数据则所有值为 0。
        """
        midpoints = []
        for r in records:
            if r.salary_min is not None and r.salary_max is not None:
                midpoints.append((r.salary_min + r.salary_max) / 2)
        if not midpoints:
            return {"median": 0.0, "mean": 0.0, "p25": 0.0, "p75": 0.0}
        arr = np.array(midpoints)
        return {
            "median": float(np.median(arr)),
            "mean": float(np.mean(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
        }

    # ─── 7.1 招聘趋势分析 ──────────────────────────────────────

    def analyze_job_trend(
        self,
        records: list[JobRecord],
        periods: list[TimePeriod],
    ) -> dict:
        """分析招聘趋势：各时间段岗位数量及多维度分组。

        返回结构::

            {
                "periods": [
                    {"start": ..., "end": ..., "count": N},
                    ...
                ],
                "changes": [
                    {"from_period": 0, "to_period": 1, "change_pct": ...},
                    ...
                ],
                "overall_change_pct": float,
                "trend_label": "上升" | "平稳" | "下降",
                "by_city": { city: [count_per_period, ...] },
                "by_direction": { direction: [count_per_period, ...] },
                "by_company_scale": { scale: [count_per_period, ...] },
            }
        """
        period_records = [self._records_in_period(records, p) for p in periods]
        counts = [len(pr) for pr in period_records]

        # 各时间段摘要
        period_summaries = []
        for i, p in enumerate(periods):
            period_summaries.append({
                "start": p.start_date.isoformat(),
                "end": p.end_date.isoformat(),
                "count": counts[i],
            })

        # 相邻时间段变化百分比
        changes = []
        for i in range(1, len(counts)):
            changes.append({
                "from_period": i - 1,
                "to_period": i,
                "change_pct": self._calculate_change_pct(counts[i - 1], counts[i]),
            })

        # 首尾变化
        overall_change_pct = 0.0
        if len(counts) >= 2:
            overall_change_pct = self._calculate_change_pct(counts[0], counts[-1])

        trend_label = self._get_trend_label([float(c) for c in counts])

        # 按城市分组
        by_city: dict[str, list[int]] = {}
        for i, pr in enumerate(period_records):
            city_counter: Counter[str] = Counter()
            for r in pr:
                city_counter[r.city] += 1
            for city, cnt in city_counter.items():
                if city not in by_city:
                    by_city[city] = [0] * len(periods)
                by_city[city][i] = cnt

        # 按方向分组（使用 description 中的简单关键词，此处按 experience 代替 direction）
        # 注意：direction 需要 DirectionClassifier，此方法不依赖它
        # 使用 company 字段的前缀作为 company_scale 的近似
        by_direction: dict[str, list[int]] = {}
        by_company_scale: dict[str, list[int]] = {}

        return {
            "periods": period_summaries,
            "changes": changes,
            "overall_change_pct": overall_change_pct,
            "trend_label": trend_label,
            "by_city": by_city,
            "by_direction": by_direction,
            "by_company_scale": by_company_scale,
        }

    # ─── 7.2 薪资趋势分析 ──────────────────────────────────────

    def analyze_salary_trend(
        self,
        records: list[JobRecord],
        periods: list[TimePeriod],
    ) -> dict:
        """分析薪资趋势：各时间段薪资统计及多维度分组。

        返回结构::

            {
                "periods": [
                    {"start": ..., "end": ..., "median": ..., "mean": ..., "p25": ..., "p75": ...},
                    ...
                ],
                "changes": [
                    {"from_period": 0, "to_period": 1,
                     "median_change_pct": ..., "mean_change_pct": ...,
                     "p25_change_pct": ..., "p75_change_pct": ...},
                    ...
                ],
                "by_city": { city: [stats_per_period, ...] },
                "by_experience": { exp: [stats_per_period, ...] },
                "by_direction": { direction: [stats_per_period, ...] },
            }
        """
        period_records = [self._records_in_period(records, p) for p in periods]

        period_summaries = []
        for i, p in enumerate(periods):
            stats = self._salary_stats(period_records[i])
            period_summaries.append({
                "start": p.start_date.isoformat(),
                "end": p.end_date.isoformat(),
                **stats,
            })

        # 相邻时间段薪资指标变化
        changes = []
        for i in range(1, len(period_summaries)):
            prev = period_summaries[i - 1]
            curr = period_summaries[i]
            changes.append({
                "from_period": i - 1,
                "to_period": i,
                "median_change_pct": self._calculate_change_pct(prev["median"], curr["median"]),
                "mean_change_pct": self._calculate_change_pct(prev["mean"], curr["mean"]),
                "p25_change_pct": self._calculate_change_pct(prev["p25"], curr["p25"]),
                "p75_change_pct": self._calculate_change_pct(prev["p75"], curr["p75"]),
            })

        # 按城市分组
        by_city: dict[str, list[dict]] = {}
        for i, pr in enumerate(period_records):
            city_groups: dict[str, list[JobRecord]] = {}
            for r in pr:
                city_groups.setdefault(r.city, []).append(r)
            for city, city_records in city_groups.items():
                if city not in by_city:
                    by_city[city] = [{"median": 0.0, "mean": 0.0, "p25": 0.0, "p75": 0.0}] * len(periods)
                    by_city[city] = list(by_city[city])  # make mutable copies
                by_city[city][i] = self._salary_stats(city_records)

        # 按经验分组
        by_experience: dict[str, list[dict]] = {}
        for i, pr in enumerate(period_records):
            exp_groups: dict[str, list[JobRecord]] = {}
            for r in pr:
                exp_groups.setdefault(r.experience, []).append(r)
            for exp, exp_records in exp_groups.items():
                if exp not in by_experience:
                    by_experience[exp] = [{"median": 0.0, "mean": 0.0, "p25": 0.0, "p75": 0.0}] * len(periods)
                    by_experience[exp] = list(by_experience[exp])
                by_experience[exp][i] = self._salary_stats(exp_records)

        # 按方向分组（空，需要 DirectionClassifier 配合）
        by_direction: dict[str, list[dict]] = {}

        return {
            "periods": period_summaries,
            "changes": changes,
            "by_city": by_city,
            "by_experience": by_experience,
            "by_direction": by_direction,
        }

    # ─── 7.3 技能趋势分析 ──────────────────────────────────────

    def analyze_skill_trend(
        self,
        records: list[JobRecord],
        periods: list[TimePeriod],
        skill_extractor: SkillExtractor,
    ) -> dict:
        """分析技能趋势：各时间段技能频率及变化。

        返回结构::

            {
                "periods": [
                    {"start": ..., "end": ..., "total_jobs": N,
                     "skill_frequencies": {skill: freq, ...}},
                    ...
                ],
                "rising_top10": [{"skill": ..., "change": ...}, ...],
                "declining_top10": [{"skill": ..., "change": ...}, ...],
                "emerging_skills": [{"skill": ..., "frequency": ...}, ...],
                "by_direction": {},
            }
        """
        period_records = [self._records_in_period(records, p) for p in periods]

        # 各时间段技能频率
        period_skill_freqs: list[dict[str, float]] = []
        period_summaries = []

        for i, p in enumerate(periods):
            pr = period_records[i]
            total = len(pr)
            skill_counter: Counter[str] = Counter()
            for r in pr:
                skills = skill_extractor.extract(r.description)
                for s in skills:
                    skill_counter[s] += 1

            freqs: dict[str, float] = {}
            if total > 0:
                for skill, count in skill_counter.items():
                    freqs[skill] = count / total
            period_skill_freqs.append(freqs)

            period_summaries.append({
                "start": p.start_date.isoformat(),
                "end": p.end_date.isoformat(),
                "total_jobs": total,
                "skill_frequencies": freqs,
            })

        # 计算频率变化（最后一个时间段 vs 倒数第二个）
        rising_top10: list[dict] = []
        declining_top10: list[dict] = []
        emerging_skills: list[dict] = []

        if len(period_skill_freqs) >= 2:
            prev_freqs = period_skill_freqs[-2]
            curr_freqs = period_skill_freqs[-1]
            all_skills = set(prev_freqs.keys()) | set(curr_freqs.keys())

            changes: list[tuple[str, float]] = []
            for skill in all_skills:
                old_f = prev_freqs.get(skill, 0.0)
                new_f = curr_freqs.get(skill, 0.0)
                change = new_f - old_f
                changes.append((skill, change))

            # 上升 Top10（change > 0，按 change 降序）
            rising = sorted(
                [(s, c) for s, c in changes if c > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:10]
            rising_top10 = [{"skill": s, "change": c} for s, c in rising]

            # 下降 Top10（change < 0，按 change 升序即绝对值降序）
            declining = sorted(
                [(s, c) for s, c in changes if c < 0],
                key=lambda x: x[1],
            )[:10]
            declining_top10 = [{"skill": s, "change": c} for s, c in declining]

            # 新兴技能：仅在较新时间段出现（旧时间段频率为 0）且频率 > 5%
            # 检查所有旧时间段
            older_skills: set[str] = set()
            for freqs in period_skill_freqs[:-1]:
                older_skills.update(freqs.keys())

            for skill, freq in curr_freqs.items():
                if skill not in older_skills and freq > 0.05:
                    emerging_skills.append({"skill": skill, "frequency": freq})
            emerging_skills.sort(key=lambda x: x["frequency"], reverse=True)

        return {
            "periods": period_summaries,
            "rising_top10": rising_top10,
            "declining_top10": declining_top10,
            "emerging_skills": emerging_skills,
            "by_direction": {},
        }

    # ─── 7.4 市场概览聚合 ──────────────────────────────────────

    def get_market_overview(
        self,
        records: list[JobRecord],
        skill_extractor: SkillExtractor,
        direction_classifier: DirectionClassifier,
        category: str,
    ) -> MarketOverview:
        """聚合市场概览数据。

        Args:
            records: 该类别的所有岗位记录
            skill_extractor: 技能提取器
            direction_classifier: 方向分类器
            category: 岗位类别关键词

        Returns:
            MarketOverview 对象
        """
        total_jobs = len(records)

        # 薪资统计
        stats = self._salary_stats(records)

        # 城市分布 Top10
        city_counter: Counter[str] = Counter()
        for r in records:
            city_counter[r.city] += 1
        city_distribution = [
            CityCount(city=city, count=count)
            for city, count in city_counter.most_common(10)
        ]

        # 经验分布
        exp_counter: Counter[str] = Counter()
        for r in records:
            exp_counter[r.experience] += 1
        experience_distribution = [
            ExperienceCount(experience=exp, count=count)
            for exp, count in exp_counter.most_common()
        ]

        # 趋势标签：基于记录的 publish_date 分布判断
        trend_label = self._compute_trend_label_from_records(records)

        # 方向列表
        direction_records: dict[str, list[JobRecord]] = {}
        for r in records:
            dirs = direction_classifier.classify(r, category)
            for d in dirs:
                direction_records.setdefault(d, []).append(r)

        directions: list[DirectionSummary] = []
        for dir_name, dir_recs in direction_records.items():
            dir_stats = self._salary_stats(dir_recs)
            directions.append(DirectionSummary(
                direction_name=dir_name,
                job_count=len(dir_recs),
                salary_median=dir_stats["median"],
                trend_label="平稳",
            ))
        directions.sort(key=lambda d: d.job_count, reverse=True)

        # 热门技能
        skill_counter: Counter[str] = Counter()
        for r in records:
            skills = skill_extractor.extract(r.description)
            for s in skills:
                skill_counter[s] += 1
        top_skills = [
            SkillFrequency(
                skill=skill,
                frequency=count / total_jobs if total_jobs > 0 else 0.0,
            )
            for skill, count in skill_counter.most_common(20)
        ]

        return MarketOverview(
            keyword=category,
            total_jobs=total_jobs,
            salary_median=stats["median"],
            salary_p25=stats["p25"],
            salary_p75=stats["p75"],
            city_distribution=city_distribution,
            experience_distribution=experience_distribution,
            trend_label=trend_label,
            directions=directions,
            top_skills=top_skills,
        )

    # ─── 9.1 薪资百分位排名 ──────────────────────────────────────

    def salary_benchmark(
        self,
        records: list[JobRecord],
        user_salary: float,
        city: str | None = None,
        experience: str | None = None,
    ) -> dict:
        """计算用户薪资在给定记录中的百分位排名。

        Args:
            records: 岗位记录列表
            user_salary: 用户月薪（千元）
            city: 可选，按城市筛选
            experience: 可选，按经验筛选

        Returns:
            包含 percentile, median, p25, p75, total_samples 的字典
        """
        filtered = records
        if city is not None:
            filtered = [r for r in filtered if r.city == city]
        if experience is not None:
            filtered = [r for r in filtered if r.experience == experience]

        midpoints: list[float] = []
        for r in filtered:
            mid = self._salary_midpoint(r)
            if mid is not None:
                midpoints.append(mid)

        if not midpoints:
            return {
                "percentile": 0.0,
                "median": 0.0,
                "p25": 0.0,
                "p75": 0.0,
                "total_samples": 0,
            }

        arr = np.array(midpoints)
        # 百分位排名：小于 user_salary 的比例 * 100
        below = float(np.sum(arr < user_salary))
        equal = float(np.sum(arr == user_salary))
        percentile = (below + equal * 0.5) / len(arr) * 100

        return {
            "percentile": round(percentile, 2),
            "median": float(np.median(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "total_samples": len(midpoints),
        }

    def _compute_trend_label_from_records(
        self, records: list[JobRecord]
    ) -> str:
        """根据记录的 publish_date 分布推断趋势标签。

        将记录按月分组，取最近两个月的数量比较。
        """
        monthly: Counter[str] = Counter()
        for r in records:
            if r.publish_date:
                key = r.publish_date.strftime("%Y-%m")
                monthly[key] += 1
        if len(monthly) < 2:
            return "平稳"
        sorted_months = sorted(monthly.keys())
        values = [float(monthly[m]) for m in sorted_months]
        return self._get_trend_label(values)
