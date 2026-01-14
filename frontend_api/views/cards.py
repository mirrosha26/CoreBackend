from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.paginator import Paginator
from django.db.models import Q, Max, Value, Case, When, IntegerField, Prefetch
from django.shortcuts import get_object_or_404
from django.http import Http404

from signals.models import SignalCard, Signal
from profile.models import (
    UserFolder, FolderCard, DeletedCard, UserNote,
    GroupAssignedCard, GroupCardMemberAssignment, UserGroup
)

from signals.utils import apply_search_query_filters
from frontend_api.serializers.cards.previews import serialize_previews
from frontend_api.serializers.cards.details import serialize_card_detail
from frontend_api.serializers.cards.public import serialize_public_card_preview, serialize_public_card_detail

# Import cache invalidation function
from graphql_app.mutations import invalidate_user_cache_after_mutation



class CardListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        user = request.user
        signal_cards = (SignalCard.objects
            .filter(is_open=True)
            .prefetch_related(
                'categories',
                'categories__parent_category',
                Prefetch(
                    'signals',
                    queryset=Signal.objects.select_related(
                        'participant',
                        'associated_participant'
                    )
                )
            )
        )
        search_query = request.query_params.get('search', '').strip()
        type = kwargs.get('type') or request.query_params.get('type')
        folder_key = request.query_params.get('folder_key')
        folder = None

        if folder_key:
            try:
                if folder_key == 'default':
                    folder = UserFolder.objects.filter(user=user, is_default=True).first()
                    if not folder:
                        return Response({
                            'success': False,
                            'error': 'DEFAULT_FOLDER_NOT_FOUND',
                            'message': 'Папка по умолчанию не найдена'
                        }, status=status.HTTP_404_NOT_FOUND)
                else:
                    folder = UserFolder.objects.get(id=folder_key, user=user)
            except UserFolder.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'FOLDER_NOT_FOUND',
                    'message': 'Папка не найдена'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Получаем карточки из папки с сортировкой по ID записей FolderCard в обратном порядке
            folder_cards = FolderCard.objects.filter(
                folder=folder
            ).select_related('signal_card').order_by('-id')
            
            folder_card_ids = [fc.signal_card_id for fc in folder_cards]
            
            # Фильтруем карточки и сортируем по порядку в папке
            signal_cards = signal_cards.filter(id__in=folder_card_ids)
            
            # Создаем case для сортировки по порядку ID записей в папке
            case_clauses = [When(id=card_id, then=Value(i)) for i, card_id in enumerate(folder_card_ids)]
            if case_clauses:
                signal_cards = signal_cards.annotate(
                    folder_position=Case(*case_clauses, default=Value(len(folder_card_ids)), output_field=IntegerField())
                ).order_by('folder_position')
        elif type == 'notes':
            # Получаем заметки пользователя с сортировкой по ID в обратном порядке
            user_notes = UserNote.objects.filter(user=user).order_by('-id')
            note_card_ids = [note.signal_card_id for note in user_notes]
            
            signal_cards = signal_cards.filter(id__in=note_card_ids)
            
            # Создаем case для сортировки по порядку ID записей заметок
            case_clauses = [When(id=card_id, then=Value(i)) for i, card_id in enumerate(note_card_ids)]
            if case_clauses:
                signal_cards = signal_cards.annotate(
                    note_position=Case(*case_clauses, default=Value(len(note_card_ids)), output_field=IntegerField())
                ).order_by('note_position')
        elif type == 'remote':
            # Получаем удаленные карточки пользователя с сортировкой по ID в обратном порядке
            deleted_cards = DeletedCard.objects.filter(user=user).order_by('-id')
            deleted_card_ids = [dc.signal_card_id for dc in deleted_cards]
            
            signal_cards = signal_cards.filter(id__in=deleted_card_ids)
            
            # Создаем case для сортировки по порядку ID записей удаленных карточек
            case_clauses = [When(id=card_id, then=Value(i)) for i, card_id in enumerate(deleted_card_ids)]
            if case_clauses:
                signal_cards = signal_cards.annotate(
                    deleted_position=Case(*case_clauses, default=Value(len(deleted_card_ids)), output_field=IntegerField())
                ).order_by('deleted_position')
        else:
            signal_cards = signal_cards.exclude(id__in=DeletedCard.objects.filter(user=user).values_list('signal_card_id', flat=True))
            signal_cards = signal_cards.exclude(stage='worth_following')
            
            # Применяем фильтры из сессии, если они есть
            session_filters = request.session.get('current_filters', {})
            
            if session_filters.get('categories'):
                from signals.models import Category
                category_ids = [int(c) for c in session_filters['categories']]
                signal_cards = signal_cards.filter(categories__id__in=category_ids)

            if session_filters.get('participants'):
                from signals.models import Participant
                participant_ids = [int(p) for p in session_filters['participants']]
                signal_cards = signal_cards.filter(
                    Q(signals__participant_id__in=participant_ids) |
                    Q(signals__associated_participant_id__in=participant_ids)
                )

            if session_filters.get('round_statuses') or session_filters.get('stages'):
                stages_rounds_filter = Q()
                if session_filters.get('round_statuses'):
                    stages_rounds_filter |= Q(round_status__in=session_filters['round_statuses'])
                if session_filters.get('stages'):
                    stages = [stage for stage in session_filters['stages'] if stage != 'worth_following']
                    if stages:
                        stages_rounds_filter |= Q(stage__in=stages)
                if stages_rounds_filter:
                    signal_cards = signal_cards.filter(stages_rounds_filter)

        if search_query:
            signal_cards, using_search_relevance_sort = apply_search_query_filters(signal_cards, search_query)
            if using_search_relevance_sort and hasattr(signal_cards, 'annotate'):
                signal_cards = signal_cards.annotate(latest_signal_date=Max('signals__created_at'))
        else:
            using_search_relevance_sort = False

        # Применение distinct
        if hasattr(signal_cards, 'distinct'):
            signal_cards = signal_cards.distinct()
        
        # Аннотация latest_signal_date (только если не папка)
        if hasattr(signal_cards, 'annotate') and not search_query and not folder_key:
            signal_cards = signal_cards.annotate(
                latest_signal_date=Max('signals__created_at')
            )
        
        # Сортировка (только если не папка, не заметки и не удаленные)
        if hasattr(signal_cards, 'order_by') and not folder_key and type not in ['notes', 'remote']:
            if using_search_relevance_sort:
                signal_cards = signal_cards.order_by('-search_relevance', '-latest_signal_date')
            else:
                signal_cards = signal_cards.order_by('-latest_signal_date')

        # Пагинация
        page_size = int(request.query_params.get('page_size', 20))
        paginator = Paginator(signal_cards, page_size)
        page_number = request.query_params.get('page', 1)
        page_obj = paginator.get_page(page_number)
        serialized_cards = serialize_previews(
            signal_cards=page_obj.object_list,
            user=user
        )
        
        return Response({
            'success': True,
            'loadMore': page_obj.has_next(),
            'cards': serialized_cards,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': int(page_number)
        })



