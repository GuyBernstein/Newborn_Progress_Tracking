from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey,
                        Integer, String, Table)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    babies = relationship("Baby", back_populates="parent")


class Baby(Base):
    __tablename__ = "babies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("User", back_populates="babies")
    progress_entries = relationship("BabyProgress", back_populates="baby", cascade="all, delete-orphan")
    media_entries = relationship("MediaItem", back_populates="baby", cascade="all, delete-orphan")


class BabyProgress(Base):
    __tablename__ = "baby_progress"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("babies.id"), nullable=False)
    record_date = Column(Date, default=date.today, nullable=False)

    # Physical measurements
    weight = Column(Float)  # in kg
    height = Column(Float)  # in cm
    head_circumference = Column(Float)  # in cm

    # Feeding data
    feeding_times = Column(JSONB)  # JSON array of feeding sessions
    feeding_type = Column(String)  # breast, formula, mixed
    feeding_amount = Column(Float)  # in ml (if applicable)

    # Sleep data
    sleep_schedule = Column(JSONB)  # JSON array of sleep sessions
    total_sleep_hours = Column(Float)

    # Diaper data
    diaper_changes = Column(JSONB)  # JSON array of diaper changes

    # Developmental milestones
    milestones = Column(JSONB)  # JSON object of milestones

    # Notes
    notes = Column(String)

    # AI-calculated insights
    growth_percentile = Column(Float)  # Based on WHO/CDC growth charts
    sleep_quality_index = Column(Float)  # AI-calculated sleep quality (0-100)
    feeding_efficiency = Column(Float)  # AI-calculated feeding efficiency (0-100)
    developmental_score = Column(Float)  # AI-calculated developmental score

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    baby = relationship("Baby", back_populates="progress_entries")


class MediaItem(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("babies.id"), nullable=False)
    media_type = Column(String, nullable=False)  # photo, video, document
    s3_key = Column(String, nullable=False)  # S3 object key
    s3_url = Column(String)  # Pre-signed URL (can be regenerated)
    filename = Column(String)
    file_size = Column(Integer)  # in bytes
    content_type = Column(String)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String)
    tags = Column(JSONB)  # JSON array of tags

    # Relationships
    baby = relationship("Baby", back_populates="media_entries")