from datetime import date, datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, validator


# User Schemas
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(UserBase):
    password: Optional[str] = None


class UserInDBBase(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        orm_mode = True


class User(UserInDBBase):
    pass


# Baby Schemas
class BabyBase(BaseModel):
    name: str
    date_of_birth: date
    gender: Optional[str] = None


class BabyCreate(BabyBase):
    pass


class BabyUpdate(BabyBase):
    name: Optional[str] = None
    date_of_birth: Optional[date] = None


class BabyInDBBase(BabyBase):
    id: int
    parent_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class Baby(BabyInDBBase):
    pass


# Progress Entry Schemas
class FeedingSession(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    type: str  # breast, bottle, etc.
    amount: Optional[float] = None  # in ml
    notes: Optional[str] = None


class SleepSession(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    quality: Optional[str] = None  # good, fair, poor
    notes: Optional[str] = None


class DiaperChange(BaseModel):
    time: datetime
    type: str  # wet, dirty, both
    notes: Optional[str] = None


class Milestone(BaseModel):
    milestone: str
    achieved_date: Optional[date] = None
    notes: Optional[str] = None


class BabyProgressBase(BaseModel):
    record_date: date = Field(default_factory=date.today)
    weight: Optional[float] = None
    height: Optional[float] = None
    head_circumference: Optional[float] = None
    feeding_times: Optional[List[FeedingSession]] = None
    feeding_type: Optional[str] = None
    feeding_amount: Optional[float] = None
    sleep_schedule: Optional[List[SleepSession]] = None
    total_sleep_hours: Optional[float] = None
    diaper_changes: Optional[List[DiaperChange]] = None
    milestones: Optional[List[Milestone]] = None
    notes: Optional[str] = None


class BabyProgressCreate(BabyProgressBase):
    baby_id: int


class BabyProgressUpdate(BabyProgressBase):
    pass


class BabyProgressInDBBase(BabyProgressBase):
    id: int
    baby_id: int
    growth_percentile: Optional[float] = None
    sleep_quality_index: Optional[float] = None
    feeding_efficiency: Optional[float] = None
    developmental_score: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class BabyProgress(BabyProgressInDBBase):
    pass


# Media Item Schemas
class MediaItemBase(BaseModel):
    media_type: str
    filename: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class MediaItemCreate(MediaItemBase):
    baby_id: int
    # File will be uploaded separately


class MediaItemUpdate(MediaItemBase):
    pass


class MediaItemInDBBase(MediaItemBase):
    id: int
    baby_id: int
    s3_key: str
    s3_url: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    upload_date: datetime

    class Config:
        orm_mode = True


class MediaItem(MediaItemInDBBase):
    pass


# Token schemas for authentication
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: Optional[int] = None