class CardFavoriteView(APIView):
    """
    API представление для управления избранными карточками.
    POST - добавление карточки в избранное
    DELETE - удаление карточки из избранного
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Получаем папку по умолчанию (избранное) для пользователя
            default_folder = get_object_or_404(UserFolder, user=request.user, is_default=True)
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Создаем запись FolderCard или получаем существующую
            folder_card, created = FolderCard.objects.get_or_create(
                folder=default_folder,
                signal_card=signal_card
            )
            
            # Удаляем карточку из списка удаленных, если она там есть
            DeletedCard.objects.filter(user=request.user, signal_card_id=card_id).delete()
            
            # Invalidate user's cache to update feed with new favorite status
            invalidate_user_cache_after_mutation(request.user.id)
            
            if created:
                return Response({
                    'success': True,
                    'message': 'Карточка успешно добавлена в избранное'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': 'ALREADY_LIKED',
                    'message': 'Карточка уже находится в избранном'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем папку по умолчанию (избранное) для пользователя
            default_folder = get_object_or_404(UserFolder, user=request.user, is_default=True)
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Удаляем запись FolderCard
            deleted, _ = FolderCard.objects.filter(
                folder=default_folder,
                signal_card=signal_card
            ).delete()
            
            # Invalidate user's cache to update feed with unfavorite status
            if deleted:
                invalidate_user_cache_after_mutation(request.user.id)
            
            if deleted:
                return Response({
                    'success': True,
                    'message': 'Карточка успешно удалена из избранного'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'NOT_LIKED',
                    'message': 'Карточка не найдена в избранном'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CardDeleteView(APIView):
    """
    API представление для управления удаленными карточками.
    POST - добавление карточки в список удаленных
    DELETE - восстановление карточки из списка удаленных
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Удаляем карточку из всех папок пользователя
            FolderCard.objects.filter(
                folder__user=request.user,
                signal_card_id=card_id
            ).delete()
            
            # Добавляем карточку в список удаленных
            deleted_card, created = DeletedCard.objects.get_or_create(
                user=request.user, 
                signal_card_id=card_id
            )
            
            # Invalidate user's cache to update feed with deletion status
            invalidate_user_cache_after_mutation(request.user.id)
            
            if created:
                return Response({
                    'success': True,
                    'message': 'Карточка успешно удалена'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': 'ALREADY_DELETED',
                    'message': 'Карточка уже находится в списке удаленных'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Удаляем запись из DeletedCard
            try:
                deleted_card = DeletedCard.objects.get(user=request.user, signal_card_id=card_id)
                deleted_card.delete()
                
                # Invalidate user's cache to update feed with restored card
                invalidate_user_cache_after_mutation(request.user.id)
                
                return Response({
                    'success': True,
                    'message': 'Карточка успешно восстановлена'
                }, status=status.HTTP_200_OK)
            except DeletedCard.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'NOT_DELETED',
                    'message': 'Карточка не найдена в списке удаленных'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CardNoteView(APIView):
    """
    API представление для управления заметками к карточкам.
    GET - получение заметки
    POST - создание или обновление заметки
    DELETE - удаление заметки
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.query_params.get('card_id')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Получаем заметку, если она существует
            try:
                note = UserNote.objects.get(
                    user=request.user,
                    signal_card=signal_card
                )
                return Response({
                    'success': True,
                    'note': {
                        'card_id': card_id,
                        'note_text': note.note_text,
                        'created_at': note.created_at,
                        'updated_at': note.updated_at
                    }
                }, status=status.HTTP_200_OK)
            except UserNote.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'NOTE_NOT_FOUND',
                    'message': 'Заметка не найдена'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            note_text = request.data.get('note_text')
            
            if not card_id:
                return Response({
                    'success': False,
                    'error': 'MISSING_CARD_ID',
                    'message': 'ID карточки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            if note_text is None:
                return Response({
                    'success': False,
                    'error': 'MISSING_NOTE_TEXT',
                    'message': 'Текст заметки не указан'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Если текст заметки пустой, удаляем заметку
            if not note_text.strip():
                deleted, _ = UserNote.objects.filter(
                    user=request.user,
                    signal_card=signal_card
                ).delete()
                
                # Invalidate user's cache to update feed with note deletion
                if deleted:
                    invalidate_user_cache_after_mutation(request.user.id)
                
                if deleted:
                    return Response({
                        'success': True,
                        'message': 'Заметка успешно удалена'
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': True,
                        'message': 'Нет заметки для удаления'
                    }, status=status.HTTP_200_OK)
            
            # Создаем или обновляем заметку
            note, created = UserNote.objects.update_or_create(
                user=request.user,
                signal_card=signal_card,
                defaults={'note_text': note_text}
            )
            
            # Invalidate user's cache to update feed with note changes
            invalidate_user_cache_after_mutation(request.user.id)
            
            if created:
                return Response({
                    'success': True,
                    'message': 'Заметка успешно создана'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': True,
                    'message': 'Заметка успешно обновлена'
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, card_id=None, *args, **kwargs):
        try:
            # Используем ID из URL параметра, если он есть
            card_id = card_id or request.data.get('card_id')
            
            if not card_id:
                return Response({
                    'success': True,
                    'message': 'Нет заметки для удаления'
                }, status=status.HTTP_200_OK)
            
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Удаляем заметку, если она существует
            deleted, _ = UserNote.objects.filter(
                user=request.user,
                signal_card=signal_card
            ).delete()
            
            # Invalidate user's cache to update feed with note deletion
            if deleted:
                invalidate_user_cache_after_mutation(request.user.id)
            
            if deleted:
                return Response({
                    'success': True,
                    'message': 'Заметка успешно удалена'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'NOTE_NOT_FOUND',
                    'message': 'Заметка не найдена'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CardDetailView(APIView):
    """
    API представление для получения детальной информации о карточке.
    GET - получение деталей карточки по ID или слагу
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id=None, slug=None, *args, **kwargs):
        try:
            user = request.user
            
            if not card_id and not slug:
                return Response({
                    'success': False,
                    'error': 'MISSING_IDENTIFIER',
                    'message': 'Необходимо указать ID или slug карточки'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Поиск карточки по ID или slug
            if card_id:
                signal_card = get_object_or_404(SignalCard, id=card_id)
            else:
                signal_card = get_object_or_404(SignalCard, slug=slug)
            
            # Проверка доступа к карточке
            # Разрешаем доступ если:
            # 1. У карточки есть LinkedIn данные, ИЛИ
            # 2. Пользователь имеет доступ к приватным участникам
            
            has_linkedin_data = signal_card.signals.filter(linkedin_data__isnull=False).exists()
            
            if not has_linkedin_data:
                # Проверяем доступ к приватным участникам только если нет LinkedIn данных
                private_participant_filter = Q(
                    # Privacy filtering removed
                )
                # Privacy filtering removed
                
                if not SignalCard.objects.filter(
                    id=signal_card.id
                ).filter(private_participant_filter | non_private_participant_filter).exists():
                    return Response({
                        'success': False,
                        'error': 'ACCESS_DENIED',
                        'message': 'У вас нет доступа к этой карточке'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Получение детальной информации о карточке через сериализатор
            card_data = serialize_card_detail(signal_card, user)
            
            return Response({
                'success': True,
                'card': card_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class PublicCardPreviewView(APIView):
    """
    Публичное API представление для получения preview информации о карточке.
    
    GET - получение preview информации о карточке по identifier (UUID или slug) без авторизации
    """
    permission_classes = []
    
    def get(self, request, identifier, *args, **kwargs):
        # Логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"PublicCardPreviewView: Received request for identifier: {identifier}")
        logger.info(f"PublicCardPreviewView: Request path: {request.path}")
        logger.info(f"PublicCardPreviewView: Request method: {request.method}")
        logger.info(f"PublicCardPreviewView: Request headers: {dict(request.headers)}")
        
        try:
            signal_card = None
            
            # Автоматически определяем тип идентификатора
            try:
                # Проверяем, является ли identifier UUID
                from uuid import UUID
                UUID(identifier)
                # Если успешно - это UUID, ищем по UUID
                try:
                    signal_card = SignalCard.objects.get(uuid=identifier, is_open=True)
                except SignalCard.DoesNotExist:
                    pass
            except ValueError:
                # Если не UUID - значит это slug, ищем по slug
                try:
                    signal_card = SignalCard.objects.get(slug=identifier, is_open=True)
                except SignalCard.DoesNotExist:
                    pass
            
            # Если карточка не найдена, проверяем, существует ли она вообще (но не публичная)
            if not signal_card:
                # Проверяем, существует ли карточка, но не публичная
                card_exists = False
                try:
                    from uuid import UUID
                    UUID(identifier)
                    card_exists = SignalCard.objects.filter(uuid=identifier).exists()
                except ValueError:
                    card_exists = SignalCard.objects.filter(slug=identifier).exists()
                
                if card_exists:
                    return Response({
                        'success': False,
                        'error_code': 'ACCESS_DENIED',
                        'message': 'Card exists but is not publicly available'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                return Response({
                    'success': False,
                    'error_code': 'NOT_FOUND',
                    'message': 'Card not found for this identifier'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Получение preview информации о карточке через публичный сериализатор
            try:
                card_data = serialize_public_card_preview(signal_card)
            except Exception as serialization_error:
                # Логируем ошибку сериализации для отладки
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error serializing card preview for identifier {identifier}: {str(serialization_error)}", exc_info=True)
                
                return Response({
                    'success': False,
                    'error_code': 'SERIALIZATION_ERROR',
                    'message': f'Error serializing card data: {str(serialization_error)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({
                'success': True,
                'card': card_data
            }, status=status.HTTP_200_OK)
            
        except Http404:
            return Response({
                'success': False,
                'error_code': 'NOT_FOUND',
                'message': 'Card not found for this identifier'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicCardDetailView(APIView):
    """
    Публичное API представление для получения детальной информации о карточке.
    
    GET - получение детальной информации о карточке по identifier (UUID или slug)
    - Без авторизации: только карточки с is_open=True
    - С авторизацией: карточки с is_open=True или карточки с LinkedIn данными
    """
    permission_classes = []
    authentication_classes = [JWTAuthentication, TokenAuthentication, SessionAuthentication]
    
    def get(self, request, identifier, *args, **kwargs):
        # Логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"PublicCardDetailView: Received request for identifier: {identifier}")
        logger.info(f"PublicCardDetailView: Request path: {request.path}")
        logger.info(f"PublicCardDetailView: Request method: {request.method}")
        logger.info(f"PublicCardDetailView: Request headers: {dict(request.headers)}")
        
        try:
            include_signals = request.GET.get('include_signals', 'true').lower() == 'true'
            signals_limit = int(request.GET.get('signals_limit', 5))
            
            signal_card = None
            
            # Автоматически определяем тип идентификатора
            try:
                # Проверяем, является ли identifier UUID
                from uuid import UUID
                UUID(identifier)
                # Если успешно - это UUID, ищем по UUID
                try:
                    signal_card = SignalCard.objects.get(uuid=identifier)
                except SignalCard.DoesNotExist:
                    pass
            except ValueError:
                # Если не UUID - значит это slug, ищем по slug
                try:
                    signal_card = SignalCard.objects.get(slug=identifier)
                except SignalCard.DoesNotExist:
                    pass
            
            # Если карточка не найдена
            if not signal_card:
                return Response({
                    'success': False,
                    'error_code': 'NOT_FOUND',
                    'message': 'Card not found for this identifier'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Проверяем доступ к карточке
            user = request.user if request.user.is_authenticated else None
            
            # Если пользователь не авторизован, проверяем is_open=True
            if not user:
                if not signal_card.is_open:
                    return Response({
                        'success': False,
                        'error': 'ACCESS_DENIED',
                        'message': 'Эта карточка недоступна для публичного просмотра'
                    }, status=status.HTTP_403_FORBIDDEN)
            else:
                # Для авторизованных пользователей проверяем доступ
                # Разрешаем доступ если:
                # 1. Карточка публичная (is_open=True), ИЛИ
                # 2. У карточки есть LinkedIn данные, ИЛИ
                # 3. Пользователь имеет доступ к приватным участникам
                
                has_linkedin_data = signal_card.signals.filter(linkedin_data__isnull=False).exists()
                
                # Если у карточки есть LinkedIn данные, разрешаем доступ авторизованным пользователям
                if has_linkedin_data:
                    # Доступ разрешен для авторизованных пользователей с LinkedIn данными
                    pass
                elif not signal_card.is_open:
                    # Проверяем доступ к приватным участникам только если нет LinkedIn данных
                    private_participant_filter = Q(
                        signals__associated_participant__is_private=True,
                        signals__associated_participant__saved_by_users__user=user
                    )
                    non_private_participant_filter = Q(signals__associated_participant__is_private=False)
                    
                    if not SignalCard.objects.filter(
                        id=signal_card.id
                    ).filter(private_participant_filter | non_private_participant_filter).exists():
                        return Response({
                            'success': False,
                            'error': 'ACCESS_DENIED',
                            'message': 'У вас нет доступа к этой карточке'
                        }, status=status.HTTP_403_FORBIDDEN)
            
            # Получение детальной информации о карточке через публичный сериализатор
            card_data = serialize_public_card_detail(
                signal_card, 
                include_signals=include_signals,
                signals_limit=signals_limit
            )
            
            return Response({
                'success': True,
                'card': card_data
            }, status=status.HTTP_200_OK)
            
        except Http404:
            return Response({
                'success': False,
                'error_code': 'NOT_FOUND',
                'message': 'Card not found for this identifier'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CardGroupMembersView(APIView):
    """
    API представление для работы с участниками группы по карточке.
    GET - получение списка участников группы с флагом назначения на карточку
    POST - назначение участников группы на карточку
    PUT/PATCH - изменение статуса назначения карточки группе
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id, *args, **kwargs):
        """
        Получить список участников группы пользователя по карточке.
        Возвращает всех участников группы с флагом is_assigned.
        """
        try:
            user = request.user
            
            # Проверяем, что у пользователя есть группа
            if not hasattr(user, 'group') or not user.group:
                return Response({
                    'success': False,
                    'error': 'NO_GROUP',
                    'message': 'Пользователь не состоит в группе'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем существование карточки
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Получаем назначение карточки группе (если есть)
            group_assigned_card = GroupAssignedCard.objects.filter(
                group=user.group,
                signal_card=signal_card
            ).first()
            
            # Получаем всех участников группы
            group_members = user.group.members.all()
            
            # Сериализуем участников группы
            from frontend_api.serializers.utils import build_absolute_image_url
            from django.conf import settings
            
            # Получаем информацию о назначениях (кто назначен и кем)
            assignments_info = {}
            if group_assigned_card:
                assignments = GroupCardMemberAssignment.objects.filter(
                    group_assigned_card=group_assigned_card
                ).select_related('user', 'assigned_by')
                
                for assignment in assignments:
                    assigned_by_info = None
                    if assignment.assigned_by:
                        assigned_by_avatar = None
                        if assignment.assigned_by.avatar and hasattr(assignment.assigned_by.avatar, 'url'):
                            assigned_by_avatar = build_absolute_image_url(
                                assignment.assigned_by, True, field_name='avatar', base_url=settings.BASE_IMAGE_URL
                            )
                        
                        assigned_by_info = {
                            'id': assignment.assigned_by.id,
                            'username': assignment.assigned_by.username,
                            'first_name': assignment.assigned_by.first_name,
                            'last_name': assignment.assigned_by.last_name,
                            'avatar': assigned_by_avatar,
                        }
                    
                    assignments_info[assignment.user.id] = {
                        'is_assigned': True,
                        'assigned_by': assigned_by_info,
                        'assigned_at': assignment.created_at.isoformat() if assignment.created_at else None
                    }
            
            members_data = []
            for member in group_members:
                avatar_url = None
                if member.avatar and hasattr(member.avatar, 'url'):
                    avatar_url = build_absolute_image_url(
                        member, True, field_name='avatar', base_url=settings.BASE_IMAGE_URL
                    )
                
                assignment_info = assignments_info.get(member.id, {'is_assigned': False})
                
                members_data.append({
                    'id': member.id,
                    'username': member.username,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'avatar': avatar_url,
                    'is_assigned': assignment_info['is_assigned'],
                    'assigned_by': assignment_info.get('assigned_by'),
                    'assigned_at': assignment_info.get('assigned_at')
                })
            
            # Сортируем список так, чтобы текущий пользователь был первым
            members_data.sort(key=lambda x: (x['id'] != user.id, x['id']))
            
            return Response({
                'success': True,
                'group': {
                    'id': user.group.id,
                    'name': user.group.name,
                    'slug': user.group.slug
                },
                'card_id': card_id,
                'card_name': signal_card.name,
                'status': group_assigned_card.status if group_assigned_card else None,
                'members': members_data,
                'has_group_assignment': group_assigned_card is not None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, card_id, *args, **kwargs):
        """
        Назначить карточку группе и/или участников группы на карточку.
        
        Можно использовать для:
        1. Просто переноса карточки в группу (без member_ids) - создаст GroupAssignedCard со статусом REVIEW
        2. Назначения участников на карточку (с member_ids)
        3. Комбинации обоих действий
        
        Параметры:
        - member_ids (опционально): список ID участников для назначения
        - status (опционально): начальный статус карточки (по умолчанию REVIEW)
        - action (опционально): 'replace' (заменить все назначения), 'add' (добавить к существующим) или 'remove' (удалить указанных участников)
        """
        try:
            user = request.user
            
            # Проверяем, что у пользователя есть группа
            if not hasattr(user, 'group') or not user.group:
                return Response({
                    'success': False,
                    'error': 'NO_GROUP',
                    'message': 'Пользователь не состоит в группе'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем существование карточки
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Получаем статус (если указан) или используем REVIEW по умолчанию
            initial_status = request.data.get('status', 'REVIEW')
            
            # Проверяем валидность статуса
            valid_statuses = [choice[0] for choice in GroupAssignedCard.STATUS_CHOICES]
            if initial_status not in valid_statuses:
                return Response({
                    'success': False,
                    'error': 'INVALID_STATUS',
                    'message': f'Недопустимый статус. Доступные: {", ".join(valid_statuses)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем или создаем назначение карточки группе
            group_assigned_card, created = GroupAssignedCard.objects.get_or_create(
                group=user.group,
                signal_card=signal_card,
                defaults={'status': initial_status}
            )
            
            # Если карточка уже была назначена группе, обновляем статус (если указан новый)
            if not created and 'status' in request.data:
                group_assigned_card.status = initial_status
                group_assigned_card.save(update_fields=['status', 'updated_at'])
            
            # Получаем список ID участников для назначения (опционально)
            member_ids = request.data.get('member_ids', [])
            
            # Если member_ids не передан или пустой, просто создаем/обновляем GroupAssignedCard
            if not member_ids:
                return Response({
                    'success': True,
                    'message': 'Карточка перенесена в группу' if created else 'Карточка уже в группе',
                    'group_assigned_card_id': group_assigned_card.id,
                    'status': group_assigned_card.status,
                    'assigned_member_ids': []
                }, status=status.HTTP_200_OK)
            
            # Если member_ids передан, проверяем его валидность
            if not isinstance(member_ids, list):
                return Response({
                    'success': False,
                    'error': 'INVALID_DATA',
                    'message': 'member_ids должен быть списком'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем, что все участники принадлежат группе пользователя
            group_member_ids = set(user.group.members.values_list('id', flat=True))
            invalid_member_ids = [mid for mid in member_ids if mid not in group_member_ids]
            
            if invalid_member_ids:
                return Response({
                    'success': False,
                    'error': 'INVALID_MEMBERS',
                    'message': f'Участники {invalid_member_ids} не принадлежат вашей группе'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Определяем действие
            action = request.data.get('action', 'replace')
            
            # Обработка действия 'remove' - удаление указанных участников
            if action == 'remove':
                deleted_count, _ = GroupCardMemberAssignment.objects.filter(
                    group_assigned_card=group_assigned_card,
                    user_id__in=member_ids
                ).delete()
                
                # Получаем оставшиеся назначения
                remaining_assignments = list(GroupCardMemberAssignment.objects.filter(
                    group_assigned_card=group_assigned_card
                ).values_list('user_id', flat=True))
                
                # Сортируем: текущий пользователь первым
                remaining_assignments.sort(key=lambda x: (x != user.id, x))
                
                return Response({
                    'success': True,
                    'message': f'Удалено назначений: {deleted_count}',
                    'group_assigned_card_id': group_assigned_card.id,
                    'status': group_assigned_card.status,
                    'assigned_member_ids': remaining_assignments
                }, status=status.HTTP_200_OK)
            
            # Удаляем старые назначения (если нужно)
            if action == 'replace':
                GroupCardMemberAssignment.objects.filter(
                    group_assigned_card=group_assigned_card
                ).delete()
            
            # Создаем новые назначения
            created_count = 0
            existing_assignment_ids = set(
                group_assigned_card.member_assignments.values_list('user_id', flat=True)
            ) if action == 'add' else set()
            
            for member_id in member_ids:
                member = user.group.members.get(id=member_id)
                assignment, created = GroupCardMemberAssignment.objects.get_or_create(
                    group_assigned_card=group_assigned_card,
                    user=member,
                    defaults={'assigned_by': user}
                )
                if created or member_id not in existing_assignment_ids:
                    created_count += 1
                elif not created:
                    assignment.assigned_by = user
                    assignment.save(update_fields=['assigned_by', 'updated_at'])
            
            # Сортируем: текущий пользователь первым
            sorted_member_ids = sorted(member_ids, key=lambda x: (x != user.id, x))
            
            return Response({
                'success': True,
                'message': f'Карточка перенесена в группу. Назначено участников: {created_count}',
                'group_assigned_card_id': group_assigned_card.id,
                'status': group_assigned_card.status,
                'assigned_member_ids': sorted_member_ids
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, card_id, *args, **kwargs):
        """Изменение статуса назначения карточки группе"""
        return self.patch(request, card_id, *args, **kwargs)
    
    def patch(self, request, card_id, *args, **kwargs):
        """
        Изменить статус назначения карточки группе и/или управлять назначениями участников.
        Требуется, чтобы пользователь относился к группе.
        
        Параметры:
        - status (опционально): новый статус карточки
        - member_ids (опционально): список ID участников для назначения
          - Если передан пустой список [] - снимает все назначения участников
          - Если передан непустой список - обновляет назначения (заменяет существующие)
        - action (опционально): 'replace' (заменить все назначения), 'add' (добавить к существующим) или 'remove' (удалить указанных участников)
        """
        try:
            user = request.user
            
            # Проверяем, что у пользователя есть группа
            if not hasattr(user, 'group') or not user.group:
                return Response({
                    'success': False,
                    'error': 'NO_GROUP',
                    'message': 'Пользователь не состоит в группе'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем существование карточки
            signal_card = get_object_or_404(SignalCard, id=card_id)
            
            # Получаем назначение карточки группе
            group_assigned_card = GroupAssignedCard.objects.filter(
                group=user.group,
                signal_card=signal_card
            ).first()
            
            if not group_assigned_card:
                return Response({
                    'success': False,
                    'error': 'NOT_ASSIGNED',
                    'message': 'Карточка не назначена вашей группе'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Обновляем статус (если передан)
            new_status = request.data.get('status')
            if new_status:
                valid_statuses = [choice[0] for choice in GroupAssignedCard.STATUS_CHOICES]
                if new_status not in valid_statuses:
                    return Response({
                        'success': False,
                        'error': 'INVALID_STATUS',
                        'message': f'Недопустимый статус. Доступные: {", ".join(valid_statuses)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                group_assigned_card.status = new_status
                group_assigned_card.save(update_fields=['status', 'updated_at'])
            
            # Управляем назначениями участников (если передан member_ids)
            member_ids = request.data.get('member_ids')
            if member_ids is not None:  # Явно передан (может быть пустым списком)
                if not isinstance(member_ids, list):
                    return Response({
                        'success': False,
                        'error': 'INVALID_DATA',
                        'message': 'member_ids должен быть списком'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Если пустой список - снимаем все назначения
                if len(member_ids) == 0:
                    deleted_count, _ = GroupCardMemberAssignment.objects.filter(
                        group_assigned_card=group_assigned_card
                    ).delete()
                    
                    return Response({
                        'success': True,
                        'message': 'Все назначения участников сняты',
                        'status': group_assigned_card.status,
                        'assigned_member_ids': []
                    }, status=status.HTTP_200_OK)
                
                # Если непустой список - обновляем назначения
                # Проверяем, что все участники принадлежат группе пользователя
                group_member_ids = set(user.group.members.values_list('id', flat=True))
                invalid_member_ids = [mid for mid in member_ids if mid not in group_member_ids]
                
                if invalid_member_ids:
                    return Response({
                        'success': False,
                        'error': 'INVALID_MEMBERS',
                        'message': f'Участники {invalid_member_ids} не принадлежат вашей группе'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Определяем действие
                action = request.data.get('action', 'replace')
                
                # Обработка действия 'remove' - удаление указанных участников
                if action == 'remove':
                    deleted_count, _ = GroupCardMemberAssignment.objects.filter(
                        group_assigned_card=group_assigned_card,
                        user_id__in=member_ids
                    ).delete()
                    
                    # Получаем оставшиеся назначения
                    remaining_assignments = list(GroupCardMemberAssignment.objects.filter(
                        group_assigned_card=group_assigned_card
                    ).values_list('user_id', flat=True))
                    
                    # Сортируем: текущий пользователь первым
                    remaining_assignments.sort(key=lambda x: (x != user.id, x))
                    
                    return Response({
                        'success': True,
                        'message': f'Удалено назначений: {deleted_count}',
                        'status': group_assigned_card.status,
                        'assigned_member_ids': remaining_assignments
                    }, status=status.HTTP_200_OK)
                
                # Удаляем старые назначения (если нужно)
                if action == 'replace':
                    GroupCardMemberAssignment.objects.filter(
                        group_assigned_card=group_assigned_card
                    ).delete()
                
                # Создаем новые назначения
                created_count = 0
                existing_assignment_ids = set(
                    group_assigned_card.member_assignments.values_list('user_id', flat=True)
                ) if action == 'add' else set()
                
                for member_id in member_ids:
                    member = user.group.members.get(id=member_id)
                    assignment, created = GroupCardMemberAssignment.objects.get_or_create(
                        group_assigned_card=group_assigned_card,
                        user=member,
                        defaults={'assigned_by': user}
                    )
                    if created or member_id not in existing_assignment_ids:
                        created_count += 1
                    elif not created:
                        assignment.assigned_by = user
                        assignment.save(update_fields=['assigned_by', 'updated_at'])
                
                # Сортируем: текущий пользователь первым
                sorted_member_ids = sorted(member_ids, key=lambda x: (x != user.id, x))
                
                return Response({
                    'success': True,
                    'message': f'Назначения обновлены. Назначено участников: {created_count}',
                    'status': group_assigned_card.status,
                    'assigned_member_ids': sorted_member_ids
                }, status=status.HTTP_200_OK)
            
            # Если ничего не передано для обновления
            if not new_status and member_ids is None:
                return Response({
                    'success': False,
                    'error': 'MISSING_DATA',
                    'message': 'Не указаны данные для обновления (status или member_ids)'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Если обновлен только статус
            return Response({
                'success': True,
                'message': 'Статус обновлен',
                'status': group_assigned_card.status,
                'status_display': group_assigned_card.get_status_display()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)