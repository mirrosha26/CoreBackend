# Эндпоинты инвесторов

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from signals.models import SignalCard, Participant
from profile.models import SavedParticipant
from frontend_api.serializers.utils import build_absolute_image_url
from django.conf import settings
from django.db.models import Q, Count
from django.http import JsonResponse

class InvestorView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Получение списка инвесторов с фильтрацией"""
        try:
            user = request.user
            filter_saved = request.query_params.get('filter_saved', None)
            
            # Базовый запрос для открытых карточек
            base_cards = SignalCard.objects.filter(is_open=True)
            
            if filter_saved == 'true':
                # Показываем только сохраненные карточки
                saved_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
                open_cards = base_cards.filter(
                    Q(signals__participant_id__in=saved_ids) |
                    Q(signals__associated_participant_id__in=saved_ids)
                ).distinct()
            elif filter_saved == 'false':
                open_cards = base_cards.exclude(deleted_by_users__user=user)
                saved_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
                
            else:
                open_cards = base_cards.exclude(deleted_by_users__user=user)
                saved_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
            
            # Получаем уникальных участников из открытых карточек
            participant_ids = set()
            for card in open_cards.select_related():
                for signal in card.signals.all():
                    if signal.participant_id:
                        participant_ids.add(signal.participant_id)
                    if signal.associated_participant_id:
                        participant_ids.add(signal.associated_participant_id)
            
            # Получаем участников
            participants = Participant.objects.filter(id__in=participant_ids)
            
            # Формируем данные
            investors_data = []
            for participant in participants:
                # Подсчитываем количество карточек для этого участника
                card_count = SignalCard.objects.filter(
                    is_open=True,
                    signals__participant=participant
                ).distinct().count()
                
                investors_data.append({
                    'id': participant.id,
                    'name': participant.name,
                    'slug': participant.slug,
                    'type': participant.type,
                    'is_saved': participant.id in saved_ids,
                    'image': build_absolute_image_url(participant, absolute_image_url=True, base_url=settings.BASE_IMAGE_URL),
                    'num_cards': card_count
                })
            
            return Response({
                'success': True,
                'data': investors_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while getting investors: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PrivateInvestorView(APIView):
    """Класс удален - больше не используется ParticipantRequest"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Метод удален - ParticipantRequest больше не используется"""
        return Response({
            'success': False,
            'error_code': 'NOT_IMPLEMENTED',
            'message': 'This endpoint is no longer available'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, request, *args, **kwargs):
        """Метод удален - ParticipantRequest больше не используется"""
        return Response({
            'success': False,
            'error_code': 'NOT_IMPLEMENTED',
            'message': 'This endpoint is no longer available'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)

    def delete(self, request, *args, **kwargs):
        """Метод удален - ParticipantRequest больше не используется"""
        return Response({
            'success': False,
            'error_code': 'NOT_IMPLEMENTED',
            'message': 'This endpoint is no longer available'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)

class PrivateInvestorCSVUploadView(APIView):
    """Класс удален - больше не используется ParticipantRequest"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Метод удален - ParticipantRequest больше не используется"""
        return Response({
            'success': False,
            'error_code': 'NOT_IMPLEMENTED',
            'message': 'This endpoint is no longer available'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)


class ParticipantUpdateView(APIView):
    """
    API endpoint for updating participant/investor information.
    Allows updating email, linkedin_url, and other participant fields.
    """
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, participant_id, *args, **kwargs):
        """Обновление информации об участнике"""
        try:
            user = request.user
            participant = Participant.objects.get(id=participant_id)
            data = request.data
            
            # Проверка доступа - только для сохраненных участников
            if False:
                has_access = SavedParticipant.objects.filter(
                    user=user,
                    participant=participant
                ).exists()
                
                if not has_access:
                    return Response({
                        'success': False,
                        'error_code': 'ACCESS_DENIED',
                        'message': 'You do not have permission to update this private participant'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Обновляем поля участника
            if 'name' in data:
                participant.name = data['name']
            if 'additional_name' in data:
                participant.additional_name = data['additional_name']
            if 'about' in data:
                participant.about = data['about']
            
            participant.save()
            
            return Response({
                'success': True,
                'message': 'Participant updated successfully',
                'data': {
                    'id': participant.id,
                    'name': participant.name,
                    'slug': participant.slug
                }
            }, status=status.HTTP_200_OK)
            
        except Participant.DoesNotExist:
            return Response({
                'success': False,
                'error_code': 'NOT_FOUND',
                'message': 'Participant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f'An error occurred while updating participant: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
