from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import json
from signals.models import SignalCard
from profile.models import TicketForCard
from frontend_api.serializers.utils import build_absolute_image_url
from django.conf import settings

class TicketContactView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            card_id = data.get('card_id')
            
            if card_id:
                signal_card = SignalCard.objects.get(pk=card_id)
                ticket, created = TicketForCard.objects.get_or_create(user=request.user, signal_card=signal_card)
                
                if created:
                    return Response({
                        'success': True,
                        'message': 'Contact request sent successfully.'
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'success': False,
                        'error_code': 'DUPLICATE_REQUEST',
                        'message': 'Contact request has already been sent.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_CARD_ID',
                    'message': 'Card ID is missing.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except SignalCard.DoesNotExist:
            return Response({
                'success': False,
                'error_code': 'CARD_NOT_FOUND',
                'message': 'The specified signal card does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while processing the request: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, *args, **kwargs):
        try:
            user = request.user
            tickets = TicketForCard.objects.filter(user=user)
            
            response_data = [
                {
                    'id': ticket.id,
                    'signal_card_name': ticket.signal_card.name,
                    'signal_card_image': build_absolute_image_url(ticket.signal_card, absolute_image_url=True, base_url=settings.BASE_IMAGE_URL),
                    'is_processed': ticket.is_processed,
                    'created_at': ticket.created_at,
                    'response_text': ticket.response_text,
                }
                for ticket in tickets
            ]
            
            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while retrieving requests: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, *args, **kwargs):
        try:
            ticket_id = request.data.get('ticket_id')
            
            if not ticket_id:
                return Response({
                    'success': False,
                    'error_code': 'MISSING_TICKET_ID',
                    'message': 'Request ID is missing.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            ticket = TicketForCard.objects.filter(id=ticket_id, user=request.user).first()
            
            if not ticket:
                return Response({
                    'success': False,
                    'error_code': 'TICKET_NOT_FOUND',
                    'message': 'Request not found or does not belong to the user.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            ticket.delete()
            return Response({
                'success': True,
                'message': 'Contact request cancelled successfully.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while cancelling the request: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
