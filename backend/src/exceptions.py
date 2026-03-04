"""Custom exceptions for TL-Video-Playground."""


class TLVideoPlaygroundException(Exception):
    """Base exception for all TL-Video-Playground errors."""
    pass


class ConfigurationError(TLVideoPlaygroundException):
    """Raised when configuration is invalid or missing."""
    pass


class AuthenticationError(TLVideoPlaygroundException):
    """Raised when authentication fails."""
    pass


class ValidationError(TLVideoPlaygroundException):
    """Raised when input validation fails."""
    pass


class ResourceNotFoundError(TLVideoPlaygroundException):
    """Raised when a requested resource is not found."""
    pass


class ResourceLimitError(TLVideoPlaygroundException):
    """Raised when a resource limit is exceeded."""
    pass


class AWSServiceError(TLVideoPlaygroundException):
    """Raised when an AWS service call fails."""
    pass


class BedrockError(AWSServiceError):
    """Raised when a Bedrock API call fails."""
    pass


class ProcessingError(TLVideoPlaygroundException):
    """Raised when video processing fails."""
    pass


class AnalysisCancelledError(TLVideoPlaygroundException):
    """Raised when an analysis operation is cancelled by the user.
    
    This exception is used for cooperative cancellation - it's raised when
    the analysis detects that the user has requested cancellation (e.g., by
    navigating away from the analysis form).
    """
    pass


# Orchestration Exceptions

class OrchestrationError(TLVideoPlaygroundException):
    """Base exception for orchestration-related errors."""
    pass


class IntentDeterminationError(OrchestrationError):
    """Raised when the Supervisor fails to determine query intent."""
    pass


class PlanningError(OrchestrationError):
    """Raised when the Planner fails to create an execution plan."""
    pass


class SearchError(OrchestrationError):
    """Raised when Marengo search fails."""
    pass


class AnalysisError(OrchestrationError):
    """Raised when Pegasus analysis fails."""
    pass


class AggregationError(OrchestrationError):
    """Raised when insight aggregation fails."""
    pass
