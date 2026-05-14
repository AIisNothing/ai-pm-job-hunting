"""
求职方向决策报告（HTML + Markdown 双输出）
============================================
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from models.database import init_db, get_engine
from models.tables import JobRecordDB

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


def load_and_analyze():
    init_db()
    engine = get_engine()
    data = []
    with Session(engine) as s:
        for r in s.query(JobRecordDB).all():
            mid = None
            if r.salary_min is not None and r.salary_max is not None:
                mid = (r.salary_min + r.salary_max) / 2
            skills = json.loads(r.skills_json) if r.skills_json else []
            data.append({
                "title": r.title or "", "company": r.company or "",
                "salary_mid": mid, "skills": skills,
                "direction": classify_direction(r.title or "", skills, r.description or ""),
            })

    valid = [d for d in data if d["salary_mid"] is not None]
    all_mids = [d["salary_mid"] for d in valid]
    overall_median = float(np.median(all_mids))
    p75 = float(np.percentile(all_mids, 75))

    dir_info = {}
    for d_name in set(d["direction"] for d in data):
        jobs = [d for d in valid if d["direction"] == d_name]
        if len(jobs) < 5:
            continue
        sals = [d["salary_mid"] for d in jobs]
        title_counter = Counter(d["title"] for d in jobs)
        skill_counter = Counter()
        company_counter = Counter()
        for d in jobs:
            for sk in d["skills"]:
                if sk and len(sk) < 25:
                    skill_counter[sk] += 1
            if d["company"]:
                company_counter[d["company"]] += 1
        high_count = sum(1 for v in sals if v >= p75)
        dir_info[d_name] = {
            "count": len(jobs),
            "median": round(float(np.median(sals)), 1),
            "p75": round(float(np.percentile(sals, 75)), 1),
            "p90": round(float(np.percentile(sals, 90)), 1),
            "high_pct": round(high_count / len(jobs) * 100, 1),
            "premium": round((float(np.median(sals)) - overall_median) / overall_median * 100, 1),
            "top_titles": [t for t, _ in title_counter.most_common(12)],
            "top_skills": [s for s, _ in skill_counter.most_common(15)],
            "top_companies": [c for c, _ in company_counter.most_common(8)],
        }

    return {
        "total": len(data), "valid": len(valid), "date": datetime.now().strftime("%Y-%m-%d"),
        "overall_median": round(overall_median, 1), "p75": round(p75, 1),
        "directions": dir_info,
    }


DIRECTION_DEEP = {
    "AI/大模型产品": {
        "action": "冲刺",
        "search_titles": ["AI产品经理", "大模型产品经理", "Agent产品经理", "AIGC产品经理", "智能助手产品经理", "AI应用产品经理", "AI工作流产品经理", "对话产品经理"],
        "high_value_jd": ["大模型应用", "Agent", "AIGC", "RAG", "Prompt", "多模态", "智能助手", "AI工作流", "AI交互", "模型效果评估", "场景落地", "AI策略"],
        "low_value_jd": ["只做AI工具运营不涉及产品设计", "只是用AI生成内容不涉及产品架构", "只写PRD协调研发跟进上线", "过度强调算法训练和模型调参（这是算法岗不是产品岗）"],
        "real_skills": ["场景判断能力：判断哪些场景适合用AI解决", "大模型能力边界理解：知道模型能做什么不能做什么", "AI交互设计：对话式/生成式产品的交互范式", "Agent/Prompt/RAG基础理解：不需要会写代码但要理解原理", "AI效果评估：如何定义和衡量AI产品的好坏", "从技术能力到用户价值的转化：不是炫技而是解决问题"],
        "migration": {"direct": ["场景化产品设计经验 → AI在家庭场景的应用（语音控制、智能推荐、自动化）", "用户体验设计 → AI交互体验设计（对话式、生成式）"], "reframe": ["智能家居场景推荐 → 基于用户行为的智能推荐产品", "设备语音控制 → 语音交互/多模态交互产品", "场景自动化 → AI Agent自动化工作流"], "portfolio": "准备一份「AI+智能家居」交叉作品集：展示AI在家庭场景的应用设计"},
        "gaps": ["大模型应用理解（Prompt/Agent/RAG原理，2-3周可入门）", "AI产品评估框架（效果指标定义，1-2周可学）", "AI行业案例积累（研究10+AI产品案例，1周）"],
        "gap_note": "不需要学算法和模型训练。重点是理解大模型能力边界、掌握AI产品设计方法论、能讲清楚AI如何在具体场景创造用户价值。",
    },
    "策略产品": {
        "action": "冲刺",
        "search_titles": ["策略产品经理", "搜索推荐产品经理", "推荐策略产品经理", "分发策略产品经理", "风控策略产品经理", "用户增长策略产品经理", "算法策略产品经理"],
        "high_value_jd": ["推荐策略", "搜索排序", "召回", "分发", "用户分层", "AB实验", "指标体系", "CTR", "CVR", "留存", "转化", "策略迭代", "算法协同"],
        "low_value_jd": ["只做运营活动策划不涉及策略机制", "只做后台配置不涉及策略设计", "只写需求文档不参与策略决策", "过度强调销售策略（这是销售岗）"],
        "real_skills": ["指标体系搭建：定义核心指标和拆解逻辑", "策略变量设计：确定哪些变量影响结果", "AB实验设计：实验分组、样本量、显著性判断", "推荐/搜索/分发基础理解：不需要写算法但要理解原理", "数据复盘：从数据中发现问题和机会", "规则与算法协同：知道什么用规则、什么用算法"],
        "migration": {"direct": ["场景化推荐经验 → 基于用户行为的推荐策略", "数据分析能力（DAU/留存/转化）→ 策略效果评估"], "reframe": ["智能家居场景Tab → 基于用户画像的内容分发策略", "设备控制率优化 → 指标驱动的策略迭代", "场景自动化规则 → 规则引擎+策略产品"], "portfolio": "准备一份「策略产品思维」作品集：展示如何用数据驱动策略迭代"},
        "gaps": ["推荐/搜索算法基础理解（2-3周可入门）", "AB实验方法论（1-2周可学）", "策略产品案例积累（研究美团/字节/快手的策略产品，1周）"],
        "gap_note": "有数据分析能力和场景化思维的候选人有基础。核心差距是推荐/搜索的技术理解和AB实验方法论，这些可以短期补齐。",
    },
    "商业化/广告": {
        "action": "冲刺",
        "search_titles": ["商业化产品经理", "广告产品经理", "商业化广告产品经理", "营销平台产品经理", "投放产品经理", "变现产品经理", "海外商业化产品经理"],
        "high_value_jd": ["广告系统", "投放平台", "ROI", "转化漏斗", "eCPM", "竞价", "定向", "归因", "商业闭环", "变现策略", "流量分配"],
        "low_value_jd": ["只做营销活动运营", "只做销售支持和客户对接", "只做内容营销不涉及广告系统", "过度强调客户资源和BD能力"],
        "real_skills": ["广告系统架构理解：竞价、定向、归因、计费", "商业化指标体系：eCPM、CTR、CVR、ROI", "流量与变现的平衡：用户体验vs商业收入", "投放策略设计：人群定向、出价策略、预算分配", "数据驱动的商业决策：从数据中找到变现机会"],
        "migration": {"direct": ["C端流量理解 → 流量变现和用户价值评估"], "reframe": ["场景化产品 → 场景化广告/营销触达", "数据分析能力 → 商业化数据分析（ROI/转化漏斗）"], "portfolio": "准备一份「商业化思维」作品集：展示如何在不损害用户体验的前提下设计变现策略"},
        "gaps": ["广告系统基础知识（竞价/定向/归因，2-3周）", "商业化指标体系（eCPM/CTR/CVR，1周）", "行业案例（研究字节/快手/百度的广告系统，1周）"],
        "gap_note": "商业化方向转型成本中等。有C端产品和数据分析基础的候选人有优势，核心差距是广告系统的专业知识。建议先从「营销平台产品经理」切入，比纯广告系统门槛低。",
    },
    "增长产品": {
        "action": "冲刺",
        "search_titles": ["用户增长产品经理", "增长产品经理", "增长策略产品经理", "拉新产品经理", "留存产品经理", "产品经理（增长方向）", "海外增长产品经理"],
        "high_value_jd": ["用户增长", "拉新", "留存", "转化", "激活", "AB实验", "增长模型", "裂变", "AARRR", "LTV", "用户生命周期", "增长飞轮"],
        "low_value_jd": ["只做活动运营不涉及增长机制", "只做渠道投放不涉及产品增长", "只做数据报表不参与增长决策"],
        "real_skills": ["增长模型搭建：AARRR/用户生命周期", "AB实验设计与分析", "用户分层与精细化运营", "增长杠杆识别：找到ROI最高的增长手段", "数据驱动的增长决策"],
        "migration": {"direct": ["DAU/留存/转化指标经验 → 增长核心指标体系", "C端用户理解 → 用户增长洞察"], "reframe": ["设备控制率优化 → 用户激活和留存优化", "场景使用率提升 → 功能渗透率和使用频次增长"], "portfolio": "准备一份「增长实验」案例：展示如何通过数据分析发现增长机会→设计实验→验证效果→规模化"},
        "gaps": ["增长方法论体系（AARRR/增长飞轮，1-2周）", "AB实验实践（可结合过往数据分析经验，1周）"],
        "gap_note": "有数据分析能力和C端经验的候选人有天然优势。核心差距是系统化的增长方法论，短期可以补齐。",
    },
    "智能硬件/IoT": {
        "action": "主投（需IoT背景）",
        "search_titles": ["IoT产品经理", "智能硬件产品经理", "智能家居产品经理", "硬件产品经理", "机器人产品经理", "设备平台产品经理", "智能穿戴产品经理"],
        "high_value_jd": ["智能硬件", "设备接入", "设备控制", "端云协同", "多端控制", "场景联动", "设备状态", "自动化", "Matter", "机器人", "OTA", "固件"],
        "low_value_jd": ["过度强调硬件结构设计和模具开发（这是硬件工程岗）", "过度强调供应链和生产制造管理", "只做项目管理不负责产品策略和体验", "只做售后支持不涉及产品设计"],
        "real_skills": ["设备控制链路理解：从用户操作到设备响应的全链路", "端云协同理解：设备端、云端、客户端的协作", "多端体验设计：手机/音箱/屏幕等多终端一致性", "场景联动设计：多设备协同的场景编排", "设备状态与异常处理：离线、超时、冲突等边界情况"],
        "migration": {"direct": ["智能家居中枢产品经验 → 完全对口", "多端协同能力 → 核心竞争力", "设备控制体验 → 直接匹配", "场景联动设计 → 核心能力"], "reframe": [], "portfolio": "不需要额外作品集，你的真实项目经验就是最好的证明。简历重点突出多端协同、场景联动、设备控制的具体成果。"},
        "gaps": ["如涉及机器人/具身智能方向，需补充机器人产品知识"],
        "gap_note": "有IoT/智能硬件经验的候选人可直接匹配。岗位数量有限（约200个），不能只投这个方向。",
    },
    "平台产品": {
        "action": "精准投",
        "search_titles": ["平台产品经理", "中台产品经理", "开放平台产品经理", "基础平台产品经理", "技术产品经理（平台方向）", "规则引擎产品经理"],
        "high_value_jd": ["平台化", "配置化", "规则引擎", "权限体系", "开放能力", "API", "多端一致性", "状态流转", "能力复用", "治理机制", "中台"],
        "low_value_jd": ["只做后台CRUD页面", "只做内部工具没有平台抽象", "只做项目管理不涉及平台设计"],
        "real_skills": ["业务抽象能力：从具体业务中提炼通用能力", "规则引擎设计：可配置的业务规则体系", "权限与状态体系：复杂的权限控制和状态流转", "多端一致性：跨端体验和数据一致性", "复杂项目治理：多团队协同的大型项目管理"],
        "migration": {"direct": ["多端协同经验 = 平台化思维的最佳证明", "规则统一经验 → 规则引擎设计", "复杂项目推进 → 平台项目治理"], "reframe": ["设备控制规则统一 → 业务规则引擎设计", "多端体验一致性 → 跨端平台能力建设", "新国标合规适配 → 复杂规则体系重构"], "portfolio": "准备一份「平台化设计」作品集：展示如何将设备控制能力从单一产品抽象为平台化能力"},
        "gaps": ["开放平台/API设计经验（如果目标是开放平台方向）"],
        "gap_note": "有多端协同或复杂规则设计经验的候选人有优势。岗位数量较少（约84个），适合精准投递而非海投。",
    },
    "车载/智能座舱": {
        "action": "精准投",
        "search_titles": ["车载产品经理", "智能座舱产品经理", "自动驾驶产品经理", "车机产品经理", "车联网产品经理", "车家互联产品经理"],
        "high_value_jd": ["智能座舱", "车机系统", "车载语音", "HMI", "车联网", "OTA", "车家互联", "自动驾驶", "L2/L3/L4", "地图导航"],
        "low_value_jd": ["过度强调汽车销售和经销商管理", "过度强调汽车金融和保险", "只做车载内容运营不涉及座舱产品"],
        "real_skills": ["座舱交互设计：车载场景的特殊交互规范", "车规级开发流程：与消费电子的差异", "多端协同（车-手机-家）：车家互联场景", "安全优先设计：驾驶场景的安全约束"],
        "migration": {"direct": ["多端协同（车是多端之一）→ 车家互联产品", "场景化产品设计 → 车内场景设计"], "reframe": ["智能家居场景 → 车内智能场景（类似的场景化思维）", "设备控制体验 → 车载设备交互体验"], "portfolio": "准备一份「车家互联」方向作品集：展示从智能家居到车载的场景迁移思考"},
        "gaps": ["车规级开发流程（与消费电子差异大，需要了解）", "座舱交互规范（HMI设计原则，1-2周可学）", "汽车行业基础知识"],
        "gap_note": "岗位数量少（约38个），有多端协同经验的候选人在车家互联方向有优势。适合精准投递有车家互联需求的公司。",
    },
    "B端/SaaS/企服": {
        "action": "保底",
        "search_titles": ["B端产品经理", "SaaS产品经理", "企业服务产品经理", "后台产品经理", "中台产品经理", "CRM产品经理", "ERP产品经理"],
        "high_value_jd": ["SaaS", "企业服务", "客户成功", "续费率", "ARR", "多租户", "权限体系", "工作流", "审批流", "数据看板"],
        "low_value_jd": ["只做内部后台工具", "只做项目交付没有产品化", "过度强调客户定制开发", "只做实施和部署"],
        "real_skills": ["B端业务流程设计", "SaaS产品架构（多租户、权限、配置化）", "客户需求管理和优先级决策", "商业指标理解（ARR、续费率、NPS）"],
        "migration": {"direct": ["复杂项目推进 → B端大客户项目管理", "跨团队协同 → B端多方协同"], "reframe": ["平台规则设计 → B端权限和工作流设计", "多端体验一致性 → B端多角色体验设计"], "portfolio": ""},
        "gaps": ["B端业务流程设计经验", "SaaS产品架构理解", "B端商业指标体系"],
        "gap_note": "B端方向岗位多（512个）但薪资溢价为负（-7.1%），适合作为保底方向确保有offer，不建议作为主攻方向。",
    },
}

LOW_RECOMMEND = {
    "金融产品": "行业壁垒高，需要金融业务知识和牌照理解，与候选人背景弱匹配。",
    "电商/交易": "电商产品需要交易链路和供应链经验，与候选人背景匹配度低。",
    "游戏产品": "游戏产品需要游戏行业经验和玩家洞察，与候选人背景几乎无关。",
    "医疗健康": "医疗产品需要医疗行业知识和合规理解，转型成本高。",
    "教育产品": "教育行业整体收缩，岗位数量和薪资都不理想。",
    "内容/社区": "与候选人背景有一定距离，如果目标是内容推荐/分发方向，可以用策略产品的思路切入。",
    "数据产品": "薪资溢价为负（-7.1%），且需要数据平台/BI工具的深度经验。候选人的数据分析能力更适合在其他方向中作为加分项。",
}


# ═══════════════════════════════════════════════════════════════════════════
# 简历包装方向
# ═══════════════════════════════════════════════════════════════════════════

RESUME_PACKAGING = [
    {"direction": "IoT/智能硬件", "identity": "智能家居/IoT中枢产品经理", "first_para": "X年智能家居/IoT产品经验，负责中枢入口产品，覆盖设备控制、场景联动、多端协同", "key_project": "智能家居中枢首页产品、多端控制规则统一、场景联动设计", "keywords": "智能硬件、设备控制、端云协同、多端协同、场景联动、Matter"},
    {"direction": "平台产品", "identity": "多端协同/复杂规则平台产品经理", "first_para": "X年平台产品经验，负责多端协同平台和规则引擎设计，支撑XX+品类设备接入", "key_project": "多端控制规则引擎、设备接入平台、跨端体验一致性", "keywords": "平台化、规则引擎、配置化、多端一致性、能力复用、治理机制"},
    {"direction": "AI产品", "identity": "AI应用场景产品经理", "first_para": "X年C端产品经验，擅长场景化产品设计和AI应用落地，有智能推荐/语音交互/自动化产品经验", "key_project": "智能家居场景推荐、语音交互产品、场景自动化", "keywords": "AI应用、场景化AI、智能推荐、语音交互、用户体验、数据驱动"},
    {"direction": "策略产品", "identity": "场景推荐/用户策略产品经理", "first_para": "X年C端产品经验，擅长基于数据的策略设计和效果验证，有推荐策略和指标体系经验", "key_project": "场景推荐策略、指标体系搭建、数据驱动迭代", "keywords": "推荐策略、指标体系、AB实验、数据驱动、用户分层、策略迭代"},
    {"direction": "增长产品", "identity": "数据驱动的C端增长产品经理", "first_para": "X年C端产品经验，关注DAU/留存/转化等核心增长指标，有数据驱动的产品迭代经验", "key_project": "用户留存优化、场景渗透率提升、数据分析驱动迭代", "keywords": "用户增长、留存、转化、DAU、AB实验、增长模型"},
    {"direction": "车载/智能座舱", "identity": "车家互联/多端场景协同产品经理", "first_para": "X年多端协同产品经验，覆盖手机/电视/音箱/车/手表五端，擅长跨端场景设计", "key_project": "多端协同产品、场景化设计、车家互联方案", "keywords": "车家互联、多端协同、场景化、智能座舱、跨端体验"},
    {"direction": "商业化/广告", "identity": "C端商业化/变现产品经理", "first_para": "X年C端产品经验，有流量理解和数据分析能力，关注用户价值和商业转化", "key_project": "用户转化漏斗优化、增值服务设计、数据驱动决策", "keywords": "商业化、转化漏斗、ROI、数据驱动、用户价值、变现策略"},
]

# ═══════════════════════════════════════════════════════════════════════════
# JD搜索词与筛选规则
# ═══════════════════════════════════════════════════════════════════════════

JD_SEARCH_RULES = [
    {"direction": "AI产品", "main_kw": "AI产品经理、大模型产品经理、Agent产品经理", "expand_kw": "AIGC产品经理、智能助手产品、AI应用产品", "caution_kw": "AI运营、AI标注、AI训练师", "note": "注意区分AI产品设计vs AI工具使用vs AI内容运营"},
    {"direction": "策略产品", "main_kw": "策略产品经理、搜索推荐产品、推荐策略产品", "expand_kw": "分发策略、增长策略产品、风控策略产品", "caution_kw": "销售策略、市场策略", "note": "策略产品=用数据和规则优化产品效果，不是营销策略"},
    {"direction": "商业化/广告", "main_kw": "商业化产品经理、广告产品经理、变现产品", "expand_kw": "营销平台产品、投放产品、海外商业化", "caution_kw": "广告销售、广告运营、媒介", "note": "商业化产品=设计变现机制，不是卖广告"},
    {"direction": "增长产品", "main_kw": "增长产品经理、用户增长产品、留存产品", "expand_kw": "拉新产品、激活产品、海外增长", "caution_kw": "增长运营、活动运营", "note": "增长产品=设计增长机制，不是做活动"},
    {"direction": "智能硬件/IoT", "main_kw": "IoT产品经理、智能硬件产品、智能家居产品", "expand_kw": "机器人产品、设备平台产品、智能穿戴", "caution_kw": "硬件工程师、结构工程师、供应链", "note": "注意区分产品经理vs硬件工程vs供应链管理"},
    {"direction": "平台产品", "main_kw": "平台产品经理、中台产品经理、开放平台产品", "expand_kw": "基础平台产品、技术产品（平台）", "caution_kw": "后台产品（可能只是CRUD）", "note": "平台产品=业务抽象+能力复用，不是做后台页面"},
    {"direction": "车载/智能座舱", "main_kw": "车载产品经理、智能座舱产品、车机产品", "expand_kw": "车联网产品、自动驾驶产品、车家互联", "caution_kw": "汽车销售、汽车金融、经销商", "note": "注意区分座舱产品vs汽车销售vs汽车金融"},
    {"direction": "B端/SaaS", "main_kw": "B端产品经理、SaaS产品经理、企业服务产品", "expand_kw": "CRM产品、ERP产品、中后台产品", "caution_kw": "实施工程师、项目交付、客户成功", "note": "B端产品=设计产品，不是做项目交付"},
    {"direction": "数据产品", "main_kw": "数据产品经理、数据平台产品、BI产品", "expand_kw": "数据中台产品、大数据产品", "caution_kw": "数据分析师、数据工程师", "note": "数据产品=设计数据工具/平台，不是做数据分析"},
    {"direction": "C端体验", "main_kw": "C端产品经理、用户产品经理、App产品经理", "expand_kw": "体验产品、用户体验产品", "caution_kw": "UI设计师、交互设计师", "note": "保底方向，匹配度高但薪资溢价一般"},
]

JD_GOOD_SIGNALS = [
    {"signal": "从0到1 / 负责人 / Owner", "why": "说明需要独立决策能力，对应高级岗位和高薪", "match_exp": "有独立负责产品线经验的候选人", "resume_kw": "独立负责、从0到1、产品owner"},
    {"signal": "指标体系 / 留存 / 转化 / DAU", "why": "说明重视数据驱动，与候选人数据分析能力匹配", "match_exp": "有指标体系搭建经验的候选人", "resume_kw": "指标体系、数据驱动、AB实验"},
    {"signal": "平台化 / 配置化 / 规则引擎", "why": "说明需要系统抽象能力，与多端协同经验高度匹配", "match_exp": "有平台化/规则引擎设计经验的候选人", "resume_kw": "平台化、规则引擎、配置化、多端一致性"},
    {"signal": "AI Agent / 大模型应用 / 智能助手", "why": "AI方向高薪岗位，可用场景化经验切入", "match_exp": "有场景化产品/AI应用经验的候选人", "resume_kw": "AI应用、场景化AI、智能推荐"},
    {"signal": "多端 / 端云 / 设备 / IoT", "why": "与候选人核心经验完全匹配", "match_exp": "有IoT/多端协同经验的候选人", "resume_kw": "多端协同、设备控制、端云协同、场景联动"},
    {"signal": "AB实验 / 策略优化 / 用户分层", "why": "策略/增长方向高价值信号", "match_exp": "数据分析驱动产品迭代", "resume_kw": "AB实验、策略迭代、用户分层、数据驱动"},
    {"signal": "商业闭环 / ROI / 变现 / 转化漏斗", "why": "商业化方向高价值信号", "match_exp": "用户转化和数据分析经验", "resume_kw": "商业闭环、转化漏斗、ROI、数据驱动"},
]

JD_BAD_SIGNALS = [
    {"signal": "只写「撰写PRD、协调研发、跟进上线」", "risk": "纯执行岗，薪资天花板低", "why_bad": "没有业务判断和决策权，做的是需求翻译而非产品设计", "how_judge": "看JD是否提到业务指标、产品方向、独立负责"},
    {"signal": "过度强调供应链、结构、生产制造", "risk": "硬件工程岗而非产品岗", "why_bad": "考察的是供应链管理能力而非产品设计能力", "how_judge": "看JD是否提到用户体验、产品策略、数据分析"},
    {"signal": "过度强调客户资源、销售支持", "risk": "销售支持岗而非产品岗", "why_bad": "核心是客户关系而非产品能力", "how_judge": "看JD是否提到产品设计、需求分析、数据驱动"},
    {"signal": "过度强调金融风控、信贷、强行业壁垒", "risk": "行业壁垒高，转型成本大", "why_bad": "需要深厚的金融业务知识，短期难以补齐", "how_judge": "除非有金融背景，否则谨慎投递"},
    {"signal": "没有明确负责范围和业务指标", "risk": "可能是打杂岗", "why_bad": "职责不清晰说明岗位定位不明确", "how_judge": "好的JD会明确写负责什么业务、关注什么指标"},
    {"signal": "只有运营活动，没有产品机制", "risk": "运营岗而非产品岗", "why_bad": "做活动策划而非产品设计", "how_judge": "看JD是否提到产品架构、功能设计、系统设计"},
    {"signal": "只是AI工具使用或AI内容运营", "risk": "不是真正的AI产品岗", "why_bad": "用AI工具≠设计AI产品", "how_judge": "看JD是否提到AI产品设计、模型效果评估、AI交互设计"},
]


ABILITY_STRUCTURE = [
    {"ability": "业务闭环能力", "jd_desc": "从需求定义到上线运营的完整闭环、独立负责业务线、端到端owner", "behind": "不只是执行需求，而是能独立判断做什么、为什么做、怎么衡量做得好不好", "directions": "所有高薪方向", "ordinary_vs_high": "普通PM：接需求→写PRD→跟开发→上线。高薪PM：发现问题→定义指标→设计方案→推动落地→复盘迭代", "candidate_proof": "某核心产品线：从用户痛点发现→方案设计→跨团队推动→数据验证的完整闭环", "resume_expr": "「负责某核心产品线从0到1，独立完成需求定义→方案设计→跨N团队推动→上线后核心指标提升XX%的完整闭环」"},
    {"ability": "指标驱动能力", "jd_desc": "数据驱动、指标体系、AB实验、ROI、留存、转化、DAU", "behind": "能用数据做决策，而不是凭感觉。能定义指标、拆解指标、用数据验证假设", "directions": "策略/增长/商业化/AI产品", "ordinary_vs_high": "普通PM：看数据报表。高薪PM：定义指标体系→设计实验→分析结果→驱动迭代", "candidate_proof": "某产品核心指标体系：定义核心指标→监控异常→定位问题→优化方案→效果验证", "resume_expr": "「建立核心业务指标/用户留存/转化三级指标体系，通过数据分析驱动N轮产品迭代，核心指标提升XX%」"},
    {"ability": "复杂系统抽象能力", "jd_desc": "平台化、配置化、规则引擎、多端一致性、系统架构", "behind": "能从具体业务中提炼通用能力，设计可扩展的产品架构", "directions": "平台产品/B端/IoT", "ordinary_vs_high": "普通PM：做一个功能。高薪PM：设计一套可配置、可扩展、多端复用的产品体系", "candidate_proof": "某复杂系统规则统一：将多端各自的业务逻辑抽象为统一规则引擎，支撑XX+业务场景", "resume_expr": "「设计统一业务规则引擎，将多端业务逻辑平台化，支撑XX+业务场景接入，实现配置化管理」"},
    {"ability": "策略/算法协同能力", "jd_desc": "推荐策略、搜索排序、算法协同、策略迭代、模型效果", "behind": "理解算法能做什么，能和算法团队有效协作，能设计策略实验", "directions": "策略/AI/增长/商业化", "ordinary_vs_high": "普通PM：提需求给算法团队。高薪PM：定义策略目标→设计策略变量→协同算法实现→AB验证→迭代优化", "candidate_proof": "某场景化推荐：定义推荐策略→与算法团队协同实现→AB验证效果→迭代优化", "resume_expr": "「负责某产品推荐策略，定义推荐目标和策略变量，协同算法团队实现，核心场景使用率提升XX%」"},
    {"ability": "AI应用落地能力", "jd_desc": "大模型应用、Agent、AIGC、智能助手、AI交互、Prompt", "behind": "能判断AI在哪些场景有价值，能设计AI产品的交互和评估体系", "directions": "AI/大模型产品", "ordinary_vs_high": "普通PM：用AI工具。高薪PM：判断场景→设计AI交互→定义评估指标→持续优化AI效果", "candidate_proof": "某AI应用场景：在具体业务场景中落地AI能力（语音交互/智能推荐/自动化等），体现AI应用思维", "resume_expr": "「探索AI在具体业务场景的应用，设计智能交互/场景自动化/智能推荐方案，用户使用率提升XX%」"},
    {"ability": "商业化变现能力", "jd_desc": "商业闭环、ROI、变现、投放、eCPM、转化漏斗", "behind": "理解商业模式，能在用户体验和商业收入之间找到平衡", "directions": "商业化/广告/增长", "ordinary_vs_high": "普通PM：做功能。高薪PM：理解商业模式→设计变现策略→平衡体验和收入→用ROI衡量效果", "candidate_proof": "C端产品的用户价值理解 + 数据分析能力 → 可以迁移到商业化场景", "resume_expr": "「负责某产品增值服务/商业化设计，建立用户付费转化漏斗，付费转化率提升XX%」（如有相关经验）"},
    {"ability": "负责人/Owner能力", "jd_desc": "独立负责、从0到1、业务owner、产品负责人、带团队", "behind": "不只是执行者，而是决策者。能独立判断方向、分配资源、为结果负责", "directions": "所有高薪方向（尤其是资深/专家/负责人级别）", "ordinary_vs_high": "普通PM：完成分配的任务。高薪PM：定义方向→拆解目标→分配资源→推动执行→为结果负责", "candidate_proof": "某产品线Owner：独立负责产品方向判断、优先级决策、跨团队资源协调", "resume_expr": "「作为产品Owner独立负责某核心产品线，制定年度产品规划，协调N个团队资源，达成年度OKR」"},
    {"ability": "跨团队复杂项目推进能力", "jd_desc": "跨团队协同、复杂项目管理、多方协调、推动落地", "behind": "能在多团队、多利益方的复杂环境中推动项目落地", "directions": "平台/B端/IoT/车载", "ordinary_vs_high": "普通PM：协调2-3个团队。高薪PM：在5+团队、多利益方、复杂约束下推动大型项目按期交付", "candidate_proof": "某合规/重构项目：协调多个团队（硬件/后端/前端/测试等），在复杂约束下完成大型项目交付", "resume_expr": "「主导某复杂项目的系统重构，协调N个团队完成XX项适配，项目按期交付且零风险」"},
]


# ═══════════════════════════════════════════════════════════════════════════
# Markdown 报告生成
# ═══════════════════════════════════════════════════════════════════════════

def generate_markdown(R):
    dirs = R["directions"]
    L = []
    A = L.append

    A("# 求职方向决策报告")
    A(f"\n数据基础：{R['total']}个岗位 | 北京·3-10年·本科+·30K+ | {R['date']}")
    A(f"整体中位数：{R['overall_median']}K | P75阈值：{R['p75']}K")

    # ── 第1章：决策矩阵 ──
    A("\n---\n\n## 一、求职方向决策矩阵\n")
    A("| 方向 | 岗位数 | 中位数 | P75 | P90 | 高薪占比 | 溢价 | 推荐动作 | 一句话判断 |")
    A("|------|--------|--------|-----|-----|----------|------|----------|-----------|")

    action_map = {}
    for d_name in ["AI/大模型产品", "策略产品", "商业化/广告", "增长产品", "智能硬件/IoT", "平台产品", "车载/智能座舱", "B端/SaaS/企服", "数据产品", "用户体验/C端", "金融产品", "电商/交易", "内容/社区"]:
        if d_name not in dirs:
            continue
        d = dirs[d_name]
        deep = DIRECTION_DEEP.get(d_name)
        action = deep["action"] if deep else "不建议" if d_name in LOW_RECOMMEND else "保底"
        action_map[d_name] = action

        # 一句话判断
        if deep:
            if action == "冲刺":
                judge = f"薪资潜力高（溢价{d['premium']:+.1f}%），但需补能力。用场景化经验切入。"
            elif action == "主投":
                judge = f"背景高度匹配，成功率最高。{'注意岗位数量有限（'+str(d['count'])+'个），精准投递。' if d['count'] < 100 else ''}"
            elif action == "精准投":
                judge = f"有迁移优势但岗位少（{d['count']}个），选择性投递。"
            else:
                judge = f"薪资溢价{d['premium']:+.1f}%，适合保底确保有offer。"
        elif d_name in LOW_RECOMMEND:
            judge = LOW_RECOMMEND[d_name][:40] + "..."
        else:
            judge = "与背景匹配度低，不建议主攻。"

        sample_note = "⚠️小样本" if d["count"] < 50 else ""
        A(f"| {d_name} | {d['count']}{sample_note} | {d['median']}K | {d['p75']}K | {d['p90']}K | {d['high_pct']}% | {d['premium']:+.1f}% | **{action}** | {judge} |")

    # 低推荐方向
    for d_name, reason in LOW_RECOMMEND.items():
        if d_name in dirs and d_name not in action_map:
            d = dirs[d_name]
            A(f"| {d_name} | {d['count']} | {d['median']}K | {d['p75']}K | {d['p90']}K | {d['high_pct']}% | {d['premium']:+.1f}% | **不建议** | {reason[:50]} |")

    A("\n### 决策总结\n")
    A("- **冲刺方向（薪资高但需补能力）：** AI/大模型产品、策略产品、商业化/广告、增长产品")
    A("- **主投方向（匹配度高成功率最高）：** 智能硬件/IoT、平台产品")
    A("- **精准投（有迁移优势但岗位少）：** 车载/智能座舱")
    A("- **保底方向（机会多确保有offer）：** B端/SaaS/企服、用户体验/C端")
    A("- **不建议主攻：** 金融产品、电商/交易、游戏、医疗、教育、数据产品（薪资溢价为负）")

    # ── 第2章：重点方向深度拆解 ──
    A("\n---\n\n## 二、重点方向深度拆解\n")

    for d_name in ["AI/大模型产品", "策略产品", "商业化/广告", "智能硬件/IoT", "平台产品", "增长产品", "车载/智能座舱", "B端/SaaS/企服"]:
        deep = DIRECTION_DEEP.get(d_name)
        d = dirs.get(d_name)
        if not deep or not d:
            continue

        A(f"\n### {d_name}\n")
        A(f"**推荐动作：{deep['action']}**\n")

        # 数据依据
        A(f"**数据依据：** {d['count']}个岗位，中位数{d['median']}K，P75={d['p75']}K，P90={d['p90']}K，高薪占比{d['high_pct']}%，溢价{d['premium']:+.1f}%")
        if d["count"] < 50:
            A(f"⚠️ 样本量较小（{d['count']}个），结论需谨慎。适合精准投递，不适合海投。")
        A("")

        # 搜索标题
        A("**适合搜索的岗位标题：**")
        for t in deep["search_titles"]:
            A(f"- {t}")

        # 数据库中真实出现的标题
        A(f"\n**数据库中实际出现的岗位标题TOP8：**")
        for t in d["top_titles"][:8]:
            A(f"- {t}")

        # 高价值JD关键词
        A(f"\n**高价值JD关键词（看到这些值得投）：**")
        A(f"{', '.join(deep['high_value_jd'])}")

        # 低价值JD信号
        A(f"\n**低价值JD信号（看到这些要谨慎）：**")
        for s in deep["low_value_jd"]:
            A(f"- ⚠️ {s}")

        # 真正考察的能力
        A(f"\n**这个方向真正考察什么能力：**")
        for s in deep["real_skills"]:
            A(f"- {s}")

        # 经验迁移
        mig = deep["migration"]
        A(f"\n**候选人经验如何迁移：**")
        if mig["direct"]:
            A("直接匹配：")
            for m in mig["direct"]:
                A(f"- ✅ {m}")
        if mig["reframe"]:
            A("换一种表达：")
            for m in mig["reframe"]:
                A(f"- 🔄 {m}")
        if mig["portfolio"]:
            A(f"作品集建议：{mig['portfolio']}")

        # 需要补的能力
        A(f"\n**需要补什么能力：**")
        for g in deep["gaps"]:
            A(f"- {g}")
        A(f"\n{deep['gap_note']}")

    # ── 第3章：高薪JD能力结构 ──
    A("\n---\n\n## 三、高薪JD背后的能力结构\n")
    A("| 能力 | JD常见描述 | 背后考察 | 对应方向 | 普通PM vs 高薪PM | 候选人如何证明 | 简历表达 |")
    A("|------|-----------|---------|---------|-----------------|-------------|---------|")
    for ab in ABILITY_STRUCTURE:
        A(f"| {ab['ability']} | {ab['jd_desc'][:30]} | {ab['behind'][:30]} | {ab['directions'][:15]} | {ab['ordinary_vs_high'][:40]} | {ab['candidate_proof'][:40]} | {ab['resume_expr'][:40]} |")

    # 详细版
    A("\n### 详细说明\n")
    for ab in ABILITY_STRUCTURE:
        A(f"**{ab['ability']}**\n")
        A(f"- JD常见描述：{ab['jd_desc']}")
        A(f"- 背后考察：{ab['behind']}")
        A(f"- 对应方向：{ab['directions']}")
        A(f"- 普通PM vs 高薪PM：{ab['ordinary_vs_high']}")
        A(f"- 候选人如何证明：{ab['candidate_proof']}")
        A(f"- 简历表达：{ab['resume_expr']}\n")

    # ── 第4章：JD搜索词与筛选规则 ──
    A("\n---\n\n## 四、JD搜索词与筛选规则\n")

    A("### 各方向搜索关键词\n")
    A("| 方向 | 主搜关键词 | 拓展关键词 | 谨慎关键词 | 说明 |")
    A("|------|-----------|-----------|-----------|------|")
    for r in JD_SEARCH_RULES:
        A(f"| {r['direction']} | {r['main_kw']} | {r['expand_kw']} | {r['caution_kw']} | {r['note']} |")

    A("\n### 值得投的JD信号\n")
    A("| JD信号 | 为什么值得投 | 适合匹配的经历 | 简历关键词 |")
    A("|--------|-----------|---------------|-----------|")
    for s in JD_GOOD_SIGNALS:
        A(f"| {s['signal']} | {s['why']} | {s['match_exp']} | {s['resume_kw']} |")

    A("\n### 谨慎投的JD信号\n")
    A("| JD信号 | 风险 | 为什么不适合 | 如何判断 |")
    A("|--------|------|-----------|---------|")
    for s in JD_BAD_SIGNALS:
        A(f"| {s['signal']} | {s['risk']} | {s['why_bad']} | {s['how_judge']} |")

    # ── 第5章：个人背景匹配 ──
    A("\n---\n\n## 五、个人背景匹配与方向选择\n")

    A("### 5.1 成功率主线（最容易拿到面试和offer）\n")
    A("| 方向 | 为什么匹配 | 可迁移经历 | 目标JD关键词 | 简历包装方式 | 主要短板 |")
    A("|------|-----------|-----------|-------------|-------------|---------|")
    A("| 智能硬件/IoT | 核心经验完全对口 | 智能家居中枢、设备控制、场景联动、多端协同 | 智能硬件、IoT、设备控制、端云协同 | 直接用真实经验，突出多端协同和场景联动 | 岗位数量有限（~200个） |")
    A("| 平台产品 | 多端协同=平台化思维 | 规则统一、多端一致性、复杂项目推进 | 平台化、规则引擎、配置化、多端一致性 | 把多端控制规则统一包装为平台化能力 | 岗位数量少（~84个），需精准投 |")
    A("| 用户体验/C端 | C端产品经验直接匹配 | 首页产品、用户体验设计、数据驱动 | C端产品、用户体验、App产品 | 突出C端全流程经验和数据驱动 | 薪资溢价为负，适合保底 |")

    A("\n### 5.2 薪资冲刺线（薪资高但需补能力）\n")
    A("| 方向 | 为什么薪资潜力高 | 候选人当前差距 | 如何补齐可信度 | 适合投的JD | 不适合投的JD |")
    A("|------|----------------|-------------|-------------|-----------|------------|")
    for d_name in ["AI/大模型产品", "策略产品", "商业化/广告", "增长产品"]:
        deep = DIRECTION_DEEP.get(d_name, {})
        d = dirs.get(d_name, {})
        gaps_short = "、".join(g.split("（")[0] for g in deep.get("gaps", [])[:2])
        portfolio = deep.get("migration", {}).get("portfolio", "")[:60]
        good_jd = "、".join(deep.get("high_value_jd", [])[:4])
        bad_jd = deep.get("low_value_jd", [""])[0][:40]
        A(f"| {d_name} | 溢价{d.get('premium', 0):+.1f}%，高薪占比{d.get('high_pct', 0)}% | {gaps_short} | {portfolio} | 含{good_jd}的JD | {bad_jd} |")

    A("\n### 5.3 迁移拓展线（有迁移关系但需选择性投递）\n")
    A("| 方向 | 迁移逻辑 | 适合投的岗位 | 不适合投的岗位 | 需要注意 |")
    A("|------|---------|-----------|-------------|---------|")
    A("| 车载/智能座舱 | 多端协同（车是多端之一）+场景化设计 | 车家互联、座舱体验、车载语音 | 自动驾驶算法、汽车销售、汽车金融 | 岗位少（~38个），重点投小米汽车/理想/蔚来 |")
    A("| 内容/社区 | 场景化推荐→内容分发策略 | 内容推荐策略、社区产品 | 纯内容运营、主播管理 | 用策略产品思路切入，不是做内容运营 |")
    A("| B端中的IoT平台 | 设备平台经验→企业IoT平台 | 设备管理平台、IoT SaaS | 纯ERP/CRM/财务系统 | 只投与IoT/设备/硬件相关的B端岗位 |")

    A("\n### 方向选择总结\n")
    A("- **最适合提高成功率：** 智能硬件/IoT、平台产品")
    A("- **最适合冲高薪：** AI/大模型产品、策略产品")
    A("- **最适合精准投：** 车载/智能座舱、平台产品")
    A("- **适合迁移拓展：** 增长产品、商业化/广告")
    A("- **适合保底：** B端/SaaS/企服、用户体验/C端")
    A("- **不建议主攻：** 金融、电商、游戏、医疗、教育、数据产品")

    # ── 第6章：简历包装方向 ──
    A("\n---\n\n## 六、简历包装方向建议\n")
    A("| 投递方向 | 建议包装身份 | 第一段强调 | 重点项目 | 核心关键词 |")
    A("|---------|-----------|-----------|---------|-----------|")
    for r in RESUME_PACKAGING:
        A(f"| {r['direction']} | {r['identity']} | {r['first_para'][:40]}... | {r['key_project']} | {r['keywords']} |")

    A("\n### 详细说明\n")
    for r in RESUME_PACKAGING:
        A(f"**投递{r['direction']}方向时：**\n")
        A(f"- 包装身份：{r['identity']}")
        A(f"- 简历第一段强调：{r['first_para']}")
        A(f"- 重点项目：{r['key_project']}")
        A(f"- 核心关键词：{r['keywords']}\n")

    A("\n### 同一段经历的不同表达\n")
    A("以「多端控制规则统一」项目为例：\n")
    A("- **投IoT方向：** 「负责手机/电视/音箱/车/手表五端的设备控制体验统一，覆盖XX+品类智能设备」")
    A("- **投平台方向：** 「设计统一控制规则引擎，将5端控制逻辑平台化，支撑XX+品类设备接入，实现配置化管理」")
    A("- **投AI方向：** 「基于用户行为数据设计智能控制策略，实现多设备场景自动化联动，场景使用率提升XX%」")
    A("- **投策略方向：** 「设计多端控制策略体系，定义控制成功率/响应时间/用户满意度指标，通过数据驱动迭代优化」")
    A("- **投车载方向：** 「负责车家互联场景下的多端协同产品设计，实现手机-车机-家居设备的无缝联动体验」")

    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════════════════
# HTML 报告生成（把 Markdown 转成带样式的 HTML）
# ═══════════════════════════════════════════════════════════════════════════

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

HTML_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;color:#333;line-height:1.8;font-size:14px}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
.header{background:linear-gradient(135deg,#1e3a5f,#4a90d9);color:#fff;padding:48px 40px;border-radius:16px;margin-bottom:28px}
.header h1{font-size:28px;margin-bottom:8px}
.header .sub{opacity:.85;font-size:13px}
.card{background:#fff;border-radius:12px;padding:28px;margin-bottom:24px;box-shadow:0 2px 12px rgba(0,0,0,.06)}
.card h2{font-size:18px;margin-bottom:16px;padding-left:14px;border-left:4px solid #2d6a9f;color:#1e3a5f}
.card h3{font-size:15px;margin:20px 0 10px;color:#1e3a5f}
.card h4{font-size:14px;margin:16px 0 8px;color:#333}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #eee}
th{background:#f5f7fa;font-weight:600;color:#555;white-space:nowrap}
tr:hover{background:#f8fafc}
.tag{display:inline-block;background:#e8f0fe;color:#2d6a9f;padding:2px 10px;border-radius:12px;margin:2px;font-size:11px}
.insight{background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:13px;line-height:1.9}
.warn{background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:14px 18px;margin:12px 0;font-size:13px;color:#92400e}
.dir-card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin:16px 0}
.dir-card h3{margin-top:0;font-size:16px}
.action-tag{display:inline-block;padding:3px 12px;border-radius:6px;font-size:12px;font-weight:600;color:#fff;margin-left:8px}
.action-冲刺{background:#f59e0b}
.action-主投{background:#16a34a}
.action-精准投{background:#2d6a9f}
.action-保底{background:#9ca3af}
.action-不建议{background:#dc2626}
ul,ol{padding-left:20px;margin:8px 0}
li{margin:4px 0}
.good{color:#16a34a}
.bad{color:#dc2626}
.footer{text-align:center;color:#9ca3af;font-size:12px;padding:24px 0}
"""


