"""
北京产品经理岗位深度招聘市场分析报告（完整版）
============================================
基于 Boss 直聘数据的深度交叉分析，覆盖 prompt.md 全部 20 个章节。
输出：自包含 HTML（内嵌 CSS + ECharts），保存到 backend/data/产品经理_深度分析.html
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from models.database import init_db, get_engine
from models.tables import JobRecordDB

# ═══════════════════════════════════════════════════════════════════════════
# 第一部分：数据加载与清洗
# ═══════════════════════════════════════════════════════════════════════════

FILTER_DESC = {
    "city": "仅北京",
    "experience": "仅 3-5 年和 5-10 年",
    "education": "仅本科及以上",
    "salary": "最高月薪 ≥ 30K",
    "job_type": "仅全职",
}


def load_data():
    """从数据库加载全部岗位记录，返回字典列表。"""
    init_db()
    engine = get_engine()
    data = []
    with Session(engine) as s:
        rows = s.query(JobRecordDB).all()
        for r in rows:
            mid = None
            annual = None
            if r.salary_min is not None and r.salary_max is not None:
                mid = (r.salary_min + r.salary_max) / 2
                months = r.salary_months if r.salary_months else 12
                annual = mid * months
            data.append({
                "title": r.title or "",
                "company": r.company or "",
                "salary_min": r.salary_min,
                "salary_max": r.salary_max,
                "salary_mid": mid,
                "salary_months": r.salary_months or 12,
                "salary_annual": annual,
                "salary_desc": r.salary_desc or "",
                "city": r.city or "",
                "area": r.area_district or "",
                "biz_district": r.business_district or "",
                "exp": r.experience or "",
                "edu": r.education or "",
                "description": r.description or "",
                "skills": json.loads(r.skills_json) if r.skills_json else [],
                "industry": r.brand_industry or "",
                "scale": r.brand_scale_name or "",
                "stage": r.brand_stage_name or "",
                "welfare": json.loads(r.welfare_json) if r.welfare_json else [],
                "boss_name": r.boss_name or "",
                "boss_title": r.boss_title or "",
                "keyword": r.keyword or "",
            })
    return data


# ═══════════════════════════════════════════════════════════════════════════
# 第二部分：分类与统计工具
# ═══════════════════════════════════════════════════════════════════════════

def salary_stats(values):
    if not values:
        return {"count": 0, "median": 0, "mean": 0, "p25": 0, "p75": 0, "p90": 0, "min": 0, "max": 0}
    a = np.array(values, dtype=float)
    return {
        "count": len(values),
        "median": round(float(np.median(a)), 1),
        "mean": round(float(np.mean(a)), 1),
        "p25": round(float(np.percentile(a, 25)), 1),
        "p75": round(float(np.percentile(a, 75)), 1),
        "p90": round(float(np.percentile(a, 90)), 1),
        "min": round(float(np.min(a)), 1),
        "max": round(float(np.max(a)), 1),
    }


DIRECTION_RULES = [
    ("AI/大模型产品", ["ai", "大模型", "gpt", "llm", "agent", "机器学习", "深度学习", "nlp", "算法产品", "智能体"]),
    ("智能硬件/IoT", ["硬件", "iot", "物联网", "智能家居", "嵌入式", "智能设备", "传感器", "智能硬件", "机器人", "具身"]),
    ("车载/智能座舱", ["车载", "座舱", "自动驾驶", "车联网", "汽车", "车机"]),
    ("数据产品", ["数据产品", "数据分析", "数据平台", "bi", "数仓", "大数据", "数据中台"]),
    ("策略产品", ["策略产品", "推荐", "搜索", "算法策略", "分发", "策略"]),
    ("商业化/广告", ["商业化", "广告", "变现", "投放", "营销", "商业产品"]),
    ("增长产品", ["增长", "用增", "growth", "拉新", "留存"]),
    ("B端/SaaS/企服", ["b端", "saas", "erp", "crm", "企业服务", "后台产品", "中后台", "中台", "企业", "g端"]),
    ("电商/交易", ["电商", "商城", "交易", "供应链", "物流", "仓储", "履约"]),
    ("金融产品", ["金融", "支付", "风控", "保险", "银行", "信贷", "理财"]),
    ("游戏产品", ["游戏", "game"]),
    ("内容/社区", ["内容", "社区", "社交", "直播", "视频", "短视频", "媒体"]),
    ("医疗健康", ["医疗", "健康", "医药", "生物"]),
    ("教育产品", ["教育", "课程", "培训"]),
    ("平台产品", ["平台产品", "开放平台", "api", "平台"]),
    ("用户体验/C端", ["c端", "用户产品", "用户体验", "体验", "app"]),
]


def classify_direction(title, skills, desc=""):
    combined = (title + " " + " ".join(skills) + " " + desc).lower()
    for direction, keywords in DIRECTION_RULES:
        if any(kw in combined for kw in keywords):
            return direction
    return "综合产品"


def is_product_role(title):
    """判断是否为产品相关岗位，过滤掉混入的开发/供应链/销售等岗位。"""
    t = title.lower()
    # 明确非产品岗位
    non_product = ["java", "python", "前端开发", "后端开发", "测试", "运维",
                   "销售", "会计", "财务", "法务", "行政", "人事", "hr",
                   "供应链vp", "供应链总监", "天然气", "电力设备"]
    if any(k in t for k in non_product):
        # 但如果同时包含"产品"则保留
        if "产品" not in t:
            return False
    # 包含产品相关关键词
    product_kw = ["产品", "product", "pm", "策略", "增长", "商业化"]
    if any(k in t for k in product_kw):
        return True
    # VP/总监/负责人如果不含产品关键词，可能是其他方向
    if any(k in t for k in ["vp", "副总裁", "总监", "cto", "ceo"]):
        if "产品" not in t:
            return False
    return True


def classify_level(title):
    t = title.lower()
    if any(k in t for k in ["vp", "副总裁"]):
        return "VP/副总裁"
    if any(k in t for k in ["总监", "director"]):
        return "总监"
    if any(k in t for k in ["负责人", "leader", "head"]):
        return "负责人"
    if any(k in t for k in ["资深", "senior", "专家"]):
        return "资深/专家"
    if any(k in t for k in ["高级"]):
        return "高级"
    if any(k in t for k in ["初级", "junior", "助理"]):
        return "初级/助理"
    return "普通"


_NON_SKILL_RE = re.compile(
    r"出差|现场办公|居家办公|坐班|远程|弹性|双休|五险|年终奖|加班|全勤"
    r"|^\d+-\d+年|\d+年以上.*经验|\d+年.*经验|经验$|经验者?优先|从业经验"
    r"|相关学历|相关专业$|本科|硕士|学历|不限$|不需要|销售经验|销售工作经验|周末双休"
)

_DIRECTION_TAGS = {
    "B端产品", "C端产品", "AI产品", "策略产品", "商业产品", "数据产品",
    "内容产品", "中后台产品", "电商产品", "金融产品", "医疗产品",
    "社区产品", "用增产品", "G端产品/政务产品", "直播/视频产品",
    "物联网产品", "云计算产品", "社交产品", "智能硬件产品",
    "区块链产品", "游戏产品", "后台产品", "用户产品", "增长产品",
    "移动端产品", "ERP产品/软件产品", "平台产品", "功能产品",
    "用户/功能产品", "TO B", "TO C", "其他产品方向",
    # 业务领域/场景标签（不等同于技能）
    "本地生活", "智能穿戴", "智能汽车", "智能驾驶", "自动驾驶",
    "新能源", "出行", "外卖", "团购", "旅游", "酒店",
    "教育", "医疗", "房产", "招聘", "物流", "快递",
    "客户端产品", "工具产品", "硬件产品", "车载产品",
}


def is_real_skill(tag):
    if not tag or len(tag) > 30:
        return False
    if _NON_SKILL_RE.search(tag):
        return False
    return True


def is_direction_tag(tag):
    return tag in _DIRECTION_TAGS



# ═══════════════════════════════════════════════════════════════════════════
# 第三部分：核心分析引擎
# ═══════════════════════════════════════════════════════════════════════════

def analyze(data):
    """执行全维度深度分析，返回结果字典 R。"""
    R = {}
    R["total"] = len(data)
    R["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    R["filter_desc"] = FILTER_DESC

    # valid_all: 所有有薪资的岗位（用于TOP15展示）
    valid_all = [d for d in data if d["salary_mid"] is not None]
    # valid: 剔除月薪中位数≥100K的极端值（用于统计计算）
    # 这些极端值多为猎头岗位（72%），薪资范围虚高，会干扰中位数/P75等统计
    valid = [d for d in valid_all if d["salary_mid"] < 100]
    R["valid_count"] = len(valid)
    R["extreme_excluded"] = len(valid_all) - len(valid)
    all_mids = [d["salary_mid"] for d in valid]
    overall_median = float(np.median(all_mids))
    R["overall_median"] = round(overall_median, 1)
    R["salary_overview"] = salary_stats(all_mids)

    p75_threshold = float(np.percentile(all_mids, 75))
    R["p75_threshold"] = round(p75_threshold, 1)
    high_salary_jobs = [d for d in valid if d["salary_mid"] >= p75_threshold]
    normal_jobs = [d for d in valid if d["salary_mid"] < p75_threshold]
    R["high_salary_count"] = len(high_salary_jobs)
    R["high_salary_pct"] = round(len(high_salary_jobs) / len(valid) * 100, 1)

    # ── 薪资分布直方图 ──
    bins = [15, 20, 25, 30, 35, 40, 45, 50, 60, 80, 100, 260]
    labels = ["15-20K", "20-25K", "25-30K", "30-35K", "35-40K", "40-45K",
              "45-50K", "50-60K", "60-80K", "80-100K", "100K+"]
    hist, _ = np.histogram(all_mids, bins=bins)
    R["salary_dist"] = [{"range": labels[i], "count": int(hist[i])} for i in range(len(labels))]

    R["exp_dist"] = [{"name": k, "value": v} for k, v in Counter(d["exp"] or "未知" for d in valid).most_common()]
    R["edu_dist"] = [{"name": k, "value": v} for k, v in Counter(d["edu"] or "未知" for d in valid).most_common()]

    # ══════════════════════════════════════════════════════════════════════
    # 岗位方向重新聚类
    # ══════════════════════════════════════════════════════════════════════
    for d in data:
        d["direction"] = classify_direction(d["title"], d["skills"], d["description"])
        d["level"] = classify_level(d["title"])

    dir_counter = Counter(d["direction"] for d in data)
    dir_salary = defaultdict(list)
    dir_jobs = defaultdict(list)
    for d in valid:
        dir_salary[d["direction"]].append(d["salary_mid"])
        dir_jobs[d["direction"]].append(d)

    direction_analysis = []
    for direction, vals in dir_salary.items():
        if len(vals) < 3:
            continue
        stats = salary_stats(vals)
        high_count = sum(1 for v in vals if v >= p75_threshold)
        high_pct = round(high_count / len(vals) * 100, 1)
        sk_counter = Counter()
        for d in dir_jobs[direction]:
            for sk in d["skills"]:
                if is_real_skill(sk) and not is_direction_tag(sk):
                    sk_counter[sk] += 1
        top_skills = [s for s, _ in sk_counter.most_common(5)]
        exp_counter = Counter(d["exp"] for d in dir_jobs[direction])
        overall_p75 = float(np.percentile(all_mids, 75))
        overall_p90 = float(np.percentile(all_mids, 90))
        p75_premium = round((stats["p75"] - overall_p75) / overall_p75 * 100, 1)
        p90_premium = round((stats["p90"] - overall_p90) / overall_p90 * 100, 1)
        direction_analysis.append({
            "direction": direction,
            "count": dir_counter[direction],
            "pct": round(dir_counter[direction] / len(data) * 100, 1),
            **stats,
            "high_pct": high_pct,
            "premium": round((stats["median"] - overall_median) / overall_median * 100, 1),
            "p75_premium": p75_premium,
            "p90_premium": p90_premium,
            "top_skills": top_skills,
            "exp_35_pct": round(exp_counter.get("3-5年", 0) / len(vals) * 100, 0),
            "exp_510_pct": round(exp_counter.get("5-10年", 0) / len(vals) * 100, 0),
        })
    direction_analysis.sort(key=lambda x: x["median"], reverse=True)
    R["direction_analysis"] = direction_analysis

    # ══════════════════════════════════════════════════════════════════════
    # 高薪 vs 普通岗位差异分析
    # ══════════════════════════════════════════════════════════════════════
    hs_skill_counter = Counter()
    nm_skill_counter = Counter()
    hs_dir_counter = Counter()
    nm_dir_counter = Counter()
    hs_level_counter = Counter()
    nm_level_counter = Counter()
    hs_industry_counter = Counter()
    nm_industry_counter = Counter()

    for d in high_salary_jobs:
        for sk in d["skills"]:
            if is_real_skill(sk):
                hs_skill_counter[sk] += 1
        hs_dir_counter[d["direction"]] += 1
        hs_level_counter[d["level"]] += 1
        if d["industry"]:
            hs_industry_counter[d["industry"]] += 1

    for d in normal_jobs:
        for sk in d["skills"]:
            if is_real_skill(sk):
                nm_skill_counter[sk] += 1
        nm_dir_counter[d["direction"]] += 1
        nm_level_counter[d["level"]] += 1
        if d["industry"]:
            nm_industry_counter[d["industry"]] += 1

    hs_total = max(len(high_salary_jobs), 1)
    nm_total = max(len(normal_jobs), 1)

    # 技能差异
    skill_diff = []
    all_skills = set(hs_skill_counter.keys()) | set(nm_skill_counter.keys())
    for sk in all_skills:
        hs_pct = round(hs_skill_counter.get(sk, 0) / hs_total * 100, 1)
        nm_pct = round(nm_skill_counter.get(sk, 0) / nm_total * 100, 1)
        if hs_pct < 2 and nm_pct < 2:
            continue
        ratio = round(hs_pct / max(nm_pct, 0.1), 2)
        skill_diff.append({
            "skill": sk, "hs_pct": hs_pct, "nm_pct": nm_pct,
            "ratio": ratio, "is_direction": is_direction_tag(sk),
        })
    skill_diff.sort(key=lambda x: x["ratio"], reverse=True)
    R["skill_diff_top"] = [s for s in skill_diff if s["ratio"] > 1.2 and s["hs_pct"] >= 3][:20]
    R["skill_diff_bottom"] = [s for s in skill_diff if s["ratio"] < 0.8 and s["nm_pct"] >= 3][:10]

    # 方向差异
    dir_diff = []
    for d in set(hs_dir_counter.keys()) | set(nm_dir_counter.keys()):
        hs_pct = round(hs_dir_counter.get(d, 0) / hs_total * 100, 1)
        nm_pct = round(nm_dir_counter.get(d, 0) / nm_total * 100, 1)
        ratio = round(hs_pct / max(nm_pct, 0.1), 2)
        dir_diff.append({"direction": d, "hs_pct": hs_pct, "nm_pct": nm_pct, "ratio": ratio})
    dir_diff.sort(key=lambda x: x["ratio"], reverse=True)
    R["dir_diff"] = dir_diff

    # 职级差异
    level_diff = []
    for lv in set(hs_level_counter.keys()) | set(nm_level_counter.keys()):
        hs_pct = round(hs_level_counter.get(lv, 0) / hs_total * 100, 1)
        nm_pct = round(nm_level_counter.get(lv, 0) / nm_total * 100, 1)
        level_diff.append({"level": lv, "hs_pct": hs_pct, "nm_pct": nm_pct})
    R["level_diff"] = level_diff

    # 行业差异
    ind_diff = []
    for ind in set(hs_industry_counter.keys()) | set(nm_industry_counter.keys()):
        hs_pct = round(hs_industry_counter.get(ind, 0) / hs_total * 100, 1)
        nm_pct = round(nm_industry_counter.get(ind, 0) / nm_total * 100, 1)
        if hs_pct < 1 and nm_pct < 1:
            continue
        ratio = round(hs_pct / max(nm_pct, 0.1), 2)
        ind_diff.append({"industry": ind, "hs_pct": hs_pct, "nm_pct": nm_pct, "ratio": ratio})
    ind_diff.sort(key=lambda x: x["ratio"], reverse=True)
    R["ind_diff"] = ind_diff[:15]

    # ══════════════════════════════════════════════════════════════════════
    # 技能价值四分类
    # ══════════════════════════════════════════════════════════════════════
    skill_salaries = defaultdict(list)
    for d in valid:
        for sk in d["skills"]:
            if is_real_skill(sk):
                skill_salaries[sk].append(d["salary_mid"])

    skill_value = []
    for sk, vals in skill_salaries.items():
        if len(vals) < 10:
            continue
        med = float(np.median(vals))
        premium = round((med - overall_median) / overall_median * 100, 1)
        hs_pct = round(hs_skill_counter.get(sk, 0) / hs_total * 100, 1)
        nm_pct = round(nm_skill_counter.get(sk, 0) / nm_total * 100, 1)
        ratio = round(hs_pct / max(nm_pct, 0.1), 2)
        # 证据等级：A=样本≥100, B=50-99, C=20-49, D=<20
        if len(vals) >= 100:
            evidence = "A"
        elif len(vals) >= 50:
            evidence = "B"
        elif len(vals) >= 20:
            evidence = "C"
        else:
            evidence = "D"
        # 新四分类
        if is_direction_tag(sk):
            category = "方向标签"  # 反映岗位方向，不等同于技能
        elif len(vals) < 20:
            category = "小样本趋势词"  # 仅作观察，不单独下结论
        elif (ratio > 1.3 or premium > 5) and len(vals) >= 20:
            category = "能力/技能信号"  # 可作为简历或作品集加分项
        elif len(vals) >= 50 and abs(premium) <= 8:
            category = "无区分度标签"  # 不适合作为能力结论
        else:
            category = "无区分度标签"
        skill_value.append({
            "skill": sk, "count": len(vals), "median": round(med, 1),
            "premium": premium, "hs_pct": hs_pct, "nm_pct": nm_pct,
            "ratio": ratio, "category": category, "evidence": evidence,
        })
    skill_value.sort(key=lambda x: x["median"], reverse=True)
    R["skill_value"] = skill_value
    R["skills_by_cat"] = {
        "方向标签": [s for s in skill_value if s["category"] == "方向标签"],
        "能力/技能信号": sorted([s for s in skill_value if s["category"] == "能力/技能信号"], key=lambda x: -x["premium"]),
        "小样本趋势词": [s for s in skill_value if s["category"] == "小样本趋势词"],
        "无区分度标签": [s for s in skill_value if s["category"] == "无区分度标签"],
    }

    # ══════════════════════════════════════════════════════════════════════
    # 公司分析 TOP20
    # ══════════════════════════════════════════════════════════════════════
    company_data = defaultdict(lambda: {"jobs": [], "salaries": [], "industries": set(), "scales": set(), "stages": set()})
    for d in data:
        c = d["company"]
        if not c:
            continue
        company_data[c]["jobs"].append(d)
        if d["salary_mid"] is not None:
            company_data[c]["salaries"].append(d["salary_mid"])
        if d["industry"]:
            company_data[c]["industries"].add(d["industry"])
        if d["scale"]:
            company_data[c]["scales"].add(d["scale"])
        if d["stage"]:
            company_data[c]["stages"].add(d["stage"])

    active_companies = []
    for company, info in company_data.items():
        n = len(info["jobs"])
        if n < 3:
            continue
        sals = info["salaries"]
        stats = salary_stats(sals) if sals else {}
        high_n = sum(1 for v in sals if v >= p75_threshold) if sals else 0
        # 判断公司类型
        ind_str = "、".join(sorted(info["industries"])[:2]) if info["industries"] else ""
        scale_str = next(iter(info["scales"]), "")
        stage_str = next(iter(info["stages"]), "")
        co_type = _classify_company_type(company, ind_str, scale_str, stage_str)
        # 主要方向
        dir_cnt = Counter(d["direction"] for d in info["jobs"])
        main_dirs = [d for d, _ in dir_cnt.most_common(2)]
        active_companies.append({
            "company": company,
            "job_count": n,
            "salary_median": stats.get("median", 0),
            "salary_p75": stats.get("p75", 0),
            "salary_p90": stats.get("p90", 0),
            "high_pct": round(high_n / max(len(sals), 1) * 100, 1),
            "industry": ind_str or "未知",
            "scale": scale_str or "未知",
            "stage": stage_str or "未知",
            "co_type": co_type,
            "main_dirs": "、".join(main_dirs),
        })
    active_companies.sort(key=lambda x: x["job_count"], reverse=True)
    R["active_companies"] = active_companies[:25]

    # 按薪资排序的公司 TOP15（至少5个岗位，避免小样本偏差）
    salary_companies = sorted([c for c in active_companies if c["salary_median"] > 0 and c["job_count"] >= 5],
                              key=lambda x: x["salary_median"], reverse=True)[:15]
    R["salary_companies"] = salary_companies

    # ══════════════════════════════════════════════════════════════════════
    # 经验 × 方向 交叉分析
    # ══════════════════════════════════════════════════════════════════════
    exp_dir = defaultdict(lambda: defaultdict(list))
    for d in valid:
        exp_dir[d["exp"]][d["direction"]].append(d["salary_mid"])

    cross = []
    for exp in ["3-5年", "5-10年"]:
        if exp not in exp_dir:
            continue
        for direction, vals in exp_dir[exp].items():
            if len(vals) < 5:
                continue
            cross.append({
                "exp": exp, "direction": direction,
                "median": round(float(np.median(vals)), 1),
                "p75": round(float(np.percentile(vals, 75)), 1),
                "count": len(vals),
            })
    cross.sort(key=lambda x: x["median"], reverse=True)
    R["exp_dir_cross"] = cross[:20]

    # ══════════════════════════════════════════════════════════════════════
    # 职级薪资
    # ══════════════════════════════════════════════════════════════════════
    level_salaries = defaultdict(list)
    for d in valid:
        level_salaries[d["level"]].append(d["salary_mid"])
    level_order = ["VP/副总裁", "总监", "负责人", "资深/专家", "高级", "普通", "初级/助理"]
    R["level_salary"] = []
    for lv in level_order:
        if lv in level_salaries and len(level_salaries[lv]) >= 3:
            R["level_salary"].append({"level": lv, **salary_stats(level_salaries[lv])})

    # ══════════════════════════════════════════════════════════════════════
    # 行业薪资 TOP15
    # ══════════════════════════════════════════════════════════════════════
    ind_salary = defaultdict(list)
    for d in valid:
        if d["industry"]:
            ind_salary[d["industry"]].append(d["salary_mid"])
    R["industry_salary"] = sorted(
        [{"industry": ind + (" ⚠️" if len(vals) < 50 else ""), **salary_stats(vals)}
         for ind, vals in ind_salary.items() if len(vals) >= 50],
        key=lambda x: x["median"], reverse=True
    )[:15]

    # ══════════════════════════════════════════════════════════════════════
    # 规模 / 融资阶段薪资
    # ══════════════════════════════════════════════════════════════════════
    scale_salary = defaultdict(list)
    stage_salary = defaultdict(list)
    for d in valid:
        if d["scale"]:
            scale_salary[d["scale"]].append(d["salary_mid"])
        if d["stage"]:
            stage_salary[d["stage"]].append(d["salary_mid"])
    R["scale_salary"] = sorted(
        [{"scale": k, **salary_stats(v)} for k, v in scale_salary.items() if len(v) >= 5],
        key=lambda x: x["median"], reverse=True
    )
    R["stage_salary"] = sorted(
        [{"stage": k, **salary_stats(v)} for k, v in stage_salary.items() if len(v) >= 5],
        key=lambda x: x["median"], reverse=True
    )

    # ══════════════════════════════════════════════════════════════════════
    # 区域薪资
    # ══════════════════════════════════════════════════════════════════════
    area_salary = defaultdict(list)
    for d in valid:
        if d["area"]:
            area_salary[d["area"]].append(d["salary_mid"])
    R["area_salary"] = sorted(
        [{"area": k + (" ⚠️" if len(v) < 20 else ""), **salary_stats(v)} for k, v in area_salary.items() if len(v) >= 10],
        key=lambda x: x["count"], reverse=True
    )

    # 商圈级别分析
    biz_salary = defaultdict(lambda: {"salaries": [], "district": "", "companies": []})
    for d in valid:
        biz = d.get("biz_district", "")
        if biz and d["area"]:
            key = f'{d["area"]}·{biz}'
            biz_salary[key]["salaries"].append(d["salary_mid"])
            biz_salary[key]["district"] = d["area"]
            biz_salary[key]["companies"].append(d["company"])

    biz_list = []
    # 集团关键词，用于判断是否被同一集团主导
    GROUP_KEYWORDS = {
        "京东": ["京东", "沃东", "JD"],
        "字节跳动": ["字节", "今日头条", "抖音", "飞书"],
        "阿里": ["阿里", "淘宝", "天猫", "蚂蚁", "高德", "钉钉", "饿了么", "菜鸟", "优酷"],
        "百度": ["百度"],
        "美团": ["美团"],
        "小米": ["小米"],
    }
    def _get_group(company):
        for group, kws in GROUP_KEYWORDS.items():
            if any(kw in company for kw in kws):
                return group
        return company

    for k, v in biz_salary.items():
        if len(v["salaries"]) < 15:
            continue
        # 按集团合并后检查是否被单一集团主导（>60%）
        group_counter = Counter(_get_group(c) for c in v["companies"])
        top_group, top_cnt = group_counter.most_common(1)[0]
        dominated = top_cnt / len(v["salaries"]) > 0.6
        note = f"（主要为{top_group}）" if dominated else ""
        biz_list.append({"biz_area": k + note, "district": v["district"], **salary_stats(v["salaries"])})
    R["biz_area_salary"] = sorted(biz_list, key=lambda x: x["count"], reverse=True)[:25]

    # ══════════════════════════════════════════════════════════════════════
    # 招聘者类型
    # ══════════════════════════════════════════════════════════════════════
    recruiter_salary = defaultdict(list)
    for d in valid:
        bt = d["boss_title"]
        if "猎头" in bt:
            rtype = "猎头"
        elif any(k in bt for k in ["总监", "VP", "CTO", "CEO", "负责人", "总经理", "合伙人"]):
            rtype = "业务负责人"
        elif any(k in bt for k in ["HR", "人事", "招聘", "人力", "hr"]):
            rtype = "HR"
        else:
            rtype = "其他"
        recruiter_salary[rtype].append(d["salary_mid"])
    R["recruiter_salary"] = sorted(
        [{"type": k, **salary_stats(v)} for k, v in recruiter_salary.items() if len(v) >= 5],
        key=lambda x: x["median"], reverse=True
    )

    # ══════════════════════════════════════════════════════════════════════
    # 高薪岗位 TOP15（仅产品相关岗位，使用未剔除极端值的全量数据）
    # ══════════════════════════════════════════════════════════════════════
    product_valid_all = [d for d in valid_all if is_product_role(d["title"])]
    top_jobs = sorted(product_valid_all, key=lambda d: d["salary_mid"], reverse=True)[:15]
    R["top_salary_jobs"] = [
        {"title": d["title"], "company": d["company"], "salary_desc": d["salary_desc"],
         "exp": d["exp"], "skills": d["skills"][:6], "industry": d["industry"],
         "scale": d["scale"], "direction": d["direction"],
         "source": "猎头" if ("猎头" in d.get("boss_title", "") or "猎" in d.get("company", "")) else "直招"}
        for d in top_jobs
    ]

    # ══════════════════════════════════════════════════════════════════════
    # 第7章新增：高薪差异因子分析
    # ══════════════════════════════════════════════════════════════════════
    R["high_salary_factors"] = _analyze_high_salary_factors(valid, high_salary_jobs, normal_jobs, dir_jobs, overall_median, p75_threshold)

    # ══════════════════════════════════════════════════════════════════════
    # 求职者背景匹配分析
    # ══════════════════════════════════════════════════════════════════════
    R["match_analysis"] = _build_match_analysis(direction_analysis, R, overall_median, p75_threshold)

    # ══════════════════════════════════════════════════════════════════════
    # 求职策略
    # ══════════════════════════════════════════════════════════════════════
    R["strategy"] = _build_strategy(R, direction_analysis, overall_median, p75_threshold)

    # ══════════════════════════════════════════════════════════════════════
    # 第11章新增：简历改造建议
    # ══════════════════════════════════════════════════════════════════════
    R["resume_advice"] = _build_resume_advice(R)

    # ══════════════════════════════════════════════════════════════════════
    # 第12章新增：作品集建议
    # ══════════════════════════════════════════════════════════════════════
    R["portfolio_advice"] = _build_portfolio_advice(R)

    # ══════════════════════════════════════════════════════════════════════
    # 第13章新增：风险与误区
    # ══════════════════════════════════════════════════════════════════════
    R["risk_analysis"] = _build_risk_analysis(R)

    # ══════════════════════════════════════════════════════════════════════
    # 第17章新增：投递关键词
    # ══════════════════════════════════════════════════════════════════════
    R["search_keywords"] = _build_search_keywords(R)

    # ══════════════════════════════════════════════════════════════════════
    # 图表洞察文字（每个图表配一段分析结论）
    # ══════════════════════════════════════════════════════════════════════
    R["chart_insights"] = _build_chart_insights(R)

    # ══════════════════════════════════════════════════════════════════════
    # 各章总结论
    # ══════════════════════════════════════════════════════════════════════
    R["chapter_conclusions"] = _build_chapter_conclusions(R)

    return R


def _classify_company_type(name, industry, scale, stage):
    """判断公司类型。"""
    n = name.lower()
    big_names = ["字节", "腾讯", "阿里", "百度", "美团", "京东", "快手", "网易", "小米", "华为",
                 "滴滴", "拼多多", "蚂蚁", "微软", "谷歌", "亚马逊", "苹果", "三星", "oppo", "vivo"]
    for bn in big_names:
        if bn in n:
            return "大厂"
    if "上市" in stage:
        return "上市公司"
    if any(k in stage for k in ["D轮", "E轮", "F轮"]):
        return "独角兽"
    if any(k in scale for k in ["10000", "万人"]):
        return "大厂"
    if any(k in industry for k in ["汽车", "车"]):
        return "车企"
    if any(k in n for k in ["外企", "外资"]):
        return "外企"
    if any(k in stage for k in ["A轮", "B轮", "C轮", "天使"]):
        return "创业公司"
    return "中型公司"


# ═══════════════════════════════════════════════════════════════════════════
# 第四部分：新增分析模块（第7/11/12/13/17章）
# ═══════════════════════════════════════════════════════════════════════════

def _analyze_high_salary_factors(valid, high_salary_jobs, normal_jobs, dir_jobs, overall_median, p75):
    """第7章：高薪差异因子分析 - 找出是什么让一个岗位更贵。"""
    factors = {}

    # 1. 经验因素
    exp_salary = defaultdict(list)
    for d in valid:
        exp_salary[d["exp"]].append(d["salary_mid"])
    exp_items = []
    for exp in ["3-5年", "5-10年"]:
        if exp in exp_salary:
            s = salary_stats(exp_salary[exp])
            exp_items.append({"exp": exp, **s})
    factors["exp_factor"] = exp_items

    # 2. 规模因素
    scale_items = []
    scale_salary = defaultdict(list)
    for d in valid:
        if d["scale"]:
            scale_salary[d["scale"]].append(d["salary_mid"])
    for sc, vals in scale_salary.items():
        if len(vals) >= 10:
            s = salary_stats(vals)
            high_n = sum(1 for v in vals if v >= p75)
            scale_items.append({"scale": sc, "high_pct": round(high_n / len(vals) * 100, 1), **s})
    scale_items.sort(key=lambda x: x["median"], reverse=True)
    factors["scale_factor"] = scale_items

    # 3. 融资阶段因素
    stage_items = []
    stage_salary = defaultdict(list)
    for d in valid:
        if d["stage"]:
            stage_salary[d["stage"]].append(d["salary_mid"])
    for st, vals in stage_salary.items():
        if len(vals) >= 10:
            s = salary_stats(vals)
            high_n = sum(1 for v in vals if v >= p75)
            stage_items.append({"stage": st, "high_pct": round(high_n / len(vals) * 100, 1), **s})
    stage_items.sort(key=lambda x: x["median"], reverse=True)
    factors["stage_factor"] = stage_items

    # 4. 方向 × 经验交叉（同方向下5-10年比3-5年溢价多少）
    dir_exp_premium = []
    for direction, jobs in dir_jobs.items():
        exp35 = [d["salary_mid"] for d in jobs if d["exp"] == "3-5年"]
        exp510 = [d["salary_mid"] for d in jobs if d["exp"] == "5-10年"]
        if len(exp35) >= 5 and len(exp510) >= 5:
            m35 = float(np.median(exp35))
            m510 = float(np.median(exp510))
            premium = round((m510 - m35) / m35 * 100, 1)
            dir_exp_premium.append({
                "direction": direction,
                "median_35": round(m35, 1),
                "median_510": round(m510, 1),
                "premium": premium,
                "count_35": len(exp35),
                "count_510": len(exp510),
            })
    dir_exp_premium.sort(key=lambda x: x["premium"], reverse=True)
    factors["dir_exp_premium"] = dir_exp_premium

    # 5. 职级因素
    level_high = Counter(d["level"] for d in high_salary_jobs)
    level_normal = Counter(d["level"] for d in normal_jobs)
    hs_total = max(len(high_salary_jobs), 1)
    nm_total = max(len(normal_jobs), 1)
    level_factor = []
    for lv in set(level_high.keys()) | set(level_normal.keys()):
        hp = round(level_high.get(lv, 0) / hs_total * 100, 1)
        np_ = round(level_normal.get(lv, 0) / nm_total * 100, 1)
        level_factor.append({"level": lv, "hs_pct": hp, "nm_pct": np_, "ratio": round(hp / max(np_, 0.1), 2)})
    level_factor.sort(key=lambda x: x["ratio"], reverse=True)
    factors["level_factor"] = level_factor

    # 6. 综合高薪因子排名（可操作能力因子优先，背景变量在后）
    summary = []
    # 可操作能力因子（求职者可以通过学习、包装、项目经历提升）
    summary.append({"factor": "业务闭环能力（对结果负责）", "impact": "强", "evidence": "高薪JD普遍要求'负责核心业务目标''对指标结果负责'，普通JD多为'需求分析/PRD撰写'", "actionable": "每段经历写清：问题判断→关键决策→落地结果→指标变化"})
    summary.append({"factor": "指标驱动能力（数据决策）", "impact": "强", "evidence": "高薪JD高频出现DAU/留存/转化/ROI/AB实验，普通JD仅'数据分析'", "actionable": "准备2-3个数据驱动决策案例，展示指标定义→实验设计→效果验证"})
    summary.append({"factor": "策略设计能力", "impact": "强", "evidence": "策略产品方向高薪占比36.4%，JD要求推荐/搜索/分发/用户分层", "actionable": "补AB实验方法论（2-3周），展示策略设计→验证→迭代链路"})
    summary.append({"factor": "AI应用落地能力", "impact": "强", "evidence": "AI/大模型方向1586个岗位，P75溢价+5.6%，高薪占比36.3%", "actionable": "理解大模型能力边界，准备AI+业务场景的作品集"})
    summary.append({"factor": "复杂系统抽象能力", "impact": "中", "evidence": "平台产品P75=55K（溢价+22%），但样本仅21个", "actionable": "需要真实复杂系统项目经历支撑，适合有相关背景的候选人"})
    summary.append({"factor": "Owner/负责人能力", "impact": "强", "evidence": "负责人级别中位数50K vs 普通35K，差距15K/月", "actionable": "简历中体现独立负责范围、决策权和业务结果"})
    # 背景变量（影响薪资但非短期可操作）
    if len(exp_items) >= 2:
        gap = exp_items[1]["median"] - exp_items[0]["median"] if exp_items[1]["median"] > exp_items[0]["median"] else exp_items[0]["median"] - exp_items[1]["median"]
        summary.append({"factor": "【背景变量】经验年限（5-10年 vs 3-5年）", "impact": "强", "evidence": f"中位数差距 {gap}K/月", "actionable": "需要时间积累，短期无法补齐"})
    summary.append({"factor": "【背景变量】岗位方向选择", "impact": "强", "evidence": "不同方向高薪占比差距可达20个百分点", "actionable": "选择高薪占比高且与自身背景匹配的方向"})
    summary.append({"factor": "【背景变量】公司规模/融资阶段", "impact": "中", "evidence": "上市/D轮+公司薪资普遍更高", "actionable": "优先投递大厂和成熟公司"})
    factors["summary"] = summary

    return factors


def _build_match_analysis(direction_analysis, R, overall_median, p75):
    """第9章：求职者背景匹配分析。"""
    results = []
    for da in direction_analysis:
        d = da["direction"]
        match = _match_score(d)
        if da["median"] >= p75:
            salary_potential = "高"
        elif da["median"] >= overall_median:
            salary_potential = "中高"
        else:
            salary_potential = "中"
        if match >= 4:
            difficulty = "低"
        elif match >= 3:
            difficulty = "中"
        else:
            difficulty = "高"
        score = match * 2 + (1 if salary_potential == "高" else 0) + (1 if da["count"] >= 50 else 0)
        if score >= 10:
            recommend = "⭐ 冲刺"
        elif score >= 8:
            recommend = "✅ 主投"
        elif score >= 6:
            recommend = "🔄 可尝试"
        elif score >= 4:
            recommend = "🛡️ 保底"
        else:
            recommend = "❌ 不建议"

        advantages, gaps = _get_match_details(d)
        results.append({
            "direction": d, "match": match,
            "match_stars": "★" * match + "☆" * (5 - match),
            "salary_potential": salary_potential, "difficulty": difficulty,
            "recommend": recommend, "count": da["count"],
            "median": da["median"], "p75": da["p75"], "high_pct": da["high_pct"],
            "advantages": advantages, "gaps": gaps,
        })
    results.sort(key=lambda x: (-x["match"], -x["median"]))
    return results


def _match_score(direction):
    scores = {
        "智能硬件/IoT": 5, "车载/智能座舱": 4, "AI/大模型产品": 3,
        "用户体验/C端": 4, "平台产品": 4, "数据产品": 3, "增长产品": 3,
        "策略产品": 2, "商业化/广告": 2, "B端/SaaS/企服": 2,
        "内容/社区": 3, "电商/交易": 2, "金融产品": 1, "游戏产品": 1,
        "医疗健康": 1, "教育产品": 1, "综合产品": 3,
    }
    return scores.get(direction, 2)


def _get_match_details(d):
    if "硬件" in d or "IoT" in d:
        return (["智能家居中枢产品经验", "多端协同能力", "设备控制体验"], ["如涉及芯片/嵌入式需补充"])
    elif "车载" in d:
        return (["多端协同（车机属于多端之一）", "场景化产品设计"], ["车规级开发流程", "座舱交互规范"])
    elif "AI" in d or "大模型" in d:
        return (["C端产品感觉", "场景化思维"], ["AI/大模型技术理解", "Prompt Engineering", "Agent架构"])
    elif "C端" in d or "用户" in d:
        return (["C端产品全流程经验", "用户体验设计", "数据驱动"], [])
    elif "平台" in d:
        return (["多端协同=平台化思维", "复杂项目推进", "规则统一经验"], ["开放平台/API设计经验"])
    elif "数据" in d:
        return (["数据分析能力", "指标体系经验"], ["数据平台/BI工具深度"])
    elif "增长" in d:
        return (["DAU/留存/转化指标经验", "C端用户理解"], ["增长实验体系", "投放经验"])
    elif "策略" in d:
        return (["场景化产品=策略思维基础"], ["推荐/搜索算法理解", "策略实验框架"])
    elif "商业化" in d or "广告" in d:
        return (["C端流量理解"], ["广告系统架构", "商业化指标体系"])
    elif "B端" in d or "SaaS" in d:
        return (["复杂项目推进", "跨团队协同"], ["B端业务流程设计", "SaaS产品架构"])
    else:
        return (["产品经理通用能力"], ["该方向专业知识"])


def _build_strategy(R, direction_analysis, overall_median, p75):
    """第10章：求职策略。"""
    strategy = {}
    sprint, main_target, backup, avoid, precise = [], [], [], [], []
    for ma in R["match_analysis"]:
        entry = f'{ma["direction"]}（中位数{ma["median"]}K，{ma["count"]}个岗位）'
        d = ma["direction"]
        if any(k in d for k in ["AI", "策略", "增长", "商业化"]):
            sprint.append(entry)
        elif any(k in d for k in ["IoT", "硬件"]):
            main_target.append(entry)
        elif any(k in d for k in ["平台", "车载"]):
            precise.append(entry)
        elif any(k in d for k in ["B端", "C端", "用户", "综合"]):
            backup.append(entry)
        elif any(k in d for k in ["金融", "医疗", "教育", "游戏", "数据产品"]):
            avoid.append(entry)
        else:
            backup.append(entry)
    strategy["sprint"] = sprint
    strategy["main_target"] = main_target
    strategy["precise"] = precise
    strategy["backup"] = backup
    strategy["avoid"] = avoid

    strategy["resume_keywords"] = [
        "智能家居中枢产品", "多端协同（手机/电视/音箱/车/手表）",
        "场景化产品设计", "设备控制体验", "复杂项目推进",
        "跨团队协同", "数据驱动（DAU/留存/转化）",
        "用户体验重构", "平台化思维", "0-1产品经验",
    ]

    strategy["action_plan"] = [
        {"week": "第1周：方向确认 + 数据消化",
         "tasks": ["精读本报告，确认冲刺/主投/保底方向", "在Boss直聘搜索目标方向岗位，收藏20-30个目标JD",
                   "对比目标JD和自身经历，列出能力差距清单", "确定2-3个重点投递方向"],
         "output": "方向选择决策文档 + 目标JD收藏夹"},
        {"week": "第2周：简历改造 + 项目包装",
         "tasks": ["按目标方向改写简历，突出匹配关键词", "将智能家居经验包装为「多端协同平台产品」",
                   "将场景化产品经验包装为「用户洞察+体验重构」", "准备2-3个版本简历（IoT方向/AI方向/通用版）"],
         "output": "2-3份定向简历"},
        {"week": "第3周：作品集 + 面试准备",
         "tasks": ["准备1份核心作品集（智能家居中枢产品设计）", "梳理STAR面试故事（复杂项目推进、数据驱动决策、跨团队协同）",
                   "研究目标公司产品，准备针对性面试问题", "模拟面试2-3次"],
         "output": "作品集PDF + 面试故事库"},
        {"week": "第4周：集中投递 + 复盘优化",
         "tasks": ["每天投递5-10个目标岗位", "优先投递冲刺方向，同步投递主投方向",
                   "记录面试反馈，持续优化简历和话术", "每周复盘投递转化率，调整策略"],
         "output": "投递记录表 + 面试复盘笔记"},
    ]
    return strategy


def _build_resume_advice(R):
    """第11章：简历改造建议。"""
    advice = {}

    # 简历关键词
    advice["keywords"] = [
        {"keyword": "多端协同平台产品", "target": "平台产品/IoT/车载", "why": "高薪岗位高频要求，体现系统化能力", "how": "「负责手机/电视/音箱/车/手表五端协同的中枢产品设计」"},
        {"keyword": "场景化产品设计", "target": "C端/IoT/AI产品", "why": "体现用户洞察和产品创新能力", "how": "「基于家庭场景洞察，设计影音/安防/节能等场景化产品方案」"},
        {"keyword": "0-1产品经验", "target": "所有高薪岗位", "why": "高薪JD中出现频率极高", "how": "「从0到1搭建智能家居中枢首页产品，DAU提升XX%」"},
        {"keyword": "数据驱动决策", "target": "数据/增长/策略产品", "why": "区分执行型和决策型产品经理", "how": "「建立控制率/留存/转化指标体系，驱动产品迭代决策」"},
        {"keyword": "复杂项目推进", "target": "平台/B端/大厂", "why": "体现高级产品经理的核心能力", "how": "「推动5个团队协同完成新国标合规适配，涉及XX个设备品类」"},
        {"keyword": "跨团队协同", "target": "所有中高级岗位", "why": "高薪岗位普遍要求", "how": "「协同硬件/固件/云端/前端/测试团队，统一多端控制规则」"},
        {"keyword": "用户体验重构", "target": "C端/体验/AI产品", "why": "体现产品设计深度", "how": "「重构智能家居首页体验，用户满意度提升XX%」"},
        {"keyword": "平台化思维", "target": "平台/B端/SaaS", "why": "高薪岗位核心区分项", "how": "「将设备控制能力平台化，支撑XX+品类接入」"},
        {"keyword": "业务闭环", "target": "商业化/增长/策略", "why": "体现从策略到落地的完整能力", "how": "「负责场景化产品从需求定义到上线运营的完整闭环」"},
        {"keyword": "AI产品思维", "target": "AI/大模型产品", "why": "当前最热门高薪方向", "how": "「探索AI在智能家居场景的应用，设计智能推荐/语音交互方案」"},
    ]

    # 经历改写建议
    advice["rewrites"] = [
        {"original": "负责智能家居App首页产品设计",
         "upgraded": "从0到1搭建智能家居中枢首页产品体系，覆盖设备控制、场景联动、影音娱乐三大核心模块，DAU提升XX%",
         "target": "IoT/C端/平台产品", "emphasis": "0-1经验、产品体系设计、数据结果"},
        {"original": "负责多端产品体验一致性",
         "upgraded": "主导手机/电视/音箱/车机/手表五端协同的产品架构设计，统一控制规则和交互规范，实现跨端体验一致性",
         "target": "平台产品/车载/IoT", "emphasis": "多端协同、架构设计、规则统一"},
        {"original": "参与场景化产品设计",
         "upgraded": "基于用户行为数据洞察，设计家庭影音/安防/节能等10+场景化产品方案，场景使用率提升XX%",
         "target": "C端/AI/IoT产品", "emphasis": "数据洞察、场景设计、量化结果"},
        {"original": "负责设备控制功能",
         "upgraded": "负责XX+品类智能设备的控制体验设计，建立设备控制率/响应时间/成功率指标体系，控制成功率提升至XX%",
         "target": "IoT/硬件/平台产品", "emphasis": "指标体系、体验优化、规模化"},
        {"original": "做了新国标合规适配",
         "upgraded": "主导新国标合规下的控制体系重构，协调5个团队完成XX个品类适配，项目按期交付且零合规风险",
         "target": "平台/B端/大厂", "emphasis": "复杂项目管理、跨团队协同、风险控制"},
        {"original": "做了数据分析",
         "upgraded": "建立产品核心指标体系（DAU/控制率/留存/转化），通过数据分析驱动3轮产品迭代，核心指标提升XX%",
         "target": "数据/增长/策略产品", "emphasis": "指标体系、数据驱动、迭代优化"},
        {"original": "跟进了跨团队项目",
         "upgraded": "作为产品Owner推动跨硬件/固件/云端/前端4个团队的协同开发，建立需求评审-排期-验收全流程机制",
         "target": "所有中高级岗位", "emphasis": "Owner角色、流程建设、跨团队推动"},
        {"original": "做了竞品分析",
         "upgraded": "深度拆解小米/华为/苹果三大生态的智能家居产品策略，输出差异化竞争方案并落地执行",
         "target": "C端/IoT/策略产品", "emphasis": "战略思维、竞争分析、落地执行"},
        {"original": "优化了用户体验",
         "upgraded": "基于用户调研和行为数据，重构智能家居核心交互流程，任务完成率提升XX%，用户满意度提升XX分",
         "target": "C端/体验/AI产品", "emphasis": "用户研究、体验设计、量化验证"},
        {"original": "参与了产品规划",
         "upgraded": "负责智能家居中枢产品年度规划，从市场洞察→策略制定→路线图→落地执行全链路闭环，达成年度OKR",
         "target": "所有高级岗位", "emphasis": "战略规划、闭环能力、结果导向"},
    ]

    # 项目包装方向
    advice["projects"] = [
        {"name": "智能家居中枢首页体验重构",
         "target": "IoT/C端/平台产品",
         "selling_point": "0-1产品设计 + 多端协同 + 数据驱动",
         "jd_match": "0-1经验、用户体验、数据分析、复杂系统",
         "resume_focus": "从用户痛点出发，重构首页信息架构，建立AB测试体系验证效果",
         "interview_story": "用STAR讲：发现首页跳出率高→分析用户行为数据→重新设计信息架构→DAU提升XX%"},
        {"name": "五端协同控制规则统一",
         "target": "平台产品/车载/IoT",
         "selling_point": "平台化思维 + 复杂项目管理 + 跨团队协同",
         "jd_match": "平台化、跨端协同、复杂项目、规则引擎",
         "resume_focus": "设计统一控制规则引擎，支撑5端+XX品类设备的一致性控制体验",
         "interview_story": "用STAR讲：各端控制逻辑不一致→设计统一规则引擎→协调5个团队落地→控制一致性达XX%"},
        {"name": "家庭场景化产品矩阵设计",
         "target": "C端/AI/IoT产品",
         "selling_point": "场景化思维 + 用户洞察 + 产品矩阵",
         "jd_match": "场景化、用户研究、产品规划、数据分析",
         "resume_focus": "基于家庭场景洞察设计影音/安防/节能等场景产品，建立场景使用率指标体系",
         "interview_story": "用STAR讲：发现用户使用场景碎片化→设计场景化产品矩阵→场景使用率提升XX%"},
        {"name": "新国标合规下的控制体系重构",
         "target": "平台/B端/大厂",
         "selling_point": "复杂项目治理 + 风险控制 + 跨团队推动",
         "jd_match": "复杂项目管理、合规、跨团队协同、系统重构",
         "resume_focus": "在合规约束下重构控制体系，协调多团队按期交付，零合规风险",
         "interview_story": "用STAR讲：新国标发布→评估影响范围→制定重构方案→协调5团队按期交付"},
        {"name": "智能设备数据分析与增长体系",
         "target": "数据/增长/策略产品",
         "selling_point": "数据驱动 + 指标体系 + 增长思维",
         "jd_match": "数据分析、指标体系、增长、A/B测试",
         "resume_focus": "建立设备控制率/留存/转化全链路指标体系，通过数据分析驱动产品迭代",
         "interview_story": "用STAR讲：发现控制率下降→建立监控体系→定位问题→优化后提升XX%"},
    ]

    return advice


def _build_portfolio_advice(R):
    """第12章：作品集/面试作品建议。"""
    return [
        {"direction": "AI产品方向作品集",
         "target": "AI/大模型产品经理",
         "why": "AI方向高薪占比最高（36.3%）且岗位量大（1586个），但需要证明AI产品思维",
         "structure": "1.AI在智能家居的应用场景分析 2.智能推荐/语音交互产品方案 3.AI Agent产品设计思路 4.效果评估框架",
         "proves": "AI产品思维、场景化AI应用能力、技术理解",
         "priority": "高（冲刺方向必备）"},
        {"direction": "智能硬件/IoT方向作品集",
         "target": "IoT/智能硬件产品经理",
         "why": "与背景最匹配，展示深度专业能力",
         "structure": "1.智能家居中枢产品架构 2.多端协同设计方案 3.设备控制体验优化案例 4.数据分析驱动迭代",
         "proves": "IoT产品全流程能力、系统设计、数据驱动",
         "priority": "高（主投方向核心）"},
        {"direction": "车载/智能座舱方向作品集",
         "target": "车载/智能座舱产品经理",
         "why": "多端协同经验可迁移，车载方向薪资有溢价",
         "structure": "1.从智能家居到车载的场景迁移分析 2.车内场景化产品设计 3.车家互联产品方案 4.多端协同在车载的应用",
         "proves": "场景迁移能力、多端协同、车载产品理解",
         "priority": "中高（冲刺方向加分）"},
        {"direction": "平台产品/多端协同方向作品集",
         "target": "平台产品经理",
         "why": "多端协同经验是平台产品的核心竞争力",
         "structure": "1.多端控制规则引擎设计 2.平台化架构演进 3.开放能力设计 4.复杂项目管理方法论",
         "proves": "平台化思维、系统设计、复杂项目管理",
         "priority": "中高（主投方向加分）"},
        {"direction": "数据分析/增长方向作品集",
         "target": "数据产品/增长产品经理",
         "why": "数据能力是高薪岗位的通用加分项",
         "structure": "1.指标体系设计方法论 2.数据分析驱动产品迭代案例 3.A/B测试实践 4.增长策略设计",
         "proves": "数据分析能力、指标体系、增长思维",
         "priority": "中（通用加分项）"},
        {"direction": "出海产品方向作品集",
         "target": "出海产品经理",
         "why": "智能家居有海外市场，出海方向有薪资溢价",
         "structure": "1.智能家居出海市场分析 2.本地化产品策略 3.海外用户研究方法 4.合规与隐私设计",
         "proves": "国际化视野、本地化能力、合规意识",
         "priority": "中（如有海外经验优先准备）"},
    ]


def _build_risk_analysis(R):
    """第13章：风险与误区分析。"""
    risks = [
        {"risk": "只看岗位数量，不看薪资质量",
         "danger": "岗位多的方向可能薪资一般，投入大量精力但薪资提升有限",
         "evidence": "数据显示B端/SaaS方向岗位多但薪资溢价低于AI/策略方向",
         "avoid": "同时关注岗位数量和薪资中位数/P75/高薪占比"},
        {"risk": "只看平均薪资，不看中位数和分布",
         "danger": "少数极端高薪岗位拉高平均值，实际大部分岗位薪资一般",
         "evidence": "部分方向平均薪资高但中位数普通，被少数总监级岗位拉高",
         "avoid": "优先看中位数和P75，关注高薪岗位占比"},
        {"risk": "盲目转AI产品，但没有AI项目表达",
         "danger": "AI方向竞争激烈，没有AI项目经验的简历很难通过筛选",
         "evidence": "AI方向高薪岗位要求大模型/Agent/算法理解等专业技能",
         "avoid": "先准备AI方向作品集，用现有经验+AI的交叉点切入"},
        {"risk": "把垂直行业经验写得太窄",
         "danger": "面试官认为你只能做某个细分领域，无法迁移到其他方向",
         "evidence": "高薪JD要求的是通用能力（平台化/数据驱动/复杂项目），不是具体行业",
         "avoid": "用通用语言包装垂直经验：行业专有名词→通用产品能力，如将具体业务流程抽象为平台化设计、将行业指标转化为增长/留存/转化等通用指标"},
        {"risk": "只写执行过程，不写业务判断和结果",
         "danger": "简历看起来像执行者而非决策者，无法匹配高级岗位",
         "evidence": "高薪岗位JD强调owner意识、业务判断、数据驱动决策",
         "avoid": "每段经历都要有：为什么做→怎么判断→做了什么→结果如何"},
        {"risk": "只写项目协同，不写自己的关键决策",
         "danger": "面试官无法判断你在项目中的核心贡献",
         "evidence": "高薪岗位要求独立负责、从0到1、业务闭环",
         "avoid": "明确写出自己的决策点：我发现→我判断→我推动→我达成"},
        {"risk": "用一份简历投所有岗位",
         "danger": "通用简历无法匹配任何方向的核心要求",
         "evidence": "不同方向的JD关键词差异很大，AI/IoT/平台/数据各有侧重",
         "avoid": "准备2-3份定向简历，每份突出不同方向的匹配关键词"},
        {"risk": "只补工具技能，不补业务能力",
         "danger": "学了Figma/SQL/Python但面试时讲不出业务判断",
         "evidence": "高薪岗位看重的是业务理解和产品判断力，不是工具熟练度",
         "avoid": "优先补业务能力（AI产品思维/数据分析/策略设计），工具只是辅助"},
        {"risk": "盲目投大厂，但简历关键词不匹配",
         "danger": "大厂简历筛选严格，关键词不匹配直接被过滤",
         "evidence": "大厂JD要求非常具体的方向经验和技能标签",
         "avoid": "先研究目标大厂的JD，确保简历关键词覆盖核心要求"},
        {"risk": "忽视职级包装，只写普通产品经理",
         "danger": "同样的经验，职级表达不同薪资差距巨大",
         "evidence": "数据显示资深/专家/负责人级别薪资显著高于普通级别",
         "avoid": "简历中体现负责人/owner角色，面试中展示决策能力"},
    ]
    return risks


def _build_search_keywords(R):
    """第17章：投递关键词建议。"""
    # 基于数据中实际出现的方向和薪资，生成搜索关键词建议
    keywords = {
        "main": [
            {"keyword": "IoT产品经理", "fit": "高", "direction": "智能硬件/IoT", "salary": "中高", "reason": "与背景直接匹配"},
            {"keyword": "智能硬件产品经理", "fit": "高", "direction": "智能硬件/IoT", "salary": "中高", "reason": "核心经验匹配"},
            {"keyword": "智能家居产品经理", "fit": "高", "direction": "智能硬件/IoT", "salary": "中", "reason": "完全对口但岗位较少"},
            {"keyword": "车载产品经理", "fit": "高", "direction": "车载/智能座舱", "salary": "高", "reason": "多端协同经验可迁移"},
            {"keyword": "平台产品经理", "fit": "高", "direction": "平台产品", "salary": "中高", "reason": "多端协同=平台化能力"},
            {"keyword": "C端产品经理", "fit": "高", "direction": "用户体验/C端", "salary": "中", "reason": "C端经验直接匹配"},
        ],
        "sprint": [
            {"keyword": "AI产品经理", "fit": "中", "direction": "AI/大模型产品", "salary": "高", "reason": "薪资最高但需补AI能力"},
            {"keyword": "大模型产品经理", "fit": "中", "direction": "AI/大模型产品", "salary": "高", "reason": "冲刺方向，需作品集支撑"},
            {"keyword": "策略产品经理", "fit": "中", "direction": "策略产品", "salary": "高", "reason": "场景化思维可迁移"},
            {"keyword": "商业化产品经理", "fit": "中", "direction": "商业化/广告", "salary": "高", "reason": "需补商业化知识"},
            {"keyword": "数据产品经理", "fit": "中", "direction": "数据产品", "salary": "中高", "reason": "数据分析能力可迁移"},
            {"keyword": "高级产品经理", "fit": "高", "direction": "综合", "salary": "高", "reason": "职级提升，薪资跃迁"},
            {"keyword": "产品专家", "fit": "高", "direction": "综合", "salary": "高", "reason": "专家级定位"},
        ],
        "backup": [
            {"keyword": "用户产品经理", "fit": "高", "direction": "用户体验/C端", "salary": "中", "reason": "匹配度高，机会多"},
            {"keyword": "App产品经理", "fit": "高", "direction": "用户体验/C端", "salary": "中", "reason": "C端经验直接匹配"},
            {"keyword": "体验产品经理", "fit": "高", "direction": "用户体验/C端", "salary": "中", "reason": "体验设计能力匹配"},
            {"keyword": "产品经理", "fit": "中", "direction": "综合", "salary": "中", "reason": "通用搜索，覆盖面广"},
        ],
    }
    return keywords


def _build_chart_insights(R):
    """为每个图表生成数据驱动的分析结论。"""
    insights = {}

    # 薪资分布图洞察
    dist = R.get("salary_dist", [])
    if dist:
        peak = max(dist, key=lambda x: x["count"])
        high_count = sum(d["count"] for d in dist if d["range"] in ("60-80K", "80-100K", "100K+"))
        total_valid = sum(d["count"] for d in dist)
        high_pct = round(high_count / max(total_valid, 1) * 100, 1)
        insights["salary_dist"] = (
            f"薪资集中在 {peak['range']} 区间（{peak['count']}个岗位）。"
            f"60K以上的高薪岗位共 {high_count} 个，占 {high_pct}%。"
            f"<b>求职启示：</b>大部分岗位在30-50K区间，突破50K需要在方向选择或职级上有突破。"
        )

    # 区域薪资图洞察
    areas = R.get("area_salary", [])
    if areas:
        top3 = areas[:3]
        top3_count = sum(a["count"] for a in top3)
        total_count = sum(a["count"] for a in areas)
        top3_pct = round(top3_count / max(total_count, 1) * 100, 1)
        top3_names = "、".join(f'{a["area"]}({a["count"]}个)' for a in top3)
        insights["area"] = (
            f"岗位最集中的三个区域：{top3_names}，合计占{top3_pct}%。"
            f"<b>求职启示：</b>海淀和朝阳是产品经理岗位的绝对主力区域，面试大概率在这两个区。"
            f"通州/大兴的岗位主要来自京东（总部在亦庄附近），如果不是目标京东可以忽略。"
            f"选择工作地点时，优先考虑岗位密集的区域，方便面试期间多家公司连续面。"
        )

    # 方向薪资图洞察
    dirs = R.get("direction_analysis", [])
    if dirs:
        # 按高薪占比排序找出最值得关注的方向
        by_high_pct = sorted([d for d in dirs if d["count"] >= 50], key=lambda x: -x["high_pct"])[:3]
        bot3 = [d for d in dirs if d["premium"] < -3][-3:] if len(dirs) > 3 else []
        
        # 生成精确描述，不使用"溢价最高"这种可能误导的表述
        desc_parts = []
        for d in by_high_pct:
            advantages = []
            if d.get("p75_premium", 0) > 0:
                advantages.append(f"P75溢价{d['p75_premium']:+.1f}%")
            advantages.append(f"高薪占比{d['high_pct']}%")
            desc_parts.append(f"{d['direction']}({', '.join(advantages)})")
        
        insights["direction"] = (
            f"高薪岗位最密集的方向：{'、'.join(desc_parts)}。"
            f"注意：多数方向中位数与整体持平（37.5K），差异主要体现在P75/P90和高薪占比上。"
        )
        if bot3:
            bot_names = "、".join(d["direction"] for d in bot3)
            insights["direction"] += f" 薪资偏低的方向：{bot_names}，不建议作为主攻。"
        insights["direction"] += " <b>求职启示：</b>方向选择影响的不是中位数，而是触达高薪岗位的概率。高薪占比高的方向意味着更多P75+机会。"

    # 经验×方向交叉图洞察
    cross = R.get("exp_dir_cross", [])
    if cross:
        top_cross = cross[0]
        insights["exp_dir"] = (
            f"薪资最高的组合是「{top_cross['exp']} × {top_cross['direction']}」（中位数{top_cross['median']}K）。"
            f"<b>求职启示：</b>5-10年经验在大部分方向都有明显薪资跃迁，但不同方向的跃迁幅度差异很大。"
        )

    # 高薪vs普通方向差异图洞察
    dir_diff = R.get("dir_diff", [])
    if dir_diff:
        top_diff = [d for d in dir_diff if d["ratio"] > 1.3][:3]
        if top_diff:
            names = "、".join(d["direction"] for d in top_diff)
            insights["dir_diff"] = (
                f"在高薪岗位中占比显著偏高的方向：{names}。"
                f"其中{top_diff[0]['direction']}在高薪岗中占{top_diff[0]['hs_pct']}%，普通岗中仅{top_diff[0]['nm_pct']}%。"
                f"<b>求职启示：</b>这些方向更容易出高薪，值得优先投递。"
            )

    # 职级薪资图洞察
    levels = R.get("level_salary", [])
    if len(levels) >= 2:
        top_lv = levels[0]
        mid_lv = next((l for l in levels if l["level"] == "普通"), levels[-1])
        gap = round(top_lv["median"] - mid_lv["median"], 1)
        insights["level"] = (
            f"{top_lv['level']}级别中位数{top_lv['median']}K，普通级别{mid_lv['median']}K，差距{gap}K/月。"
            f"<b>求职启示：</b>主动搜索和投递「资深/高级/专家/负责人」级别的岗位，不要只投「产品经理」。"
            f"简历中用具体数据证明你做过的事配得上这个级别：独立负责过什么业务、带过多大项目、做过哪些关键决策、取得了什么量化结果。"
        )

    # 行业薪资图洞察
    inds = R.get("industry_salary", [])
    if inds:
        top_ind = inds[0]
        insights["industry"] = (
            f"薪资最高的行业是{top_ind['industry']}（中位数{top_ind['median']}K）。"
            f"<b>求职启示：</b>同样是产品经理，行业选择可以带来10-20%的薪资差异。AI、自动驾驶、金融等行业普遍薪资更高。"
        )

    # 规模/融资薪资图洞察
    scales = R.get("scale_salary", [])
    stages = R.get("stage_salary", [])
    if scales:
        top_sc = scales[0]
        insights["scale"] = (
            f"薪资最高的公司规模是「{top_sc['scale']}」（中位数{top_sc['median']}K）。"
        )
    if stages:
        top_st = stages[0]
        insights["scale"] = insights.get("scale", "") + (
            f" 融资阶段中，「{top_st['stage']}」薪资最高（{top_st['median']}K）。"
            f"<b>求职启示：</b>上市公司和D轮+公司薪资普遍更高，但创业公司可能给更高的职级和期权。"
        )

    # 技能价值散点图洞察
    sv = R.get("skills_by_cat", {})
    high_skills = sv.get("能力/技能信号", [])[:3]
    if high_skills:
        names = "、".join(s["skill"] for s in high_skills)
        insights["skill_value"] = (
            f"高薪岗位中更常见的技能信号TOP3：{names}。"
            f"其中{high_skills[0]['skill']}的薪资溢价达{high_skills[0]['premium']:+.1f}%。"
            f"<b>求职启示：</b>这些标签反映了高薪岗位更看重的能力方向（如搜索推荐、AIGC、增长等），简历和作品集应围绕这些方向背后的能力展开。无区分度标签（如需求分析、项目管理）有则达标，不能拉开差距。"
        )

    # ── 表格洞察 ──

    # 公司TOP25表
    cos = R.get("active_companies", [])
    if cos:
        big_cos = [c for c in cos if c["co_type"] == "大厂"]
        unicorns = [c for c in cos if c["co_type"] == "独角兽"]
        high_pct_cos = sorted(cos, key=lambda x: -x["high_pct"])[:3]
        hp_names = "、".join(f'{c["company"]}({c["high_pct"]}%)' for c in high_pct_cos)
        insights["company_top25"] = (
            f"招聘最活跃的公司以大厂为主（字节{cos[0]['job_count']}个岗位领先）。"
            f"<b>高薪占比最高的公司：</b>{hp_names}——这些公司值得重点投递。"
            f"<b>求职启示：</b>岗位多不等于薪资高。关注「高薪占比」列，优先投递高薪占比>40%的公司。"
        )

    # 高薪公司TOP15表
    sal_cos = R.get("salary_companies", [])
    if sal_cos:
        top_name = sal_cos[0]["company"]
        top_med = sal_cos[0]["salary_median"]
        insights["company_salary"] = (
            f"薪资中位数最高的公司是{top_name}（{top_med}K），但注意这些公司岗位数量不一定多。"
            f"<b>求职启示：</b>冲刺目标选薪资高的公司，主投目标选岗位多+高薪占比高的公司，两者结合效果最好。"
        )

    # 方向分析表
    dirs = R.get("direction_analysis", [])
    if dirs:
        # 按综合表现分类
        # 第一类：整体薪资高 + 高薪占比高（优先投递）
        tier1 = [d for d in dirs if d["high_pct"] >= 30 and d["premium"] >= 0 and d["count"] >= 50]
        # 第二类：整体薪资一般，但天花板高（有实力可以冲）
        tier2 = [d for d in dirs if d.get("p90_premium", 0) > 0 and d["high_pct"] < 30 and d["count"] >= 20]
        # 第三类：岗位多、薪资中等（保底方向）
        tier3 = [d for d in dirs if d["count"] >= 200 and d["premium"] < 0 and d not in tier2]
        # 第四类：薪资偏低且岗位少（不建议主攻）
        tier4 = [d for d in dirs if d["premium"] < -15 or (d["count"] < 20 and d["premium"] < 0)]

        insights["direction_table"] = ""
        if tier1:
            t1_parts = []
            for d in sorted(tier1, key=lambda x: -x["high_pct"]):
                t1_parts.append(f'{d["direction"]}(高薪占比{d["high_pct"]}%，P90={d["p90"]}K)')
            t1_text = "、".join(t1_parts)
            insights["direction_table"] += f"<b>第一类：高薪机会密度高（高薪占比≥30%，值得重点关注）：</b>{t1_text}。注意：多数方向中位数与整体持平（37.5K），优势主要体现在P75+岗位更密集。<br>"
        if tier2:
            t2_parts = []
            for d in sorted(tier2, key=lambda x: -x.get("p90_premium", 0)):
                t2_parts.append(f'{d["direction"]}(中位数{d["median"]}K偏低，但P90={d["p90"]}K)')
            t2_text = "、".join(t2_parts)
            insights["direction_table"] += f"<b>第二类：中位数一般但P90天花板高（有实力可以冲）：</b>{t2_text}。少数高级岗位薪资很好，适合能力较强且有相关经验的人。<br>"
        if tier3:
            t3_parts = [f'{d["direction"]}({d["count"]}个，中位数{d["median"]}K)' for d in sorted(tier3, key=lambda x: -x["count"])]
            t3_text = "、".join(t3_parts)
            insights["direction_table"] += f"<b>第三类：岗位多但薪资中等（保底方向）：</b>{t3_text}。容易拿到面试机会，但薪资提升空间有限。<br>"
        if tier4:
            t4_names = "、".join(d["direction"] for d in tier4)
            insights["direction_table"] += f"<b>第四类：薪资偏低或岗位太少（不建议主攻）：</b>{t4_names}。"

        # 特别说明小样本高数据方向
        small_high = [d for d in dirs if d["count"] < 50 and d["high_pct"] > 30]
        if small_high:
            sh_parts = [f'{d["direction"]}(仅{d["count"]}个岗位，P90={d["p90"]}K)' for d in small_high]
            sh_text = "、".join(sh_parts)
            insights["direction_table"] += f"<br><b>⚠️ 特别说明：</b>{sh_text}表面数据很亮眼，但样本太少（<50个），少数高薪岗位就能大幅拉高P90，结论不稳定，不建议据此做方向决策。"

    # 技能差异表
    sd = R.get("skill_diff_top", [])
    if sd:
        top3 = sd[:3]
        names = "、".join(s["skill"] for s in top3)
        insights["skill_diff_table"] = (
            f"高薪岗位中出现频率显著更高的技能：{names}。"
            f"其中{top3[0]['skill']}在高薪岗中占{top3[0]['hs_pct']}%，普通岗仅{top3[0]['nm_pct']}%，差异{top3[0]['ratio']}倍。"
            f"<b>求职启示：</b>差异倍数>1.5x的标签反映高薪岗位的方向偏好，简历应围绕这些方向背后的能力展开。差异倍数接近1的只是普遍出现的标签，无区分度。"
        )

    # 高薪岗位TOP15表
    tj = R.get("top_salary_jobs", [])
    if tj:
        dir_counter = Counter(j["direction"] for j in tj)
        top_dir = dir_counter.most_common(1)[0] if dir_counter else ("", 0)
        insights["top_jobs_table"] = (
            f"薪资最高的15个岗位中，{top_dir[0]}方向占{top_dir[1]}个。"
            f"这些岗位普遍要求5-10年经验，职级多为总监/负责人/专家级别。"
            f"<b>求职启示：</b>研究这些岗位的JD关键词，确保简历覆盖其中至少3-5个核心要求。"
        )

    # 匹配分析表
    ma = R.get("match_analysis", [])
    if ma:
        sprint = [m for m in ma if "冲刺" in m["recommend"]]
        main = [m for m in ma if "主投" in m["recommend"]]
        s_names = "、".join(m["direction"] for m in sprint) if sprint else "无"
        m_names = "、".join(m["direction"] for m in main) if main else "无"
        insights["match_table"] = (
            f"基于市场数据分析：<b>冲刺方向：</b>{s_names}。<b>主投方向：</b>{m_names}。"
            f"<b>求职启示：</b>冲刺方向薪资高但需要额外准备（作品集/技能补齐），主投方向匹配度高可以直接投。建议70%精力放主投，30%放冲刺。"
        )

    return insights


def _build_chapter_conclusions(R):
    """为每章生成针对性的总结论，回答该章讨论的核心问题。"""
    cc = {}

    # ── 第4章：公司分析 → 哪些公司值得投、怎么分层 ──
    cos = R.get("active_companies", [])
    sal_cos = R.get("salary_companies", [])
    if cos:
        sprint_cos = [c for c in cos if c["high_pct"] >= 50 and c["salary_median"] >= 45]
        main_cos = [c for c in cos if c["job_count"] >= 20 and c["high_pct"] >= 25]
        backup_cos = [c for c in cos if c["job_count"] >= 30 and c["high_pct"] < 25]
        lines = ['<h3>📌 本章结论：公司投递分层</h3>']
        if sprint_cos:
            names = "、".join(c["company"] for c in sprint_cos[:5])
            lines.append(f'<p><b>冲刺公司（高薪占比≥50%）：</b>{names}。这些公司超过一半的岗位薪资在P75以上，值得重点准备。</p>')
        if main_cos:
            names = "、".join(c["company"] for c in main_cos[:5])
            lines.append(f'<p><b>主投公司（岗位≥20且高薪占比≥25%）：</b>{names}。岗位充足且薪资有竞争力，投递成功率和薪资都有保障。</p>')
        if backup_cos:
            names = "、".join(c["company"] for c in backup_cos[:5])
            lines.append(f'<p><b>保底公司（岗位多但高薪占比一般）：</b>{names}。机会多容易拿到offer，但薪资提升空间有限。</p>')
        cc["ch4"] = "\n".join(lines)

    # ── 第5章：方向分析 → 第7章已有通用方向判断，此处不再重复 ──
    # 第3章结论已删除，避免与第7章重复
    cc["ch5"] = ""

    # ── 第6章：高薪JD拆解 → 高薪岗位到底多要求了什么 ──
    sd = R.get("skill_diff_top", [])
    if sd:
        lines = ['<h3>📌 本章结论：高薪岗位的标签特征</h3>']
        strong_diff = [s for s in sd if s["ratio"] > 1.5]
        weak_diff = [s for s in sd if 1.2 < s["ratio"] <= 1.5]
        if strong_diff:
            names = "、".join(s["skill"] for s in strong_diff[:5])
            lines.append(f'<p><b>高薪岗位中显著更常见的标签（差异>1.5倍）：</b>{names}。</p>')
            lines.append('<p>⚠️ 注意：这些是岗位方向/类型标签，不是具体技能。差异倍数只能说明"高薪岗位中这些标签更常见"，不能直接解释为"拥有这些标签就能高薪"。这些标签背后可能对应的能力包括：用户增长机制设计、社区/内容分发策略、指标驱动的业务闭环、商业化变现等。简历包装应聚焦这些底层能力，而非堆砌标签。</p>')
        if weak_diff:
            names = "、".join(s["skill"] for s in weak_diff[:5])
            lines.append(f'<p><b>有一定偏向的标签（差异1.2-1.5倍）：</b>{names}。高薪岗位中略多，但区分度不强。</p>')
        # 职级结论
        lvs = R.get("level_salary", [])
        if len(lvs) >= 2:
            lines.append(f'<p><b>职级影响：</b>{lvs[0]["level"]}中位数{lvs[0]["median"]}K，{lvs[-1]["level"]}仅{lvs[-1]["median"]}K。投递时主动搜索「资深/高级/专家/负责人」级别的岗位，不要只投「产品经理」。</p>')
        cc["ch6"] = "\n".join(lines)

    # ── 第7章：高薪因子 → 可操作的能力因子为核心 ──
    factors = R.get("high_salary_factors", {})
    if factors:
        lines = ['<h3>📌 本章结论：高薪JD背后的可操作能力因子</h3>']
        lines.append('<p>高薪岗位和普通岗位的核心差异不在于背景变量（经验、职级、行业），而在于JD中体现的能力要求。以下是从高薪JD中提炼的可操作能力因子：</p>')
        lines.append('<ol style="padding-left:20px;font-size:13px;line-height:2">')
        lines.append('<li><b>业务闭环能力</b>——高薪JD要求"对核心业务目标负责""从策略到复盘"，普通JD只写"需求分析/PRD撰写"</li>')
        lines.append('<li><b>指标驱动能力</b>——高薪JD高频出现DAU/留存/转化/ROI/AB实验，普通JD仅"数据分析"</li>')
        lines.append('<li><b>策略设计能力</b>——推荐/搜索/分发/用户分层/算法协同，需要设计策略并验证效果</li>')
        lines.append('<li><b>AI应用落地能力</b>——大模型/Agent/RAG/多模态/模型效果评估，需要把AI能力落到真实业务场景</li>')
        lines.append('<li><b>复杂系统抽象能力</b>——平台化/配置化/规则引擎/权限体系，需要从具体业务中提炼通用能力</li>')
        lines.append('<li><b>Owner/负责人能力</b>——独立负责/从0到1/业务owner，需要独立判断方向并为结果负责</li>')
        lines.append('</ol>')
        lines.append('<p><b>背景变量（影响薪资但非短期可操作）：</b></p><ul style="padding-left:20px;font-size:13px">')
        lines.append('<li>经验年限：5-10年比3-5年中位数高7.5K/月，需要时间积累</li>')
        lines.append('<li>岗位方向：不同方向高薪占比差距可达20个百分点</li>')
        lines.append('<li>公司规模：上市/D轮+公司薪资普遍更高</li>')
        lines.append('</ul>')
        lines.append('<p><b>核心启示：</b>简历和面试应围绕上述6个能力因子展开，用具体项目经历证明你具备这些能力。背景变量通过选对方向和公司来优化。</p>')
        cc["ch7"] = "\n".join(lines)

    # ── 第8章：技能分析 → 必须补的技能、优先级、怎么补 ──
    sv = R.get("skills_by_cat", {})
    if sv:
        lines = ['<h3>📌 本章结论：技能补齐优先级</h3>']
        high_skills = sv.get("能力/技能信号", [])[:5]
        if high_skills:
            lines.append('<p><b>高薪岗位中更常见的技能信号（可作为简历方向参考）：</b></p><ul style="padding-left:20px;font-size:13px;line-height:2">')
            for s in high_skills:
                lines.append(f'<li>{s["skill"]}（溢价{s["premium"]:+.1f}%，高薪岗占比{s["hs_pct"]}%）</li>')
            lines.append('</ul>')
        base_skills = sv.get("无区分度标签", [])[:3]
        if base_skills:
            names = "、".join(s["skill"] for s in base_skills)
            lines.append(f'<p><b>无区分度标签：</b>{names}——普遍出现，高薪和普通岗位差别不大，简历中提一下即可。</p>')
        pack_skills = sv.get("小样本趋势词", [])[:3]
        if pack_skills:
            names = "、".join(s["skill"] for s in pack_skills)
            lines.append(f'<p><b>小样本趋势词（仅作观察）：</b>{names}——样本不足，不宜作为求职决策依据，但可关注趋势。</p>')
        cc["ch8"] = "\n".join(lines)

    return cc


# ═══════════════════════════════════════════════════════════════════════════
# 第五部分：HTML 报告生成
# ═══════════════════════════════════════════════════════════════════════════

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;background:#f0f2f5;color:#333;line-height:1.7}
.wrap{max-width:1280px;margin:0 auto;padding:24px}
.header{background:linear-gradient(135deg,#1e3a5f 0%,#2d6a9f 50%,#4a90d9 100%);color:#fff;padding:52px 44px;border-radius:16px;margin-bottom:28px;position:relative;overflow:hidden}
.header::after{content:'';position:absolute;top:-50%;right:-20%;width:60%;height:200%;background:radial-gradient(circle,rgba(255,255,255,.06) 0%,transparent 70%);pointer-events:none}
.header h1{font-size:30px;margin-bottom:8px;position:relative;z-index:1}
.header .sub{opacity:.85;font-size:13px;position:relative;z-index:1;line-height:1.8}
.toc{background:#fff;border-radius:12px;padding:24px 28px;margin-bottom:24px;box-shadow:0 2px 12px rgba(0,0,0,.06)}
.toc h2{font-size:16px;margin-bottom:12px;color:#1e3a5f}
.toc ul{list-style:none;columns:2;gap:20px}
.toc li{padding:4px 0;font-size:14px}
.toc a{color:#2d6a9f;text-decoration:none}
.toc a:hover{text-decoration:underline}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}
.kpi{background:#fff;border-radius:12px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.06)}
.kpi .val{font-size:28px;font-weight:700;color:#1e3a5f}
.kpi .lbl{font-size:12px;color:#888;margin-top:4px}
.card{background:#fff;border-radius:12px;padding:28px;margin-bottom:24px;box-shadow:0 2px 12px rgba(0,0,0,.06)}
.card h2{font-size:17px;margin-bottom:14px;padding-left:14px;border-left:4px solid #2d6a9f;line-height:1.4}
.card h3{font-size:15px;margin:18px 0 10px;color:#1e3a5f}
.card .prose{font-size:14px;line-height:2;color:#444}
.card .prose p{margin-bottom:12px}
.chart{width:100%;height:420px}
.chart-sm{width:100%;height:360px}
.chart-lg{width:100%;height:520px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #eee}
th{background:#f5f7fa;font-weight:600;color:#555;white-space:nowrap}
tr:hover{background:#f8fafc}
.tag{display:inline-block;background:#e8f0fe;color:#2d6a9f;padding:2px 10px;border-radius:12px;margin:2px;font-size:11px}
.warn-box{background:#fffbeb;border:1px solid #fcd34d;border-radius:12px;padding:18px 20px;margin-bottom:20px;font-size:14px;line-height:1.9;color:#92400e}
.insight{background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:14px;line-height:1.8}
.strategy-box{background:linear-gradient(135deg,#eff6ff,#dbeafe);border:2px solid #93c5fd;border-radius:14px;padding:28px;margin-bottom:24px}
.strategy-box h2{color:#1e40af;border-left-color:#3b82f6}
.up{color:#16a34a;font-weight:600}
.down{color:#dc2626;font-weight:600}
.note{color:#9ca3af;font-size:12px;margin-top:6px}
.footer{text-align:center;color:#9ca3af;font-size:12px;padding:24px 0;margin-top:20px}
.stars{color:#f59e0b;letter-spacing:2px}
.risk-card{background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;padding:14px 18px;margin:10px 0;font-size:13px;line-height:1.8}
.risk-card b{color:#991b1b}
.resume-card{background:#f0f9ff;border:1px solid #7dd3fc;border-radius:10px;padding:14px 18px;margin:10px 0;font-size:13px;line-height:1.8}
"""


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get_insight(R, key):
    """获取图表洞察文字，允许HTML标签。"""
    return R.get("chart_insights", {}).get(key, "")


