"""
Custom exception hierarchy for the AI Companion System.

This module defines all custom exceptions used throughout the system,
organized in a hierarchy with a common base class for consistent error handling.
"""

from typing import Optional


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
        
        super().__init__(
            message,
            error_code="SECURITY_THREAT_DETECTED",
            details={
                "threat_type": threat_type,
                "confidence": confidence,
                "detected_content": detected_content
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