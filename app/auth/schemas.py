import uuid
from datetime import datetime

from disposable_email_domains import blocklist
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import User


def _reject_disposable_domain(email: EmailStr) -> EmailStr:
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in blocklist:
        raise ValueError("Disposable email addresses are not allowed")
    return email


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    _validate_domain = field_validator("email")(_reject_disposable_domain)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class MessageOut(BaseModel):
    detail: str
