"""SQLAlchemy ORM 表模型定义（SQLAlchemy 2.0 风格）"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class DataSnapshotDB(Base):
    """数据快照表"""
    __tablename__ = "data_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 关系：一个快照包含多条岗位记录
    job_records: Mapped[list["JobRecordDB"]] = relationship(
        "JobRecordDB", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DataSnapshot id={self.id} keyword={self.keyword!r} total_jobs={self.total_jobs}>"


class JobRecordDB(Base):
    """岗位记录表"""
    __tablename__ = "job_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    encrypt_job_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    salary_desc: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    area_district: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    business_district: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    experience: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    education: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_snapshots.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # 公司信息
    brand_industry: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    brand_scale_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    brand_stage_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    brand_logo: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # 福利与标签
    welfare_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    job_labels_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 招聘者信息
    boss_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    boss_title: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    boss_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 地理位置
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 原始数据备份
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # 关系
    snapshot: Mapped["DataSnapshotDB"] = relationship("DataSnapshotDB", back_populates="job_records")
    skill_tags: Mapped[list["SkillTagDB"]] = relationship(
        "SkillTagDB", back_populates="job_record", cascade="all, delete-orphan"
    )
    job_directions: Mapped[list["JobDirectionDB"]] = relationship(
        "JobDirectionDB", back_populates="job_record", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JobRecord id={self.id} title={self.title!r} company={self.company!r}>"


class SkillTagDB(Base):
    """技能标签表"""
    __tablename__ = "skill_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    job_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_records.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 关系
    job_record: Mapped["JobRecordDB"] = relationship("JobRecordDB", back_populates="skill_tags")

    def __repr__(self) -> str:
        return f"<SkillTag id={self.id} name={self.name!r}>"


class JobDirectionDB(Base):
    """岗位方向表"""
    __tablename__ = "job_directions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    job_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_records.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    direction_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 关系
    job_record: Mapped["JobRecordDB"] = relationship("JobRecordDB", back_populates="job_directions")

    def __repr__(self) -> str:
        return f"<JobDirection id={self.id} direction={self.direction_name!r}>"


class DirectionRuleDB(Base):
    """方向分类规则表"""
    __tablename__ = "direction_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    direction_name: Mapped[str] = mapped_column(String(100), nullable=False)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    def __repr__(self) -> str:
        return f"<DirectionRule id={self.id} category={self.category!r} direction={self.direction_name!r}>"


class SkillDictionaryDB(Base):
    """技能词典表"""
    __tablename__ = "skill_dictionary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    synonyms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    def __repr__(self) -> str:
        return f"<SkillDictionary id={self.id} skill={self.skill_name!r}>"


class AssessmentResultDB(Base):
    """职业测评结果表"""
    __tablename__ = "assessment_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    user_profile_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recommendations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AssessmentResult id={self.id} created_at={self.created_at}>"
