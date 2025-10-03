"""
Authentication and authorization utilities for the AI Companion System.

This module provides dependencies for verifying admin access and user authentication.
"""

from fastapi import Header, HTTPException, Depends, Request
from typing import Optional
import logging

from ..models.user import UserProfile
from ..services.user_service import UserService

logger = logging.getLogger(__name__)


def get_user_service(request: Request) -> UserService:
    """Get UserService from app state."""
    if not hasattr(request.app.state, 'user_service'):
        raise HTTPException(
            status_code=500,
            detail="Internal server error: UserService not initialized"
        )
    return request.app.state.user_service


async def verify_admin(
    x_user_id: Optional[str] = Header(None),
    user_service: UserService = Depends(get_user_service)
) -> UserProfile:
    """
    Verify that the requesting user has admin privileges.

    Args:
        x_user_id: User ID from request header
        user_service: UserService instance

    Returns:
        UserProfile of the admin user

    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    if not x_user_id:
        logger.warning("Admin endpoint accessed without user ID")
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-User-ID header."
        )

    try:
        user = await user_service.get_user_profile(x_user_id)
        if not user:
            logger.warning(f"Admin endpoint accessed by non-existent user: {x_user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"User {x_user_id} not found"
            )

        if not user.is_admin:
            logger.warning(f"Admin endpoint accessed by non-admin user: {x_user_id}")
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )

        logger.info(f"Admin access granted to user: {x_user_id}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error verifying admin access for user %s", x_user_id)
        raise HTTPException(
            status_code=500,
            detail="Internal server error during admin verification"
        ) from e