def generate_html(R):
    dirs = R["directions"]

    def _dir_card(d_name):
        deep = DIRECTION_DEEP.get(d_name)
        d = dirs.get(d_name)
        if not deep or not d:
            return ""
        action = deep["action"]
        mig = deep["migration"]

        search_titles = "".join(f'<span class="tag">{_esc(t)}</span>' for t in deep["search_titles"])
        real_titles = "".join(f'<span class="tag">{_esc(t)}</span>' for t in d["top_titles"][:8])
        high_kw = "".join(f'<span class="tag" style="background:#dcfce7;color:#166534">{_esc(k)}</span>' for k in deep["high_value_jd"])
        low_signals = "".join(f'<li>{_esc(s)}</li>' for s in deep["low_value_jd"])
        real_skills = "".join(f'<li>{_esc(s)}</li>' for s in deep["real_skills"])
        direct_mig = "".join(f'<li class="good">✅ {_esc(m)}</li>' for m in mig.get("direct", []))
        reframe_mig = "".join(f'<li>🔄 {_esc(m)}</li>' for m in mig.get("reframe", []))
        gaps = "".join(f'<li>{_esc(g)}</li>' for g in deep["gaps"])

        sample_warn = f'<div class="warn">⚠️ 样本量较小（{d["count"]}个），适合精准投递，不适合海投。</div>' if d["count"] < 50 else ""

        return f'''
        <div class="dir-card">
          <h3>{_esc(d_name)} <span class="action-tag action-{action}">{action}</span></h3>
          <p><b>数据：</b>{d["count"]}个岗位，中位数{d["median"]}K，P75={d["p75"]}K，P90={d["p90"]}K，高薪占比{d["high_pct"]}%，溢价{d["premium"]:+.1f}%</p>
          {sample_warn}
          <h4>适合搜索的岗位标题</h4><div>{search_titles}</div>
          <h4>数据库中实际出现的标题</h4><div>{real_titles}</div>
          <h4>高价值JD关键词（看到这些值得投）</h4><div>{high_kw}</div>
          <h4>低价值JD信号（看到这些要谨慎）</h4><ul>{low_signals}</ul>
          <h4>真正考察的能力</h4><ul>{real_skills}</ul>
          <h4>候选人经验迁移</h4><ul>{direct_mig}{reframe_mig}</ul>
          {"<p><b>作品集：</b>" + _esc(mig.get("portfolio", "")) + "</p>" if mig.get("portfolio") else ""}
          <h4>需要补的能力</h4><ul>{gaps}</ul>
          <p style="color:#666;font-size:13px">{_esc(deep["gap_note"])}</p>
        </div>'''

    # 决策矩阵表格
    matrix_rows = ""
    for d_name in ["AI/大模型产品", "策略产品", "商业化/广告", "增长产品", "智能硬件/IoT", "平台产品", "车载/智能座舱", "B端/SaaS/企服", "数据产品", "用户体验/C端", "金融产品"]:
        d = dirs.get(d_name)
        if not d:
            continue
        deep = DIRECTION_DEEP.get(d_name)
        action = deep["action"] if deep else ("不建议" if d_name in LOW_RECOMMEND else "保底")
        matrix_rows += f'<tr><td><b>{_esc(d_name)}</b></td><td>{d["count"]}</td><td>{d["median"]}K</td><td>{d["p75"]}K</td><td>{d["p90"]}K</td><td>{d["high_pct"]}%</td><td>{d["premium"]:+.1f}%</td><td><span class="action-tag action-{action}">{action}</span></td></tr>'

    # 能力结构表格
    ability_rows = ""
    for ab in ABILITY_STRUCTURE:
        ability_rows += f'<tr><td><b>{_esc(ab["ability"])}</b></td><td>{_esc(ab["jd_desc"])}</td><td>{_esc(ab["behind"])}</td><td>{_esc(ab["directions"])}</td><td style="font-size:12px">{_esc(ab["candidate_proof"])}</td><td style="font-size:12px">{_esc(ab["resume_expr"])}</td></tr>'

    # JD搜索规则表格
    search_rows = ""
    for r in JD_SEARCH_RULES:
        search_rows += f'<tr><td><b>{_esc(r["direction"])}</b></td><td>{_esc(r["main_kw"])}</td><td>{_esc(r["expand_kw"])}</td><td class="bad">{_esc(r["caution_kw"])}</td><td style="font-size:12px">{_esc(r["note"])}</td></tr>'

    good_signal_rows = ""
    for s in JD_GOOD_SIGNALS:
        good_signal_rows += f'<tr><td class="good"><b>{_esc(s["signal"])}</b></td><td>{_esc(s["why"])}</td><td>{_esc(s["match_exp"])}</td><td>{_esc(s["resume_kw"])}</td></tr>'

    bad_signal_rows = ""
    for s in JD_BAD_SIGNALS:
        bad_signal_rows += f'<tr><td class="bad"><b>{_esc(s["signal"])}</b></td><td>{_esc(s["risk"])}</td><td>{_esc(s["why_bad"])}</td><td>{_esc(s["how_judge"])}</td></tr>'

    # 简历包装表格
    resume_rows = ""
    for r in RESUME_PACKAGING:
        resume_rows += f'<tr><td><b>{_esc(r["direction"])}</b></td><td>{_esc(r["identity"])}</td><td style="font-size:12px">{_esc(r["first_para"])}</td><td>{_esc(r["key_project"])}</td><td>{_esc(r["keywords"])}</td></tr>'

    # 方向深度拆解卡片
    dir_cards = ""
    for d_name in ["AI/大模型产品", "策略产品", "商业化/广告", "智能硬件/IoT", "平台产品", "增长产品", "车载/智能座舱", "B端/SaaS/企服"]:
        dir_cards += _dir_card(d_name)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>求职方向决策报告</title>
