"""Dependency injection providers for GoCars."""

from app.dependencies.auth import get_current_user, require_roles

__all__ = ["get_current_user", "require_roles"]
