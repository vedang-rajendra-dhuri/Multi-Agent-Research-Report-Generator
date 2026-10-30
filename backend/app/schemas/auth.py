from uuid import UUID

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