def _get_conclusion(R, key):
    """获取章节总结论。"""
    return R.get("chapter_conclusions", {}).get(key, "")


def generate_html(R):
    """生成完整的自包含 HTML 报告，结构与 v12 Markdown 版本完全一致（0-10章）。"""
    data_json = json.dumps(R, ensure_ascii=False)
    so = R["salary_overview"]

    conclusions = _generate_conclusions(R)
    conclusions_html = "".join(f"<li>{c}</li>" for c in conclusions)

    # ── 各章节 HTML（按v12结构排列）──
    ch3_html = _render_direction_chapter(R)       # 第3章：岗位方向深度分析
    ch4_html = _render_high_salary_jd_chapter(R)  # 第4章：高薪岗位画像分析
    ch5_html = _render_high_salary_factors_chapter(R)  # 第5章：高薪差异因子与JD能力解构
    ch6_html = _render_skill_value_chapter(R)     # 第6章：技能与标签价值分析
    ch7_html = _render_direction_judgment_chapter(R)  # 第7章：通用求职方向判断
    ch8_html = _render_company_chapter(R)         # 第8章：公司与行业机会分析
    ch10_html = _render_risk_chapter(R)           # 第10章：风险与误区

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>北京产品经理深度招聘市场分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div class="header">
  <h1>📊 北京·产品经理深度招聘市场分析报告</h1>
  <p class="sub">数据来源：Boss直聘 | 分析时间：{R["date"]} | 样本量：{R["valid_count"]} 个岗位</p>
  <p class="sub">筛选条件：北京 · 3-10年经验 · 本科+ · 月薪30K+ · 全职</p>
  <p class="sub">高薪定义：月薪中位数 ≥ P75（{R["p75_threshold"]}K/月）</p>
