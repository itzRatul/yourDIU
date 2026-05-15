from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class ProfileBase(BaseModel):
    full_name:  Optional[str]      = None
    avatar_url: Optional[str]      = None
    role:       UserRole           = UserRole.student
    student_id: Optional[str]      = None
    department: Optional[str]      = None
    batch:      Optional[str]      = None
    is_verified: bool              = False


class ProfileCreate(ProfileBase):
    id:    str
    email: str

    @field_validator("email")
    @classmethod
    def must_be_diu(cls, v: str) -> str:
        if not v.endswith("@diu.edu.bd"):
            raise ValueError("Only @diu.edu.bd email accounts are allowed.")
        return v


class ProfileUpdate(BaseModel):
    full_name:  Optional[str]      = None
    student_id: Optional[str]      = None
    department: Optional[str]      = None
    batch:      Optional[str]      = None


class ProfileResponse(ProfileBase):
    id:         str
    email:      str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminRoleUpdate(BaseModel):
    """Admin-only: change a user's role."""
    user_id: str
    role:    UserRole
