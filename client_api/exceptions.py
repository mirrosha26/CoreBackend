"""
Custom exception handlers for Client API.
Ensures all errors are returned in JSON format with consistent structure.

Standard error response format:
{
    "error": "error_code",
    "message": "Human-readable error message",
    "details": {}  # Optional additional details
}
"""
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import (
    APIException, AuthenticationFailed, NotAuthenticated, PermissionDenied,
    NotFound, MethodNotAllowed, NotAcceptable, UnsupportedMediaType,
    Throttled, ValidationError, ParseError
)
from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
import logging

logger = logging.getLogger(__name__)


def client_api_exception_handler(exc, context):
    """
    Custom exception handler for Client API.
    Returns all errors in JSON format with consistent structure.
    
    This handler ensures:
    - All errors are in JSON format (never HTML)
    - Consistent error response structure
    - Proper HTTP status codes
    - Detailed error information when appropriate
    
    Error response format:
    {
        "error": "error_code",
        "message": "Human-readable error message",
        "details": {}  # Optional additional details
    }
    """
    # Get the standard exception response from DRF
    response = exception_handler(exc, context)
    
    # If DRF handled it, format it consistently
    if response is not None:
        # Extract error details
        error_data = response.data
        
        # Handle different error formats from DRF
        if isinstance(error_data, dict):
            # Single error or multiple errors
            if 'detail' in error_data:
                # Standard DRF error format
                detail = error_data['detail']
                # Если detail - это словарь с нашим форматом ошибки (для throttling), используем его
                if isinstance(detail, dict) and 'error' in detail:
                    return Response(detail, status=response.status_code)
                error_message = detail
                error_code = get_error_code(exc)
            elif 'non_field_errors' in error_data:
                # Non-field errors
                error_message = error_data['non_field_errors'][0] if isinstance(error_data['non_field_errors'], list) else error_data['non_field_errors']
                error_code = 'validation_error'
            else:
                # Field-specific errors
                error_message = 'Validation error'
                error_code = 'validation_error'
                error_data = {'fields': error_data}
        elif isinstance(error_data, list):
            # List of errors
            error_message = error_data[0] if error_data else 'An error occurred'
            error_code = get_error_code(exc)
        else:
            # String error
            error_message = str(error_data)
            error_code = get_error_code(exc)
        
        # Build consistent error response
        error_response = {
            'error': error_code,
            'message': str(error_message)
        }
        
        # Add details if available (for validation errors)
        if isinstance(error_data, dict) and 'fields' in error_data:
            error_response['details'] = error_data['fields']
        elif isinstance(error_data, dict) and 'detail' not in error_data and 'non_field_errors' not in error_data:
            error_response['details'] = error_data
        
        return Response(error_response, status=response.status_code)
    
    # Handle Django-specific exceptions
    if isinstance(exc, Http404):
        return Response({
            'error': 'not_found',
            'message': 'Resource not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
        return Response({
            'error': 'permission_denied',
            'message': 'You do not have permission to perform this action'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if isinstance(exc, (ValidationError, DjangoValidationError)):
        error_details = None
        if hasattr(exc, 'message_dict'):
            error_details = exc.message_dict
        elif hasattr(exc, 'messages'):
            error_details = {'non_field_errors': list(exc.messages)}
        elif hasattr(exc, 'detail'):
            error_details = exc.detail
        
        return Response({
            'error': 'validation_error',
            'message': 'Validation error',
            'details': error_details if error_details else str(exc)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle DRF APIException that wasn't caught by standard handler
    if isinstance(exc, APIException):
        # Для Throttled проверяем, есть ли кастомный формат в detail
        if isinstance(exc, Throttled) and isinstance(exc.detail, dict) and 'error' in exc.detail:
            return Response(exc.detail, status=exc.status_code)
        
        error_code = get_error_code(exc)
        error_message = str(exc.detail) if hasattr(exc, 'detail') else str(exc)
        return Response({
            'error': error_code,
            'message': error_message
        }, status=exc.status_code)
    
    # Log unexpected errors with context
    request = context.get('request') if context else None
    logger.error(
        f"Unhandled exception in Client API: {exc}",
        exc_info=True,
        extra={
            'path': request.path if request else None,
            'method': request.method if request else None,
        }
    )
    
    # Return generic error for unhandled exceptions
    return Response({
        'error': 'internal_server_error',
        'message': 'An internal server error occurred'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_error_code(exception):
    """
    Get standardized error code from exception type.
    
    Returns:
        str: Error code string (e.g., 'not_found', 'validation_error')
    """
    error_code_map = {
        AuthenticationFailed: 'authentication_failed',
        NotAuthenticated: 'not_authenticated',
        PermissionDenied: 'permission_denied',
        NotFound: 'not_found',
        MethodNotAllowed: 'method_not_allowed',
        NotAcceptable: 'not_acceptable',
        UnsupportedMediaType: 'unsupported_media_type',
        Throttled: 'throttled',
        ValidationError: 'validation_error',
        ParseError: 'parse_error',
    }
    
    exception_type = type(exception)
    
    # Try to get code from exception's default_code if available
    if hasattr(exception, 'default_code'):
        return exception.default_code
    
    # Use mapping
    if exception_type in error_code_map:
        return error_code_map[exception_type]
    
    # Fallback to exception class name in snake_case
    class_name = exception_type.__name__
    return class_name.lower().replace('exception', '').replace('error', 'error')