</div>

<div class="toc">
  <h2>📑 报告目录（共11章）</h2>
  <ul>
    <li><a href="#ch0">0. 核心结论摘要</a></li>
    <li><a href="#ch1">1. 数据质量与分析口径</a></li>
    <li><a href="#ch2">2. 整体薪资结构与市场基准</a></li>
    <li><a href="#ch3">3. 岗位方向深度分析</a></li>
    <li><a href="#ch4">4. 高薪岗位画像分析</a></li>
    <li><a href="#ch5">5. 高薪差异因子与JD能力解构</a></li>
    <li><a href="#ch6">6. 技能与标签价值分析</a></li>
    <li><a href="#ch7">7. 通用求职方向判断</a></li>
    <li><a href="#ch8">8. 公司与行业机会分析</a></li>
    <li><a href="#ch9">9. 区域分布分析</a></li>
    <li><a href="#ch10">10. 风险与误区</a></li>
  </ul>
</div>

<!-- ═══ 第0章：核心结论摘要 ═══ -->
<div class="card" id="ch0">
  <h2>🎯 第0章：核心结论摘要</h2>
  <div class="insight">
    <ol style="padding-left:20px;font-size:14px;line-height:2.2">{conclusions_html}</ol>
  </div>
</div>

<!-- ═══ 第1章：数据质量与分析口径 ═══ -->
<div class="warn-box" id="ch1">
  <h2 style="font-size:16px;margin-bottom:10px">⚠️ 第1章：数据质量与分析口径</h2>
  <p><b>样本说明：</b>本报告基于 <b>{R["valid_count"]}</b> 个有效岗位样本。样本清洗后得到 {R["valid_count"]} 条有效记录（剔除月薪中位数≥100K的极端值 {R["extreme_excluded"]} 条，多为猎头发布、薪资范围虚高）。</p>
  <p><b>数据筛选条件（已在采集阶段完成）：</b></p>
  <ul style="padding-left:20px;margin:8px 0">
    <li><b>地区：</b>仅北京</li>
    <li><b>工作经验：</b>仅 3-5 年和 5-10 年</li>
    <li><b>学历：</b>仅本科及以上</li>
    <li><b>薪资：</b>最高月薪 ≥ 30K（因此低薪岗位已被排除，薪资分布整体偏高）</li>
    <li><b>岗位类型：</b>仅全职</li>
  </ul>
  <p><b>分析口径说明：</b></p>
  <ul style="padding-left:20px;margin:8px 0">
    <li>薪资取 salary_min 和 salary_max 的中位数作为月薪中位数</li>
    <li>年薪 = 月薪中位数 × 薪资月数（默认12薪，有标注的按实际）</li>
    <li>高薪定义：月薪中位数 ≥ P75（{R["p75_threshold"]}K），即筛选范围内前25%</li>
    <li>岗位方向：不依赖原始搜索关键词，根据 title + skills + description 重新聚类</li>
    <li>除高薪岗位TOP15保留原始招聘薪资格式外，其他薪资统计均按月薪中位数口径计算</li>
    <li><b>极端值处理：</b>月薪中位数≥100K的岗位（{R["extreme_excluded"]}条）仅在TOP15中展示，不参与统计计算</li>
  </ul>
  <p><b>⚠️ 数据局限性：</b></p>
  <ul style="padding-left:20px;margin:8px 0">
    <li>所有结论仅适用于「北京·3-10年·本科+·30K+·全职」细分市场，不代表市场全貌</li>
    <li>学历分布中本科占比高是筛选条件导致的，不是市场天然特征</li>
    <li>薪资分布整体偏高是因为已排除30K以下岗位</li>
    <li>仅北京数据，无法做跨城市对比</li>
    <li>JD 正文内容有限（多数仅含技能标签+福利），深度 JD 文本分析受限</li>
    <li>数据为单一时间点快照，不反映趋势变化</li>
  </ul>
