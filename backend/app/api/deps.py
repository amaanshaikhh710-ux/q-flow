"""FastAPI authentication and authorization dependencies."""

import uuid
from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=True,
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Validate JWT access token and return the authenticated user record.

    Raises:
        HTTPException: 401 if token is missing, expired, or invalid.
    """
    payload = decode_access_token(token)
    user_id_str: str = payload.get("sub")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: UserRole):
    """Dependency factory enforcing server-side role-based access control."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Operation requires one of {[r.value for r in allowed_roles]} role",
            )
        return current_user
    return role_checker


# Specialized role dependencies
require_patient = require_role(UserRole.PATIENT)
require_staff = require_role(UserRole.STAFF)
require_admin = require_role(UserRole.ADMIN)
require_staff_or_admin = require_role(UserRole.STAFF, UserRole.ADMIN)


def get_queue_hospital_id(db: Session, queue_id: uuid.UUID) -> uuid.UUID:
    """Resolve the hospital ID for a given queue via Queue -> OPDSession -> Department."""
    from app.models.queue import Queue
    from app.models.opd_session import OPDSession
    from app.models.department import Department

    record = (
        db.query(Department.hospital_id)
        .join(OPDSession, OPDSession.department_id == Department.id)
        .join(Queue, Queue.opd_session_id == OPDSession.id)
        .filter(Queue.id == queue_id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue with ID {queue_id} does not exist or has no hospital mapping",
        )
    return record[0]


def verify_staff_hospital_access(current_user: User, hospital_id: uuid.UUID) -> None:
    """Enforce hospital-scoped authorization for staff members.
    
    Admins are superusers and have access across all hospitals.
    Staff members are strictly restricted to their assigned hospital_id.
    """
    if current_user.role == UserRole.ADMIN:
        return

    if current_user.role == UserRole.STAFF:
        if current_user.hospital_id is None or current_user.hospital_id != hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Staff members cannot access or manage queues outside their assigned hospital",
            )
