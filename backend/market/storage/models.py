# -*- coding: utf-8 -*-
"""存储层：SQLAlchemy ORM models（Schema 见需求文档 4.2）。

- market_jobs 表：每个 job_id 只保留最新状态（幂等 upsert）
- market_job_snapshots 表：按 (job_id, crawl_date) 追加历史快照（REQ-DB-04）

表名加 market_ 前缀（合并决策）：与宿主 A 的 jobs/job_events 业务表区分，
建表由 A 的迁移脚本 002_market_jobs.sql 负责（见 migrations/）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Job(Base):
    """岗位最新状态表（REQ-DB-01/03）"""

    __tablename__ = "market_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 幂等唯一键
    job_title: Mapped[str] = mapped_column(String(128), nullable=False)
    job_category: Mapped[str] = mapped_column(String(32), nullable=False)
    job_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 实习/校招/社招/不限
    company_name: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    company_size: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    city: Mapped[str] = mapped_column(String(32), nullable=False)
    salary_raw: Mapped[str] = mapped_column(String(64), nullable=False)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_avg: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    experience_req: Mapped[str] = mapped_column(String(32), nullable=False)
    education_req: Mapped[str] = mapped_column(String(32), nullable=False)
    job_desc: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # 源端无标签时空数组
    post_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    crawl_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # TINYINT
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Job {self.job_id} {self.job_title} {self.city} {self.salary_raw}>"


class JobSnapshot(Base):
    """岗位快照表：按 (job_id, crawl_date) 追加（REQ-DB-04）"""

    __tablename__ = "market_job_snapshots"
    __table_args__ = (
        UniqueConstraint("job_id", "crawl_date", name="uq_job_snapshot"),
        Index("ix_snapshot_crawl_date", "crawl_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),  # SQLite 需 INTEGER 才支持自增 rowid
        primary_key=True, autoincrement=True,
    )
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    crawl_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_avg: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JobSnapshot {self.job_id} {self.crawl_date}>"