<style>{HTML_CSS}</style>
</head>
<body>
<div class="wrap">

<div class="header">
  <h1>🎯 求职方向决策报告</h1>
  <p class="sub">数据基础：{R["total"]}个岗位 | 北京·3-10年·本科+·30K+ | {R["date"]}</p>
  <p class="sub">整体中位数：{R["overall_median"]}K | P75阈值：{R["p75"]}K | 重点回答：方向怎么选、JD怎么筛、经验怎么迁移</p>
</div>

<!-- 第1章：决策矩阵 -->
<div class="card">
  <h2>一、求职方向决策矩阵</h2>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>方向</th><th>岗位数</th><th>中位数</th><th>P75</th><th>P90</th><th>高薪占比</th><th>溢价</th><th>推荐动作</th></tr></thead>
    <tbody>{matrix_rows}</tbody>
  </table>
  </div>
  <div class="insight">
    <b>决策总结：</b><br>
    🔥 <b>冲刺（薪资高需补能力）：</b>AI/大模型、策略、商业化/广告、增长<br>
    ✅ <b>主投（匹配度高成功率最高）：</b>智能硬件/IoT、平台产品<br>
    🎯 <b>精准投（有迁移优势但岗位少）：</b>车载/智能座舱<br>
    🛡️ <b>保底（机会多确保有offer）：</b>B端/SaaS、C端体验<br>
    ❌ <b>不建议主攻：</b>金融、电商、游戏、医疗、教育、数据产品
  </div>
