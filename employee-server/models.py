from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel
from pydantic import BaseModel


class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    object_key: Optional[str] = Field(default=None, max_length=80)

    full_name: str = Field(max_length=200)
    location: str = Field(max_length=200)
    job_title: str = Field(max_length=200)
    badges: str = Field(max_length=200)

    created_datetime: datetime = Field(default_factory=datetime.now)

    # =========================
    # ✅ 신규 추가 필드
    # =========================
    storage_type: Optional[str] = Field(default="ceph", max_length=50)
    backup_status: int = Field(default=0)  # 0: false, 1: true
    upload_time: Optional[datetime] = None
    last_access_time: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class EmployeePublic(BaseModel):
    id: int
    object_key: Optional[str] = None

    full_name: str
    location: str
    job_title: str
    badges: str

    photo_url: Optional[str] = None

    # =========================
    # public에도 추가 (조회용)
    # =========================
    storage_type: Optional[str] = None
    backup_status: int = 0
    upload_time: Optional[datetime] = None
    last_access_time: Optional[datetime] = None

    class Config:
        from_attributes = True


EmployeesListResponse = List[EmployeePublic]