</div>

<!-- ═══ KPI 概览 ═══ -->
<div class="kpi-row">
  <div class="kpi"><div class="val">{R["valid_count"]}</div><div class="lbl">有效样本数</div></div>
  <div class="kpi"><div class="val">{so["median"]}K</div><div class="lbl">薪资中位数/月</div></div>
  <div class="kpi"><div class="val">{so["p25"]}-{so["p75"]}K</div><div class="lbl">P25-P75 区间</div></div>
  <div class="kpi"><div class="val">{so["p90"]}K</div><div class="lbl">P90 薪资</div></div>
  <div class="kpi"><div class="val">{R["high_salary_count"]}</div><div class="lbl">高薪岗位（P75+）</div></div>
  <div class="kpi"><div class="val">{len(R["direction_analysis"])}</div><div class="lbl">聚类方向数</div></div>
</div>

<!-- ═══ 第2章：整体薪资结构与市场基准 ═══ -->
<div class="card" id="ch2">
  <h2>📈 第2章：整体薪资结构与市场基准</h2>
  <div class="prose">
    <p>在投简历之前，你需要先知道这个市场的"底价"和"天花板"在哪里。本章告诉你：大部分产品经理拿多少钱、什么水平算高薪、薪资主要集中在哪个区间。这些数字是后续所有分析的基准线。</p>
    <p>薪资中位数 <b>{so["median"]}K/月</b>，P25-P75 区间 {so["p25"]}-{so["p75"]}K，P90 达 {so["p90"]}K。</p>
    <p>高薪岗位（P75+）：<b>{R["high_salary_count"]}</b> 个（{R["high_salary_count"]*100//R["valid_count"]}%）。</p>
    <p>经验分布：5-10年 {next((e["value"] for e in R["exp_dist"] if e["name"]=="5-10年"), "N/A")} 个，3-5年 {next((e["value"] for e in R["exp_dist"] if e["name"]=="3-5年"), "N/A")} 个。</p>
  </div>
  <div class="grid2">
    <div id="c_salary_dist" class="chart"></div>
    <div id="c_exp_edu" class="chart"></div>
  </div>
  <div class="insight">📊 {R.get("chart_insights", {}).get("salary_dist", "")}</div>
</div>

{ch3_html}
{ch4_html}
{ch5_html}
{ch6_html}
{ch7_html}
{ch8_html}

<!-- ═══ 第9章：区域分布分析 ═══ -->
<div class="card" id="ch9">
  <h2>🏙️ 第9章：区域分布分析</h2>
  <div class="prose">
    <p>岗位集中在北京哪些区？本章帮你规划面试路线和工作地点选择。</p>
    <p class="note">区域薪资差异主要反映入驻公司类型不同（如通州/大兴以京东为主），不代表该区域工资更高。实际投递仍应优先看岗位方向、公司质量和JD匹配度。</p>
  </div>
  <div id="c_area" class="chart-lg"></div>
  <div class="insight">📊 {R.get("chart_insights", {}).get("area", "")}</div>

  <h3>📍 商圈级别分布 TOP25</h3>
  <div class="prose"><p class="note">细化到商圈，帮你了解具体哪些区域产品经理岗位最集中。柱状图为岗位数量，折线为薪资中位数。</p></div>
  <div id="c_biz_area" class="chart-lg"></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>商圈</th><th>岗位数</th><th>中位数</th><th>P75</th></tr></thead>
    <tbody>{"".join(f'<tr><td>{b["biz_area"]}</td><td>{b["count"]}</td><td>{b["median"]}K</td><td>{b["p75"]}K</td></tr>' for b in R.get("biz_area_salary", []))}</tbody>
  </table>
  </div>
  <div class="insight">📊 <b>商圈分布结论：</b><br>
• <b>岗位最密集但薪资偏低：</b>望京（444个）岗位最多，但中位数仅32.5K，低于整体水平（35K），说明望京以中等薪资的互联网中厂为主，面试机会多但薪资竞争力一般。<br>
• <b>薪资较高且岗位充足：</b>海淀·学院路/苏州桥（中位数37.5K，P75达45K）和大兴·亦庄（37.5K）兼具薪资和机会，是"既能拿到面试又有薪资上限"的区域。<br>
• <b>上地-西二旗：</b>岗位量大（355+54个）且薪资适中（35K），大厂集中，适合冲大厂的求职者重点关注。<br>
• <b>单一公司主导需谨慎：</b>通州·马驹桥中位数40K看似最高，但91%岗位来自京东系，反映的是京东薪资水平而非区域市场特征。<br>
• <b>薪资偏低区域：</b>酒仙桥（30K）、高碑店（30K）、花乡（27.5K）中位数低于整体水平，投递时需关注具体JD质量。</div>
</div>

{ch10_html}

<div class="footer">
  报告由 Boss直聘数据分析系统自动生成 | {R["date"]} | 样本量 {R["valid_count"]} 条<br>
  数据仅适用于「北京·3-10年·本科+·30K+·全职」细分市场，不代表市场全貌，不构成职业建议
</div>

</div>
<script>
const D = {data_json};
const OM = D.overall_median;
const P75 = D.p75_threshold;
const blue = '#2d6a9f';
const green = '#16a34a';
const red = '#dc2626';
const orange = '#f59e0b';
const teal = '#0d9488';
const purple = '#7c3aed';
function initChart(id) {{
  const el = document.getElementById(id);
  if (!el) return null;
  return echarts.init(el);
}}
'''
    html += _generate_charts_js()
    html += "\n</script>\n</body>\n</html>"
    return html


# ═══════════════════════════════════════════════════════════════════════════
# 各章节 HTML 渲染函数
# ═══════════════════════════════════════════════════════════════════════════

def _render_company_chapter(R):
    """第8章：公司与行业机会分析。"""
    # 按岗位数排序的表格
    co_rows = ""
    for c in R.get("active_companies", []):
        co_rows += (
            f'<tr><td><b>{_esc(c["company"])}</b></td><td>{c["job_count"]}</td>'
            f'<td>{c["salary_median"]}K</td><td>{c["salary_p75"]}K</td><td>{c["salary_p90"]}K</td>'
            f'<td>{c["high_pct"]}%</td><td>{_esc(c["industry"])}</td>'
            f'<td>{_esc(c["co_type"])}</td><td>{_esc(c["main_dirs"])}</td></tr>'
        )
    # 按薪资排序的表格
    sal_rows = ""
    for c in R.get("salary_companies", []):
        sal_rows += (
            f'<tr><td><b>{_esc(c["company"])}</b></td><td>{c["salary_median"]}K</td>'
            f'<td>{c["salary_p75"]}K</td><td>{c["high_pct"]}%</td>'
            f'<td>{c["job_count"]}</td><td>{_esc(c["co_type"])}</td>'
            f'<td>{_esc(c["main_dirs"])}</td></tr>'
        )

    return f'''
<div class="card" id="ch8">
  <h2>🏢 第8章：公司与行业机会分析</h2>
  <div class="prose">
    <p>方向选好了，具体投哪些公司？本章列出招聘最活跃和薪资最高的公司，帮你缩小投递范围。注意：公司榜单是辅助参考，不应替代方向和JD质量判断。</p>
    <p class="note">部分公司名称为脱敏名称，公司类型来自原始字段或规则识别。</p>
  </div>

  <h3>📊 招聘活跃公司 TOP25（按岗位数量）</h3>
  <div class="prose"><p class="note">岗位多≠薪资高。关注高薪占比列，判断该公司是否值得重点投递。</p></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>公司</th><th>岗位数</th><th>中位数</th><th>P75</th><th>P90</th><th>高薪占比</th><th>行业</th><th>公司类型</th><th>主要方向</th></tr></thead>
    <tbody>{co_rows}</tbody>
  </table>
  </div>
  <div class="insight">📊 {_get_insight(R, "company_top25")}</div>

  <h3>💰 高薪公司 TOP15（按薪资中位数，≥5个岗位）</h3>
  <div class="prose"><p class="note">仅展示至少有5个岗位的公司，避免小样本偏差。</p></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>公司</th><th>中位数</th><th>P75</th><th>高薪占比</th><th>岗位数</th><th>公司类型</th><th>主要方向</th></tr></thead>
    <tbody>{sal_rows}</tbody>
  </table>
  </div>
  <div class="warn-box" style="margin:12px 0;padding:12px 16px;font-size:13px">
⚠️ <b>注意：</b>高薪公司TOP15中大部分为脱敏名称（"某大型互联网公司"），且几乎全部由猎头发布。这些公司名称无法验证真实雇主，薪资也可能存在虚标。建议求职者重点参考上方"招聘活跃公司TOP25"中的真实公司名，高薪榜单仅作为市场上限的参考观察。
</div>
  <div class="insight">📊 {_get_insight(R, "company_salary")}</div>

  <div id="c_scale_stage" class="chart"></div>
  <div class="insight">📊 {_get_insight(R, "scale")}</div>

  {_get_conclusion(R, "ch8")}
</div>'''


def _render_direction_chapter(R):
    """第3章：岗位方向深度分析。"""
    dir_rows = ""
    for da in R["direction_analysis"]:
        skills_html = " ".join(f'<span class="tag">{_esc(s)}</span>' for s in da["top_skills"][:3])
        cls = "up" if da["premium"] > 0 else "down" if da["premium"] < -5 else ""
        # 样本可信度
        if da["count"] >= 100:
            credibility = "较高"
        elif da["count"] >= 50:
            credibility = "中等"
        elif da["count"] >= 20:
            credibility = "谨慎"
        else:
            credibility = "小样本"
        p75_cls = "up" if da.get("p75_premium", 0) > 0 else "down" if da.get("p75_premium", 0) < -5 else ""
        p90_cls = "up" if da.get("p90_premium", 0) > 0 else "down" if da.get("p90_premium", 0) < -5 else ""
        dir_rows += (
            f'<tr><td><b>{_esc(da["direction"])}</b></td><td>{da["count"]}</td><td>{da["pct"]}%</td>'
            f'<td>{da["median"]}K</td><td>{da["p75"]}K</td><td>{da["p90"]}K</td>'
            f'<td class="{cls}">{da["premium"]:+.1f}%</td>'
            f'<td class="{p75_cls}">{da.get("p75_premium", 0):+.1f}%</td>'
            f'<td class="{p90_cls}">{da.get("p90_premium", 0):+.1f}%</td>'
            f'<td>{da["high_pct"]}%</td>'
            f'<td>{credibility}</td>'
            f'<td>{skills_html}</td></tr>'
        )
    return f'''
<div class="card" id="ch3">
  <h2>🧭 第3章：岗位方向深度分析</h2>
  <div class="prose">
    <p>产品经理不是一个方向，而是十几个方向。AI产品、策略产品、B端产品、金融产品……虽然多数方向中位数接近（集中在32.5-37.5K），但不同方向的高薪岗位密度（P75+占比）差异显著——从17%到38%不等。本章帮你看清：哪些方向高薪机会多、哪些方向岗位量大、哪些方向值得重点关注。</p>
    <p><i>注：JD高频标签来自岗位标题、skills和description字段，反映该方向的常见标签，不等同于能力要求。</i></p>
    <p>以下方向基于 title + skills + description 重新聚类，不依赖原始搜索关键词。
    <b>溢价</b>列表示该方向中位数相对整体中位数的偏离程度。
    <b>高薪占比</b>表示该方向中P75+岗位的比例。</p>
    <p><b>样本可信度规则：</b>≥100较高可信，50-99中等可信，20-49谨慎观察，&lt;20小样本仅作观察。</p>
  </div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>方向</th><th>岗位数</th><th>占比</th><th>中位数</th><th>P75</th><th>P90</th><th>中位数溢价</th><th>P75溢价</th><th>P90溢价</th><th>高薪占比</th><th>样本可信度</th><th>JD高频标签</th></tr></thead>
    <tbody>{dir_rows}</tbody>
  </table>
  </div>
  <div class="insight">📊 {_get_insight(R, "direction_table")}</div>
  <div id="c_direction" class="chart"></div>
  <div class="insight">📊 {_get_insight(R, "direction")}</div>

  {_get_conclusion(R, "ch5")}
</div>'''


def _render_direction_judgment_chapter(R):
    """第7章：通用求职方向判断。"""
    dirs = R.get("direction_analysis", [])
    if not dirs:
        return ""

    # 基于当前数据特征重新分类：
    # 第一类：稳定高薪方向（高薪占比>=35% 且 样本>=100，或 P75有正溢价 且 样本>=50）
    stable_high = [d for d in dirs if (d["high_pct"] >= 35 and d["count"] >= 100) or (d.get("p75_premium", 0) > 0 and d["count"] >= 50)]
    # 第二类：高薪机会充足但无中位数溢价（高薪占比>=28% 且 中位数溢价>=0 且 P75溢价<=0 且 样本>=100）
    opportunity_pool = [d for d in dirs if d["high_pct"] >= 28 and d["premium"] >= 0 and d.get("p75_premium", 0) <= 0 and d["count"] >= 100]
    # 第三类：小样本高上限（样本<50 且 高薪占比>30%）
    small_high = [d for d in dirs if d["count"] < 50 and d["high_pct"] > 30]
    # 第三b类：天花板高但中位数一般（P90溢价>0 且 中位数溢价<0 且 样本>=50）
    high_ceiling = [d for d in dirs if d.get("p90_premium", 0) > 0 and d["premium"] < 0 and d["count"] >= 50]
    # 第四类：岗位多但薪资一般（样本>=50 且 中位数溢价<0）
    many_low = [d for d in dirs if d["count"] >= 50 and d["premium"] < 0]
    # 第五类：不建议主攻（溢价<-20% 或 样本<20）
    avoid = [d for d in dirs if d["premium"] < -20 or d["count"] < 20]

    # Remove duplicates across categories (priority order)
    used = set()
    def _filter(items):
        result = []
        for d in items:
            if d["direction"] not in used:
                result.append(d)
                used.add(d["direction"])
        return result

    stable_high = _filter(stable_high)
    opportunity_pool = _filter(opportunity_pool)
    small_high = _filter(small_high)
    high_ceiling = _filter(high_ceiling)
    many_low = _filter(many_low)
    avoid = _filter(avoid)

    def _cat_table(items, suit_text):
        if not items:
            return "<p>暂无符合条件的方向。</p>"
        rows = ""
        for d in items:
            evidence = f"溢价{d['premium']:+.1f}%，样本{d['count']}个"
            rows += (
                f'<tr><td><b>{_esc(d["direction"])}</b></td><td>{d["count"]}</td>'
                f'<td>{d["median"]}K</td><td>{d["high_pct"]}%</td>'
                f'<td>{d["premium"]:+.1f}%</td><td>{evidence}</td>'
                f'<td>{suit_text}</td></tr>'
            )
        return f'''<table>
            <thead><tr><th>方向</th><th>岗位数</th><th>中位数</th><th>高薪占比</th><th>溢价</th><th>数据依据</th><th>适合什么求职者</th></tr></thead>
            <tbody>{rows}</tbody></table>'''

    return f'''
<div class="card" id="ch7">
  <h2>🧭 第7章：通用求职方向判断</h2>
  <div class="prose">
    <p>前面分析了方向、薪资、能力、标签，信息量很大。本章把所有数据综合起来，直接给出结论：哪些方向值得冲、哪些适合保底、哪些不建议投。</p>
    <p>基于高薪占比、P75溢价、岗位数量、样本可信度等数据，将方向分为五类，帮助求职者快速判断投递优先级。</p>
  </div>

  <h3>⭐ 稳定高薪方向（高薪占比≥35%且样本充足，或P75有正溢价）</h3>
  <div class="prose"><p class="note">高薪岗位占比高、样本充足，是最值得重点投递的方向。注意：中位数可能与整体持平，优势体现在P75/P90更高或高薪岗位更密集。</p></div>
  {_cat_table(stable_high, "有相关经验或愿意投入准备的求职者")}

  <h3>📊 高薪机会充足但中位数无溢价（高薪占比≥28%，中位数=整体水平）</h3>
  <div class="prose"><p class="note">高薪岗位占比不低，但整体薪资与市场持平。适合有对应背景的候选人精准投递高薪岗位，不适合作为"薪资一定更高"的判断依据。部分方向（如金融）有行业壁垒，跨行需谨慎。</p></div>
  {_cat_table(opportunity_pool, "有对应行业/方向经验的求职者，需精准筛选JD")}

  <h3>🔍 小样本高上限方向（岗位<50，高薪占比>30%）</h3>
  <div class="prose"><p class="note">数据显示高薪占比不错，但样本少，容易被少数极端岗位拉高，结论不够稳定。仅适合恰好有匹配经验的候选人精准看JD，不建议作为大众转型方向。</p></div>
  {_cat_table(small_high, "恰好有匹配经验的求职者，不建议专门转型")}

  <h3>📈 天花板高但中位数一般（P90有正溢价，中位数偏低）</h3>
  <div class="prose"><p class="note">中位数低于整体，但P90薪资高于整体——说明少数高级岗位薪资很好，但大部分岗位薪资一般。适合能力较强且有相关经验的候选人冲击高级岗位。</p></div>
  {_cat_table(high_ceiling, "能力较强且有相关经验的候选人，目标高级/专家岗位")}

  <h3>📦 岗位多但薪资一般方向（岗位≥50，中位数溢价<0）</h3>
  <div class="prose"><p class="note">投递机会多，容易拿到面试，但薪资提升空间有限。适合保底或有相关背景者的机会池。</p></div>
  {_cat_table(many_low, "需要快速拿到offer或有对应经验的求职者")}

  <h3>❌ 不建议主攻方向（溢价<-20%或岗位<20）</h3>
  <div class="prose"><p class="note">薪资明显偏低或岗位太少，投入产出比不高。有强行业背景者除外。</p></div>
  {_cat_table(avoid, "有强行业背景者除外")}
</div>'''


def _render_high_salary_jd_chapter(R):
    """第4章：高薪岗位画像分析。"""
    skill_diff_rows = ""
    for s in R.get("skill_diff_top", [])[:15]:
        if s["ratio"] > 1.5:
            diff_label = "强"
            cls = "up"
        elif s["ratio"] > 1.2:
            diff_label = "中"
            cls = ""
        else:
            diff_label = "弱"
            cls = ""
        skill_diff_rows += (
            f'<tr><td>{_esc(s["skill"])}</td>'
            f'<td>{s["hs_pct"]}%</td><td>{s["nm_pct"]}%</td>'
            f'<td class="{cls}">{s["ratio"]}x</td>'
            f'<td>{diff_label}</td></tr>'
        )
    top_rows = ""
    for j in R.get("top_salary_jobs", []):
        skills_html = " ".join(f'<span class="tag">{_esc(s)}</span>' for s in j.get("skills", []))
        source_cls = "down" if j.get("source") == "猎头" else ""
        top_rows += (
            f'<tr><td>{_esc(j["title"])}</td><td>{_esc(j["company"])}</td>'
            f'<td><b>{_esc(j["salary_desc"])}</b></td><td>{_esc(j["exp"])}</td>'
            f'<td>{_esc(j["direction"])}</td><td class="{source_cls}">{j.get("source", "")}</td></tr>'
        )
    return f'''
<div class="card" id="ch4">
  <h2>💎 第4章：高薪岗位画像分析</h2>
  <div class="prose">
    <p>知道了哪些方向薪资高，接下来要看：高薪岗位到底长什么样？是什么职级、什么行业、什么标签？本章拆解高薪岗位的共同特征，帮你判断自己离高薪还差什么。</p>
    <p>高薪定义：月薪中位数 ≥ {R["p75_threshold"]}K（P75），共 {R["high_salary_count"]} 个岗位。</p>
  </div>

  <h3>📊 高薪岗位更常见的方向/岗位标签</h3>
  <div class="prose"><p class="note"><b>如何阅读此表：</b>「差异倍数」= 高薪岗占比 ÷ 普通岗占比，反映该标签在高薪岗位中是否更集中。「区分度」基于差异倍数判定：强（>1.5x，高薪岗位显著更常见）、中（1.2-1.5x，有一定偏向）、弱（<1.2x，高薪和普通岗位差别不大）。</p></div>
  <table>
    <thead><tr><th>方向/标签</th><th>高薪岗占比</th><th>普通岗占比</th><th>差异倍数</th><th>区分度</th></tr></thead>
    <tbody>{skill_diff_rows}</tbody>
  </table>
  <div class="insight">📊 注意：以上是岗位方向标签，不是具体技能。高薪岗位背后真正有区分度的是：业务闭环、指标驱动、策略设计、复杂系统抽象、AI应用落地、商业化变现和Owner能力。</div>

  <h3>📊 职级 × 薪资</h3>
  <div id="c_level_salary" class="chart-sm"></div>
  <div class="prose"><p class="note">职级是影响薪资的重要背景变量，但"职级越高薪资越高"本身不是可操作的求职洞察。后文（第5章）进一步分析同经验、同方向下，高薪JD更强调什么能力。</p></div>
  <div class="insight">📊 {_get_insight(R, "level")}</div>

  <h3>📊 行业 × 薪资 TOP15</h3>
  <div id="c_industry" class="chart"></div>
  <div class="prose"><p class="note">行业是辅助观察维度，不应替代岗位方向判断。行业样本少时不应过度解读。</p></div>
  <div class="insight">📊 {_get_insight(R, "industry")}</div>

  <h3>🔥 高薪岗位 TOP15</h3>
  <div class="warn-box" style="margin:12px 0;padding:12px 16px;font-size:13px">
⚠️ <b>风险提示：</b>TOP15主要用于观察极端高薪岗位画像（多为总监/负责人/VP级别），不适合作为普通求职者薪资预期。普通求职者应优先参考中位数（{R["salary_overview"]["median"]}K）、P75（{R["p75_threshold"]}K）、P90（{R["salary_overview"]["p90"]}K）和各方向高薪占比。
</div>
  <div class="prose"><p class="note">薪资口径说明：TOP15保留招聘网站原始薪资格式，未统一折算为月薪中位数，因此不能与前文方向中位数直接横向比较。</p></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>岗位</th><th>公司</th><th>薪资</th><th>经验</th><th>方向</th><th>来源</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
  </div>
  <div class="warn-box" style="margin:12px 0;padding:12px 16px;font-size:13px">
⚠️ <b>关于"猎头"来源的说明：</b>TOP15中大部分岗位由猎头发布。猎头岗位有以下特点需注意：<br>
① 薪资范围通常偏宽（如100-200K），实际offer可能在区间中下段；<br>
② 部分猎头为吸引候选人投递，可能虚标高价；<br>
③ 公司名称多为脱敏处理（"某大型互联网公司"），无法验证真实雇主；<br>
④ 这些岗位多为总监/负责人/VP级别，不代表普通产品经理的薪资水平。<br>
<b>建议：</b>普通求职者参考薪资时，应优先看前文的中位数（{R["salary_overview"]["median"]}K）和P75（{R["p75_threshold"]}K），而非TOP15的极端值。
</div>

  {_get_conclusion(R, "ch6")}
</div>'''


def _render_high_salary_factors_chapter(R):
    """第5章：高薪差异因子与JD能力解构。"""
    factors = R.get("high_salary_factors", {})

    # 经验因素
    exp_rows = ""
    for e in factors.get("exp_factor", []):
        exp_rows += f'<tr><td>{e["exp"]}</td><td>{e["count"]}</td><td>{e["median"]}K</td><td>{e["p75"]}K</td><td>{e["p90"]}K</td></tr>'

    # 方向×经验溢价
    dep_rows = ""
    for d in factors.get("dir_exp_premium", [])[:10]:
        cls = "up" if d["premium"] > 15 else ""
        dir_label = d["direction"]
        if d["count_35"] + d["count_510"] < 30:
            dir_label += " ⚠️仅作观察"
        dep_rows += (
            f'<tr><td>{_esc(dir_label)}</td><td>{d["median_35"]}K</td><td>{d["median_510"]}K</td>'
            f'<td class="{cls}">{d["premium"]:+.1f}%</td><td>{d["count_35"]}/{d["count_510"]}</td></tr>'
        )

    return f'''
<div class="card" id="ch5">
  <h2>🔍 第5章：高薪差异因子与JD能力解构</h2>
  <div class="prose">
    <p>高薪岗位和普通岗位的JD到底有什么不同？不是"职级高所以薪资高"这种废话，而是同样5-10年经验，为什么有人拿45K有人拿65K。本章拆解高薪JD背后真正考察的能力，告诉你怎么证明自己具备这些能力。</p>
  </div>

  <h3>5.1 背景变量：经验、职级、方向</h3>
  <h4>经验因素</h4>
  <table>
    <thead><tr><th>经验</th><th>样本</th><th>中位数</th><th>P75</th><th>P90</th></tr></thead>
    <tbody>{exp_rows}</tbody>
  </table>

  <h4>经验 × 方向交叉薪资</h4>
  <div class="prose"><p class="note">同一方向下，5-10年比3-5年薪资高多少？溢价越高说明该方向越看重经验积累。样本较充足方向和小样本观察方向分开展示。</p></div>
  <table>
    <thead><tr><th>方向</th><th>3-5年中位数</th><th>5-10年中位数</th><th>经验溢价</th><th>样本(3-5/5-10)</th></tr></thead>
    <tbody>{dep_rows}</tbody>
  </table>
  <div id="c_exp_dir" class="chart-lg"></div>

  <h3>5.2 高薪JD vs 普通JD的能力差异</h3>
  <div class="prose"><p class="note"><i>以下基于JD文本和统计结果的趋势判断，不是确定性因果结论。</i></p></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>能力因子</th><th>高薪JD常见表述</th><th>普通JD常见表述</th><th>背后考察</th><th>对应方向</th><th>求职者如何证明</th></tr></thead>
    <tbody>
      <tr><td><b>业务闭环</b></td><td>负责核心业务目标、从策略到复盘、对指标结果负责</td><td>负责需求分析、PRD撰写、项目推进</td><td>是否能对业务结果负责</td><td>所有高薪方向</td><td>写清问题判断→关键决策→落地结果→指标变化</td></tr>
      <tr><td><b>指标驱动</b></td><td>DAU/留存/转化/ROI/GMV、AB实验、指标体系</td><td>数据分析、数据监控</td><td>是否能用指标判断产品价值</td><td>策略/增长/商业化</td><td>准备完整的数据复盘案例</td></tr>
      <tr><td><b>策略设计</b></td><td>推荐策略/搜索排序/分发/用户分层/算法协同</td><td>功能设计、需求管理</td><td>是否能设计策略并验证效果</td><td>策略/AI/增长</td><td>展示策略设计→AB验证→效果迭代的完整链路</td></tr>
      <tr><td><b>商业化变现</b></td><td>ROI/eCPM/转化漏斗/投放/变现/商业闭环</td><td>活动策划、运营支持</td><td>是否理解商业模式并能平衡体验和收入</td><td>商业化/广告</td><td>展示变现策略设计和ROI优化案例</td></tr>
      <tr><td><b>AI应用落地</b></td><td>大模型/Agent/RAG/多模态/模型效果评估/场景落地</td><td>了解AI、使用AI工具</td><td>是否能把AI能力落到真实业务场景</td><td>AI/大模型</td><td>用作品集展示AI解决真实业务问题</td></tr>
      <tr><td><b>复杂系统抽象</b></td><td>平台化/配置化/规则引擎/权限体系/开放能力</td><td>后台管理、需求配置、流程优化</td><td>是否能把复杂业务抽象成可复用能力</td><td>平台/B端/IoT</td><td>说明如何把复杂流程抽象成平台能力</td></tr>
      <tr><td><b>跨团队复杂项目</b></td><td>5+团队协同/多利益方/复杂约束/按期交付</td><td>协调研发、跟进上线</td><td>是否能在复杂环境中推动大型项目</td><td>平台/B端/IoT/车载</td><td>展示多团队协同的具体案例和交付结果</td></tr>
      <tr><td><b>Owner/负责人</b></td><td>独立负责/从0到1/业务owner/产品负责人</td><td>参与项目、配合团队</td><td>是否能独立判断方向并为结果负责</td><td>所有高薪方向</td><td>写清独立负责的范围、决策和结果</td></tr>
    </tbody>
  </table>
  </div>

  <h4>上述能力因子的证据强度与补齐建议</h4>
  <div class="prose"><p class="note">上面列了8个能力因子，但哪些是真的重要、哪些只是我们的推测？下表回答两个问题：① 这个结论有多靠谱（证据强度）；② 如果你现在不具备，能不能短期补上。</p></div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>高薪因子</th><th>证据来源</th><th>证据强度</th><th>主要出现方向</th><th>是否适合短期补齐</th><th>说明</th></tr></thead>
    <tbody>
      <tr><td><b>指标驱动</b></td><td>方向薪资+JD标签</td><td>高</td><td>增长/策略/AI/商业化</td><td>是（通过项目复盘）</td><td>准备2-3个数据驱动决策案例</td></tr>
      <tr><td><b>AI应用落地</b></td><td>方向岗位量+高薪占比</td><td>高</td><td>AI/大模型</td><td>部分（通过作品集）</td><td>需要理解大模型能力边界</td></tr>
      <tr><td><b>商业化变现</b></td><td>方向溢价</td><td>中高</td><td>商业化/广告</td><td>部分（需真实业务经验）</td><td>从营销平台切入门槛较低</td></tr>
      <tr><td><b>策略设计</b></td><td>方向高薪占比</td><td>高</td><td>策略/增长</td><td>是（补AB实验方法论）</td><td>2-3周可入门</td></tr>
      <tr><td><b>复杂系统抽象</b></td><td>平台产品P75/P90</td><td>中</td><td>平台/B端</td><td>需要真实项目</td><td>适合有复杂系统经验的人</td></tr>
      <tr><td><b>业务闭环</b></td><td>高薪JD通用要求</td><td>高</td><td>所有方向</td><td>是（改写简历表达）</td><td>每段经历写清决策和结果</td></tr>
      <tr><td><b>Owner能力</b></td><td>职级薪资差异</td><td>高</td><td>所有方向</td><td>部分（需真实负责经历）</td><td>投递高级别岗位+简历体现</td></tr>
      <tr><td><b>行业壁垒</b></td><td>金融方向溢价</td><td>中高</td><td>金融</td><td>否（短期难补）</td><td>有行业背景者可投</td></tr>
    </tbody>
  </table>
  </div>

  <h3>5.3 高薪JD识别规则</h3>
  <h4>值得优先投的JD信号</h4>
  <table>
    <thead><tr><th>JD信号</th><th>代表什么能力</th><th>适合投递的候选人</th><th>是否值得优先投</th></tr></thead>
    <tbody>
      <tr><td>负责核心业务/核心模块/owner</td><td>业务闭环+Owner</td><td>有独立负责经历的人</td><td>是</td></tr>
      <tr><td>对DAU/留存/转化/ROI/GMV负责</td><td>指标驱动</td><td>有数据分析和指标体系经验的人</td><td>是</td></tr>
      <tr><td>推荐/搜索/分发/策略/AB实验</td><td>策略设计</td><td>有策略或算法协同经验的人</td><td>是</td></tr>
      <tr><td>大模型/Agent/RAG/多模态/模型评估</td><td>AI应用落地</td><td>有AI应用或场景化产品经验的人</td><td>是</td></tr>
      <tr><td>平台化/规则引擎/配置化/开放能力</td><td>复杂系统抽象</td><td>有平台或复杂系统设计经验的人</td><td>是</td></tr>
    </tbody>
  </table>
  <h4>需要谨慎的低价值JD信号</h4>
  <table>
    <thead><tr><th>JD信号</th><th>风险</th><th>为什么谨慎</th></tr></thead>
    <tbody>
      <tr><td>只写PRD/协调研发/跟进上线</td><td>纯执行岗</td><td>薪资天花板低，无业务判断权</td></tr>
      <tr><td>活动配置/运营支持/后台维护</td><td>运营岗而非产品岗</td><td>做活动策划而非产品设计</td></tr>
      <tr><td>客户资源/销售支持</td><td>销售支持岗</td><td>核心是客户关系而非产品能力</td></tr>
      <tr><td>过度强调供应链/结构/生产制造</td><td>硬件工程岗</td><td>考察供应链管理而非产品设计</td></tr>
    </tbody>
  </table>

  <h3>5.4 控制变量说明</h3>
  <div class="prose">
    <p>以上高薪因子分析不能简单把"职级高、经验长"当成能力。更有价值的比较是：</p>
    <ul style="padding-left:20px">
      <li>同经验段下，高薪JD和普通JD的差异；</li>
      <li>同方向下，高薪JD和普通JD的差异；</li>
      <li>非总监/负责人岗位中，高薪JD和普通JD的差异。</li>
    </ul>
    <p>当前数据JD正文内容有限（多数仅含技能标签+福利），上述能力因子分析基于JD文本和统计结果的趋势判断，不是确定性因果结论。</p>
  </div>

  {_get_conclusion(R, "ch7")}
</div>'''


def _render_skill_value_chapter(R):
    """第6章：技能与标签价值分析。"""
    cat_labels = {"方向标签": "🎯", "能力/技能信号": "💰", "小样本趋势词": "🔍", "无区分度标签": "🔧"}
    skill_cat_html = ""
    for cat, icon in cat_labels.items():
        items = R["skills_by_cat"].get(cat, [])[:10]
        if not items:
            continue
        # Filter out "产品总监" (job level, not a skill)
        items = [s for s in items if s["skill"] != "产品总监"]
        rows = ""
        for s in items:
            # Evidence level based on sample size
            if s["count"] >= 50:
                evidence = "A"
                sample_label = "高可信"
            elif s["count"] >= 20:
                evidence = "B"
                sample_label = "中等"
            else:
                evidence = "C/D"
                sample_label = "小样本"
            # Annotate "iaa"
            skill_name = s["skill"]
            if skill_name.lower() == "iaa":
                skill_name = "iaa（应用内广告）"
            rows += (
                f'<tr><td>{_esc(skill_name)}</td><td>{s["count"]}</td>'
                f'<td>{s["median"]}K</td><td>{s["premium"]:+.1f}%</td>'
                f'<td>{s["hs_pct"]}%</td><td>{s["nm_pct"]}%</td><td>{s["ratio"]}x</td>'
                f'<td>{evidence}（{sample_label}）</td></tr>'
            )
        desc = {
            "方向标签": "反映岗位方向，不等同于技能。出现频率高只说明该方向岗位多，不能作为能力判断依据。",
            "能力/技能信号": "在高薪岗位中明显更常见的标签/技能信号。差异倍数反映相关性而非因果，但可作为简历和作品集的方向参考。",
            "小样本趋势词": "样本<20，仅作趋势观察，不宜单独下结论或作为求职决策依据。",
            "无区分度标签": "普遍出现，高薪和普通岗位差别不大，不能拉开差距。确保简历覆盖即可。",
        }
        skill_cat_html += f"""
        <h3>{icon} {cat}</h3>
        <p style="font-size:13px;color:#666;margin-bottom:8px">{desc.get(cat, "")}</p>
        <table><thead><tr><th>技能</th><th>样本</th><th>中位数</th><th>溢价</th><th>高薪岗占比</th><th>普通岗占比</th><th>差异倍数</th><th>证据等级</th></tr></thead>
        <tbody>{rows}</tbody></table>"""

    return f'''
<div class="card" id="ch6">
  <h2>🛠️ 第6章：技能与标签价值分析</h2>
  <div class="prose">
    <p>JD里经常出现各种技能标签，但哪些标签真的和高薪相关？哪些只是"写了但没用"？本章从{R["valid_count"]}个岗位的技能标签中，筛选出对薪资有实际影响的标签，帮你判断简历里该重点写什么、学什么优先级更高。</p>
    <p>按对薪资的影响程度分为四类：</p>
    <ul style="padding-left:20px">
      <li><b>方向标签：</b>反映岗位方向，不等同于技能——不能作为能力判断依据</li>
      <li><b>能力/技能信号：</b>在高薪岗位中出现频率明显更高——可作为简历和作品集的方向参考</li>
      <li><b>小样本趋势词：</b>样本<20，仅作趋势观察——不宜单独下结论</li>
      <li><b>无区分度标签：</b>普遍出现，高薪和普通岗位差别不大——确保简历覆盖即可</li>
    </ul>
    <p style="margin-top:12px"><b>证据等级说明：</b>基于样本量判定结论可信度。A=样本≥100（结论稳定可信）；B=50-99（中等可信）；C=20-49（趋势信号，需谨慎）；D=<20（小样本，仅作观察，不宜作为决策依据）。</p>
  </div>
  {skill_cat_html}

  {_get_conclusion(R, "ch6")}
</div>'''
    match_rows = ""
    for ma in R.get("match_analysis", []):
        adv = "、".join(ma["advantages"][:2]) if ma["advantages"] else "-"
        gap = "、".join(ma["gaps"][:2]) if ma["gaps"] else "-"
        match_rows += (
            f'<tr><td><b>{_esc(ma["direction"])}</b></td>'
            f'<td class="stars">{ma["match_stars"]}</td>'
            f'<td>{ma["salary_potential"]}</td><td>{ma["difficulty"]}</td>'
            f'<td>{ma["count"]}</td><td>{ma["median"]}K</td><td>{ma["high_pct"]}%</td>'
            f'<td>{_esc(adv)}</td><td>{_esc(gap)}</td>'
            f'<td><b>{ma["recommend"]}</b></td></tr>'
        )
    return f'''
<div class="strategy-box" id="ch9">
  <h2>🎯 第9章：结合求职者背景的匹配分析</h2>
  <div class="prose">
    <p><b>求职者背景：</b>智能家居/IoT/米家类中枢产品 → 首页产品、场景化产品、设备控制体验 → 多端协同（手机、电视、音箱、车、手表）→ 复杂项目推进、跨团队协同 → 有数据分析能力 → 目标：薪资提升、职业上限提升。</p>
    <p><b>匹配度评分标准：</b>★★★★★=核心经验直接匹配，★★★★=经验高度可迁移，★★★=部分可迁移需补齐，★★=需要较大转型，★=不建议。</p>
  </div>

  <h3>从通用市场结论到个人策略的推导</h3>
  <table>
  <thead><tr><th>通用市场结论</th><th>个人背景匹配</th><th>推导出的策略</th></tr></thead>
  <tbody>
  <tr><td>AI/策略/商业化/增长方向薪资溢价+7%</td><td>有场景化产品+数据分析基础，可迁移</td><td>→ 薪资冲刺线</td></tr>
  <tr><td>智能硬件/IoT方向匹配度最高</td><td>核心经验完全对口</td><td>→ 成功率主线</td></tr>
  <tr><td>平台产品溢价高但样本少</td><td>多端协同=平台化思维</td><td>→ 精准迁移线</td></tr>
  <tr><td>B端/C端岗位多但溢价为负</td><td>有C端经验可匹配</td><td>→ 保底方向</td></tr>
  <tr><td>金融/医疗/教育行业壁垒高</td><td>无相关行业背景</td><td>→ 不建议主攻</td></tr>
  </tbody>
  </table>

  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>方向</th><th>匹配度</th><th>薪资潜力</th><th>转型难度</th><th>岗位数</th><th>中位数</th><th>高薪占比</th><th>已有优势</th><th>短板</th><th>推荐</th></tr></thead>
    <tbody>{match_rows}</tbody>
  </table>
  </div>
  <div class="insight">📊 {_get_insight(R, "match_table")}</div>
</div>'''


def _render_strategy_chapter(R):
    """第10章：求职策略。"""
    strat = R.get("strategy", {})
    def _list_html(items):
        if not items:
            return "<p>暂无</p>"
        return "<ul>" + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>"

    kw_tags = " ".join(f'<span class="tag" style="font-size:13px;padding:4px 14px">{_esc(k)}</span>' for k in strat.get("resume_keywords", []))

    return f'''
<div class="strategy-box" id="ch10">
  <h2>🚀 第10章：求职策略</h2>

  <h3>🎯 薪资冲刺线（薪资高但需要额外准备）</h3>
  {_list_html(strat.get("sprint", []))}

  <h3>✅ 成功率主线（匹配度高且薪资有提升空间）</h3>
  {_list_html(strat.get("main_target", []))}

  <h3>🔀 精准迁移线（经验可迁移，溢价潜力大）</h3>
  {_list_html(strat.get("precise", []))}

  <h3>🛡️ 保底 / 可尝试方向（机会多，确保有offer）</h3>
  {_list_html(strat.get("backup", []))}

  <h3>❌ 不建议重点投入（匹配度低或薪资无优势）</h3>
  {_list_html(strat.get("avoid", []))}

  <h3>📝 简历核心关键词（确保覆盖）</h3>
  <div style="margin:12px 0">{kw_tags}</div>
</div>'''


def _render_search_keywords_chapter(R):
    """第17章：投递关键词建议。"""
    kws = R.get("search_keywords", {})

    def _kw_table(items):
        rows = ""
        for k in items:
            rows += (
                f'<tr><td><b>{_esc(k["keyword"])}</b></td><td>{k["fit"]}</td>'
                f'<td>{_esc(k["direction"])}</td><td>{k["salary"]}</td>'
                f'<td>{_esc(k["reason"])}</td></tr>'
            )
        return f'''<table>
            <thead><tr><th>关键词</th><th>适合度</th><th>对应方向</th><th>薪资潜力</th><th>匹配原因</th></tr></thead>
            <tbody>{rows}</tbody></table>'''

    return f'''
<div class="card" id="ch10b">
  <h2>🔑 投递关键词建议</h2>
  <div class="prose"><p>以下关键词基于数据中实际出现的岗位方向和薪资水平，按投递优先级分层。在Boss直聘搜索时使用这些关键词。</p></div>

  <h3>✅ 主投关键词（匹配度高，优先搜索）</h3>
  {_kw_table(kws.get("main", []))}

  <h3>⭐ 冲刺关键词（薪资高，需额外准备）</h3>
  {_kw_table(kws.get("sprint", []))}

  <h3>🛡️ 保底关键词（机会多，确保有offer）</h3>
  {_kw_table(kws.get("backup", []))}
</div>'''


def _render_resume_chapter(R):
    """第11章：简历改造建议。"""
    advice = R.get("resume_advice", {})

    # 关键词表格
    kw_rows = ""
    for k in advice.get("keywords", []):
        kw_rows += (
            f'<tr><td><b>{_esc(k["keyword"])}</b></td><td>{_esc(k["target"])}</td>'
            f'<td>{_esc(k["why"])}</td><td style="font-size:12px">{_esc(k["how"])}</td></tr>'
        )

    # 经历改写
    rewrite_html = ""
    for i, r in enumerate(advice.get("rewrites", []), 1):
        rewrite_html += f'''
        <div class="resume-card">
          <p><b>#{i} 原始表达：</b>{_esc(r["original"])}</p>
          <p><b>升级表达：</b><span style="color:#1e40af">{_esc(r["upgraded"])}</span></p>
          <p><b>适合方向：</b>{_esc(r["target"])} | <b>强调能力：</b>{_esc(r["emphasis"])}</p>
        </div>'''

    # 项目包装
    proj_rows = ""
    for p in advice.get("projects", []):
        proj_rows += (
            f'<tr><td><b>{_esc(p["name"])}</b></td><td>{_esc(p["target"])}</td>'
            f'<td>{_esc(p["selling_point"])}</td><td style="font-size:12px">{_esc(p["jd_match"])}</td>'
            f'<td style="font-size:12px">{_esc(p["resume_focus"])}</td></tr>'
        )

    return f'''
<div class="card" id="ch11">
  <h2>📝 第11章：简历改造建议</h2>
  <div class="prose">
    <p><b>核心原则：</b>用高薪JD的语言重新包装你的经历。不是编造经历，而是用更匹配的表达方式呈现真实经验。</p>
  </div>

  <h3>1️⃣ 简历关键词建议（确保覆盖）</h3>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>关键词</th><th>适合岗位</th><th>为什么重要</th><th>如何写进简历</th></tr></thead>
    <tbody>{kw_rows}</tbody>
  </table>
  </div>

  <h3>2️⃣ 经历改写建议（10条）</h3>
  <div class="prose"><p class="note">每条都是从「执行者视角」升级为「决策者视角」的改写示例。</p></div>
  {rewrite_html}

  <h3>3️⃣ 项目经历包装方向（5个核心项目）</h3>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>项目名称</th><th>适合岗位</th><th>核心卖点</th><th>高薪JD匹配点</th><th>简历表达重点</th></tr></thead>
    <tbody>{proj_rows}</tbody>
  </table>
  </div>
</div>'''


def _render_portfolio_chapter(R):
    """第12章：作品集/面试作品建议。"""
    items = R.get("portfolio_advice", [])
    rows = ""
    for p in items:
        rows += (
            f'<tr><td><b>{_esc(p["direction"])}</b></td><td>{_esc(p["target"])}</td>'
            f'<td>{_esc(p["why"])}</td><td style="font-size:12px">{_esc(p["structure"])}</td>'
            f'<td>{_esc(p["proves"])}</td><td>{_esc(p["priority"])}</td></tr>'
        )
    return f'''
<div class="card" id="ch12">
  <h2>📂 第12章：作品集 / 面试作品建议</h2>
  <div class="prose">
    <p><b>为什么需要作品集？</b>高薪岗位（尤其AI/IoT/车载方向）面试时经常要求展示产品思考。
    作品集不需要是完整的产品方案，而是展示你的<b>产品思维、数据分析能力和系统设计能力</b>。</p>
    <p><b>避免空想方案：</b>每个作品集都应基于你的真实经验延伸，而非凭空设计。面试官一眼能看出是否有实战基础。</p>
  </div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>作品集方向</th><th>对应岗位</th><th>为什么值得准备</th><th>核心内容结构</th><th>可以证明的能力</th><th>优先级</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</div>'''


def _render_risk_chapter(R):
    """第10章：风险与误区。"""
    risks = R.get("risk_analysis", [])
    risk_html = ""
    for i, r in enumerate(risks, 1):
        risk_html += f'''
        <div class="risk-card">
          <p><b>误区{i}：{_esc(r["risk"])}</b></p>
          <p>⚠️ 为什么危险：{_esc(r["danger"])}</p>
          <p>📊 数据证据：{_esc(r["evidence"])}</p>
          <p>✅ 如何避免：{_esc(r["avoid"])}</p>
        </div>'''
    return f'''
<div class="card" id="ch10">
  <h2>⚠️ 第10章：风险与误区</h2>
  <div class="prose"><p>求职中最常踩的坑，每个都有数据支撑。看完能帮你少走弯路。</p></div>
  {risk_html}
</div>'''


def _render_action_plan_chapter(R):
    """第14章：30天行动计划。"""
    strat = R.get("strategy", {})
    action_html = ""
    for week in strat.get("action_plan", []):
        tasks = "".join(f"<li>{_esc(t)}</li>" for t in week["tasks"])
        action_html += f"""
        <div style="margin-bottom:16px;padding:16px;background:#f8fafc;border-radius:10px;border-left:4px solid #2d6a9f">
            <h3 style="margin:0 0 8px">{_esc(week["week"])}</h3>
            <ul style="padding-left:20px;font-size:14px">{tasks}</ul>
            <p class="note">产出：{_esc(week["output"])}</p>
        </div>"""
    return f'''
<div class="card" id="ch14">
  <h2>📅 附录：个人求职准备计划（仅供参考）</h2>
  <p class="note">本附录为个人定制内容，如报告需对外复用请删除此章节。</p>
  <div class="prose"><p>以下是基于数据分析结论制定的4周求职准备计划。每周都有明确的任务和产出物。</p></div>
  {action_html}
</div>'''


# ═══════════════════════════════════════════════════════════════════════════
# 结论与市场判断生成
# ═══════════════════════════════════════════════════════════════════════════

def _generate_conclusions(R):
    """生成核心结论摘要——每个章节提炼一条最关键的结论。"""
    so = R["salary_overview"]
    conclusions = []
    dirs = R["direction_analysis"]

    # 来自第2章：市场基准
    conclusions.append(
        f"【市场基准】本次分析覆盖北京 {R['valid_count']} 个产品经理岗位（3-10年·本科+·30K+），"
        f"薪资中位数 {so['median']}K/月，P75 为 {so['p75']}K，P90 达 {so['p90']}K。"
        f"大部分岗位集中在30-50K区间，突破50K需要在方向选择或职级上有突破。"
    )

    # 来自第3章：方向选择
    # tier1: 高薪占比高且有结构性薪资优势的方向
    tier1 = sorted([d for d in dirs if d["high_pct"] >= 35 and d["count"] >= 100], key=lambda x: -x["high_pct"])
    # tier1b: 高薪占比>=28%但中位数无溢价的方向
    tier1b = sorted([d for d in dirs if d["high_pct"] >= 28 and d["high_pct"] < 35 and d["premium"] >= 0 and d["count"] >= 100], key=lambda x: -x["high_pct"])
    tier2 = [d for d in dirs if d.get("p90_premium", 0) > 0 and d["high_pct"] < 28 and d["count"] >= 20]
    tier3 = sorted([d for d in dirs if d["count"] >= 200 and d["premium"] < 0], key=lambda x: -x["count"])[:3]
    if tier1 or tier1b:
        parts = []
        if tier1:
            # 为每个方向生成精确描述
            tier1_descs = []
            for d in tier1:
                adv_parts = []
                if d.get("p75_premium", 0) > 0:
                    adv_parts.append(f"P75溢价{d['p75_premium']:+.1f}%")
                adv_parts.append(f"高薪占比{d['high_pct']}%")
                if d["count"] >= 500:
                    adv_parts.append(f"岗位量大({d['count']}个)")
                tier1_descs.append(f'{d["direction"]}({", ".join(adv_parts)})')
            names = "、".join(tier1_descs)
            parts.append(f"重点投递：{names}——高薪岗位密集，值得优先关注。")
        if tier1b:
            names_b = "、".join(f'{d["direction"]}({d["high_pct"]}%)' for d in tier1b)
            parts.append(f"高薪机会多但中位数无溢价：{names_b}——高薪占比≥28%但整体薪资与市场持平，需结合自身背景精准筛选JD。")
        if tier2:
            t2_names = "、".join(f'{d["direction"]}(P90={d["p90"]}K)' for d in tier2)
            parts.append(f"天花板高但需要实力：{t2_names}。")
        if tier3:
            t3_names = "、".join(d["direction"] for d in tier3)
            parts.append(f"保底方向：{t3_names}——岗位多但薪资中等。")
        small_high = [d for d in dirs if d["count"] < 50 and d["high_pct"] > 30]
        if small_high:
            sh_names = "、".join(d["direction"] for d in small_high)
            parts.append(f"{sh_names}数据亮眼但样本太少，不建议据此决策。")
        conclusions.append("【方向选择】" + " ".join(parts))

    # 来自第4章：高薪画像
    conclusions.append(
        f"【高薪画像】高薪岗位（P75+）共{R['high_salary_count']}个，"
        f"主要集中在策略产品(37%)、AI/大模型(35%)方向，"
        f"职级以资深/专家/负责人为主。VP/负责人级别中位数比普通级别高出15-30K/月。"
    )

    # 来自第5章：能力因子
    conclusions.append(
        "【高薪能力】高薪JD和普通JD的核心差异不在于工具技能，而在于：业务闭环（对结果负责）、"
        "指标驱动（用数据判断价值）、策略设计（设计策略并验证效果）、AI应用落地、复杂系统抽象和Owner能力。"
    )

    # 来自第5章：经验跃迁
    exp_salary = R.get("high_salary_factors", {}).get("exp_factor", [])
    if len(exp_salary) >= 2:
        exp35 = next((e for e in exp_salary if e["exp"] == "3-5年"), None)
        exp510 = next((e for e in exp_salary if e["exp"] == "5-10年"), None)
        if exp35 and exp510:
            gap = round(exp510["median"] - exp35["median"], 1)
            # 从数据中取经验溢价最高的方向（样本充足）
            dep = R.get("high_salary_factors", {}).get("dir_exp_premium", [])
            top_exp_dirs = [d for d in dep if d["count_35"] + d["count_510"] >= 50][:3]
            if top_exp_dirs:
                dir_names = "、".join(f'{d["direction"]}(+{d["premium"]:.0f}%)' for d in top_exp_dirs)
                conclusions.append(
                    f"【经验价值】5-10年比3-5年薪资中位数高{gap}K/月（{exp510['median']}K vs {exp35['median']}K），"
                    f"经验溢价最明显的方向：{dir_names}。"
                )
            else:
                conclusions.append(
                    f"【经验价值】5-10年比3-5年薪资中位数高{gap}K/月（{exp510['median']}K vs {exp35['median']}K）。"
                )

    # 来自第6章：技能标签
    high_skills = R.get("skills_by_cat", {}).get("能力/技能信号", [])[:3]
    if high_skills:
        sk_names = "、".join(s["skill"] for s in high_skills)
        conclusions.append(
            f"【技能信号】JD中与高薪最相关的技能标签：{sk_names}。"
            f"但真正拉开差距的不是标签本身，而是能用项目经历证明你具备对应能力。"
        )

    # 来自第8章/第9章：辅助信息
    conclusions.append(
        "【辅助判断】公司、行业、区域是辅助参考维度，不应替代方向和JD质量判断。"
        "岗位最集中在望京和上地，但望京薪资偏低（32.5K），海淀学院路/苏州桥兼具薪资和机会。"
    )

    return conclusions


def _generate_market_judgment(R):
    """生成500-1000字的整体市场判断。"""
    so = R["salary_overview"]
    dirs = R["direction_analysis"]
    top_dirs = sorted(dirs, key=lambda x: -x["median"])[:3]
    big_dirs = sorted(dirs, key=lambda x: -x["count"])[:3]
    low_dirs = [d for d in dirs if d["premium"] < -5]

    exp_35 = next((e for e in R["exp_dist"] if e["name"] == "3-5年"), None)
    exp_510 = next((e for e in R["exp_dist"] if e["name"] == "5-10年"), None)

    text = f"""<p>基于 {R['total']} 个北京产品经理岗位的分析（筛选条件：3-10年经验、本科+、月薪30K+、全职），
    当前市场呈现以下核心特征：</p>

    <p><b>一、市场整体偏向资深化。</b>
    {"5-10年经验岗位（" + str(exp_510['value']) + "个）占比超过3-5年（" + str(exp_35['value']) + "个），" if exp_510 and exp_35 else ""}
    薪资中位数 {so['median']}K/月，P75 达 {so['p75']}K，P90 达 {so['p90']}K。
    这意味着在30K+的细分市场中，大部分岗位集中在30-50K区间，真正的高薪（50K+）岗位需要更强的专业深度或管理能力。</p>

    <p><b>二、方向选择比努力更重要。</b>
    薪资最高的方向是{top_dirs[0]['direction']}（中位数{top_dirs[0]['median']}K）、
    {top_dirs[1]['direction']}（{top_dirs[1]['median']}K）、
    {top_dirs[2]['direction']}（{top_dirs[2]['median']}K），
    而岗位数量最多的方向是{big_dirs[0]['direction']}（{big_dirs[0]['count']}个）、
    {big_dirs[1]['direction']}（{big_dirs[1]['count']}个）、
    {big_dirs[2]['direction']}（{big_dirs[2]['count']}个）。
    岗位多的方向不一定薪资高——{big_dirs[0]['direction']}虽然岗位最多，但薪资溢价仅{big_dirs[0]['premium']:+.1f}%。
    求职者应优先选择「薪资溢价高 + 岗位量适中 + 与自身背景匹配」的方向。</p>

    <p><b>三、市场对产品经理的要求已从"写PRD、跟项目"转向"业务深度+技术理解+数据驱动"。</b>
    高薪岗位（P75+）中，AI/大模型、数据分析、策略产品等技能标签出现频率显著高于普通岗位。
    纯执行型产品经理的薪资天花板明显，要突破需要在某个垂直方向建立专业壁垒。</p>

    <p><b>四、高薪方向的进入门槛各不相同。</b>
    AI/大模型方向高薪占比最高且岗位量大，但竞争激烈，需要AI产品思维和技术理解；
    策略/增长/商业化方向需要数据驱动和业务闭环能力；
    智能硬件/IoT和车载方向需要硬件协同和场景化设计经验；
    平台产品方向需要系统设计和平台化思维。
    求职者应根据自身背景选择最匹配的高溢价方向切入。</p>

    <p><b>五、投「资深/专家/负责人」级别的岗位是提薪的关键。</b>
    数据显示，同一方向下「资深/专家」和「负责人」级别的薪资中位数比「普通」级别高出30-50%。
    这意味着求职时应主动搜索和投递带有「资深」「高级」「专家」「负责人」等关键词的岗位，而不是只投「产品经理」。
    同时，简历中要用具体事实证明你具备这个级别的能力——比如独立负责过什么业务线、带过多大规模的项目、做过哪些关键决策并取得了什么结果。
    面试官判断你值不值这个级别，看的是你做过的事，不是你怎么包装title。</p>"""

    if low_dirs:
        names = "、".join(d["direction"] for d in low_dirs[:3])
        text += f"""
    <p><b>六、需要警惕的方向：</b>{names}等方向在筛选范围内薪资偏低（低于整体中位数5%+），
    除非有强匹配度，否则不建议作为主攻方向。</p>"""

    return text


def _generate_charts_js():
    """生成所有 ECharts 图表的 JavaScript 代码。"""
    return '''
// ═══ 薪资分布直方图 ═══
(function() {
  const ch = initChart('c_salary_dist'); if(!ch) return;
  const d = D.salary_dist;
  const maxIdx = d.reduce((mi,v,i,a) => v.count > a[mi].count ? i : mi, 0);
  ch.setOption({
    title:{text:'薪资分布（筛选后）',textStyle:{fontSize:14}},
    tooltip: {trigger:'axis'},
    xAxis: {type:'category', data:d.map(x=>x.range), axisLabel:{fontSize:11,rotate:20}},
    yAxis: {type:'value', name:'岗位数'},
    series: [{
      type:'bar', data:d.map((x,i) => ({
        value: x.count,
        itemStyle: {color: i===maxIdx ? blue : '#a5c4e0'}
      })),
      label:{show:true, position:'top', fontSize:10},
      barMaxWidth: 45
    }]
  });
})();

// ═══ 经验/学历分布 ═══
(function() {
  const ch = initChart('c_exp_edu'); if(!ch) return;
  ch.setOption({
    title:{text:'经验 & 学历分布',textStyle:{fontSize:14}},
    tooltip:{trigger:'item'},
    legend:{bottom:0,data:['经验要求','学历要求']},
    series:[
      {name:'经验要求',type:'pie',radius:['20%','45%'],center:['30%','45%'],
        data:D.exp_dist.map(d=>({name:d.name,value:d.value})),
        label:{fontSize:11,formatter:'{b}\\n{d}%'}},
      {name:'学历要求',type:'pie',radius:['20%','45%'],center:['75%','45%'],
        data:D.edu_dist.map(d=>({name:d.name,value:d.value})),
        label:{fontSize:11,formatter:'{b}\\n{d}%'}}
    ]
  });
})();

// ═══ 区域岗位分布 ═══
(function() {
  const ch = initChart('c_area'); if(!ch) return;
  const items = D.area_salary;
  if (!items || !items.length) return;
  const total = items.reduce((s,d)=>s+d.count, 0);
  ch.setOption({
    title:{text:'北京各区岗位数量分布（机会集中度）',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis',formatter:function(p){
      const d=items[p[0].dataIndex];
      return d.area+'<br>岗位数: '+d.count+'个<br>占比: '+(d.count/total*100).toFixed(1)+'%'
    }},
    grid:{bottom:80},
    xAxis:{type:'category',data:items.map(d=>d.area),axisLabel:{rotate:25,fontSize:11}},
    yAxis:{type:'value',name:'岗位数'},
    series:[
      {type:'bar',data:items.map((d,i)=>({
        value:d.count,
        itemStyle:{color: i===0 ? blue : '#a5c4e0'}
      })),label:{show:true,position:'top',fontSize:10,formatter:function(v){
        return v.value+'个\\n'+(v.value/total*100).toFixed(0)+'%'
      }},barMaxWidth:45}
    ]
  });
})();

