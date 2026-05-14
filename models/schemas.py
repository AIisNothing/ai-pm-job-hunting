"""Pydantic v2 数据模型定义 - 核心数据结构"""

from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


# ─── 基础统计模型 ───────────────────────────────────────────────

class SalaryRange(BaseModel):
    """薪资范围"""
    model_config = {"frozen": False}

    min_monthly: float = Field(..., description="月薪最低值（千元）")
    max_monthly: float = Field(..., description="月薪最高值（千元）")
    months_per_year: int = Field(default=12, description="年薪月数")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def median_monthly(self) -> float:
        """等效月薪中位数"""
        return (self.min_monthly + self.max_monthly) / 2


class CityCount(BaseModel):
    """城市岗位数量"""
    city: str
    count: int


class ExperienceCount(BaseModel):
    """经验要求分布"""
    experience: str
    count: int


class SkillFrequency(BaseModel):
    """技能出现频率"""
    skill: str
    frequency: float


class SkillWeight(BaseModel):
    """技能权重"""
    skill: str
    weight: float


# ─── 岗位数据模型 ───────────────────────────────────────────────

class JobRecord(BaseModel):
    """岗位记录"""
    id: str
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    salary_min: float | None = Field(default=None, description="月薪最低值（千元）")
    salary_max: float | None = Field(default=None, description="月薪最高值（千元）")
    salary_months: int = Field(default=12, description="年薪月数")
    city: str = Field(..., description="工作城市")
    experience: str = Field(default="", description="工作经验要求")
    education: str = Field(default="", description="学历要求")
    description: str = Field(default="", description="岗位描述全文")
    publish_date: date | None = Field(default=None, description="发布日期")
    keyword: str = Field(..., description="搜索关键词来源")
    snapshot_id: str = Field(..., description="所属快照ID")


class DataSnapshot(BaseModel):
    """数据快照"""
    id: str
    keyword: str
    collected_at: datetime
    total_jobs: int
    archived: bool = False


# ─── 方向与概览模型 ─────────────────────────────────────────────

class DirectionSummary(BaseModel):
    """方向摘要"""
    direction_name: str
    job_count: int
    salary_median: float
    trend_label: str


class MarketOverview(BaseModel):
    """市场概览"""
    keyword: str
    total_jobs: int
    salary_median: float
    salary_p25: float
    salary_p75: float
    city_distribution: list[CityCount]
    experience_distribution: list[ExperienceCount]
    trend_label: str = Field(..., description="'上升' | '平稳' | '下降'")
    directions: list[DirectionSummary]
    top_skills: list[SkillFrequency]


# ─── 用户与技能画像模型 ─────────────────────────────────────────

class SkillProfile(BaseModel):
    """技能画像"""
    keyword: str = Field(..., description="岗位类别")
    core_skills: list[SkillWeight] = Field(..., description="核心技能及权重")
    domain: str = Field(..., description="所属领域")
    work_style_tags: list[str] = Field(default_factory=list, description="工作方式标签")


class UserProfile(BaseModel):
    """用户画像"""
    interest_areas: list[str] = Field(..., description="兴趣领域")
    skills: list[str] = Field(..., description="已掌握技能")
    work_style: str = Field(..., description="工作方式偏好")
    expected_salary_min: float = Field(..., description="期望薪资下限")
    expected_salary_max: float = Field(..., description="期望薪资上限")
    preferred_city: str | None = Field(default=None, description="偏好城市")


# ─── 推荐模型 ───────────────────────────────────────────────────

class CareerRecommendation(BaseModel):
    """职业推荐"""
    keyword: str
    match_score: float = Field(..., description="匹配度得分 0-100")
    match_reasons: list[str] = Field(..., description="匹配原因")
    trend_label: str
    salary_range: SalaryRange
    skill_gaps: list[str] = Field(..., description="需要补充的技能")


class TransferRecommendation(BaseModel):
    """跳槽推荐"""
    target_keyword: str
    skill_overlap: float = Field(..., description="技能重叠度 0-1")
    trend_label: str
    salary_median: float
    skill_gaps: list[str] = Field(..., description="需要补充的技能")


# ─── 测评模型 ───────────────────────────────────────────────────

class AssessmentAnswers(BaseModel):
    """测评问卷回答"""
    interest_areas: list[str]
    skills: list[str]
    work_style: str
    expected_salary_min: float
    expected_salary_max: float
    preferred_city: str | None = None


class MatchScore(BaseModel):
    """匹配度得分"""
    skill_score: float
    interest_score: float
    work_style_score: float
    salary_score: float
    total: float


# ─── 采集结果模型 ───────────────────────────────────────────────

class ScrapeResult(BaseModel):
    """采集结果"""
    keyword: str
    total_fetched: int
    total_stored: int
    duplicates_skipped: int
    errors: list[str] = Field(default_factory=list)
    snapshot_id: str


class TimePeriod(BaseModel):
    """时间段"""
    start_date: date
    end_date: date


# ─── 通用响应模型 ───────────────────────────────────────────────

class PaginatedResult(BaseModel, Generic[T]):
    """分页结果"""
    items: list[T]
    page: int
    page_size: int
    total: int


class Pagination(BaseModel):
    """分页元数据"""
    page: int
    page_size: int
    total: int


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 200
    data: Any = None
    message: str = "success"
    pagination: Pagination | None = None