</div>

<!-- 第2章：重点方向深度拆解 -->
<div class="card">
  <h2>二、重点方向深度拆解</h2>
  <p>以下8个方向按优先级排列，每个方向都回答：是否建议投、搜什么岗位、看什么JD关键词、考察什么能力、怎么迁移经验、需要补什么。</p>
  {dir_cards}
</div>

<!-- 第3章：高薪JD能力结构 -->
<div class="card">
  <h2>三、高薪JD背后的能力结构</h2>
  <p>高薪岗位JD里写的那些要求，背后真正考察的是什么？候选人怎么用现有经历证明？</p>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>能力</th><th>JD常见描述</th><th>背后考察</th><th>对应方向</th><th>候选人如何证明</th><th>简历表达</th></tr></thead>
    <tbody>{ability_rows}</tbody>
  </table>
  </div>
</div>

<!-- 第4章：JD搜索词与筛选规则 -->
<div class="card">
  <h2>四、JD搜索词与筛选规则</h2>

  <h3>各方向搜索关键词</h3>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>方向</th><th>主搜关键词</th><th>拓展关键词</th><th>谨慎关键词</th><th>说明</th></tr></thead>
    <tbody>{search_rows}</tbody>
  </table>
  </div>

  <h3>✅ 值得投的JD信号</h3>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>JD信号</th><th>为什么值得投</th><th>适合匹配的经历</th><th>简历关键词</th></tr></thead>
    <tbody>{good_signal_rows}</tbody>
  </table>
  </div>

  <h3>⚠️ 谨慎投的JD信号</h3>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>JD信号</th><th>风险</th><th>为什么不适合</th><th>如何判断</th></tr></thead>
    <tbody>{bad_signal_rows}</tbody>
  </table>
  </div>