// ═══ 方向薪资对比 ═══
(function() {
  const ch = initChart('c_direction'); if(!ch) return;
  const items = D.direction_analysis;
  if (!items || !items.length) return;
  ch.setOption({
    title:{text:'各方向薪资对比（中位数 + 溢价）',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis',formatter:function(p){
      const d=items[p[0].dataIndex];
      return d.direction+'<br>中位数: '+d.median+'K<br>P75: '+d.p75+'K<br>P90: '+d.p90+'K<br>溢价: '+(d.premium>0?'+':'')+d.premium+'%<br>岗位: '+d.count+'个<br>高薪占比: '+d.high_pct+'%'
    }},
    grid:{bottom:100},
    xAxis:{type:'category',data:items.map(d=>d.direction),axisLabel:{rotate:35,fontSize:11}},
    yAxis:{type:'value',name:'月薪(K)'},
    series:[
      {name:'中位数',type:'bar',data:items.map(d=>({value:d.median,itemStyle:{color:d.premium>0?green:d.premium<-5?red:blue}})),
        label:{show:true,position:'top',formatter:function(v){const d=items[v.dataIndex];return v.value+'K\\n('+(d.premium>0?'+':'')+d.premium+'%)'},fontSize:10},
        barMaxWidth:40},
    ]
  });
})();

