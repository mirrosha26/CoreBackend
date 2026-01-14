from notifications.models import DigestSettings, DigestLog
from profile.models import SavedParticipant, SavedFilter, UserFolder, FolderCard
from signals.models import Signal, SignalCard, Participant, STAGES, ROUNDS, Category
from datetime import datetime, date, timedelta
from django.db.models import Q, OuterRef, Exists, QuerySet, Count, Case, When
from django.utils import timezone
from django.db import models
from typing import Union, Optional, List, Dict, Any, Tuple
import pytz
import requests
import logging
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class DigestManager:
    BASE_URL = 'https://app.theveck.com/'
    APP_URL = 'https://app.theveck.com/app/'
    
    WEB3_FOLDER_ID = 173
    WEB2_FOLDER_ID = 157
    
    MAX_CARDS_PER_GROUP = 4
    MAX_INVESTORS_PER_CARD = 2
    MIN_CARDS_FOR_DIGEST = 2

    
    @staticmethod
    def get_media_url(media_field: Union[models.ImageField, models.FileField]) -> Optional[str]:
        if media_field and hasattr(media_field, 'url'):
            return f"{DigestManager.BASE_URL}{media_field.url}"
        return None
    
    @staticmethod
    def get_all_digest_settings() -> QuerySet[DigestSettings]:
        return DigestSettings.objects.select_related('user').all()
    
    @staticmethod
    def get_digest_settings_ready_for_sending() -> List[DigestSettings]:
        ready_settings = []
        for settings in DigestManager.get_all_digest_settings():
            if (settings.is_enabled and
                DigestManager.is_digest_time_reached(settings) and 
                not DigestManager.was_digest_sent_today(settings)):
                ready_settings.append(settings)
        return ready_settings
    
    @staticmethod
    def is_digest_time_reached(settings: DigestSettings) -> bool:
        try:
            tz = pytz.timezone(settings.timezone)
            current_time = datetime.now(tz)
            
            digest_time = current_time.replace(
                hour=settings.digest_hour,
                minute=0,
                second=0,
                microsecond=0
            )
            return current_time >= digest_time
            
        except Exception:
            return False
    
    @staticmethod
    def was_digest_sent_today(settings: DigestSettings) -> bool:
        try:
            tz = pytz.timezone(settings.timezone)
            current_time = datetime.now(tz)
            today = current_time.date()
            
            # Создаем диапазон времени для "сегодня" в часовом поясе пользователя
            today_start = tz.localize(datetime.combine(today, datetime.min.time()))
            today_end = tz.localize(datetime.combine(today, datetime.max.time()))
            
            # Конвертируем в UTC для сравнения с БД
            today_start_utc = today_start.astimezone(pytz.UTC)
            today_end_utc = today_end.astimezone(pytz.UTC)

            sent_today = DigestLog.objects.filter(
                user=settings.user,
                status='SENT',
                sent_at__gte=today_start_utc,
                sent_at__lte=today_end_utc
            ).exists()
            
            return sent_today
            
        except Exception:
            return False
    
    @staticmethod
    def get_investor_cards_list(settings: DigestSettings) -> List[SignalCard]:
        try:
            if settings.custom_investors_enabled:
                saved_participants = SavedParticipant.objects.filter(
                    user=settings.user,
                    in_digest=True
                ).select_related('participant')
            else:
                saved_participants = SavedParticipant.objects.filter(
                    user=settings.user
                ).select_related('participant')
            
            if not saved_participants.exists():
                return []
            
            investor_ids = [sp.participant.id for sp in saved_participants]
            yesterday = timezone.now() - timedelta(days=1)
            
            recent_signals = Signal.objects.filter(
                participant_id__in=investor_ids,
                created_at__gte=yesterday
            ).select_related('signal_card', 'participant')
            
            unique_cards = []
            seen_card_ids = set()
            
            card_investors_count = {}
            for signal in recent_signals:
                if signal.signal_card and signal.participant:
                    card_id = signal.signal_card.id
                    participant_id = signal.participant.id
                    
                    if card_id not in card_investors_count:
                        card_investors_count[card_id] = set()
                    card_investors_count[card_id].add(participant_id)
            
            for signal in recent_signals:
                if signal.signal_card and signal.signal_card.id not in seen_card_ids:
                    signal.signal_card.digest_investors_count = len(card_investors_count[signal.signal_card.id])                    
                    signals_count = Signal.objects.filter(
                        signal_card=signal.signal_card,
                        created_at__gte=yesterday
                    ).count()
                    signal.signal_card.digest_signals_count = signals_count
                    
                    unique_cards.append(signal.signal_card)
                    seen_card_ids.add(signal.signal_card.id)
            
            return unique_cards
            
        except Exception as e:
            print(f"Ошибка при получении данных о проектах: {e}")
            return []

    @staticmethod
    def get_filter_projects_data(settings: DigestSettings) -> Tuple[Dict[SavedFilter, List[SignalCard]], bool]:
        """
        Получить данные о проектах от фильтров для digest.
        
        Returns:
            Tuple[Dict[SavedFilter, List[SignalCard]], bool]: 
            - Результаты фильтров
            - Есть ли вообще включенные фильтры (True если есть хотя бы один фильтр)
        """
        try:
            # 1. Определяем интересующие фильтры
            if settings.custom_filters_enabled:
                # Берем только SavedFilter с in_digest=True
                saved_filters = SavedFilter.objects.filter(
                    user=settings.user,
                    in_digest=True
                ).prefetch_related('categories', 'participants')
            else:
                # Берем все фильтры пользователя
                saved_filters = SavedFilter.objects.filter(
                    user=settings.user
                ).prefetch_related('categories', 'participants')
            
            has_filters = saved_filters.exists()
            
            if not has_filters:
                return {}, False
            
            # 2. Получаем предобработанный список карточек за последние сутки
            # Используем серверное время, timezone уже учтен в основной логике
            yesterday = timezone.now() - timedelta(days=1)
            
            # Базовый queryset карточек за последние сутки
            recent_cards = SignalCard.objects.filter(
                created_at__gte=yesterday
            ).prefetch_related('categories', 'signals__participant', 'signals__associated_participant')
            
            # 2.5. Применяем фильтрацию по signal_display_preference (WEB2/WEB3)
            # Это важно для согласованности с основным приложением и защиты от утечек
            # когда фильтры используют location/stage/participants без категорий
            user = settings.user
            if hasattr(user, 'signal_display_preference'):
                if user.signal_display_preference == 'WEB3':
                    # Показываем только сигналы с категорией web3 или её дочерними категориями
                    web3_category = Category.objects.filter(slug='web3').first()
                    if web3_category:
                        web3_subcategories = Category.objects.filter(parent_category=web3_category).values_list('id', flat=True)
                        recent_cards = recent_cards.filter(Q(categories__slug='web3') | Q(categories__id__in=web3_subcategories))
                    else:
                        recent_cards = recent_cards.filter(categories__slug='web3')
                elif user.signal_display_preference == 'WEB2':
                    # Исключаем сигналы с категорией web3
                    web3_category = Category.objects.filter(slug='web3').first()
                    if web3_category:
                        web3_subcategories = Category.objects.filter(parent_category=web3_category).values_list('id', flat=True)
                        recent_cards = recent_cards.exclude(Q(categories__slug='web3') | Q(categories__id__in=web3_subcategories))
                    else:
                        recent_cards = recent_cards.exclude(categories__slug='web3')
            
            # 3. Группируем результаты по фильтрам
            filter_results = {}
            
            for saved_filter in saved_filters:
                # Применяем фильтр к предобработанному списку
                filtered_cards = DigestManager._apply_filter_to_cards(saved_filter, recent_cards)
                
                # Добавляем атрибут с количеством сигналов для каждой карточки
                cards_with_signals_count = []
                for card in filtered_cards:
                    # Подсчитываем количество сигналов для этой карточки за последние сутки
                    signals_count = Signal.objects.filter(
                        signal_card=card,
                        created_at__gte=yesterday
                    ).count()
                    # Добавляем атрибут с количеством сигналов
                    card.digest_signals_count = signals_count
                    cards_with_signals_count.append(card)
                
                filter_results[saved_filter] = cards_with_signals_count
            
            return filter_results, True
            
        except Exception as e:
            print(f"Ошибка при получении данных о проектах от фильтров: {e}")
            return {}, False
    
    @staticmethod
    def _apply_filter_to_cards(saved_filter: SavedFilter, cards_queryset: QuerySet) -> QuerySet:
        """Применить фильтр к queryset карточек."""
        filtered_cards = cards_queryset
        
        if saved_filter.categories.exists():
            category_ids = [cat.id for cat in saved_filter.categories.all()]
            category_filter = Q(categories__id__in=category_ids) | Q(categories__parent_category_id__in=category_ids)
            filtered_cards = filtered_cards.filter(category_filter)
        
        # 2. Фильтр по stage ИЛИ round_status (OR) - как в реальном эндпоинте
        if saved_filter.stages or saved_filter.round_statuses:
            stage_round_filter = Q()
            if saved_filter.stages:
                stage_round_filter |= Q(stage__in=saved_filter.stages)
            if saved_filter.round_statuses:
                stage_round_filter |= Q(round_status__in=saved_filter.round_statuses)
            filtered_cards = filtered_cards.filter(stage_round_filter)
        
        # 3. Фильтр по locations - как в реальном эндпоинте
        if saved_filter.locations:
            filtered_cards = filtered_cards.filter(location__in=saved_filter.locations)
        
        # 4. Фильтр по participants - используем ту же логику что и в реальном эндпоинте
        if saved_filter.participants.exists():
            participant_ids = [p.id for p in saved_filter.participants.all()]
            # Используем EXISTS как в реальном эндпоинте
            participant_signals = Signal.objects.filter(
                Q(participant_id__in=participant_ids) | 
                Q(associated_participant_id__in=participant_ids),
                signal_card=OuterRef('pk')
            )
            filtered_cards = filtered_cards.filter(Exists(participant_signals))
        
        # 5. Текстовый поиск по name и description - как в реальном эндпоинте
        if saved_filter.search:
            # Используем ту же логику что и в apply_search_query_filters
            search_q = Q(name__icontains=saved_filter.search) | Q(description__icontains=saved_filter.search)
            filtered_cards = filtered_cards.filter(search_q)
        
        # Возвращаем уникальные карточки
        return filtered_cards.distinct()
    
    @staticmethod
    def get_updated_cards_list(settings: DigestSettings) -> List[Dict[str, Any]]:
        """Получить данные об обновлениях статусов за последние сутки."""
        try:
            from django.utils import timezone
            from signals.models import SignalCardStatusChange
            from profile.models import UserFolder, FolderCard
            
            yesterday = timezone.now() - timedelta(days=1)            
            
            if settings.custom_folders_enabled:
                tracked_folders = UserFolder.objects.filter(
                    user=settings.user,
                    in_digest=True
                )
            else:
                tracked_folders = UserFolder.objects.filter(
                    user=settings.user
                )
                
            if not tracked_folders.exists():
                return []
                
            # Получаем все карточки из отслеживаемых папок
            tracked_cards = FolderCard.objects.filter(
                folder__in=tracked_folders
            ).values_list('signal_card_id', flat=True)
            
            if not tracked_cards:
                return []
                
            # Фильтруем обновления только по отслеживаемым карточкам
            status_changes = SignalCardStatusChange.objects.filter(
                created_at__gte=yesterday,
                signal_card_id__in=tracked_cards
            ).select_related('signal_card')

            
            updates = []
            for change in status_changes:
                # Формируем описание изменения
                change_description = []
                
                # Stage changes - показываем только если новый статус не unknown
                if (change.old_stage and change.new_stage and 
                    change.old_stage != change.new_stage and change.new_stage != "unknown"):
                    if change.old_stage == "unknown":
                        # Из unknown в известный статус
                        new_stage_display = dict(STAGES).get(change.new_stage, change.new_stage)
                        change_description.append(f"Stage: {new_stage_display}")
                    else:
                        # Из известного в известный статус  
                        old_stage_display = dict(STAGES).get(change.old_stage, change.old_stage)
                        new_stage_display = dict(STAGES).get(change.new_stage, change.new_stage)
                        change_description.append(f"Stage: {old_stage_display} → {new_stage_display}")
                
                # Round changes - показываем только если новый статус не unknown
                if (change.old_round_status and change.new_round_status and 
                    change.old_round_status != change.new_round_status and change.new_round_status != "unknown"):
                    if change.old_round_status == "unknown":
                        # Из unknown в известный статус
                        new_round_display = dict(ROUNDS).get(change.new_round_status, change.new_round_status)
                        change_description.append(f"Round: {new_round_display}")
                    else:
                        # Из известного в известный статус
                        old_round_display = dict(ROUNDS).get(change.old_round_status, change.old_round_status)
                        new_round_display = dict(ROUNDS).get(change.new_round_status, change.new_round_status)
                        change_description.append(f"Round: {old_round_display} → {new_round_display}")
                
                if change_description:
                    updates.append({
                        'startup_name': change.signal_card.name,
                        'new_status': ' | '.join(change_description).replace(' | ', '<br>'),  # Заменяем | на <br>
                        'url': f"{DigestManager.BASE_URL}/public/{change.signal_card.slug}",
                        'image_url': DigestManager.get_media_url(change.signal_card.image),
                    })
            
            return updates
            
        except Exception as e:
            print(f"Ошибка при получении обновлений статусов: {e}")
            return []

    @staticmethod
    def count_total_digest_cards(investor_data: List, filter_data: Dict, status_updates: List) -> int:
        """
        Подсчитывает общее количество карточек в рассылке.
        
        Args:
            investor_data: Данные от инвесторов
            filter_data: Данные от фильтров  
            status_updates: Обновления статусов
            
        Returns:
            Общее количество карточек
        """
        # Карточки от инвесторов
        investor_cards_count = len(investor_data)
        
        # Карточки от фильтров
        filter_cards_count = 0
        for cards in filter_data.values():
            filter_cards_count += len(cards)
        
        # Обновления статусов
        status_updates_count = len(status_updates)
        
        return investor_cards_count + filter_cards_count + status_updates_count

    @staticmethod
    def serialize_signal_card(card: SignalCard) -> Dict[str, Any]:
        tags = []
        if card.round_status and card.round_status != "unknown":
            round_display = dict(ROUNDS).get(card.round_status, card.round_status)
            tags.append(round_display)
        if card.stage and card.stage != "unknown":
            stage_display = dict(STAGES).get(card.stage, card.stage)
            tags.append(stage_display)
        for category in card.categories.all()[:2]:
            tags.append(category.name)
        
        all_card_investors = []
        for signal in card.signals.filter(created_at__gte=timezone.now() - timedelta(days=1))[:3]:
            if signal.participant:
                all_card_investors.append({
                    'name': signal.participant.name,
                    'avatar_url': DigestManager.get_media_url(signal.participant.image)
                })
        
        card_investors = all_card_investors[:DigestManager.MAX_INVESTORS_PER_CARD]
        more_investors_count = max(0, len(all_card_investors) - DigestManager.MAX_INVESTORS_PER_CARD)
        
        return {
            'name': card.name,
            'description': card.description[:200] + '...' if len(card.description) > 200 else card.description,
            'image_url': DigestManager.get_media_url(card.image),
            'url': f"{DigestManager.BASE_URL}/public/{card.slug}",
            'tags': tags,
            'investors': card_investors,
            'more_investors_count': more_investors_count
        }

    @staticmethod
    def serialize_digest_groups(settings: DigestSettings) -> Dict[str, Any]:
        try:
            groups= []
            filter_data, has_any_filters = DigestManager.get_filter_projects_data(settings)
            investor_cards = DigestManager.get_investor_cards_list(settings)
            updated_cards = DigestManager.get_updated_cards_list(settings)

            print(f"DEBUG serialize_digest_groups:")
            print(f"  - Filter data: {len(filter_data)} filters")
            print(f"  - Has any filters enabled: {has_any_filters}")
            print(f"  - Investor cards: {len(investor_cards)} cards")
            print(f"  - Updated cards: {len(updated_cards)} cards")

            # Правильный подсчет total_cards: считаем карточки от фильтров, а не количество фильтров
            filter_cards_count = sum(len(cards) for cards in filter_data.values())
            total_cards = len(investor_cards) + len(updated_cards) + filter_cards_count
            
            # Проверяем, есть ли карточки от фильтров (для логики fallback)
            has_filter_cards = filter_cards_count > 0
        
            for saved_filter, cards in filter_data.items():
                if cards:
                    sorted_cards = sorted(
                        cards, 
                        key=lambda card: getattr(card, 'digest_signals_count', 0), 
                        reverse=True
                    )
                    
                    total_cards_count = len(sorted_cards)
                    
                    filter_cards = []
                    for card in sorted_cards[:DigestManager.MAX_CARDS_PER_GROUP]:  # Первые N карточек
                        filter_cards.append(DigestManager.serialize_signal_card(card))
                    
                    if filter_cards:
                        # Вычисляем количество оставшихся карточек
                        more_count = max(0, total_cards_count - len(filter_cards))
                        
                        group = {
                            'title': saved_filter.name,
                            'subtitle': f'{total_cards_count} new cards from your saved filter "{saved_filter.name}"',
                            'cards': filter_cards,
                            'type': 'default',
                            'total_count': total_cards_count
                        }
                        if more_count > 0:
                            group['more_button'] = {
                                'text': f'See more from {saved_filter.name} (+{more_count} cards)',
                                'url': f"{DigestManager.APP_URL}/feeds?filter={saved_filter.slug}" if hasattr(saved_filter, 'slug') else "#",
                            }
                        groups.append(group)

            if investor_cards:
                investor_cards_count = len(investor_cards)
                more_investors_count = max(0, investor_cards_count - DigestManager.MAX_CARDS_PER_GROUP)
                
                serialized_investor_cards = []
                for card in investor_cards[:DigestManager.MAX_CARDS_PER_GROUP]:
                    serialized_investor_cards.append(DigestManager.serialize_signal_card(card))

                group = {
                    'title': f'{investor_cards_count} new signals from your investors:',
                    'cards': serialized_investor_cards,
                    'type': 'default',
                }

                if more_investors_count > 0:
                    group['more_button'] = {
                        'text': f'See more in your feed ({more_investors_count} signals from your investors)',
                        'url': f"{DigestManager.APP_URL}/feeds/"
                    }
                groups.append(group)

            # Fallback работает только если:
            # 1. Нет включенных фильтров вообще (has_any_filters == False)
            # 2. И общее количество карточек меньше минимума
            # Если фильтры есть, но не дали результатов - fallback НЕ работает
            if not has_any_filters and total_cards < DigestManager.MIN_CARDS_FOR_DIGEST:
                print(f"DEBUG: No filters enabled and total cards ({total_cards}) is less than {DigestManager.MIN_CARDS_FOR_DIGEST}")
                web3_cards = DigestManager.get_fallback_cards_by_type(settings,'WEB3')
                web2_cards = DigestManager.get_fallback_cards_by_type(settings,'WEB2')
                print(f"DEBUG: Fallback cards - Web3: {len(web3_cards)}, Web2: {len(web2_cards)}")

                for group_cards, group_type in [(web3_cards, 'Web3'), (web2_cards, 'Web2')]:
                    if group_cards:
                        cards = [
                            DigestManager.serialize_signal_card(card)
                            for card in group_cards
                        ]
                        more_count = max(0, len(group_cards) - DigestManager.MAX_CARDS_PER_GROUP)
                        group = {
                            'title': f'{group_type}',
                            'subtitle': f'{len(group_cards)} new  {group_type} cards',
                            'cards': cards[:DigestManager.MAX_CARDS_PER_GROUP],
                            'type': 'default',
                            'total_count': len(group_cards)
                        }
                        if more_count > 0:
                            group['more_button'] = {
                                'text': f'See more in your feed (+{more_count} {group_type} cards)',
                                'url': f"{DigestManager.APP_URL}/feeds/"
                            }
                        groups.append(group)
           
            if updated_cards:
                updated_cards_count = len(updated_cards[:DigestManager.MAX_CARDS_PER_GROUP])
                group = {
                    'title': f'{updated_cards_count} new updates:',
                    'cards': updated_cards[:DigestManager.MAX_CARDS_PER_GROUP],
                    'type': 'update',
                }
                groups.append(group)

            print(f"DEBUG: Created {len(groups)} groups total")
            return groups
        except Exception as e:
            print(f"DEBUG: Exception in serialize_digest_groups: {e}")
            return []


    @staticmethod
    def send_digest_email_to_user(user, groups, digest_settings) -> tuple[bool, str]:
        try:
            from django.conf import settings as django_settings
            
            api_key = getattr(django_settings, 'MAILGUN_API_KEY', None)
            domain = getattr(django_settings, 'MAILGUN_DOMAIN', None)
            
            if not api_key or not domain:
                logger.warning("Mailgun credentials not configured")
                return False
            
            api_url = f"https://api.mailgun.net/v3/{domain}/messages"
            
            # Email получателя
            to_email = user.email
            subject = f"Daily Digest {timezone.now().strftime('%d.%m.%Y')}"
            
            context = {
                'name': user.first_name if user.first_name else user.username,
                'avatar_url': DigestManager.get_media_url(user.avatar),
                'user_initial': user.first_name[0] if user.first_name else user.username[0],
                'groups': groups,
            }            
            
            # Рендерим HTML и текстовую версии
            html_content = render_to_string('notifications/emails/digest.html', context)
            text_content = render_to_string('notifications/emails/digest.txt', context)
            
            # Данные для Mailgun API
            data = {
                'from': f"Veck Digest <digest@{domain}>",
                'to': to_email,
                'subject': subject,
                'html': html_content,
                'text': text_content,
                'h:Reply-To': getattr(django_settings, 'SUPPORT_EMAIL', 'support@theveck.com'),
            }
            
            # Добавляем дополнительные email если есть + обязательная копия на digest@theveck.com
            cc_emails = []
            if hasattr(digest_settings, 'additional_emails') and digest_settings.additional_emails:
                cc_emails.extend(digest_settings.additional_emails)
            data['cc'] = ','.join(cc_emails)
            
            # Отправляем через Mailgun API
            response = requests.post(
                api_url,
                auth=('api', api_key),
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Digest email sent successfully to {to_email}")
                return True, text_content
            else:
                logger.error(f"Failed to send digest email to {to_email}. Status: {response.status_code}")
                return False, text_content
                
        except Exception as e:
            logger.error(f"Error sending digest email to {to_email}: {str(e)}")
            return False, ""

    @staticmethod
    def send_digest_copy_to_admin(user, groups, digest_settings) -> bool:
        """Отправить копию digest на digest@theveck.com после успешной отправки"""
        try:
            from django.conf import settings as django_settings
            
            api_key = getattr(django_settings, 'MAILGUN_API_KEY', None)
            domain = getattr(django_settings, 'MAILGUN_DOMAIN', None)
            
            if not api_key or not domain:
                logger.warning("Mailgun credentials not configured")
                return False
            
            api_url = f"https://api.mailgun.net/v3/{domain}/messages"
            
            # Email получателя
            to_email = 'digest@theveck.com'
            subject = f"Digest Copy - {user.username} ({user.email}) - {timezone.now().strftime('%d.%m.%Y')}"
            
            context = {
                'name': f"Admin Copy - {user.username}",
                'avatar_url': DigestManager.get_media_url(user.avatar),
                'user_initial': user.username[0],
                'groups': groups,
                'original_user': user,
            }            
            
            # Рендерим HTML и текстовую версии
            html_content = render_to_string('notifications/emails/digest.html', context)
            text_content = render_to_string('notifications/emails/digest.txt', context)
            
            # Данные для Mailgun API
            data = {
                'from': f"Veck Digest Copy <digest@{domain}>",
                'to': to_email,
                'subject': subject,
                'html': html_content,
                'text': text_content,
                'h:Reply-To': getattr(django_settings, 'SUPPORT_EMAIL', 'support@theveck.com'),
            }
            
            # Отправляем через Mailgun API
            response = requests.post(
                api_url,
                auth=('api', api_key),
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Digest copy sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send digest copy to {to_email}. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending digest copy to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_digest_email(settings: DigestSettings) -> bool:
        try:
            from django.utils import timezone
            
            groups = DigestManager.serialize_digest_groups(settings)
            print(f"DEBUG: Found {len(groups)} groups for user {settings.user.username}")
            
            if groups:
                success, text_content = DigestManager.send_digest_email_to_user(
                user=settings.user,
                    groups=groups,
                digest_settings=settings
            )
                if success:
                    print(f"DEBUG: Email sent successfully to {settings.user.email}")
            
                    # Отправляем копию на digest@theveck.com
                    try:
                        copy_success = DigestManager.send_digest_copy_to_admin(
                            user=settings.user,
                            groups=groups,
                            digest_settings=settings
                        )
                        if copy_success:
                            print(f"DEBUG: Digest copy sent to digest@theveck.com")
                        else:
                            print(f"DEBUG: Failed to send digest copy to digest@theveck.com")
                    except Exception as copy_error:
                        print(f"DEBUG: Error sending digest copy: {copy_error}")
            
                    # Создаем запись в логе при успешной отправке
                    try:
                        current_time = timezone.now()
                        DigestLog.objects.create(
                            user=settings.user,
                            recipient_email=settings.user.email,
                            subject=f"Daily Digest {current_time.strftime('%d.%m.%Y')}",
                            user_data_snapshot={
                                'timezone': settings.timezone,
                                'digest_hour': settings.digest_hour,
                                'custom_investors_enabled': settings.custom_investors_enabled,
                                'custom_filters_enabled': settings.custom_filters_enabled,
                                'custom_folders_enabled': settings.custom_folders_enabled,
                                'groups_count': len(groups)
                            },
                            status='SENT',
                            sent_at=current_time,
                            scheduled_for=current_time
                        )
                    except Exception as log_error:
                        print(f"DEBUG: Error creating digest log: {log_error}")
                    
                    return True, text_content
                else:
                    print(f"DEBUG: Email sending failed for {settings.user.email}")
                    
                    # Создаем запись в логе при неудачной отправке
                    try:
                        current_time = timezone.now()
                        DigestLog.objects.create(
                            user=settings.user,
                            recipient_email=settings.user.email,
                            subject=f"Daily Digest {current_time.strftime('%d.%m.%Y')}",
                            user_data_snapshot={
                                'timezone': settings.timezone,
                                'digest_hour': settings.digest_hour,
                                'groups_count': len(groups)
                            },
                            status='FAILED',
                            sent_at=current_time,
                            scheduled_for=current_time,
                            error_message="Email sending failed"
                        )
                    except Exception as log_error:
                        print(f"DEBUG: Error creating digest log: {log_error}")
                    
                    return False
            else:
                print(f"DEBUG: No groups found for user {settings.user.username}")
                
                # Создаем запись в логе когда нет контента для отправки
                try:
                    current_time = timezone.now()
                    DigestLog.objects.create(
                    user=settings.user,
                    recipient_email=settings.user.email,
                        subject=f"Daily Digest {current_time.strftime('%d.%m.%Y')}",
                        user_data_snapshot={
                            'timezone': settings.timezone,
                            'digest_hour': settings.digest_hour,
                            'groups_count': 0
                        },
                    status='FAILED',
                    sent_at=current_time,
                    scheduled_for=current_time,
                        error_message="No content to send"
                )
                except Exception as log_error:
                    print(f"DEBUG: Error creating digest log: {log_error}")
                
                return False
            
        except Exception as e:
            print(f"DEBUG: Exception in send_digest_email: {e}")
            
            # Создаем запись в логе при исключении
            try:
                current_time = timezone.now()
                DigestLog.objects.create(
                    user=settings.user,
                    recipient_email=settings.user.email,
                    subject=f"Daily Digest {current_time.strftime('%d.%m.%Y')}",
                    user_data_snapshot={
                        'timezone': settings.timezone,
                        'digest_hour': settings.digest_hour,
                    },
                    status='FAILED',
                    sent_at=current_time,
                    scheduled_for=current_time,
                    error_message=str(e)
                )
            except Exception as log_error:
                print(f"DEBUG: Error creating digest log: {log_error}")
            
            return False

        
    @staticmethod
    def get_fallback_cards_by_type(settings, folder_type: str) -> List['SignalCard']:
        try:
            print(f"DEBUG get_fallback_cards_by_type for {folder_type}")
            print(f"DEBUG user.signal_display_preference: {getattr(settings.user, 'signal_display_preference', 'NOT_SET')}")
            
            if folder_type == 'WEB3':
                folder_id = DigestManager.WEB3_FOLDER_ID
            elif folder_type == 'WEB2':
                folder_id = DigestManager.WEB2_FOLDER_ID
            else:
                print(f"DEBUG: Unknown folder_type: {folder_type}")
                return []
            
            if settings.user.signal_display_preference in ['ALL',folder_type]:
                print(f"DEBUG: Looking for folder with ID {folder_id}")
                folder = UserFolder.objects.get(id=folder_id)
            else:
                print(f"DEBUG: User preference '{settings.user.signal_display_preference}' not in ['ALL', '{folder_type}']")
                return []
            
            yesterday = timezone.now() - timedelta(days=1)
            folder_cards = FolderCard.objects.filter(
                folder=folder,
                added_at__gte=yesterday
            ).select_related('signal_card').order_by('-added_at')
            
            signal_cards = [fc.signal_card for fc in folder_cards if fc.signal_card]
            
            if len(signal_cards) < 3:
                try:
                    web3_category = Category.objects.get(slug='web3')
                    if folder_type == 'WEB3':
                        category_filter = Q(categories=web3_category) | Q(categories__parent_category=web3_category)
                    else:
                        category_filter = ~(Q(categories=web3_category) | Q(categories__parent_category=web3_category))
                    
                    additional_cards_query = SignalCard.objects.filter(
                        category_filter,
                        created_at__gte=yesterday
                    ).exclude(
                        id__in=[card.id for card in signal_cards]
                    ).annotate(
                        signals_count=Count(
                            Case(
                                When(
                                    signals__participant__associated_with__isnull=False,
                                    then='signals__participant__associated_with'
                                ),
                                default='signals__participant',
                            ),
                            filter=Q(signals__created_at__gte=yesterday),
                            distinct=True
                        )
                    ).order_by('-signals_count')
                    
                    additional_cards = list(additional_cards_query)
                    signal_cards.extend(additional_cards)                    
                    
                except Category.DoesNotExist:
                    return []
            
            return signal_cards
        
        except Exception:
            return []