</div>

<!-- 第5章：个人背景匹配 -->
<div class="card">
  <h2>五、个人背景匹配与方向选择</h2>

  <h3>5.1 成功率主线（最容易拿到面试和offer）</h3>
  <div class="insight">
    <b>智能硬件/IoT：</b>核心经验完全对口，直接用真实经验投递。注意岗位数量有限（~200个），不能只投这个方向。<br>
    <b>平台产品：</b>多端协同=平台化思维，把规则统一经验包装为平台能力。岗位少（~84个），精准投递。<br>
    <b>C端体验：</b>C端经验直接匹配，适合保底确保有offer。
  </div>

  <h3>5.2 薪资冲刺线（薪资高但需补能力）</h3>
  <div class="insight">
    <b>AI/大模型产品：</b>用智能家居场景化经验切入AI应用，准备AI+IoT交叉作品集。补大模型应用理解（2-3周）。<br>
    <b>策略产品：</b>数据分析能力+场景化推荐经验是基础，补推荐/搜索算法理解和AB实验方法论（2-3周）。<br>
    <b>商业化/广告：</b>C端流量理解是基础，补广告系统知识（2-3周）。从营销平台产品切入门槛更低。<br>
    <b>增长产品：</b>DAU/留存/转化指标经验是天然优势，补增长方法论体系（1-2周）。转型成本最低的冲刺方向。
  </div>

  <h3>5.3 迁移拓展线（有迁移关系但需选择性投递）</h3>
  <div class="insight">
    <b>车载/智能座舱：</b>多端协同（车是多端之一）+场景化设计。重点投小米汽车/理想/蔚来的车家互联岗位。<br>
    <b>B端中的IoT平台：</b>只投与IoT/设备/硬件相关的B端岗位，不投纯ERP/CRM。
  </div>

  <div class="insight" style="background:#eff6ff;border-color:#93c5fd">
    <b>方向选择总结：</b><br>
    建议精力分配：<b>主投40%</b>（IoT+平台）+ <b>冲刺40%</b>（AI+策略+增长）+ <b>保底20%</b>（C端+B端）<br>
    不要把所有精力放在IoT方向（岗位少），也不要只冲AI方向（需要补能力）。两条线并行效率最高。
  </div>
