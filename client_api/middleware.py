"""
Middleware for Client API to ensure all errors are returned in JSON format.
This middleware catches exceptions before they reach Django's default error handlers.
"""
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
import logging

logger = logging.getLogger(__name__)


class ClientAPIExceptionMiddleware:
    """
    Middleware to catch exceptions for Client API routes and return JSON errors.
    """
    
    # Paths that should use JSON error responses
    CLIENT_API_PREFIXES = ['/v1/', '/api/v1/']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Process exceptions for Client API routes.
        Returns JSON error response if the request is for Client API.
        """
        # Check if this is a Client API request
        if not self._is_client_api_request(request):
            return None  # Let Django handle it normally
        
        # Handle different exception types
        if isinstance(exception, Http404):
            return JsonResponse({
                'error': 'not_found',
                'message': 'Resource not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if isinstance(exception, PermissionDenied):
            return JsonResponse({
                'error': 'permission_denied',
                'message': 'You do not have permission to perform this action'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if isinstance(exception, APIException):
            # DRF exceptions are already handled by DRF's exception handler
            # But we ensure JSON format
            return JsonResponse({
                'error': getattr(exception, 'default_code', 'error'),
                'message': str(exception.detail) if hasattr(exception, 'detail') else str(exception)
            }, status=exception.status_code)
        
        # Log unexpected errors
        logger.error(f"Unhandled exception in Client API: {exception}", exc_info=True, extra={
            'path': request.path,
            'method': request.method,
        })
        
        # Return generic error for unhandled exceptions
        return JsonResponse({
            'error': 'internal_server_error',
            'message': 'An internal server error occurred'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _is_client_api_request(self, request):
        """
        Check if the request is for Client API.
        """
        path = request.path
        return any(path.startswith(prefix) for prefix in self.CLIENT_API_PREFIXES)