// ═══ 经验×方向交叉 ═══
(function() {
  const ch = initChart('c_exp_dir'); if(!ch) return;
  const items = D.exp_dir_cross;
  if (!items || !items.length) return;
  const labels = items.map(d=>d.exp+' | '+d.direction).reverse();
  const colors = items.map(d=>d.exp==='5-10年'?orange:blue).reverse();
  ch.setOption({
    title:{text:'经验 × 方向 交叉薪资（TOP20）',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},
    grid:{left:'30%',right:'15%',top:40,bottom:10},
    xAxis:{type:'value',name:'月薪中位数(K)'},
    yAxis:{type:'category',data:labels,axisLabel:{fontSize:11}},
    series:[{type:'bar',data:items.map((d,i)=>({value:d.median,itemStyle:{color:colors[items.length-1-i]}})).reverse(),
      label:{show:true,position:'right',formatter:v=>v.value+'K',fontSize:11},barMaxWidth:20}]
  });
})();

// ═══ 高薪vs普通方向差异 ═══
(function() {
  const ch = initChart('c_dir_diff'); if(!ch) return;
  const items = D.dir_diff;
  if (!items || !items.length) return;
  items.sort((a,b) => b.ratio - a.ratio);
  ch.setOption({
    title:{text:'高薪岗 vs 普通岗：方向分布差异',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},
    legend:{data:['高薪岗占比','普通岗占比']},
    grid:{left:'22%',right:'10%',bottom:20,top:50},
    yAxis:{type:'category',data:items.map(d=>d.direction).reverse(),axisLabel:{fontSize:11}},
    xAxis:{type:'value',name:'占比(%)'},
    series:[
      {name:'高薪岗占比',type:'bar',data:items.map(d=>d.hs_pct).reverse(),itemStyle:{color:orange},barMaxWidth:16},
      {name:'普通岗占比',type:'bar',data:items.map(d=>d.nm_pct).reverse(),itemStyle:{color:'#a5c4e0'},barMaxWidth:16}
    ]
  });
})();

