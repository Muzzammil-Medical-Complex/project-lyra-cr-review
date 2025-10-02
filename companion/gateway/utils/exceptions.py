"""
Custom exception hierarchy for the AI Companion System.

This module defines all custom exceptions used throughout the system,
organized in a hierarchy with a common base class for consistent error handling.
"""

from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

# Sensitive field patterns to sanitize
SENSITIVE_KEYS = {
    'api_key', 'token', 'password', 'secret', 'credential', 'auth',
    'ssn', 'social_security', 'credit_card', 'internal_id', 'db_id'
}

def sanitize_for_logs(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitize exception details for logging by masking sensitive fields.

    Args:
        details: Original exception details

    Returns:
        Sanitized details safe for logging
    """
    if not details:
        return {}

    sanitized = {}
    for key, value in details.items():
        # Check if key contains sensitive patterns
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 1000:
            # Truncate large strings
            sanitized[key] = value[:1000] + "...[truncated]"
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_for_logs(value)
        else:
            sanitized[key] = value

    return sanitized


def sanitize_for_response(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitize exception details for API responses by whitelisting safe fields.

    Args:
        details: Original exception details

    Returns:
        Sanitized details safe for external responses
    """
    if not details:
        return {}

    # Whitelist of safe fields to include in responses
    safe_fields = {
        'threat_type', 'confidence', 'severity', 'error_type',
        'field_name', 'resource_type', 'content_hash', 'content_redacted'
    }

    sanitized = {}
    for key, value in details.items():
        if key in safe_fields:
            # Only include whitelisted fields
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
        elif key == 'detected_content':
            # Never include full detected_content, use hash instead
            continue

    return sanitized


def sanitize_and_hash_content(content: str, max_length: int = 200) -> Dict[str, Any]:
    """
    Sanitize and truncate content, providing a hash for traceability.

    Args:
        content: Original content string
        max_length: Maximum length for snippet

    Returns:
        Dict with sanitized_snippet, content_hash, and content_redacted flag
    """
    # Remove control characters except newline, tab, and carriage return
    # Preserve newlines and tabs for multi-line content
    sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', content)
    # Normalize excessive whitespace while preserving line breaks
    lines = sanitized.split('\n')
    normalized_lines = []
    for line in lines:
        # Collapse runs of spaces/tabs within each line
        normalized_line = re.sub(r'[ \t]+', ' ', line).strip()
        normalized_lines.append(normalized_line)
    # Rejoin lines with preserved newlines
    sanitized = '\n'.join(normalized_lines)

    # Truncate to max_length
    if len(sanitized) > max_length:
        snippet = sanitized[:max_length] + "...[truncated]"
    else:
        snippet = sanitized

    # Generate deterministic hash for traceability
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    return {
        'sanitized_snippet': snippet,
        'content_hash': content_hash,
        'content_redacted': len(content) > max_length
    }


class CompanionBaseException(Exception):
    """Base exception class for all custom exceptions in the AI Companion System."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[dict] = None):
        """
        Initialize the base exception with a message and optional error code and details.

        Args:
            message (str): Human-readable error description
            error_code (Optional[str]): Machine-readable error identifier
            details (Optional[dict]): Additional context information about the error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

    def __str__(self):
        return f"{self.error_code}: {self.message}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message!r}, {self.error_code!r})"


class UserNotFoundError(CompanionBaseException):
    """Raised when a user cannot be found in the system."""

    def __init__(self, user_id: str, message: Optional[str] = None):
        """
        Initialize the exception with a specific user ID.

        Args:
            user_id (str): The ID of the user that was not found
            message (Optional[str]): Custom error message
        """
        if message is None:
            message = f"User with ID '{user_id}' not found in the system"

        super().__init__(message, error_code="USER_NOT_FOUND", details={"user_id": user_id})


class UserCreationError(CompanionBaseException):
    """Raised when user creation fails."""

    def __init__(self, message: str, user_id: Optional[str] = None):
        """
        Initialize the exception with error details.

        Args:
            message (str): Error message describing what went wrong
            user_id (Optional[str]): The user ID associated with the failed creation attempt
        """
        super().__init__(
            message,
            error_code="USER_CREATION_FAILED",
            details={"user_id": user_id} if user_id else {}
        )


class SecurityThreatDetected(CompanionBaseException):
    """Raised when a security threat is detected in user input."""
    
    def __init__(self, threat_type: str, confidence: float, detected_content: str, message: Optional[str] = None):
        """
        Initialize the exception with threat details.

        Args:
            threat_type (str): Type of threat detected (e.g., 'injection_attempt', 'role_manipulation')
            confidence (float): Confidence level of threat detection (0.0 to 1.0)
            detected_content (str): The content that triggered the threat detection
            message (Optional[str]): Custom error message
        """
        if message is None:
            message = f"Security threat ({threat_type}) detected with {confidence:.2f} confidence"

        # Sanitize and hash the detected content instead of storing it raw
        sanitized_content = sanitize_and_hash_content(detected_content, max_length=200)

        super().__init__(
            message,
            error_code="SECURITY_THREAT_DETECTED",
            details={
                "threat_type": threat_type,
                "confidence": confidence,
                **sanitized_content  # Includes sanitized_snippet, content_hash, content_redacted
            }
        )


class ServiceUnavailableError(CompanionBaseException):
    """Raised when an external service is unavailable."""
    
    def __init__(self, service_name: str, message: Optional[str] = None):
        """
        Initialize the exception with the name of the unavailable service.

        Args:
            service_name (str): Name of the service that is unavailable
            message (Optional[str]): Custom error message
        """
        if message is None:
            message = f"External service '{service_name}' is currently unavailable"
        
        super().__init__(message, error_code="SERVICE_UNAVAILABLE", details={"service_name": service_name})


class MemoryConflictError(CompanionBaseException):
    """Raised when conflicting memories are detected during storage or retrieval."""
    
    def __init__(self, primary_memory_id: str, conflicting_memory_id: str, message: Optional[str] = None):
        """
        Initialize the exception with IDs of conflicting memories.

        Args:
            primary_memory_id (str): ID of the primary memory
            conflicting_memory_id (str): ID of the conflicting memory
            message (Optional[str]): Custom error message
        """
        if message is None:
            message = f"Memory conflict detected between '{primary_memory_id}' and '{conflicting_memory_id}'"
        
        super().__init__(
            message,
            error_code="MEMORY_CONFLICT",
            details={
                "primary_memory_id": primary_memory_id,
                "conflicting_memory_id": conflicting_memory_id
            }
        )


class PersonalityEngineError(CompanionBaseException):
    """Raised when an error occurs in the personality engine."""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        """
        Initialize the exception with details about the personality engine error.

        Args:
            message (str): Error message describing what went wrong
            operation (Optional[str]): The specific operation that failed
        """
        super().__init__(
            message,
            error_code="PERSONALITY_ENGINE_ERROR",
            details={"operation": operation}
        )


class MemoryManagerError(CompanionBaseException):
    """Raised when an error occurs in the memory manager."""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        """
        Initialize the exception with details about the memory manager error.

        Args:
            message (str): Error message describing what went wrong
            operation (Optional[str]): The specific operation that failed
        """
        super().__init__(
            message,
            error_code="MEMORY_MANAGER_ERROR",
            details={"operation": operation}
        )


class ChatProcessingError(CompanionBaseException):
    """Raised when an error occurs during chat message processing."""
    
    def __init__(self, message: str, user_id: Optional[str] = None):
        """
        Initialize the exception with details about the chat processing error.

        Args:
            message (str): Error message describing what went wrong
            user_id (Optional[str]): The user ID associated with the error (if applicable)
        """
        super().__init__(
            message,
            error_code="CHAT_PROCESSING_ERROR",
            details={"user_id": user_id}
        )


class LettaServiceError(CompanionBaseException):
    """Raised when an error occurs in the Letta service integration."""
    
    def __init__(self, message: str, agent_id: Optional[str] = None):
        """
        Initialize the exception with details about the Letta service error.

        Args:
            message (str): Error message describing what went wrong
            agent_id (Optional[str]): The agent ID associated with the error (if applicable)
        """
        super().__init__(
            message,
            error_code="LETTA_SERVICE_ERROR",
            details={"agent_id": agent_id}
        )


class ConfigurationError(CompanionBaseException):
    """Raised when there is an error in configuration or missing required settings."""

    def __init__(self, setting_name: str, message: Optional[str] = None):
        """
        Initialize the exception with details about the configuration error.

        Args:
            setting_name (str): Name of the problematic setting
            message (Optional[str]): Custom error message
        """
        if message is None:
            message = f"Configuration error: missing or invalid setting '{setting_name}'"

        super().__init__(message, error_code="CONFIGURATION_ERROR", details={"setting_name": setting_name})


class SecurityError(CompanionBaseException):
    """Raised when a security constraint is violated."""

    def __init__(self, message: str, violation_type: Optional[str] = None):
        """
        Initialize the exception with security violation details.

        Args:
            message (str): Error message describing the security violation
            violation_type (Optional[str]): Type of security violation
        """
        super().__init__(
            message,
            error_code="SECURITY_VIOLATION",
            details={"violation_type": violation_type} if violation_type else {}
        )


def setup_exception_handlers(app: FastAPI):
    """
    Set up custom exception handlers for the FastAPI application.

    Args:
        app (FastAPI): The FastAPI application instance
    """

    @app.exception_handler(CompanionBaseException)
    async def companion_exception_handler(request: Request, exc: CompanionBaseException):
        """Handle all custom Companion exceptions."""
        # Sanitize details for logging (masks sensitive fields, truncates large values)
        sanitized_log_details = sanitize_for_logs(exc.details)
        logger.error(
            f"Companion exception: {exc.error_code} - {exc.message}",
            extra={"details": sanitized_log_details}
        )

        # Map specific exception types to HTTP status codes
        status_code_map = {
            "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "USER_CREATION_FAILED": status.HTTP_400_BAD_REQUEST,
            "SECURITY_THREAT_DETECTED": status.HTTP_403_FORBIDDEN,
            "SERVICE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
            "MEMORY_CONFLICT": status.HTTP_409_CONFLICT,
            "CONFIGURATION_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }

        status_code = status_code_map.get(exc.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Sanitize details for response (whitelist safe fields only)
        sanitized_response_details = sanitize_for_response(exc.details)

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": sanitized_response_details
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all uncaught exceptions."""
        logger.exception(f"Unhandled exception: {str(exc)}")

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": {}
            }
        )