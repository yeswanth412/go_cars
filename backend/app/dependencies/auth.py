"""Authentication and Authorization Dependencies for FastAPI.

Provides:
- get_current_user: Validates Bearer token and returns active User
- require_roles: Factory returning a dependency to enforce role-based access control (RBAC)
"""

from typing import Callable, List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

# HTTPBearer security scheme enabling the "Authorize" button in Swagger UI
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT bearer token from Authorization header and return authenticated User.

    Raises:
        HTTPException: 401 Unauthorized if token is missing, invalid, expired,
                       or if the user is inactive or deleted.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Decode and validate token claims
    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    # Query user from repository
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(*required_roles: str) -> Callable[[User], User]:
    """Factory returning a dependency that ensures the user has at least one of the specified roles.

    Supports multi-role users. If a user possesses any of the required roles,
    access is permitted.

    Example:
        @router.get("/admin", dependencies=[Depends(require_roles("ADMIN"))])

    Raises:
        HTTPException: 403 Forbidden if user lacks the required role.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names: List[str] = [role.name for role in current_user.roles]
        has_permission = any(req_role in user_role_names for req_role in required_roles)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Requires role: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker
