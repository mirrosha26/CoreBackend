import logging
from typing import List, Optional

import strawberry
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from profile.models import (
    UserFolder, FolderCard, DeletedCard, UserNote,
    SavedFilter as SavedFilterModel
)
from signals.models import SignalCard

from .types import (
    SignalCardFiltersOutput, FlexibleDate, SavedFilterInput,
    SavedFilterMutationResult
)

logger = logging.getLogger(__name__)


def invalidate_user_cache_after_mutation(user_id: int):
    """
    Централизованная инвалидация кэша для пользовательских мутаций.
    
    Функция инвалидирует все кэши, которые могут быть затронуты при изменении
    данных пользователя (избранное, заметки, удаления и т.д.), чтобы лента
    отображала актуальное состояние.
    """
    try:
        from .comprehensive_query_caching import get_comprehensive_cache_manager
        from .query_caching import CachedQueryManager
        
        comprehensive_cache_manager = get_comprehensive_cache_manager()
        comprehensive_cache_manager.invalidate_user_feed_cache(user_id, partial=True)
        
        query_cache_manager = CachedQueryManager()
        query_cache_manager.invalidate_user_data(user_id)
        
    except Exception as e:
        logger.error(f"Не удалось инвалидировать кэш для пользователя {user_id}: {e}")


@strawberry.type
class ParticipantFollowResult:
    """Тип результата для операций подписки/отписки от участника."""
    success: bool
    message: str
    is_saved: bool
    participant_id: Optional[str] = None


@strawberry.type
class Mutation:
    """Определения GraphQL мутаций для управления карточками."""
    
    @strawberry.field
    def create_saved_filter(
        self, 
        info, 
        filter_input: SavedFilterInput
    ) -> SavedFilterMutationResult:
        """Создает новый сохраненный фильтр для аутентифицированного пользователя."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            if SavedFilterModel.objects.filter(user=user, name=filter_input.name).exists():
                return SavedFilterMutationResult(
                    success=False,
                    message=f"Фильтр с именем '{filter_input.name}' уже существует",
                    error_code="NAME_EXISTS"
                )
            
            participant_filter_mode = None
            participant_filter_ids = None
            participant_filter_types = None
            
            if filter_input.participant_filter:
                participant_filter_mode = filter_input.participant_filter.mode.value
                if filter_input.participant_filter.participantIds:
                    participant_filter_ids = [int(pid) for pid in filter_input.participant_filter.participantIds]
                participant_filter_types = filter_input.participant_filter.participantTypes
            
            saved_filter = SavedFilterModel.objects.create(
                user=user,
                name=filter_input.name,
                description=filter_input.description,
                is_default=filter_input.is_default or False,
                stages=filter_input.stages,
                round_statuses=filter_input.round_statuses,
                search=filter_input.search,
                featured=filter_input.featured,
                is_open=filter_input.is_open,
                new=filter_input.new,
                trending=filter_input.trending,
                hide_liked=filter_input.hide_liked,
                start_date=filter_input.start_date,
                end_date=filter_input.end_date,
                min_signals=filter_input.min_signals,
                max_signals=filter_input.max_signals,
                participant_filter_mode=participant_filter_mode,
                participant_filter_ids=participant_filter_ids,
                participant_filter_types=participant_filter_types,
            )
            
            if filter_input.categories:
                from signals.models import Category
                categories = Category.objects.filter(id__in=filter_input.categories)
                saved_filter.categories.set(categories)
            
            if filter_input.participants:
                from signals.models import Participant
                participants = Participant.objects.filter(id__in=filter_input.participants)
                saved_filter.participants.set(participants)
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Сохраненный фильтр '{saved_filter.name}' успешно создан",
                saved_filter=saved_filter
            )
            
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при создании сохраненного фильтра: {str(e)}",
                error_code="CREATE_ERROR"
            )

    @strawberry.field
    def update_saved_filter(
        self, 
        info, 
        filter_id: strawberry.ID,
        filter_input: SavedFilterInput
    ) -> SavedFilterMutationResult:
        """Обновляет существующий сохраненный фильтр."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            saved_filter = SavedFilterModel.objects.get(id=int(filter_id), user=user)
            
            if (filter_input.name != saved_filter.name and 
                SavedFilterModel.objects.filter(user=user, name=filter_input.name).exists()):
                return SavedFilterMutationResult(
                    success=False,
                    message=f"Фильтр с именем '{filter_input.name}' уже существует",
                    error_code="NAME_EXISTS"
                )
            
            saved_filter.name = filter_input.name
            saved_filter.description = filter_input.description
            saved_filter.is_default = filter_input.is_default or False
            saved_filter.stages = filter_input.stages
            saved_filter.round_statuses = filter_input.round_statuses
            saved_filter.search = filter_input.search
            saved_filter.featured = filter_input.featured
            saved_filter.is_open = filter_input.is_open
            saved_filter.new = filter_input.new
            saved_filter.trending = filter_input.trending
            saved_filter.hide_liked = filter_input.hide_liked
            saved_filter.start_date = filter_input.start_date
            saved_filter.end_date = filter_input.end_date
            saved_filter.min_signals = filter_input.min_signals
            saved_filter.max_signals = filter_input.max_signals
            
            if filter_input.participant_filter is not None:
                saved_filter.participant_filter_mode = filter_input.participant_filter.mode.value
                if filter_input.participant_filter.participantIds:
                    saved_filter.participant_filter_ids = [int(pid) for pid in filter_input.participant_filter.participantIds]
                else:
                    saved_filter.participant_filter_ids = None
                saved_filter.participant_filter_types = filter_input.participant_filter.participantTypes
            else:
                saved_filter.participant_filter_mode = None
                saved_filter.participant_filter_ids = None
                saved_filter.participant_filter_types = None
            
            saved_filter.save()
            
            if filter_input.categories is not None:
                from signals.models import Category
                categories = Category.objects.filter(id__in=filter_input.categories)
                saved_filter.categories.set(categories)
            
            if filter_input.participants is not None:
                from signals.models import Participant
                participants = Participant.objects.filter(id__in=filter_input.participants)
                saved_filter.participants.set(participants)
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Сохраненный фильтр '{filter_input.name}' успешно обновлен",
                saved_filter=saved_filter
            )
            
        except SavedFilterModel.DoesNotExist:
            return SavedFilterMutationResult(
                success=False,
                message="Сохраненный фильтр не найден",
                error_code="NOT_FOUND"
            )
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при обновлении сохраненного фильтра: {str(e)}",
                error_code="UPDATE_ERROR"
            )

    @strawberry.field
    def delete_saved_filter(
        self, 
        info, 
        filter_id: strawberry.ID
    ) -> SavedFilterMutationResult:
        """Удаляет сохраненный фильтр."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            saved_filter = SavedFilterModel.objects.get(id=int(filter_id), user=user)
            filter_name = saved_filter.name
            saved_filter.delete()
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Сохраненный фильтр '{filter_name}' успешно удален"
            )
            
        except SavedFilterModel.DoesNotExist:
            return SavedFilterMutationResult(
                success=False,
                message="Сохраненный фильтр не найден",
                error_code="NOT_FOUND"
            )
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при удалении сохраненного фильтра: {str(e)}",
                error_code="DELETE_ERROR"
            )

    @strawberry.field
    def apply_saved_filter(
        self, 
        info, 
        filter_id: strawberry.ID
    ) -> SavedFilterMutationResult:
        """Применяет сохраненный фильтр к сессии пользователя."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            saved_filter = SavedFilterModel.objects.get(id=int(filter_id), user=user)
            
            # Применяем фильтр к сессии
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
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Сохраненный фильтр '{saved_filter.name}' успешно применен",
                saved_filter=saved_filter
            )
            
        except SavedFilterModel.DoesNotExist:
            return SavedFilterMutationResult(
                success=False,
                message="Сохраненный фильтр не найден",
                error_code="NOT_FOUND"
            )
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при применении сохраненного фильтра: {str(e)}",
                error_code="APPLY_ERROR"
            )

    @strawberry.field
    def save_current_filter_as(
        self, 
        info, 
        name: str,
        description: Optional[str] = None,
        is_default: Optional[bool] = False
    ) -> SavedFilterMutationResult:
        """Сохраняет текущее состояние фильтров из сессии как новый сохраненный фильтр."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            if SavedFilterModel.objects.filter(user=user, name=name).exists():
                return SavedFilterMutationResult(
                    success=False,
                    message=f"Фильтр с именем '{name}' уже существует",
                    error_code="NAME_EXISTS"
                )
            
            # Получаем текущие фильтры из сессии
            current_filters = request.session.get('current_filters', {})
            
            if not current_filters:
                return SavedFilterMutationResult(
                    success=False,
                    message="Нет текущего фильтра для сохранения",
                    error_code="NO_CURRENT_FILTER"
                )
            
            from signals.models import Category, Participant
            from datetime import datetime
            
            # Парсим даты из строк
            start_date = None
            if current_filters.get('start_date'):
                try:
                    start_date = datetime.fromisoformat(current_filters['start_date']).date()
                except (ValueError, TypeError):
                    pass
            
            end_date = None
            if current_filters.get('end_date'):
                try:
                    end_date = datetime.fromisoformat(current_filters['end_date']).date()
                except (ValueError, TypeError):
                    pass
            
            saved_filter = SavedFilterModel.objects.create(
                user=user,
                name=name,
                description=description,
                is_default=is_default or False,
                stages=current_filters.get('stages', []),
                round_statuses=current_filters.get('round_statuses', []),
                search=current_filters.get('search'),
                featured=current_filters.get('featured'),
                is_open=current_filters.get('is_open'),
                hide_liked=current_filters.get('hide_liked'),
                start_date=start_date,
                end_date=end_date,
                min_signals=current_filters.get('min_signals'),
                max_signals=current_filters.get('max_signals'),
            )
            
            # Устанавливаем категории и участников
            if current_filters.get('categories'):
                categories = Category.objects.filter(id__in=[int(c) for c in current_filters['categories']])
                saved_filter.categories.set(categories)
            
            if current_filters.get('participants'):
                participants = Participant.objects.filter(id__in=[int(p) for p in current_filters['participants']])
                saved_filter.participants.set(participants)
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Текущий фильтр успешно сохранен как '{name}'",
                saved_filter=saved_filter
            )
            
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при сохранении текущего фильтра: {str(e)}",
                error_code="SAVE_ERROR"
            )

    @strawberry.field
    def set_default_saved_filter(
        self, 
        info, 
        filter_id: strawberry.ID
    ) -> SavedFilterMutationResult:
        """Устанавливает сохраненный фильтр как фильтр по умолчанию для пользователя."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return SavedFilterMutationResult(
                success=False,
                message="Требуется аутентификация",
                error_code="AUTH_REQUIRED"
            )
        
        try:
            saved_filter = SavedFilterModel.objects.get(id=int(filter_id), user=user)
            
            SavedFilterModel.objects.filter(user=user, is_default=True).update(is_default=False)
            
            saved_filter.is_default = True
            saved_filter.save()
            
            return SavedFilterMutationResult(
                success=True,
                message=f"Фильтр '{saved_filter.name}' установлен как фильтр по умолчанию",
                saved_filter=saved_filter
            )
            
        except SavedFilterModel.DoesNotExist:
            return SavedFilterMutationResult(
                success=False,
                message="Сохраненный фильтр не найден",
                error_code="NOT_FOUND"
            )
        except Exception as e:
            return SavedFilterMutationResult(
                success=False,
                message=f"Ошибка при установке фильтра по умолчанию: {str(e)}",
                error_code="SET_DEFAULT_ERROR"
            )

    @strawberry.field
    def toggle_participant_follow(
        self, 
        info, 
        participant_id: strawberry.ID,
        is_saved: bool
    ) -> ParticipantFollowResult:
        """Устанавливает статус подписки на участника (сохранить/удалить инвестора на основе параметра isSaved)."""
        request = info.context["request"]
        user = request.user
        
        if not user.is_authenticated:
            return ParticipantFollowResult(
                success=False,
                message="Требуется аутентификация",
                is_saved=False
            )
        
        try:
            from signals.models import Participant
            from profile.models import SavedParticipant, UserFeed
            
            participant = get_object_or_404(Participant, id=int(participant_id))
            
            saved_participant = SavedParticipant.objects.filter(
                user=user, 
                participant=participant
            ).first()
            
            if is_saved:
                if saved_participant:
                    return ParticipantFollowResult(
                        success=True,
                        message="Инвестор уже сохранен",
                        is_saved=True,
                        participant_id=str(participant_id)
                    )
                else:
                    SavedParticipant.objects.create(user=user, participant=participant)
                    
                    user_feed, _ = UserFeed.objects.get_or_create(user=user)
                    if not user_feed.participants.filter(pk=participant.id).exists():
                        user_feed.participants.add(participant)
                        user_feed.save()
                    
                    invalidate_user_cache_after_mutation(user.id)
                    
                    return ParticipantFollowResult(
                        success=True,
                        message="Инвестор добавлен в список сохраненных",
                        is_saved=True,
                        participant_id=str(participant_id)
                    )
            else:
                if saved_participant:
                    saved_participant.delete()
                    
                    user_feed, _ = UserFeed.objects.get_or_create(user=user)
                    if user_feed.participants.filter(pk=participant.id).exists():
                        user_feed.participants.remove(participant)
                        user_feed.save()
                    
                    invalidate_user_cache_after_mutation(user.id)
                    
                    return ParticipantFollowResult(
                        success=True,
                        message="Инвестор удален из списка сохраненных",
                        is_saved=False,
                        participant_id=str(participant_id)
                    )
                else:
                    return ParticipantFollowResult(
                        success=True,
                        message="Инвестор уже не сохранен",
                        is_saved=False,
                        participant_id=str(participant_id)
                    )
                
        except Participant.DoesNotExist:
            return ParticipantFollowResult(
                success=False,
                message="Инвестор не найден",
                is_saved=False
            )
        except Exception as e:
            return ParticipantFollowResult(
                success=False,
                message=f"Ошибка при установке статуса подписки на инвестора: {str(e)}",
                is_saved=False
            )