</div>

<!-- 第6章：简历包装 -->
<div class="card">
  <h2>六、简历包装方向建议</h2>
  <p>同一段经历投不同方向时，表达侧重点不同。不是编造经历，而是用目标方向的语言重新表达真实经验。</p>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>投递方向</th><th>包装身份</th><th>第一段强调</th><th>重点项目</th><th>核心关键词</th></tr></thead>
    <tbody>{resume_rows}</tbody>
  </table>
  </div>

  <h3>同一段经历的不同表达</h3>
  <p>以「多端控制规则统一」项目为例：</p>
  <ul>
    <li><b>投IoT方向：</b>「负责手机/电视/音箱/车/手表五端的设备控制体验统一，覆盖XX+品类智能设备」</li>
    <li><b>投平台方向：</b>「设计统一控制规则引擎，将5端控制逻辑平台化，支撑XX+品类设备接入，实现配置化管理」</li>
    <li><b>投AI方向：</b>「基于用户行为数据设计智能控制策略，实现多设备场景自动化联动，场景使用率提升XX%」</li>
    <li><b>投策略方向：</b>「设计多端控制策略体系，定义控制成功率/响应时间/用户满意度指标，通过数据驱动迭代优化」</li>
    <li><b>投车载方向：</b>「负责车家互联场景下的多端协同产品设计，实现手机-车机-家居设备的无缝联动体验」</li>
  </ul>
</div>

<div class="footer">
  求职方向决策报告 | 基于{R["total"]}条Boss直聘数据 | {R["date"]} | 仅适用于北京·3-10年·本科+·30K+细分市场
</div>

</div>
</body>
</html>'''
    return html


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  求职方向决策报告")
    print("=" * 55)

    print("\n📥 加载数据...")
    R = load_and_analyze()
    print(f"   {R['total']} 个岗位，{len(R['directions'])} 个方向")

    os.makedirs("data", exist_ok=True)

    print("📝 生成 Markdown...")
    md = generate_markdown(R)
    md_path = "data/求职方向决策报告.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    print("📝 生成 HTML...")
    html = generate_html(R)
    html_path = "data/求职方向决策报告.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 完成！")
    print(f"   HTML：{os.path.abspath(html_path)}")
    print(f"   Markdown：{os.path.abspath(md_path)}")

    import subprocess
    if sys.platform == "darwin":
        subprocess.run(["open", os.path.abspath(html_path)])


if __name__ == "__main__":
    main()
