import strawberry
import strawberry_django
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Min, Max, Count, Q, Exists, OuterRef
from django.utils import timezone

from profile.models import (
    UserNote as UserNoteModel, FolderCard, DeletedCard, SavedParticipant,
    SavedFilter as SavedFilterModel, GroupAssignedCard, UserGroup
)
from signals.models import (
    SignalCard, Signal, Category, Participant, TeamMember, STAGES, ROUNDS,
    Source, SourceType as SourceTypeModel, SignalType
)

User_Model = get_user_model()


def parse_flexible_date_value(value) -> date:
    """Парсит гибкий ввод даты - принимает DD.MM.YYYY, YYYY-MM-DD или объекты date."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%m-%d-%Y").date()
        except ValueError:
            raise ValueError(f"Неверный формат даты: {value}. Ожидается DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY или MM-DD-YYYY")
    raise ValueError(f"Неверный тип даты: {type(value)}")


def serialize_flexible_date(value) -> str:
    """Сериализует дату в формат DD.MM.YYYY для единообразия."""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def parse_flexible_date_literal(value_node) -> date:
    """Парсит дату из GraphQL литерала."""
    return parse_flexible_date_value(value_node.value)


FlexibleDate = strawberry.scalar(
    date,
    serialize=serialize_flexible_date,
    parse_value=parse_flexible_date_value,
    parse_literal=parse_flexible_date_literal,
    description="Гибкий скаляр даты, принимающий форматы DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY или MM-DD-YYYY"
)


class ParticipantTypeEnum(Enum):
    """Enum для типов участников на основе PARTICIPANTS_TYPES из моделей."""
    FUND = "fund"
    RESEARCH = "research"
    INVESTOR = "investor"
    ENGINEER = "engineer"
    ANGEL = "angel"
    INFLUENCER = "influencer"
    UNKNOWN = "unknown"
    FOUNDER = "founder"
    SCOUT = "scout"
    ACCELERATOR = "accelerator"
    PLATFORM = "platform"
    MARKETING = "marketing"
    WRITING = "writing"
    CHIEF_OF_STAFF = "chief_of_staff"
    TALENT_PARTNER = "talent_partner"
    LEGAL = "legal"
    OPERATIONS = "operations"
    SOCIALS = "socials"
    BUSINESS_DEVELOPMENT = "business_development"
    SECURITY = "security"
    FINANCE = "finance"
    DUE_DILIGENCE = "due_diligence"
    DATA_SCIENCE = "data_science"
    PRODUCT = "product"
    PROTOCOL = "protocol"
    DEFI = "defi"
    GROWTH = "growth"
    DESIGN = "design"
    EIR = "eir"
    DATA = "data"
    STRATEGY = "strategy"
    RAISING_CAPITAL = "raising_capital"
    BOARD = "board"
    ANALYST = "analyst"
    CONTENT = "content"
    INVESTOR_RELATIONS = "investor_relations"
    ADVISOR = "advisor"
    CEO = "ceo"
    PORTFOLIO = "portfolio"
    ASSET_MANAGEMENT = "asset_management"
    EVENTS = "events"
    COMMUNICATIONS = "communications"
    COMMUNITY = "community"
    TRADING = "trading"
    SYNDICATE = "syndicate"
    MARKET_MAKER = "market_maker"
    GA = "GA"
    COMPANY = "company"
    OTHER = "other"


@strawberry_django.type(User_Model)
class User:
    """Оптимизированный GraphQL тип User с использованием strawberry_django."""
    id: strawberry.auto
    username: strawberry.auto
    email: strawberry.auto
    first_name: strawberry.auto
    last_name: strawberry.auto
    is_active: strawberry.auto
    date_joined: strawberry.auto
    
    @strawberry_django.field(only=["avatar"], name="avatar")
    def avatar_url(self, info) -> Optional[str]:
        """Получает полный URL аватара."""
        if not self.avatar:
            return None
        from frontend_api.serializers.utils import build_absolute_image_url
        from django.conf import settings
        return build_absolute_image_url(
            self, True, field_name='avatar', base_url=settings.BASE_IMAGE_URL
        )


@strawberry_django.type(Category)
class Category:
    """Оптимизированный GraphQL тип Category."""
    id: strawberry.auto
    name: strawberry.auto
    slug: strawberry.auto
    
    parent_category_id: Optional[strawberry.ID] = strawberry_django.field(
        only=["parent_category__id"]
    )


@strawberry_django.type(SignalType)
class SignalType:
    """GraphQL тип SignalType."""
    id: strawberry.auto
    name: strawberry.auto
    slug: strawberry.auto


@strawberry_django.type(Source)
class SourceType:
    id: strawberry.auto
    slug: strawberry.auto
    tracking_enabled: strawberry.auto
    blocked: strawberry.auto
    nonexistent: strawberry.auto
    social_network_id: strawberry.auto

    @strawberry_django.field
    def source_type(self, info) -> Optional[str]:
        return self.source_type.name if self.source_type else None

    @strawberry_django.field
    def profile_link(self, info) -> Optional[str]:
        return self.get_profile_link()


@strawberry_django.type(Participant)
class Participant:
    """Оптимизированный GraphQL тип Participant с подсказками оптимизации."""
    id: strawberry.auto
    name: strawberry.auto
    slug: strawberry.auto
    type: strawberry.auto
    
    additional_name: strawberry.auto = strawberry_django.field(name="additionalName")
    about: strawberry.auto
    image: strawberry.auto
    
    monthly_signals_count: strawberry.auto = strawberry_django.field(name="monthlySignalsCount")
    
    @strawberry_django.field
    def sources(self, info) -> List[SourceType]:
        """Получает источники используя DataLoader для предотвращения N+1 запросов."""
        from .dataloaders import load_participant_sources
        return load_participant_sources(info, self.id)
    
    @strawberry_django.field(
        only=["id"],
        name="isSaved"
    )
    def is_saved(self, info) -> bool:
        """Проверяет, сохранил ли пользователь этого участника."""
        if not info.context:
            return False
            
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return False
        
        from .dataloaders import load_participant_saved_status
        saved_status = load_participant_saved_status(info, self.id)
        return saved_status if saved_status is not None else False
    
    @strawberry_django.field(only=["image"], name="imageUrl")
    def image_url(self, info) -> Optional[str]:
        """Получает полный URL изображения."""
        if not self.image:
            return None
        request = info.context.get("request")
        if request:
            return request.build_absolute_uri(self.image.url)
        return self.image.url

    @strawberry_django.field
    def children(self, info) -> List["Participant"]:
        """Дочерние участники (те, у кого associated_with = этот участник, но не сам на себя)"""
        from .dataloaders import load_participant_children
        return load_participant_children(info, self.id)

    @strawberry_django.field
    def parent(self, info) -> Optional["Participant"]:
        """Родительский участник (associated_with), если он существует и не является самим собой"""
        from .dataloaders import load_participant_parent
        return load_participant_parent(info, self.id)


@strawberry_django.type(TeamMember)
class TeamMember:
    """Оптимизированный GraphQL тип TeamMember."""
    id: strawberry.auto
    name: strawberry.auto
    headline: strawberry.auto
    site: strawberry.auto
    crunchbase: strawberry.auto
    twitter: strawberry.auto
    linkedin: strawberry.auto
    instagram: strawberry.auto
    github: strawberry.auto
    producthunt: strawberry.auto
    email: strawberry.auto
    
    @strawberry_django.field(only=["image"])
    def image_url(self, info) -> Optional[str]:
        if not self.image:
            return None
        request = info.context.get("request")
        if request:
            return request.build_absolute_uri(self.image.url)
        return self.image.url


@strawberry_django.type(Signal)
class Signal:
    """Оптимизированный GraphQL тип Signal с подсказками предзагрузки."""
    id: strawberry.auto
    created_at: strawberry.auto
    updated_at: strawberry.auto
    
    @strawberry_django.field(only=["created_at"])
    def date(self, info) -> datetime:
        return self.created_at
    
    participant: Optional[Participant] = strawberry_django.field(
        select_related=["participant"]
    )
    
    associated_participant: Optional[Participant] = strawberry_django.field(
        select_related=["associated_participant"],
        name="associatedParticipant"
    )
    
    signal_type: Optional[SignalType] = strawberry_django.field(
        select_related=["signal_type"],
        name="signalType"
    )
    
    @strawberry_django.field(
        only=["participant__about", "associated_participant__about", "signal_type__name"]
    )
    def description(self, info) -> Optional[str]:
        """Генерирует описание с подсказками оптимизации."""
        if self.associated_participant and hasattr(self.associated_participant, 'about'):
            return self.associated_participant.about
        elif self.participant and hasattr(self.participant, 'about'):
            return self.participant.about
        elif self.signal_type and hasattr(self.signal_type, 'name'):
            return f"Signal from {self.signal_type.name}"
        return None


@strawberry_django.type(UserNoteModel)
class UserNote:
    """Оптимизированный GraphQL тип UserNote."""
    id: strawberry.auto
    note_text: strawberry.auto
    created_at: strawberry.auto
    updated_at: strawberry.auto


@strawberry_django.type(UserGroup)
class UserGroupGraphQL:
    """GraphQL тип UserGroup."""
    id: strawberry.auto
    name: strawberry.auto
    slug: strawberry.auto
    logo: strawberry.auto
    
    @strawberry_django.field(only=["logo"])
    def logo_url(self, info) -> Optional[str]:
        """Получает полный URL логотипа."""
        if not self.logo:
            return None
        request = info.context.get("request")
        if request:
            return request.build_absolute_uri(self.logo.url)
        return self.logo.url
    
    @strawberry_django.field(name="createdAt")
    def created_at(self) -> datetime:
        return self.created_at
    
    @strawberry_django.field(name="updatedAt")
    def updated_at(self) -> datetime:
        return self.updated_at


@strawberry.type
class AssignedMemberInfo:
    """Информация о пользователе, назначенном на карточку."""
    user: User
    assigned_by: Optional[User] = strawberry.field(name="assignedBy")
    assigned_at: Optional[datetime] = strawberry.field(name="assignedAt")


@strawberry_django.type(GroupAssignedCard)
class GroupAssignedCardGraphQL:
    """GraphQL тип GroupAssignedCard."""
    id: strawberry.auto
    status: strawberry.auto
    
    @strawberry_django.field(name="createdAt")
    def created_at(self) -> datetime:
        return self.created_at
    
    @strawberry_django.field(name="updatedAt")
    def updated_at(self) -> datetime:
        return self.updated_at
    
    group: UserGroupGraphQL = strawberry_django.field(
        select_related=["group"]
    )
    
    signal_card: "SignalCard" = strawberry_django.field(
        select_related=["signal_card"],
        name="signalCard"
    )
    
    @strawberry_django.field(name="assignedUsersCount")
    def assigned_users_count(self, info) -> int:
        """Возвращает количество специально назначенных участников на эту карточку."""
        return self.get_assigned_member_count()
    
    @strawberry_django.field(name="totalGroupMembersCount")
    def total_group_members_count(self, info) -> int:
        """Возвращает общее количество участников группы."""
        return self.get_all_group_member_count()
    
    @strawberry_django.field(name="statusName")
    def status_name(self, info) -> Optional[str]:
        """Получает читаемое имя статуса вместо кода статуса."""
        if not self.status:
            return None
        
        from profile.models import GroupAssignedCard
        status_dict = dict(GroupAssignedCard.STATUS_CHOICES)
        return status_dict.get(self.status, self.status)
    
    @strawberry_django.field(name="assignedMembers")
    def assigned_members(self, info) -> List[AssignedMemberInfo]:
        """
        Returns list of specifically assigned members with assignment metadata.
        Only populated when includeAssignedMembers flag is set to true.
        """
        request = info.context.get("request") if info.context else None
        if request and hasattr(request, '_graphql_flags'):
            include_assigned_members = request._graphql_flags.get('include_assigned_members', False)
            if not include_assigned_members:
                return []
        
        if hasattr(self, 'prefetched_assignments'):
            assignments = self.prefetched_assignments
        else:
            from profile.models import GroupCardMemberAssignment
            assignments = GroupCardMemberAssignment.objects.filter(
                group_assigned_card=self
            ).select_related('user', 'assigned_by')
        
        result = []
        for assignment in assignments:
            result.append(AssignedMemberInfo(
                user=assignment.user,
                assigned_by=assignment.assigned_by,
                assigned_at=assignment.created_at
            ))
        
        return result


@strawberry.type
class FolderInfo:
    """Детальная информация о папке, соответствующая формату REST API."""
    id: strawberry.ID
    name: str
    is_default: bool
    has_card: bool


@strawberry.type
class UserData:
    """Пользовательские данные для SignalCard."""
    is_favorited: bool
    is_deleted: bool
    user_note: Optional[UserNote] = None
    folders: List[FolderInfo]
    is_assigned_to_group: bool = strawberry.field(name="isAssignedToGroup")


@strawberry.type
class SocialLink:
    """GraphQL тип SocialLink."""
    name: str
    url: str


@strawberry_django.type(SignalCard)
class SignalCard:
    """Оптимизированный GraphQL тип SignalCard с комплексными подсказками оптимизации."""
    id: strawberry.auto
    slug: strawberry.auto
    uuid: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    url: strawberry.auto
    created_at: strawberry.auto
    updated_at: strawberry.auto
    last_round: strawberry.auto
    stage: strawberry.auto
    round_status: strawberry.auto
    is_open: strawberry.auto
    reference_url: strawberry.auto
    featured: strawberry.auto
    
    @strawberry_django.field(only=["image"])
    def image_url(self, info) -> Optional[str]:
        """Получает полный URL изображения с оптимизацией."""
        if not self.image:
            return None
        request = info.context.get("request")
        if request:
            return request.build_absolute_uri(self.image.url)
        return self.image.url
    
    @strawberry_django.field
    def trending(self, info) -> bool:
        """Проверяет, является ли проект трендовым (минимум 5 уникальных связанных участников за последнюю неделю)."""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Q
        from signals.models import Signal
        
        # Calculate the date 7 days ago
        one_week_ago = timezone.now() - timedelta(days=7)
        
        # Build query for recent signals
        recent_signals = Signal.objects.filter(
            signal_card=self,
            created_at__gte=one_week_ago
        ).filter(
            # Must have at least one participant (either main or associated)
            Q(participant__isnull=False) | Q(associated_participant__isnull=False)
        )
        
        # Count unique associated_participants for this signal card in the last week
        # Since we only count signals where participants appear as associated_participant
        unique_participants_count = recent_signals.values(
            'associated_participant_id'
        ).distinct().count()
        
        return unique_participants_count >= 5
    
    categories: List[Category] = strawberry_django.field(
        prefetch_related=["categories"]
    )
    
    team_members: List[TeamMember] = strawberry_django.field(
        prefetch_related=["team_members"]
    )
    
    @strawberry_django.field
    def signals(self, info, limit_participants: Optional[bool] = None) -> List[Signal]:
        """
        Получает сигналы с оптимизированной пакетной загрузкой и фильтрацией приватности.
        
        Использует OptimizedSignalResolver для лучшей производительности с:
        - Фильтрацией приватности на уровне БД
        - Кэшированием на уровне запроса
        - Эффективным ограничением участников
        - Пакетными операциями когда возможно
        
        Args:
            limit_participants: Если True, ограничивает первыми 8 уникальными участниками для производительности.
                              Если False/None, возвращает ВСЕ сигналы, прошедшие фильтрацию приватности.
                              Автоматически определяется на основе контекста запроса, если не указано.
        """
        if hasattr(self, '_optimized_signals') and hasattr(self, '_signals_preloaded') and self._signals_preloaded:
            return self._optimized_signals
        
        from .optimized_signal_resolver import get_optimized_signals_for_card
        
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if limit_participants is None:
            parent_field = None
            if hasattr(info, 'path') and info.path and hasattr(info.path, 'prev') and info.path.prev:
                parent_field = info.path.prev.key
            
            limit_participants = parent_field != 'signalCard'
        return get_optimized_signals_for_card(
            signal_card_id=self.id,
            user=user,
            limit_participants=limit_participants
        )
    
    @strawberry_django.field(name="remainingParticipantsCount")
    def remaining_participants_count(self, info) -> int:
        """
        Получает количество участников сверх первых 5 с оптимизированной пакетной загрузкой.
        
        Использует DataLoader для пакетной оптимизации когда возможно, иначе использует индивидуальное вычисление.
        """
        from .dataloaders import get_dataloader_manager
        
        dataloader_manager = get_dataloader_manager(info)
        if dataloader_manager:
            remaining_count_loader = dataloader_manager.get_remaining_participants_count_loader()
            if remaining_count_loader:
                return remaining_count_loader.load(self.id)
        
        from .optimized_signal_resolver import get_remaining_participants_count
        
        parent_field = None
        if hasattr(info, 'path') and info.path and hasattr(info.path, 'prev') and info.path.prev:
            parent_field = info.path.prev.key
        
        if parent_field == 'signalCard':
            return 0
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        return get_remaining_participants_count(
            signal_card_id=self.id,
            user=user
        )
    
    @strawberry_django.field(name="latestSignalDate")
    def latest_signal_date(self, info) -> Optional[datetime]:
        """Получает дату последнего сигнала используя оптимизацию DataLoader."""
        from .dataloaders import get_dataloader_manager
        
        dataloader_manager = get_dataloader_manager(info)
        if dataloader_manager:
            latest_date_loader = dataloader_manager.get_latest_signal_date_loader()
            if latest_date_loader:
                return latest_date_loader.load(self.id)
        
        from django.db.models import Max
        from signals.models import Signal
        
        result = Signal.objects.filter(signal_card_id=self.id).aggregate(
            latest_date=Max('created_at')
        )
        return result['latest_date']
    
    @strawberry_django.field(
        annotate={
            "oldest_signal_date": lambda info: Min("signals__created_at")
        }
    )
    def oldest_signal_date(self, info) -> Optional[datetime]:
        return self.oldest_signal_date
    
    @strawberry_django.field(
        annotate={
            "oldest_signal_date": lambda info: Min("signals__created_at")
        },
        name="discoveredAt"
    )
    def discovered_at(self, info) -> Optional[datetime]:
        return self.oldest_signal_date
    
    @strawberry_django.field(only=["id"], name="hasTicket")
    def has_ticket(self, info) -> bool:
        """Проверяет, создал ли текущий пользователь тикет для этой карточки."""
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return False
        
        from .dataloaders import load_signal_card_ticket_status
        ticket_status = load_signal_card_ticket_status(info, self.id)
        return ticket_status if ticket_status is not None else False
    
    @strawberry_django.field(only=["more"], name="socialLinks")
    def social_links(self, info) -> List[SocialLink]:
        """Извлекает социальные ссылки из поля 'more'."""
        try:
            from frontend_api.serializers.cards.base import extract_social_links
            if not hasattr(self, 'more') or not self.more:
                return []
            social_links_data = extract_social_links(self.more)
            return [SocialLink(name=link['name'], url=link['url']) for link in social_links_data]
        except Exception:
            return []
    
    @strawberry_django.field(
        only=["id"],
        name="userData"
    )
    def user_data(self, info) -> Optional[UserData]:
        """Получает пользовательские данные с оптимизацией используя DataLoader."""
        try:
            request = info.context.get("request")
            if not request:
                return None
                
            user = getattr(request, 'user', None)
            if not user or not getattr(user, 'is_authenticated', False):
                return None
            
            if not hasattr(user, 'id') or user.id is None:
                return None
            
            from .dataloaders import get_dataloader_manager
            
            dataloader_manager = get_dataloader_manager(info)
            if dataloader_manager:
                bulk_loader = dataloader_manager.get_user_data_bulk_loader()
                if bulk_loader:
                    try:
                        bulk_data = bulk_loader.load(self.id)
                        if bulk_data:
                            from profile.models import UserFolder
                            
                            all_user_folders = UserFolder.objects.filter(user=user)
                            
                            folders_with_card_ids = set(UserFolder.objects.filter(
                                user=user,
                                folder_cards__signal_card=self
                            ).values_list('id', flat=True))
                            
                            # Build folder info list
                            folders = []
                            for folder in all_user_folders:
                                folders.append(FolderInfo(
                                    id=str(folder.id),
                                    name=folder.name,
                                    is_default=folder.is_default,
                                    has_card=folder.id in folders_with_card_ids
                                ))
                            
                            is_assigned_to_group = False
                            if hasattr(user, 'group') and user.group:
                                is_assigned_to_group = GroupAssignedCard.objects.filter(
                                    group=user.group,
                                    signal_card=self
                                ).exists()
                            
                            return UserData(
                                is_favorited=bulk_data.get('isFavorited', False),
                                is_deleted=bulk_data.get('isDeleted', False),
                                user_note=bulk_data.get('userNote'),
                                folders=folders,
                                is_assigned_to_group=is_assigned_to_group
                            )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Bulk loader failed for userData on card {self.id}: {type(e).__name__}: {e}", exc_info=True)
            
            from profile.models import FolderCard, DeletedCard
            
            is_favorited = FolderCard.objects.filter(
                folder__user=user,
                signal_card=self
            ).exists()
            
            is_deleted = DeletedCard.objects.filter(
                user=user,
                signal_card=self
            ).exists()
            
            # Get user note
            try:
                user_note = UserNoteModel.objects.get(user=user, signal_card=self)
            except UserNoteModel.DoesNotExist:
                user_note = None
            
            from profile.models import UserFolder
            
            all_user_folders = UserFolder.objects.filter(user=user)
            
            folders_with_card_ids = set(UserFolder.objects.filter(
                user=user,
                folder_cards__signal_card=self
            ).values_list('id', flat=True))
            
            # Build folder info list
            folders = []
            for folder in all_user_folders:
                folders.append(FolderInfo(
                    id=str(folder.id),
                    name=folder.name,
                    is_default=folder.is_default,
                    has_card=folder.id in folders_with_card_ids
                ))
            
            is_assigned_to_group = False
            if hasattr(user, 'group') and user.group:
                is_assigned_to_group = GroupAssignedCard.objects.filter(
                    group=user.group,
                    signal_card=self
                ).exists()
            
            return UserData(
                is_favorited=is_favorited,
                is_deleted=is_deleted,
                user_note=user_note,
                folders=folders,
                is_assigned_to_group=is_assigned_to_group
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in userData resolver for signal_card {self.id}: {e}", exc_info=True)
            return None
    
    @strawberry_django.field(name="assignedMembers")
    def assigned_members(self, info) -> List[AssignedMemberInfo]:
        """
        Возвращает список специально назначенных участников для этой карточки, если она назначена группе пользователя.
        Заполняется только когда флаг includeAssignedMembers установлен в true в запросе signalCards.
        """
        # Check if flag is set in request context
        request = info.context.get("request") if info.context else None
        if request and hasattr(request, '_graphql_flags'):
            include_assigned_members = request._graphql_flags.get('include_assigned_members', False)
            if not include_assigned_members:
                return []
        else:
            return []
        
        # Check if user is authenticated and has a group
        user = request.user if request and request.user.is_authenticated else None
        if not user or not hasattr(user, 'group') or not user.group:
            return []
        
        # Check if card is assigned to user's group
        from profile.models import GroupAssignedCard, GroupCardMemberAssignment
        try:
            group_assigned_card = GroupAssignedCard.objects.get(
                group=user.group,
                signal_card=self
            )
        except GroupAssignedCard.DoesNotExist:
            return []
        
        # Get assignments with prefetch for optimization
        assignments = GroupCardMemberAssignment.objects.filter(
            group_assigned_card=group_assigned_card
        ).select_related('user', 'assigned_by')
        
        result = []
        for assignment in assignments:
            result.append(AssignedMemberInfo(
                user=assignment.user,
                assigned_by=assignment.assigned_by,
                assigned_at=assignment.created_at
            ))
        
        return result
    
    @strawberry_django.field(only=["stage"])
    def stage_name(self, info) -> Optional[str]:
        """Получает читаемое имя стадии вместо slug."""
        if not self.stage:
            return None
        
        stage_dict = dict(STAGES)
        return stage_dict.get(self.stage, self.stage)
    
    @strawberry_django.field(only=["round_status"])
    def round_status_name(self, info) -> Optional[str]:
        """Получает читаемое имя статуса раунда вместо slug."""
        if not self.round_status:
            return None
            
        rounds_dict = dict(ROUNDS)
        return rounds_dict.get(self.round_status, self.round_status)


@strawberry.type
class SignalCardConnection:
    """Тип соединения для пагинированных результатов SignalCard."""
    nodes: List[SignalCard]
    total_count: int
    has_next_page: bool
    has_previous_page: bool
    current_page: int
    total_pages: int


@strawberry.type
class GroupAssignedCardConnection:
    """Тип соединения для пагинированных результатов GroupAssignedCard."""
    nodes: List[GroupAssignedCardGraphQL]
    total_count: int
    has_next_page: bool
    has_previous_page: bool
    current_page: int
    total_pages: int


@strawberry.type
class ParticipantConnection:
    """Тип соединения для пагинированных результатов Participant."""
    nodes: List[Participant]
    total_count: int
    has_next_page: bool
    has_previous_page: bool
    current_page: int
    total_pages: int


@strawberry.type
class FounderInfo:
    """Информация об основателе для сигналов основателей."""
    name: str
    slug: str
    image_url: Optional[str] = None


@strawberry.type
class PageInfo:
    """Relay тип PageInfo для курсорной пагинации."""
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


@strawberry.type
class ParticipantEdge:
    """Relay тип Edge для Participant."""
    node: Participant
    cursor: str


@strawberry.type
class CategoryStats:
    """Статистика для категории, показывающая количество участников."""
    id: strawberry.ID
    name: str
    slug: str
    count: int


@strawberry.type
class ParticipantRelayConnection:
    """Relay тип соединения для пагинированных результатов Participant."""
    edges: List[ParticipantEdge]
    page_info: PageInfo
    total_count: int
    category_stats: List[CategoryStats] = strawberry.field(
        description="Статистика для категорий с количеством участников"
    )


@strawberry.input
class SignalCardFilters:
    """Входной тип для фильтрации SignalCards с гибкой поддержкой дат."""
    search: Optional[str] = None
    categories: Optional[List[strawberry.ID]] = None
    participants: Optional[List[strawberry.ID]] = None
    stages: Optional[List[str]] = None
    round_statuses: Optional[List[str]] = None
    featured: Optional[bool] = None
    is_open: Optional[bool] = None
    new: Optional[bool] = None
    trending: Optional[bool] = None
    start_date: Optional[FlexibleDate] = None
    end_date: Optional[FlexibleDate] = None
    min_signals: Optional[int] = None
    max_signals: Optional[int] = None
    hide_liked: Optional[bool] = None
    show_old: Optional[bool] = None
    display_preference: Optional[str] = None
    participant_filter: Optional["ParticipantFilterInput"] = None


@strawberry.enum
class ParticipantFilterMode(Enum):
    """Enum для режимов фильтрации участников."""
    INCLUDE_ONLY = "INCLUDE_ONLY"
    EXCLUDE_FROM_TYPE = "EXCLUDE_FROM_TYPE"


@strawberry.input
class ParticipantFilterInput:
    """Входной тип для расширенной фильтрации участников."""
    mode: ParticipantFilterMode
    participantIds: Optional[List[strawberry.ID]] = None
    participantTypes: Optional[List[str]] = None


@strawberry.input
class PaginationInput:
    """Входной тип для пагинации."""
    page: Optional[int] = 1
    page_size: Optional[int] = 20


@strawberry.enum
class CardType(Enum):
    """Enum для различных типов карточек."""
    ALL = "all"
    SAVED = "saved"
    NOTES = "notes"
    DELETED = "deleted"
    WORTH_FOLLOWING = "worth_following"


@strawberry.enum
class SortOrder(Enum):
    """Enum для порядка сортировки."""
    ASC = "asc"
    DESC = "desc"


@strawberry.enum
class SortBy(Enum):
    """Enum для полей сортировки."""
    LATEST_SIGNAL_DATE = "latest_signal_date"
    CREATED_AT = "created_at"
    NAME = "name"
    UPDATED_AT = "updated_at"


@strawberry.enum
class AssignmentStatus(Enum):
    """Enum для статусов назначения."""
    REVIEW = "REVIEW"
    REACHING_OUT = "REACHING_OUT"
    CONNECTED = "CONNECTED"
    NOT_A_FIT = "NOT_A_FIT"


@strawberry.enum
class AssignmentFilterType(Enum):
    """Enum для типов фильтров назначения."""
    MY_ASSIGNMENTS = "MY_ASSIGNMENTS"
    ALL = "ALL"


@strawberry.type
class FilterStats:
    """Статистика для опции фильтра, показывающая количество доступных карточек."""
    count: Optional[int] = 0
    active: bool


@strawberry.type
class CategoryFilter:
    """Фильтр категории с метаданными."""
    id: strawberry.ID
    name: str
    slug: str
    stats: FilterStats


@strawberry.type
class ParticipantFilter:
    """Фильтр участника с метаданными."""
    id: strawberry.ID
    name: str
    slug: str
    image_url: Optional[str] = None
    is_private: bool
    stats: FilterStats


@strawberry.type
class StageFilter:
    """Фильтр стадии с метаданными."""
    slug: str
    name: str
    stats: FilterStats


@strawberry.type
class RoundFilter:
    """Фильтр статуса раунда с метаданными."""
    slug: str
    name: str
    stats: FilterStats


@strawberry.type
class AvailableFilters:
    """Все доступные опции фильтров с их текущими состояниями и количествами."""
    categories: List[CategoryFilter]
    participants: List[ParticipantFilter]
    stages: List[StageFilter]
    rounds: List[RoundFilter]
    total_cards: Optional[int] = 0
    cache_key: str


@strawberry.type
class SignalCardFiltersOutput:
    """Выходной тип для фильтров SignalCard. Использует FlexibleDate для единообразной обработки дат."""
    search: Optional[str] = None
    categories: Optional[List[str]] = None
    participants: Optional[List[str]] = None
    stages: Optional[List[str]] = None
    round_statuses: Optional[List[str]] = None
    featured: Optional[bool] = None
    is_open: Optional[bool] = None
    new: Optional[bool] = None
    trending: Optional[bool] = None
    hide_liked: Optional[bool] = None
    start_date: Optional[FlexibleDate] = None
    end_date: Optional[FlexibleDate] = None
    min_signals: Optional[int] = None
    max_signals: Optional[int] = None


@strawberry_django.type(SavedFilterModel)
class SavedFilter:
    """GraphQL тип для модели SavedFilter."""
    id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    
    @strawberry_django.field(name="isDefault")
    def is_default(self) -> bool:
        return self.is_default
    
    @strawberry_django.field(name="createdAt")
    def created_at(self) -> datetime:
        return self.created_at
    
    @strawberry_django.field(name="updatedAt")
    def updated_at(self) -> datetime:
        return self.updated_at
    
    stages: Optional[List[str]] = strawberry.auto
    search: strawberry.auto
    featured: strawberry.auto
    
    @strawberry_django.field(name="roundStatuses")
    def round_statuses(self) -> Optional[List[str]]:
        return self.round_statuses
        
    @strawberry_django.field(name="isOpen")
    def is_open(self) -> Optional[bool]:
        return self.is_open
        
    @strawberry_django.field(name="startDate")
    def start_date(self) -> Optional[FlexibleDate]:
        return self.start_date
        
    @strawberry_django.field(name="endDate")
    def end_date(self) -> Optional[FlexibleDate]:
        return self.end_date
        
    @strawberry_django.field(name="minSignals")
    def min_signals(self) -> Optional[int]:
        return self.min_signals
        
    @strawberry_django.field(name="maxSignals")
    def max_signals(self) -> Optional[int]:
        return self.max_signals
    
    @strawberry_django.field(name="new")
    def new(self) -> Optional[bool]:
        return self.new
    
    @strawberry_django.field(name="trending")
    def trending(self) -> Optional[bool]:
        return self.trending
    
    categories: List[Category] = strawberry_django.field(
        prefetch_related=["categories"]
    )
    
    participants: List[Participant] = strawberry_django.field(
        prefetch_related=["participants"]
    )
    
    @strawberry_django.field(name="participantFilterMode")
    def participant_filter_mode(self) -> Optional[str]:
        return self.participant_filter_mode
    
    @strawberry_django.field(name="participantFilterIds")
    def participant_filter_ids(self) -> Optional[List[str]]:
        """Получает ID фильтров участников как строки для GraphQL."""
        if self.participant_filter_ids:
            return [str(pid) for pid in self.participant_filter_ids]
        return None
    
    @strawberry_django.field(name="participantFilterTypes")
    def participant_filter_types(self) -> Optional[List[str]]:
        return self.participant_filter_types
    
    @strawberry_django.field(only=["id", "name", "description"])
    def filter_summary(self, info) -> str:
        """Получает читаемое резюме конфигурации фильтра."""
        return self.get_filter_summary()
    
    @strawberry_django.field(only=["stages", "round_statuses", "search", "featured", "is_open", "start_date", "end_date", "min_signals", "max_signals", "new", "trending", "participant_filter_mode", "participant_filter_ids", "participant_filter_types"])
    def has_active_filters(self, info) -> bool:
        """Проверяет, есть ли у этого сохраненного фильтра активные критерии фильтрации."""
        return any([
            self.search,
            self.stages,
            self.round_statuses,
            self.featured is not None,
            self.is_open is not None,
            self.new is not None,
            self.trending is not None,
            self.start_date,
            self.end_date,
            self.min_signals is not None,
            self.max_signals is not None,
            self.categories.exists(),
            self.participants.exists(),
            self.participant_filter_mode is not None,
            self.participant_filter_ids,
            self.participant_filter_types,
        ])

    @strawberry_django.field(name="recentProjectsCount")
    def recent_projects_count(self, info) -> int:
        """Количество карточек сигналов, созданных за последние 7 дней, соответствующих критериям этого фильтра."""
        request = info.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            return 0
        
        # Check if recent counts computation is requested
        include_recent_counts = False
        if hasattr(request, '_graphql_flags'):
            include_recent_counts = request._graphql_flags.get('include_recent_counts', False)
        
        # Skip expensive computation if not requested
        if not include_recent_counts:
            return 0
        
        # Import here to avoid circular imports
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Q, Max, Min, Count, Exists, OuterRef
        from signals.models import SignalCard, Signal
        from profile.models import DeletedCard
        from signals.utils import apply_search_query_filters
        
        try:
            queryset = SignalCard.objects.filter(is_open=True)
            accessible_signals = Signal.objects.filter(
                signal_card=OuterRef('pk')
            ).filter(
                # Must have at least one participant (either main or associated)
                Q(participant__isnull=False) | Q(associated_participant__isnull=False)
            )
            
            # Only return cards that have at least one accessible signal
            queryset = queryset.filter(Exists(accessible_signals))
            
            # Exclude deleted cards
            deleted_cards = DeletedCard.objects.filter(
                user=user,
                signal_card=OuterRef('pk')
            )
            queryset = queryset.exclude(Exists(deleted_cards))
            
            # Display preference всегда ALL (удалено)
            
            # Filter to last 7 days only
            seven_days_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(created_at__gte=seven_days_ago)
            
            # Apply saved filter criteria - same logic as _apply_optimized_filters
            
            # Search filter
            if self.search:
                queryset, _ = apply_search_query_filters(queryset, self.search)
            
            # Category filters
            if self.categories.exists():
                if hasattr(self, '_prefetched_objects_cache') and 'categories' in self._prefetched_objects_cache:
                    category_ids = [cat.id for cat in self.categories.all()]
                else:
                    category_ids = list(self.categories.values_list('id', flat=True))
                
                category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
                queryset = queryset.filter(category_filter)
            
            # Participant filters - handle both legacy and advanced filtering
            # Advanced participant filtering
            if self.participant_filter_mode:
                participant_filter_ids = self.participant_filter_ids or []
                participant_filter_types = self.participant_filter_types or []
                
                # Get legacy participant IDs to include alongside advanced filtering
                legacy_participant_ids = []
                if self.participants.exists():
                    if hasattr(self, '_prefetched_objects_cache') and 'participants' in self._prefetched_objects_cache:
                        legacy_participant_ids = [part.id for part in self.participants.all()]
                    else:
                        legacy_participant_ids = list(self.participants.values_list('id', flat=True))
                
                if self.participant_filter_mode == 'INCLUDE_ONLY':
                    # Only show signals from these specific participants (combine both sources)
                    # Only count signals where participant is the associated_participant
                    all_included_ids = participant_filter_ids + legacy_participant_ids
                    if all_included_ids:
                        participant_signals = Signal.objects.filter(
                            Q(associated_participant_id__in=all_included_ids),
                            signal_card=OuterRef('pk')
                        )
                        queryset = queryset.filter(Exists(participant_signals))
                elif self.participant_filter_mode == 'EXCLUDE_FROM_TYPE':
                    # Include participants of specified types, exclude specific IDs, plus legacy participants
                    # Only count signals where participant is the associated_participant
                    if participant_filter_types:
                        filter_conditions = Q()
                        
                        # 1. Include signals from participants of specified types, excluding specific IDs
                        type_filter = Q(associated_participant__type__in=participant_filter_types)
                        
                        # Exclude specific participant IDs from the type selection if provided
                        if participant_filter_ids:
                            type_filter &= ~Q(associated_participant_id__in=participant_filter_ids)
                        
                        filter_conditions |= type_filter
                        
                        # 2. Additionally include signals from legacy participants (regardless of type)
                        if legacy_participant_ids:
                            legacy_filter = Q(associated_participant_id__in=legacy_participant_ids)
                            filter_conditions |= legacy_filter
                        
                        # Apply the combined filter
                        participant_signals = Signal.objects.filter(
                            filter_conditions,
                            signal_card=OuterRef('pk')
                        )
                        queryset = queryset.filter(Exists(participant_signals))
                    elif legacy_participant_ids:
                        # No participant types specified, just use legacy participants
                        participant_signals = Signal.objects.filter(
                            Q(associated_participant_id__in=legacy_participant_ids),
                            signal_card=OuterRef('pk')
                        )
                        queryset = queryset.filter(Exists(participant_signals))
            elif self.participants.exists():
                # Legacy participant filtering only (when no advanced filtering is set)
                # Only count signals where participant is the associated_participant
                if hasattr(self, '_prefetched_objects_cache') and 'participants' in self._prefetched_objects_cache:
                    participant_ids = [part.id for part in self.participants.all()]
                else:
                    participant_ids = list(self.participants.values_list('id', flat=True))
                
                participant_signals = Signal.objects.filter(
                    Q(associated_participant_id__in=participant_ids),
                    signal_card=OuterRef('pk')
                )
                queryset = queryset.filter(Exists(participant_signals))
            
            # Stage filters
            if self.stages:
                queryset = queryset.filter(stage__in=self.stages)
            
            # Round status filters
            if self.round_statuses:
                queryset = queryset.filter(round_status__in=self.round_statuses)
            
            # Featured filter
            if self.featured is not None:
                queryset = queryset.filter(featured=self.featured)
            
            # Open status filter
            if self.is_open is not None:
                queryset = queryset.filter(is_open=self.is_open)
            
            # Date range filters
            from datetime import datetime, time
            if self.start_date and self.end_date:
                start_datetime = timezone.make_aware(datetime.combine(self.start_date, time.min))
                end_datetime = timezone.make_aware(datetime.combine(self.end_date, time.max))
                
                queryset = queryset.annotate(
                    latest_signal_date=Max('signals__created_at')
                ).filter(
                    latest_signal_date__range=(start_datetime, end_datetime)
                )
            elif self.start_date:
                start_datetime = timezone.make_aware(datetime.combine(self.start_date, time.min))
                queryset = queryset.annotate(
                    latest_signal_date=Max('signals__created_at')
                ).filter(latest_signal_date__gte=start_datetime)
            elif self.end_date:
                end_datetime = timezone.make_aware(datetime.combine(self.end_date, time.max))
                queryset = queryset.annotate(
                    latest_signal_date=Max('signals__created_at')
                ).filter(latest_signal_date__lte=end_datetime)
            
            # Signal count filters
            if self.min_signals or self.max_signals:
                queryset = queryset.annotate(
                    signal_count=Count('signals__participant_id', distinct=True)
                )
                if self.min_signals:
                    queryset = queryset.filter(signal_count__gte=self.min_signals)
                if self.max_signals:
                    queryset = queryset.filter(signal_count__lte=self.max_signals)
            
            # Use database-level count for efficiency
            return queryset.distinct().count()
            
        except Exception:
            # Fallback in case of any issues
            return 0

    @strawberry_django.field(name="hideLiked")
    def hide_liked(self) -> Optional[bool]:
        return self.hide_liked
    
@strawberry.type
class SavedFilterConnection:
    """Тип соединения для пагинированных результатов SavedFilter."""
    nodes: List[SavedFilter]
    total_count: int
    has_next_page: bool
    has_previous_page: bool
    current_page: int
    total_pages: int


@strawberry.input
class SavedFilterInput:
    """Входной тип для создания и обновления сохраненных фильтров."""
    name: str
    description: Optional[str] = None
    is_default: Optional[bool] = False
    
    categories: Optional[List[strawberry.ID]] = None
    participants: Optional[List[strawberry.ID]] = None
    participant_filter: Optional[ParticipantFilterInput] = None
    stages: Optional[List[str]] = None
    round_statuses: Optional[List[str]] = None
    featured: Optional[bool] = None
    is_open: Optional[bool] = None
    new: Optional[bool] = None
    trending: Optional[bool] = None
    hide_liked: Optional[bool] = None
    start_date: Optional[FlexibleDate] = None
    end_date: Optional[FlexibleDate] = None
    min_signals: Optional[int] = None
    max_signals: Optional[int] = None
    search: Optional[str] = None


@strawberry.type
class SavedFilterMutationResult:
    """Тип результата для мутаций сохраненных фильтров."""
    success: bool
    message: str
    saved_filter: Optional[SavedFilter] = None
    error_code: Optional[str] = None


@strawberry.type
class SavedFilterListResult:
    """Тип результата для списка сохраненных фильтров с метаданными."""
    saved_filters: List[SavedFilter]
    total_count: int
    default_filter: Optional[SavedFilter] = None
