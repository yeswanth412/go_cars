"""Pydantic Schemas for Authentication and User Management.

Defines:
- RegisterRequest & RegisterResponse
- LoginRequest & TokenResponse
- UserResponse
"""

from datetime import datetime
from typing import List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Schema for user self-registration."""

    full_name: str = Field(..., min_length=2, max_length=150, description="Legal full name")
    email: EmailStr = Field(..., description="Valid email address for login and communication")
    phone_number: str = Field(..., min_length=7, max_length=20, description="Contact phone number")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email casing to lowercase to prevent duplicates."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        """Clean phone number string."""
        if isinstance(v, str):
            return v.strip()
        return v


class LoginRequest(BaseModel):
    """Schema for user login credentials."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email casing to lowercase."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResponse(BaseModel):
    """Public user profile schema (never exposes password hashes)."""

    id: UUID
    full_name: str
    email: str
    phone_number: str
    is_active: bool
    is_verified: bool
    roles: List[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    """Response returned upon successful user registration."""

    message: str = "User registered successfully"
    user: UserResponse


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
