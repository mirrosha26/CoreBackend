from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from profile.models import SavedFilter
from frontend_api.serializers.saved_filters import (
    SavedFilterSerializer,
    SavedFilterListSerializer
)


class SavedFilterListCreateView(APIView):
    """
    List all saved filters for the authenticated user or create a new one
    
    GET: Returns list of all saved filters for the user
    POST: Creates a new saved filter
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        List all saved filters for the authenticated user
        
        Query parameters:
        - include_default: bool - If true, also returns which filter is default
        - detailed: bool - If true, returns full filter details instead of summary
        """
        user = request.user
        detailed = request.query_params.get('detailed', '').lower() == 'true'
        
        # Get all saved filters for the user
        saved_filters = SavedFilter.objects.filter(user=user).prefetch_related(
            'categories',
            'participants'
        )
        
        # Choose serializer based on detail level
        serializer_class = SavedFilterSerializer if detailed else SavedFilterListSerializer
        serializer = serializer_class(saved_filters, many=True)
        
        # Find the default filter
        default_filter = saved_filters.filter(is_default=True).first()
        
        return Response({
            'success': True,
            'count': saved_filters.count(),
            'filters': serializer.data,
            'default_filter_id': default_filter.id if default_filter else None
        })
    
    def post(self, request):
        """
        Create a new saved filter
        
        Request body should contain filter configuration fields
        """
        user = request.user
        
        # Create serializer with request context (for user access)
        serializer = SavedFilterSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            saved_filter = serializer.save()
            return Response({
                'success': True,
                'message': f"Filter '{saved_filter.name}' created successfully",
                'filter': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Failed to create filter',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class SavedFilterDetailView(APIView):
    """
    Retrieve, update, or delete a specific saved filter
    
    GET: Retrieve filter details
    PUT/PATCH: Update filter
    DELETE: Delete filter
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, user, filter_id):
        """
        Get a saved filter, ensuring it belongs to the authenticated user
        """
        return get_object_or_404(SavedFilter, id=filter_id, user=user)
    
    def get(self, request, filter_id):
        """
        Retrieve a specific saved filter
        """
        saved_filter = self.get_object(request.user, filter_id)
        serializer = SavedFilterSerializer(saved_filter)
        
        return Response({
            'success': True,
            'filter': serializer.data
        })
    
    def put(self, request, filter_id):
        """
        Full update of a saved filter
        """
        saved_filter = self.get_object(request.user, filter_id)
        
        serializer = SavedFilterSerializer(
            saved_filter,
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': f"Filter '{saved_filter.name}' updated successfully",
                'filter': serializer.data
            })
        
        return Response({
            'success': False,
            'message': 'Failed to update filter',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, filter_id):
        """
        Partial update of a saved filter
        """
        saved_filter = self.get_object(request.user, filter_id)
        
        serializer = SavedFilterSerializer(
            saved_filter,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': f"Filter '{saved_filter.name}' updated successfully",
                'filter': serializer.data
            })
        
        return Response({
            'success': False,
            'message': 'Failed to update filter',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, filter_id):
        """
        Delete a saved filter
        """
        saved_filter = self.get_object(request.user, filter_id)
        filter_name = saved_filter.name
        is_default = saved_filter.is_default
        
        saved_filter.delete()
        
        return Response({
            'success': True,
            'message': f"Filter '{filter_name}' deleted successfully",
            'was_default': is_default
        }, status=status.HTTP_200_OK)


class SavedFilterApplyView(APIView):
    """
    Apply a saved filter to the user's current filter settings
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, filter_id):
        """
        Apply a saved filter to UserFilter
        """
        saved_filter = get_object_or_404(
            SavedFilter,
            id=filter_id,
            user=request.user
        )
        
        try:
            # Apply the saved filter to session
            from signals.models import Category, Participant
            
            request.session['current_filters'] = {
                'search': saved_filter.search,
                'categories': [str(c.id) for c in saved_filter.categories.all()],
                'participants': [str(p.id) for p in saved_filter.participants.all()],
                'stages': saved_filter.stages or [],
                'round_statuses': saved_filter.round_statuses or [],
                'featured': saved_filter.featured,
                'is_open': saved_filter.is_open,
                'start_date': saved_filter.start_date.isoformat() if saved_filter.start_date else None,
                'end_date': saved_filter.end_date.isoformat() if saved_filter.end_date else None,
                'min_signals': saved_filter.min_signals,
                'max_signals': saved_filter.max_signals,
                'hide_liked': saved_filter.hide_liked
            }
            
            return Response({
                'success': True,
                'message': f"Filter '{saved_filter.name}' applied successfully",
                'filter_name': saved_filter.name
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': f"Failed to apply filter: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SavedFilterSetDefaultView(APIView):
    """
    Set a saved filter as the user's default filter
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, filter_id):
        """
        Set a specific filter as default
        """
        user = request.user
        saved_filter = get_object_or_404(SavedFilter, id=filter_id, user=user)
        
        # Unset any existing default filter
        SavedFilter.objects.filter(user=user, is_default=True).update(is_default=False)
        
        # Set this filter as default
        saved_filter.is_default = True
        saved_filter.save()
        
        return Response({
            'success': True,
            'message': f"Filter '{saved_filter.name}' set as default",
            'filter_id': saved_filter.id
        })
    
    def delete(self, request, filter_id):
        """
        Unset a filter as default (no filter will be default)
        """
        user = request.user
        saved_filter = get_object_or_404(SavedFilter, id=filter_id, user=user)
        
        if not saved_filter.is_default:
            return Response({
                'success': False,
                'message': f"Filter '{saved_filter.name}' is not set as default"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        saved_filter.is_default = False
        saved_filter.save()
        
        return Response({
            'success': True,
            'message': f"Filter '{saved_filter.name}' unset as default"
        })