// ═══ 职级薪资 ═══
(function() {
  const ch = initChart('c_level_salary'); if(!ch) return;
  const items = D.level_salary;
  if (!items || !items.length) return;
  ch.setOption({
    title:{text:'职级 × 薪资',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis',formatter:function(p){
      const d=items[p[0].dataIndex];
      return d.level+'<br>中位数: '+d.median+'K<br>P25: '+d.p25+'K<br>P75: '+d.p75+'K<br>样本: '+d.count+'条'
    }},
    grid:{bottom:60,top:40},
    xAxis:{type:'category',data:items.map(d=>d.level),axisLabel:{fontSize:12}},
    yAxis:{type:'value',name:'月薪(K)'},
    series:[
      {name:'中位数',type:'bar',data:items.map(d=>d.median),itemStyle:{color:blue},
        label:{show:true,position:'top',formatter:v=>v.value+'K'},barMaxWidth:45},
      {name:'P75',type:'line',data:items.map(d=>d.p75),lineStyle:{type:'dashed'},itemStyle:{color:orange}},
      {name:'P25',type:'line',data:items.map(d=>d.p25),lineStyle:{type:'dashed'},itemStyle:{color:teal}}
    ]
  });
})();

// ═══ 行业薪资 ═══
(function() {
  const ch = initChart('c_industry'); if(!ch) return;
  const items = D.industry_salary;
  if (!items || !items.length) return;
  ch.setOption({
    title:{text:'行业 × 薪资 TOP15',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},
    grid:{left:'28%',right:'12%',top:40},
    xAxis:{type:'value',name:'月薪中位数(K)'},
    yAxis:{type:'category',data:items.map(d=>d.industry).reverse(),axisLabel:{fontSize:11}},
    series:[{type:'bar',data:items.map(d=>d.median).reverse(),itemStyle:{color:teal},
      label:{show:true,position:'right',formatter:v=>v.value+'K'},barMaxWidth:24}]
  });
})();

// ═══ 规模/融资薪资 ═══
(function() {
  const ch = initChart('c_scale_stage'); if(!ch) return;
  const sc = D.scale_salary || [];
  const st = D.stage_salary || [];
  if (!sc.length && !st.length) return;
  const labels = sc.map(d=>d.scale).concat(['---']).concat(st.map(d=>d.stage)).reverse();
  const values = sc.map(d=>d.median).concat([0]).concat(st.map(d=>d.median)).reverse();
  const colors = sc.map(()=>blue).concat(['transparent']).concat(st.map(()=>purple)).reverse();
  ch.setOption({
    title:{text:'公司规模 & 融资阶段 × 薪资',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},
    grid:{left:'25%',right:'12%',top:40},
    xAxis:{type:'value',name:'月薪中位数(K)'},
    yAxis:{type:'category',data:labels,axisLabel:{fontSize:11}},
    series:[{type:'bar',data:values.map((v,i)=>({value:v,itemStyle:{color:colors[i]}})),
      label:{show:true,position:'right',formatter:v=>v.value?v.value+'K':''},barMaxWidth:22}]
  });
})();

// ═══ 技能价值散点图 ═══
(function() {
  const ch = initChart('c_skill_value'); if(!ch) return;
  const items = D.skill_value;
  if (!items || !items.length) return;
  const catColors = {'方向标签':'#2d6a9f','能力/技能信号':'#f59e0b','小样本趋势词':'#9ca3af','无区分度标签':'#d1d5db'};
  const series = {};
  items.forEach(function(s) {
    if (!series[s.category]) series[s.category] = [];
    series[s.category].push([s.count, s.median, s.skill, s.premium]);
  });
  const seriesArr = Object.keys(series).map(function(cat) {
    return {
      name: cat, type: 'scatter', data: series[cat],
      symbolSize: function(d) { return Math.min(Math.max(d[0]/3, 8), 40); },
      itemStyle: {color: catColors[cat] || '#999'},
      label: {show: series[cat].length <= 8, formatter: function(p){return p.data[2]}, fontSize:10, position:'right'}
    };
  });
  ch.setOption({
    title:{text:'技能价值分布（样本量 vs 薪资中位数）',textStyle:{fontSize:14}},
    tooltip:{formatter:function(p){return p.data[2]+'<br>样本: '+p.data[0]+'<br>中位数: '+p.data[1]+'K<br>溢价: '+(p.data[3]>0?'+':'')+p.data[3]+'%'}},
    legend:{data:Object.keys(series),bottom:0},
    grid:{bottom:50,top:40},
    xAxis:{type:'value',name:'样本量',nameLocation:'center',nameGap:30},
    yAxis:{type:'value',name:'月薪中位数(K)'},
    series:seriesArr
  });
})();

// ═══ 商圈级别分布（柱状+折线） ═══
(function() {
  const ch = initChart('c_biz_area'); if(!ch) return;
  const items = D.biz_area_salary;
  if (!items || !items.length) return;
  ch.setOption({
    title:{text:'商圈岗位数量 & 薪资中位数',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis',formatter:function(p){
      const d=items[p[0].dataIndex];
      return d.biz_area+'<br>岗位数: '+d.count+'个<br>中位数: '+d.median+'K<br>P75: '+d.p75+'K'
    }},
    legend:{data:['岗位数','薪资中位数'],bottom:0},
    grid:{bottom:100,top:50,right:'12%'},
    xAxis:{type:'category',data:items.map(d=>d.biz_area.replace(/（.*）/,'')),axisLabel:{rotate:40,fontSize:10}},
    yAxis:[
      {type:'value',name:'岗位数',position:'left'},
      {type:'value',name:'月薪(K)',position:'right',min:25,max:45}
    ],
    series:[
      {name:'岗位数',type:'bar',data:items.map(d=>({
        value:d.count,
        itemStyle:{color: d.biz_area.indexOf('主要为')>-1 ? orange : blue}
      })),barMaxWidth:30},
      {name:'薪资中位数',type:'line',yAxisIndex:1,data:items.map(d=>d.median),
        lineStyle:{color:red,width:2},itemStyle:{color:red},
        label:{show:true,formatter:v=>v.value+'K',fontSize:9,position:'top'}}
    ]
  });
})();

