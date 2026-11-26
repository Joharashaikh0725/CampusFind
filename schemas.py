from typing import Optional, Dict

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):

    full_name: str = Field(
        min_length=2,
        max_length=120
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=256
    )


class LoginRequest(BaseModel):

    email: EmailStr

    password: str


class LostCreate(BaseModel):

    title: str

    category: str

    brand: Optional[str] = None

    model: Optional[str] = None

    color: Optional[str] = None

    lost_date: Optional[str] = None

    lost_time: Optional[str] = None

    location: Optional[str] = None

    description: Optional[str] = None

    image_url: Optional[str] = None


class FoundCreate(BaseModel):

    title: str

    category: str

    brand: Optional[str] = None

    model: Optional[str] = None

    color: Optional[str] = None

    found_date: Optional[str] = None

    found_time: Optional[str] = None

    location: Optional[str] = None

    description: Optional[str] = None

    image_url: Optional[str] = None


class ClaimCreate(BaseModel):

    lost_report_id: int

    found_report_id: int


class MessageCreate(BaseModel):

    message: str = Field(
        min_length=1,
        max_length=2000
    )


class EvidenceCreate(BaseModel):

    evidence_type: str

    secret_value: str

    base_weight: Optional[float] = None


class VerifyRequest(BaseModel):

    answers: Dict[int, str]


class AdminItemCreate(BaseModel):

    found_report_id: int

    storage_location: Optional[str] = None


class ClaimDecision(BaseModel):

    note: Optional[str] = None


class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePassword(BaseModel):

    current_password: str

    new_password: str = Field(
        min_length=8,
        max_length=128
    )
