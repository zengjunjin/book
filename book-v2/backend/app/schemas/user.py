from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
import re


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

    @model_validator(mode='after')
    def check_email_format(self):
        if self.email is not None and self.email != "":
            # Simple RFC 5322 basic regex - checks format, not domain deliverability
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', self.email):
                raise ValueError('邮箱格式不正确')
        return self


class UserCreate(UserBase):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('密码长度至少 8 个字符')
        if len(v) > 128:
            raise ValueError('密码长度不能超过 128 个字符')
        if not any(c.isupper() for c in v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not any(c.islower() for c in v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含至少一个数字')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError('用户名长度至少 3 个字符')
        if len(v) > 50:
            raise ValueError('用户名长度不能超过 50 个字符')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('用户名只能包含字母、数字、下划线和连字符')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