// ═══ 响应式 ═══
window.addEventListener('resize', function() {
  document.querySelectorAll('[id^="c_"]').forEach(function(el) {
    var ch = echarts.getInstanceByDom(el);
    if (ch) ch.resize();
  });
});
'''


# ═══════════════════════════════════════════════════════════════════════════
# 第六部分：主入口
# ═══════════════════════════════════════════════════════════════════════════

def generate_markdown(R):
    """生成纯 Markdown 版本报告，适合给 ChatGPT/Claude 等 LLM 阅读。"""
    so = R["salary_overview"]
    lines = []
    L = lines.append

    L("# 北京产品经理深度招聘市场分析报告")
    L(f"\n分析时间：{R['date']} | 样本量：{R['valid_count']} 个岗位")
    L(f"筛选条件：北京 · 3-10年经验 · 本科+ · 月薪30K+ · 全职")
    L(f"高薪定义：月薪中位数 ≥ P75（{R['p75_threshold']}K）")

    # 第0章
    L("\n## 0. 核心结论摘要\n")
    for i, c in enumerate(_generate_conclusions(R), 1):
        L(f"{i}. {c}")

    # 第1章
    L("\n## 1. 数据质量与分析口径\n")
    L(f"本报告基于 {R['valid_count']} 个有效岗位样本。样本清洗后得到 {R['valid_count']} 条有效记录（剔除月薪中位数≥100K的极端值 {R['extreme_excluded']} 条，多为猎头发布、薪资范围虚高）。\n")
    L("**筛选条件：**")
    L("- 地区：仅北京")
    L("- 工作经验：仅 3-5 年和 5-10 年")
    L("- 学历：仅本科及以上")
    L("- 薪资：最高月薪 ≥ 30K（低薪岗位已排除）")
    L("- 岗位类型：仅全职")
    L("")
    L("**分析口径：**")
    L("- 薪资口径：取 salary_min 和 salary_max 中位数")
    L("- 岗位方向：根据 title + skills + description 重新聚类，不依赖原始关键词")
    L(f"- 极端值处理：月薪中位数≥100K的岗位（{R['extreme_excluded']}条）不参与统计计算，仅在高薪TOP15中展示")
    L("- ⚠️ 所有结论仅适用于筛选后的细分市场，不代表市场全貌")

    # 第2章
    L("\n## 2. 整体薪资结构与市场基准\n")
    L(f"- 薪资中位数：{so['median']}K/月，P25-P75：{so['p25']}-{so['p75']}K，P90：{so['p90']}K")
    L(f"- 高薪岗位（P75+）：{R['high_salary_count']} 个（{R['high_salary_pct']}%）")
    L(f"- 聚类方向数：{len(R['direction_analysis'])}")
    for e in R.get("exp_dist", []):
        L(f"- 经验分布：{e['name']} {e['value']}个")

    # 薪资分布
    L("\n### 薪资分布\n")
    L("| 区间 | 岗位数 |")
    L("|------|--------|")
    for d in R.get("salary_dist", []):
        L(f"| {d['range']} | {d['count']} |")

    # 第3章：岗位方向深度分析（原第5章）
    L("\n## 3. 岗位方向深度分析\n")
    L("*注：JD高频标签来自岗位标题、skills和description字段，反映该方向的常见标签，不等同于能力要求。*\n")
    L("| 方向 | 岗位数 | 占比 | 中位数 | P75 | P90 | 中位数溢价 | P75溢价 | P90溢价 | 高薪占比 | 样本可信度 | JD高频标签 |")
    L("|------|--------|------|--------|-----|-----|----------|--------|--------|----------|----------|----------|")
    for d in R.get("direction_analysis", []):
        skills = "、".join(d["top_skills"][:3])
        credibility = "较高" if d["count"] >= 100 else "中等" if d["count"] >= 50 else "谨慎" if d["count"] >= 20 else "小样本"
        L(f"| {d['direction']} | {d['count']} | {d['pct']}% | {d['median']}K | {d['p75']}K | {d['p90']}K | {d['premium']:+.1f}% | {d.get('p75_premium', 0):+.1f}% | {d.get('p90_premium', 0):+.1f}% | {d['high_pct']}% | {credibility} | {skills} |")

    # 第4章：高薪岗位画像分析（原第6章）
    L("\n## 4. 高薪岗位画像分析\n")
    L("### 高薪岗位更常见的方向/岗位标签\n")
    L("| 方向/岗位标签 | 高薪岗占比 | 普通岗占比 | 差异倍数 |")
    L("|-------------|-----------|-----------|----------|")
    for s in R.get("skill_diff_top", [])[:15]:
        L(f"| {s['skill']} | {s['hs_pct']}% | {s['nm_pct']}% | {s['ratio']}x |")
    L("\n*注：以上是岗位方向标签，不是具体技能。高薪岗位背后真正有区分度的是：业务闭环、指标驱动、策略设计、复杂系统抽象、AI应用落地、商业化变现和Owner能力。*")

    L("\n### 职级 × 薪资\n")
    L("| 职级 | 样本 | 中位数 | P25 | P75 |")
    L("|------|------|--------|-----|-----|")
    for lv in R.get("level_salary", []):
        L(f"| {lv['level']} | {lv['count']} | {lv['median']}K | {lv['p25']}K | {lv['p75']}K |")

    L("\n### 行业 × 薪资 TOP15\n")
    L("| 行业 | 样本 | 中位数 | P75 |")
    L("|------|------|--------|-----|")
    for ind in R.get("industry_salary", []):
        L(f"| {ind['industry']} | {ind['count']} | {ind['median']}K | {ind['p75']}K |")

    L("\n⚠️ **风险提示：** TOP15主要用于观察极端高薪岗位画像（多为总监/负责人/VP级别），不适合作为普通求职者薪资预期。普通求职者应优先参考中位数、P75、P90和各方向高薪占比。\n")
    L("*薪资口径说明：TOP15保留招聘网站原始薪资格式，未统一折算为月薪中位数，因此不能与前文方向中位数直接横向比较。*\n")
    L("### 高薪岗位 TOP15\n")
    L("| 岗位 | 公司 | 薪资 | 经验 | 方向 | 来源 |")
    L("|------|------|------|------|------|------|")
    for j in R.get("top_salary_jobs", []):
        L(f"| {j['title']} | {j['company']} | {j['salary_desc']} | {j['exp']} | {j['direction']} | {j.get('source', '')} |")

    # 第5章：高薪差异因子与JD能力解构
    L("\n## 5. 高薪差异因子与JD能力解构\n")
    L('*本章分析高薪岗位背后的能力要求。背景变量（经验、职级）能解释"谁更贵"，但不能直接告诉求职者"怎么变得更值钱"。真正有价值的是分析高薪JD和普通JD在能力要求上的差异。*\n')

    # 5.1 背景变量
    L("### 5.1 背景变量：经验、职级、方向\n")
    factors = R.get("high_salary_factors", {})
    L("#### 经验因素\n")
    L("| 经验 | 样本 | 中位数 | P75 | P90 |")
    L("|------|------|--------|-----|-----|")
    for e in factors.get("exp_factor", []):
        L(f"| {e['exp']} | {e['count']} | {e['median']}K | {e['p75']}K | {e['p90']}K |")

    L("\n#### 经验 × 方向交叉薪资\n")
    L("\n**样本较充足方向（合计≥30）：**\n")
    L("| 方向 | 3-5年中位数 | 5-10年中位数 | 经验溢价 | 样本(3-5/5-10) |")
    L("|------|-----------|-------------|----------|---------------|")
    large_sample = [d for d in factors.get("dir_exp_premium", []) if d["count_35"] + d["count_510"] >= 30]
    for d in large_sample[:8]:
        L(f"| {d['direction']} | {d['median_35']}K | {d['median_510']}K | {d['premium']:+.1f}% | {d['count_35']}/{d['count_510']} |")
    small_sample_dirs = [d for d in factors.get("dir_exp_premium", []) if d["count_35"] + d["count_510"] < 30]
    if small_sample_dirs:
        L("\n**小样本观察方向（合计<30，仅作参考）：**\n")
        L("| 方向 | 3-5年中位数 | 5-10年中位数 | 经验溢价 | 样本 | 说明 |")
        L("|------|-----------|-------------|----------|------|------|")
        for d in small_sample_dirs[:5]:
            L(f"| {d['direction']} | {d['median_35']}K | {d['median_510']}K | {d['premium']:+.1f}% | {d['count_35']}/{d['count_510']} | ⚠️仅作观察 |")

    # 5.2 高薪JD vs 普通JD能力差异
    L("\n### 5.2 高薪JD vs 普通JD的能力差异\n")
    L("*以下基于JD文本和统计结果的趋势判断，不是确定性因果结论。*\n")
    L("| 能力因子 | 高薪JD常见表述 | 普通JD常见表述 | 背后考察 | 对应方向 | 求职者如何证明 |")
    L("|---------|-------------|-------------|---------|---------|-------------|")
    L("| 业务闭环 | 负责核心业务目标、从策略到复盘、对指标结果负责 | 负责需求分析、PRD撰写、项目推进 | 是否能对业务结果负责 | 所有高薪方向 | 写清问题判断→关键决策→落地结果→指标变化 |")
    L("| 指标驱动 | DAU/留存/转化/ROI/GMV、AB实验、指标体系 | 数据分析、数据监控 | 是否能用指标判断产品价值 | 策略/增长/商业化 | 准备完整的数据复盘案例 |")
    L("| 策略设计 | 推荐策略/搜索排序/分发/用户分层/算法协同 | 功能设计、需求管理 | 是否能设计策略并验证效果 | 策略/AI/增长 | 展示策略设计→AB验证→效果迭代的完整链路 |")
    L("| 商业化变现 | ROI/eCPM/转化漏斗/投放/变现/商业闭环 | 活动策划、运营支持 | 是否理解商业模式并能平衡体验和收入 | 商业化/广告 | 展示变现策略设计和ROI优化案例 |")
    L("| AI应用落地 | 大模型/Agent/RAG/多模态/模型效果评估/场景落地 | 了解AI、使用AI工具 | 是否能把AI能力落到真实业务场景 | AI/大模型 | 用作品集展示AI解决真实业务问题 |")
    L("| 复杂系统抽象 | 平台化/配置化/规则引擎/权限体系/开放能力 | 后台管理、需求配置、流程优化 | 是否能把复杂业务抽象成可复用能力 | 平台/B端/IoT | 说明如何把复杂流程抽象成平台能力 |")
    L("| 跨团队复杂项目 | 5+团队协同/多利益方/复杂约束/按期交付 | 协调研发、跟进上线 | 是否能在复杂环境中推动大型项目 | 平台/B端/IoT/车载 | 展示多团队协同的具体案例和交付结果 |")
    L("| Owner/负责人 | 独立负责/从0到1/业务owner/产品负责人 | 参与项目、配合团队 | 是否能独立判断方向并为结果负责 | 所有高薪方向 | 写清独立负责的范围、决策和结果 |")

    # 5.3 高薪能力因子证据强度
    L("\n### 5.3 高薪能力因子证据强度\n")
    L("| 高薪因子 | 证据来源 | 证据强度 | 主要出现方向 | 是否适合短期补齐 | 说明 |")
    L("|---------|---------|---------|-----------|-------------|------|")
    L("| 指标驱动 | 方向薪资+JD标签 | 高 | 增长/策略/AI/商业化 | 是（通过项目复盘） | 准备2-3个数据驱动决策案例 |")
    L("| AI应用落地 | 方向岗位量+高薪占比 | 高 | AI/大模型 | 部分（通过作品集） | 需要理解大模型能力边界 |")
    L("| 商业化变现 | 方向溢价 | 中高 | 商业化/广告 | 部分（需真实业务经验） | 从营销平台切入门槛较低 |")
    L("| 策略设计 | 方向高薪占比 | 高 | 策略/增长 | 是（补AB实验方法论） | 2-3周可入门 |")
    L("| 复杂系统抽象 | 平台产品P75/P90 | 中 | 平台/B端 | 需要真实项目 | 适合有复杂系统经验的人 |")
    L("| 业务闭环 | 高薪JD通用要求 | 高 | 所有方向 | 是（改写简历表达） | 每段经历写清决策和结果 |")
    L("| Owner能力 | 职级薪资差异 | 高 | 所有方向 | 部分（需要真实负责经历） | 投递高级别岗位+简历体现 |")
    L("| 行业壁垒 | 金融方向溢价 | 中高 | 金融 | 否（短期难补） | 有行业背景者可投 |")

    # 5.4 高薪JD识别规则
    L("\n### 5.4 高薪JD识别规则\n")
    L("\n**值得优先投的JD信号：**\n")
    L("| JD信号 | 代表什么能力 | 适合投递的候选人 | 是否值得优先投 |")
    L("|--------|-----------|-------------|-------------|")
    L("| 负责核心业务/核心模块/owner | 业务闭环+Owner | 有独立负责经历的人 | 是 |")
    L("| 对DAU/留存/转化/ROI/GMV负责 | 指标驱动 | 有数据分析和指标体系经验的人 | 是 |")
    L("| 推荐/搜索/分发/策略/AB实验 | 策略设计 | 有策略或算法协同经验的人 | 是 |")
    L("| 大模型/Agent/RAG/多模态/模型评估 | AI应用落地 | 有AI应用或场景化产品经验的人 | 是 |")
    L("| 平台化/规则引擎/配置化/开放能力 | 复杂系统抽象 | 有平台或复杂系统设计经验的人 | 是 |")
    L("\n**需要谨慎的低价值JD信号：**\n")
    L("| JD信号 | 风险 | 为什么谨慎 |")
    L("|--------|------|-----------|")
    L("| 只写PRD/协调研发/跟进上线 | 纯执行岗 | 薪资天花板低，无业务判断权 |")
    L("| 活动配置/运营支持/后台维护 | 运营岗而非产品岗 | 做活动策划而非产品设计 |")
    L("| 客户资源/销售支持 | 销售支持岗 | 核心是客户关系而非产品能力 |")
    L("| 过度强调供应链/结构/生产制造 | 硬件工程岗 | 考察供应链管理而非产品设计 |")

    # 5.5 控制变量说明
    L("\n### 5.5 控制变量说明\n")
    L('以上高薪因子分析不能简单把"职级高、经验长"当成能力。更有价值的比较是：')
    L("- 同经验段下，高薪JD和普通JD的差异；")
    L("- 同方向下，高薪JD和普通JD的差异；")
    L("- 非总监/负责人岗位中，高薪JD和普通JD的差异。")
    L('当前数据JD正文内容有限（多数仅含技能标签+福利），上述能力因子分析基于JD文本和统计结果的趋势判断，不是确定性因果结论。')

    # 第6章：技能与标签价值分析（原第8章）
    L("\n## 6. 技能与标签价值分析\n")
    L("*证据等级：A=样本≥100（稳定观察），B=50-99（中等可信），C=20-49（趋势信号），D=<20（仅作观察）*\n")

    all_skills = R.get("skill_value", [])
    # 过滤掉职级标签和技术栈标签
    all_skills = [s for s in all_skills if s["skill"] not in ("产品总监", "Java", "java")]

    # 6.1 方向标签
    direction_tags = [s for s in all_skills if s["category"] == "方向标签"][:8]
    if direction_tags:
        L("\n### 6.1 方向标签（反映岗位方向，不等同于技能）\n")
        L("| 标签 | 样本 | 中位数 | 溢价 | 证据等级 |")
        L("|------|------|--------|------|---------|")
        for s in direction_tags:
            ev = "A" if s["count"]>=100 else "B" if s["count"]>=50 else "C" if s["count"]>=20 else "D"
            L(f"| {s['skill']} | {s['count']} | {s['median']}K | {s['premium']:+.1f}% | {ev} |")

    # 6.2 能力/技能信号
    skill_signals = [s for s in all_skills if s["category"] == "能力/技能信号" and s["count"] >= 20][:8]
    if skill_signals:
        L("\n### 6.2 能力/技能信号（可作为简历或作品集加分项）\n")
        L("| 技能信号 | 样本 | 中位数 | 溢价 | 高薪岗占比 | 普通岗占比 | 证据等级 |")
        L("|---------|------|--------|------|-----------|-----------|---------|")
        for s in skill_signals:
            ev = "A" if s["count"]>=100 else "B" if s["count"]>=50 else "C"
            skill_name = s["skill"]
            if skill_name.lower() == "iaa":
                skill_name = "iaa（应用内广告）"
            L(f"| {skill_name} | {s['count']} | {s['median']}K | {s['premium']:+.1f}% | {s['hs_pct']}% | {s['nm_pct']}% | {ev} |")

    # 6.3 小样本趋势词
    small_sample = [s for s in all_skills if s["category"] == "小样本趋势词"][:6]
    if small_sample:
        L("\n### 6.3 小样本趋势词（仅作观察，不单独下结论）\n")
        L("| 标签 | 样本 | 中位数 | 溢价 | 证据等级 |")
        L("|------|------|--------|------|---------|")
        for s in small_sample:
            skill_name = s["skill"]
            if skill_name.lower() == "iaa":
                skill_name = "iaa（应用内广告）"
            L(f"| {skill_name} | {s['count']} | {s['median']}K | {s['premium']:+.1f}% | D |")

    # 6.4 不适合作为能力结论的标签
    base_skills = [s for s in all_skills if s["category"] == "无区分度标签"][:6]
    if base_skills:
        L("\n### 6.4 不适合作为能力结论的标签（无区分度）\n")
        L("| 标签 | 样本 | 中位数 | 溢价 | 说明 |")
        L("|------|------|--------|------|------|")
        for s in base_skills:
            L(f"| {s['skill']} | {s['count']} | {s['median']}K | {s['premium']:+.1f}% | 普遍出现，无法拉开差距 |")

    # 第7章：通用求职方向判断（原第9章）
    L("\n## 7. 通用求职方向判断\n")
    L("基于高薪占比、P75溢价、岗位数量、样本可信度等数据，将方向分为以下类型：\n")
    L("| 方向类型 | 方向 | 数据依据 | 适合人群 | 求职建议 |")
    L("|---------|------|---------|---------|---------|")
    dirs = R.get("direction_analysis", [])
    used_dirs = set()
    # 第一类：稳定高薪方向（高薪占比>=35%且样本>=100，或P75有正溢价且样本>=50）
    for d in dirs:
        if (d["high_pct"] >= 35 and d["count"] >= 100) or (d.get("p75_premium", 0) > 0 and d["count"] >= 50):
            if d["direction"] in used_dirs:
                continue
            crowd = {"AI/大模型产品": "有AI应用、场景化产品、技术协同或复杂C端经验的人",
                     "策略产品": "有数据分析、推荐/搜索、规则策略、用户分层、AB实验经验的人"}.get(d["direction"], "有对应方向深度经验的求职者")
            L(f"| 稳定高薪方向 | {d['direction']} | {d['count']}个岗位,高薪占比{d['high_pct']}%,P75溢价{d.get('p75_premium',0):+.1f}% | {crowd} | 高薪岗位密集，值得重点投递 |")
            used_dirs.add(d["direction"])
    # 第二类：高薪机会充足但中位数无溢价（高薪占比>=28%，中位数>=0，样本>=100）
    for d in dirs:
        if d["direction"] in used_dirs:
            continue
        if d["high_pct"] >= 28 and d["premium"] >= 0 and d.get("p75_premium", 0) <= 0 and d["count"] >= 100:
            crowd = {"金融产品": "有金融/支付/风控行业背景的求职者，跨行壁垒高",
                     "电商/交易": "有电商/交易/供应链经验的求职者",
                     "商业化/广告": "有广告系统、商业化、ROI优化经验的求职者"}.get(d["direction"], "有对应方向经验的求职者")
            L(f"| 高薪机会多但无中位数溢价 | {d['direction']} | {d['count']}个岗位,高薪占比{d['high_pct']}%,中位数溢价{d['premium']:+.1f}% | {crowd} | 高薪占比>30%但整体薪资与市场持平，需精准筛选JD |")
            used_dirs.add(d["direction"])
    # 第三类：小样本高上限（样本<50，高薪占比>30%）
    for d in dirs:
        if d["direction"] in used_dirs:
            continue
        if d["count"] < 50 and d["high_pct"] > 30:
            crowd = "恰好有匹配经验的求职者，不建议专门转型"
            L(f"| 小样本高上限 | {d['direction']} | {d['count']}个岗位,高薪占比{d['high_pct']}% | {crowd} | 样本少，容易被极端值拉高，仅适合精准投递 |")
            used_dirs.add(d["direction"])
    # 第三b类：天花板高但中位数一般（P90溢价>0，中位数溢价<0，样本>=50）
    for d in dirs:
        if d["direction"] in used_dirs:
            continue
        if d.get("p90_premium", 0) > 0 and d["premium"] < 0 and d["count"] >= 50:
            crowd = "能力较强且有相关经验的候选人，目标高级/专家岗位"
            L(f"| 天花板高但中位数一般 | {d['direction']} | {d['count']}个岗位,中位数溢价{d['premium']:+.1f}%,P90溢价{d.get('p90_premium',0):+.1f}% | {crowd} | 少数高级岗位薪资很好，但大部分岗位薪资一般 |")
            used_dirs.add(d["direction"])
    # 第四类：岗位多但薪资一般（样本>=50，中位数溢价<0）
    for d in dirs:
        if d["direction"] in used_dirs:
            continue
        if d["count"] >= 50 and d["premium"] < 0:
            crowd = {"B端/SaaS/企服": "有业务系统、权限流程、企业服务经验的人",
                     "数据产品": "有数据平台、BI、数仓经验的人"}.get(d["direction"], "需要快速拿到offer或有对应经验的求职者")
            L(f"| 岗位多但薪资一般 | {d['direction']} | {d['count']}个岗位,溢价{d['premium']:+.1f}% | {crowd} | 不适合作为通用冲高薪主线，可作为保底或有相关背景者的机会池 |")
            used_dirs.add(d["direction"])
    # 第五类：不建议主攻（溢价<-20%或样本<20）
    for d in dirs:
        if d["direction"] in used_dirs:
            continue
        if d["premium"] < -20 or d["count"] < 20:
            L(f"| 不建议主攻 | {d['direction']} | {d['count']}个岗位,溢价{d['premium']:+.1f}% | 有强行业背景者除外 | 薪资明显偏低或岗位太少，投入产出比不高 |")
            used_dirs.add(d["direction"])

    # 第8章：公司与行业机会分析（原第4章）
    L("\n## 8. 公司与行业机会分析\n")
    L("*注：部分公司名称为脱敏名称，公司类型来自原始字段或规则识别。公司榜单主要用于观察样本结构，不宜作为精确公司投递排名。*\n")
    L("### 招聘活跃公司 TOP25\n")
    L("| 公司 | 岗位数 | 中位数 | P75 | P90 | 高薪占比 | 行业 | 公司类型 | 主要方向 |")
    L("|------|--------|--------|-----|-----|----------|------|----------|----------|")
    for c in R.get("active_companies", []):
        L(f"| {c['company']} | {c['job_count']} | {c['salary_median']}K | {c['salary_p75']}K | {c['salary_p90']}K | {c['high_pct']}% | {c['industry']} | {c['co_type']} | {c['main_dirs']} |")

    L("\n### 高薪公司 TOP15（≥5个岗位）\n")
    L("| 公司 | 中位数 | P75 | 高薪占比 | 岗位数 | 公司类型 | 主要方向 |")
    L("|------|--------|-----|----------|--------|----------|----------|")
    for c in R.get("salary_companies", []):
        L(f"| {c['company']} | {c['salary_median']}K | {c['salary_p75']}K | {c['high_pct']}% | {c['job_count']} | {c['co_type']} | {c['main_dirs']} |")

    # 第9章：区域分布分析（原第3章）
    L("\n## 9. 北京各区岗位分布\n")
    L("| 区域 | 岗位数 | 中位数 | P75 |")
    L("|------|--------|--------|-----|")
    for a in R.get("area_salary", []):
        L(f"| {a['area']} | {a['count']} | {a['median']}K | {a['p75']}K |")

    L("\n### 商圈级别分布 TOP25\n")
    L("| 商圈 | 岗位数 | 中位数 | P75 |")
    L("|------|--------|--------|-----|")
    for b in R.get("biz_area_salary", []):
        L(f"| {b['biz_area']} | {b['count']} | {b['median']}K | {b['p75']}K |")

    # 第10章
    L("\n## 10. 风险与误区\n")
    L("| 误区 | 为什么危险 | 数据证据 | 如何避免 |")
    L("|------|-----------|---------|---------|")
    for r in R.get("risk_analysis", []):
        L(f"| {r['risk']} | {r['danger']} | {r['evidence']} | {r['avoid']} |")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("  北京产品经理深度招聘市场分析报告（完整版）")
    print("=" * 60)

    print("\n📥 加载数据...")
    data = load_data()
    print(f"   共加载 {len(data)} 条岗位数据")

    if not data:
        print("❌ 数据库为空，无法生成报告")
        sys.exit(1)

    print("\n🔬 深度分析中...")
    R = analyze(data)
    print(f"   有效薪资样本：{R['valid_count']} 条")
    print(f"   薪资中位数：{R['salary_overview']['median']}K/月")
    print(f"   P75 阈值：{R['p75_threshold']}K/月")
    print(f"   高薪岗位（P75+）：{R['high_salary_count']} 个")
    print(f"   聚类方向数：{len(R['direction_analysis'])}")

    print("\n📝 生成 HTML 报告...")
    html = generate_html(R)
    os.makedirs("data", exist_ok=True)
    VERSION = "v18"
    html_path = f"data/产品经理_深度分析_{VERSION}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   HTML 报告已保存：{html_path}")

    print("📝 生成 Markdown 报告...")
    md = generate_markdown(R)
    md_path = f"data/产品经理_深度分析_{VERSION}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"   Markdown 报告已保存：{md_path}")

    abs_html = os.path.abspath(html_path)
    abs_md = os.path.abspath(md_path)
    print(f"\n✅ 完成！")
    print(f"   HTML（可视化）：{abs_html}")
    print(f"   Markdown（给AI）：{abs_md}")

    if sys.platform == "darwin":
        subprocess.run(["open", abs_html])
    elif sys.platform == "win32":
        os.startfile(abs_html)
    else:
        subprocess.run(["xdg-open", abs_html], stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
