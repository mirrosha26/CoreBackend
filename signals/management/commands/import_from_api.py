"""
Django management команда для импорта данных из Veck API.

Использование:
    python manage.py import_from_api --token YOUR_API_TOKEN [--cards 20] [--participants 50]
"""

import requests
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from signals.models import (
    SignalCard, Signal, Participant, Category, Source, SourceType, 
    SignalType, TeamMember, STAGES, ROUNDS, PARTICIPANTS_TYPES
)


class Command(BaseCommand):
    help = 'Импорт данных из Veck API в базу данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            required=True,
            help='API токен для авторизации'
        )
        parser.add_argument(
            '--cards',
            type=int,
            default=20,
            help='Количество карточек для импорта (по умолчанию: 20)'
        )
        parser.add_argument(
            '--participants',
            type=int,
            default=50,
            help='Количество участников для импорта (по умолчанию: 50)'
        )
        parser.add_argument(
            '--base-url',
            type=str,
            default='https://api.theveck.com',
            help='Базовый URL API (по умолчанию: https://api.theveck.com)'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = None
        self.headers = None
        self.stats = {
            'cards_created': 0,
            'cards_updated': 0,
            'participants_created': 0,
            'participants_updated': 0,
            'signals_created': 0,
            'categories_created': 0,
            'errors': []
        }

    def handle(self, *args, **options):
        self.base_url = options['base_url']
        token = options['token']
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

        self.stdout.write(self.style.SUCCESS('🚀 Начинаем импорт данных из Veck API...'))
        
        # Создаем базовые типы
        self.create_base_types()
        
        # Импортируем участников
        self.stdout.write('\n📊 Импорт участников...')
        self.import_participants(limit=options['participants'])
        
        # Импортируем карточки
        self.stdout.write('\n📦 Импорт карточек...')
        self.import_cards(limit=options['cards'])
        
        # Выводим статистику
        self.print_statistics()

    def create_base_types(self):
        """Создает базовые типы источников и сигналов"""
        self.stdout.write('🔧 Создание базовых типов...')
        
        # SourceType
        source_types = [
            {
                'slug': 'twitter',
                'name': 'Twitter',
                'description': 'Twitter/X social network',
                'profile_base_url': 'https://x.com/'
            },
            {
                'slug': 'linkedin',
                'name': 'LinkedIn',
                'description': 'LinkedIn professional network',
                'profile_base_url': 'https://linkedin.com/in/'
            },
            {
                'slug': 'linkedin-company',
                'name': 'LinkedIn Company',
                'description': 'LinkedIn company pages',
                'profile_base_url': 'https://linkedin.com/company/'
            },
        ]
        
        for st_data in source_types:
            SourceType.objects.get_or_create(
                slug=st_data['slug'],
                defaults={
                    'name': st_data['name'],
                    'description': st_data.get('description', ''),
                    'profile_base_url': st_data.get('profile_base_url', '')
                }
            )
        
        # SignalType
        signal_types = [
            {'slug': 'follow', 'name': 'Follow'},
            {'slug': 'like', 'name': 'Like'},
            {'slug': 'retweet', 'name': 'Retweet'},
            {'slug': 'mention', 'name': 'Mention'},
            {'slug': 'investment', 'name': 'Investment'},
            {'slug': 'founder', 'name': 'Founder'},
        ]
        
        for sig_type in signal_types:
            SignalType.objects.get_or_create(
                slug=sig_type['slug'],
                defaults={'name': sig_type['name']}
            )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Базовые типы созданы'))

    def api_get(self, endpoint, params=None):
        """Выполняет GET запрос к API с обработкой ошибок"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Ошибка запроса к {endpoint}: {str(e)}'))
            self.stats['errors'].append(f'{endpoint}: {str(e)}')
            return None

    def import_participants(self, limit=50):
        """Импортирует участников из API"""
        offset = 0
        imported = 0
        
        while imported < limit:
            params = {
                'limit': min(100, limit - imported),
                'offset': offset
            }
            
            data = self.api_get('/v1/participants/', params=params)
            if not data or 'data' not in data:
                break
            
            participants = data['data']
            if not participants:
                break
            
            for p_data in participants:
                try:
                    self.create_or_update_participant(p_data)
                    imported += 1
                    
                    if imported % 10 == 0:
                        self.stdout.write(f'  📥 Импортировано участников: {imported}/{limit}')
                    
                    if imported >= limit:
                        break
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Ошибка импорта участника {p_data.get("slug")}: {str(e)}')
                    )
                    self.stats['errors'].append(f'Participant {p_data.get("slug")}: {str(e)}')
            
            offset += len(participants)
            
            # Проверяем, есть ли еще данные
            if not data.get('pagination', {}).get('has_next', False):
                break
            
            # Небольшая пауза между запросами
            time.sleep(0.5)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Импортировано участников: {imported}'))

    def create_or_update_participant(self, data):
        """Создает или обновляет участника"""
        slug = data.get('slug')
        if not slug:
            return None
        
        # Нормализуем тип участника
        participant_type = data.get('type', 'unknown')
        if participant_type not in dict(PARTICIPANTS_TYPES):
            participant_type = 'unknown'
        
        defaults = {
            'name': data.get('name', slug),
            'additional_name': data.get('alt_name') or '',
            'about': data.get('about') or '',
            'type': participant_type,
            'monthly_signals_count': data.get('monthly_signals', 0),
        }
        
        participant, created = Participant.objects.update_or_create(
            slug=slug,
            defaults=defaults
        )
        
        if created:
            self.stats['participants_created'] += 1
        else:
            self.stats['participants_updated'] += 1
        
        # Создаем источники из sources (если есть детальная информация)
        if 'sources' in data:
            for source_data in data['sources']:
                self.create_source(participant, source_data)
        
        return participant

    def create_source(self, participant, source_data):
        """Создает источник для участника"""
        source_type_slug = source_data.get('type')
        source_slug = source_data.get('slug')
        
        if not source_type_slug or not source_slug:
            return None
        
        source_type = SourceType.objects.filter(slug=source_type_slug).first()
        if not source_type:
            return None
        
        source, _ = Source.objects.get_or_create(
            slug=source_slug,
            source_type=source_type,
            defaults={'participant': participant}
        )
        
        return source

    def import_cards(self, limit=20):
        """Импортирует карточки из API"""
        offset = 0
        imported = 0
        
        while imported < limit:
            params = {
                'limit': min(100, limit - imported),
                'offset': offset,
                'sort': 'recent'
            }
            
            data = self.api_get('/v1/cards/', params=params)
            if not data or 'data' not in data:
                break
            
            cards = data['data']
            if not cards:
                break
            
            for card_data in cards:
                try:
                    # Получаем детальную информацию о карточке
                    slug = card_data.get('slug')
                    detailed_data = self.api_get(f'/v1/cards/{slug}/')
                    
                    if detailed_data and 'data' in detailed_data:
                        card = self.create_or_update_card(detailed_data['data'])
                        
                        # Импортируем взаимодействия (сигналы)
                        if card:
                            self.import_card_interactions(card, slug)
                    
                    imported += 1
                    
                    if imported % 5 == 0:
                        self.stdout.write(f'  📥 Импортировано карточек: {imported}/{limit}')
                    
                    if imported >= limit:
                        break
                    
                    # Пауза между запросами
                    time.sleep(1)
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Ошибка импорта карточки {card_data.get("slug")}: {str(e)}')
                    )
                    self.stats['errors'].append(f'Card {card_data.get("slug")}: {str(e)}')
            
            offset += len(cards)
            
            # Проверяем, есть ли еще данные
            if not data.get('pagination', {}).get('has_next', False):
                break
            
            time.sleep(0.5)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Импортировано карточек: {imported}'))

    def create_or_update_card(self, data):
        """Создает или обновляет карточку"""
        slug = data.get('slug')
        if not slug:
            return None
        
        # Нормализуем стадию и раунд
        stage = self.normalize_stage(data.get('stage'))
        round_status = self.normalize_round(data.get('round'))
        
        # Парсим даты
        created_at = self.parse_datetime(data.get('created_at'))
        last_round_date = self.parse_date(data.get('last_round'))
        
        defaults = {
            'name': data.get('name', slug),
            'description': data.get('description', ''),
            'url': data.get('url', f'https://example.com/{slug}'),
            'created_at': created_at or timezone.now(),
            'stage': stage,
            'round_status': round_status,
            'is_open': True,
            'last_round': last_round_date,
            'more': {},
        }
        
        card, created = SignalCard.objects.update_or_create(
            slug=slug,
            defaults=defaults
        )
        
        if created:
            self.stats['cards_created'] += 1
        else:
            self.stats['cards_updated'] += 1
        
        # Создаем категории
        if 'categories' in data and data['categories']:
            for cat_item in data['categories']:
                # Если категория - это словарь, извлекаем имя
                if isinstance(cat_item, dict):
                    cat_name = cat_item.get('name') or cat_item.get('slug') or str(cat_item)
                else:
                    cat_name = cat_item
                
                category = self.get_or_create_category(cat_name)
                if category:
                    card.categories.add(category)
        
        # Создаем team members (если есть)
        if 'team_members' in data:
            for tm_data in data['team_members']:
                self.create_team_member(card, tm_data)
        
        return card

    def import_card_interactions(self, card, slug):
        """Импортирует взаимодействия (сигналы) для карточки"""
        params = {'limit': 50}
        
        data = self.api_get(f'/v1/cards/{slug}/interactions/', params=params)
        if not data or 'data' not in data:
            return
        
        interactions = data['data']
        
        for interaction_data in interactions:
            try:
                self.create_signal(card, interaction_data)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'    ⚠️  Ошибка импорта сигнала: {str(e)}')
                )

    def create_signal(self, card, data):
        """Создает сигнал из данных взаимодействия"""
        # Получаем или создаем участника
        participant_data = data.get('participant')
        if not participant_data:
            return None
        
        participant = self.get_or_create_participant_from_interaction(participant_data)
        if not participant:
            return None
        
        # Получаем associated_participant (если есть)
        associated_participant = None
        assoc_data = data.get('associated_participant')
        if assoc_data:
            associated_participant = self.get_or_create_participant_from_interaction(assoc_data)
        
        # Создаем или получаем source
        source = self.get_or_create_source_for_participant(participant)
        if not source:
            return None
        
        # Получаем тип сигнала (используем дефолтный)
        signal_type = SignalType.objects.first()
        if not signal_type:
            return None
        
        # Парсим дату
        created_at = self.parse_datetime(data.get('created_at')) or timezone.now()
        
        # Проверяем, существует ли уже такой сигнал
        existing_signal = Signal.objects.filter(
            signal_card=card,
            participant=participant,
            created_at=created_at
        ).first()
        
        if existing_signal:
            return existing_signal
        
        # Создаем сигнал
        signal = Signal.objects.create(
            source=source,
            signal_type=signal_type,
            signal_card=card,
            participant=participant,
            associated_participant=associated_participant,
            created_at=created_at
        )
        
        self.stats['signals_created'] += 1
        return signal

    def get_or_create_participant_from_interaction(self, data):
        """Получает или создает участника из данных взаимодействия"""
        slug = data.get('slug')
        if not slug:
            return None
        
        participant_type = data.get('type', 'unknown')
        if participant_type not in dict(PARTICIPANTS_TYPES):
            participant_type = 'unknown'
        
        participant, created = Participant.objects.get_or_create(
            slug=slug,
            defaults={
                'name': data.get('name', slug),
                'type': participant_type,
            }
        )
        
        if created:
            self.stats['participants_created'] += 1
        
        return participant

    def get_or_create_source_for_participant(self, participant):
        """Получает или создает источник для участника"""
        # Пытаемся найти существующий источник
        source = participant.sources.first()
        if source:
            return source
        
        # Создаем новый источник (Twitter по умолчанию)
        source_type = SourceType.objects.filter(slug='twitter').first()
        if not source_type:
            return None
        
        source = Source.objects.create(
            slug=participant.slug,
            source_type=source_type,
            participant=participant
        )
        
        return source

    def get_or_create_category(self, name):
        """Получает или создает категорию"""
        if not name:
            return None
        
        slug = slugify(name)
        category, created = Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name}
        )
        
        if created:
            self.stats['categories_created'] += 1
        
        return category

    def create_team_member(self, card, data):
        """Создает члена команды"""
        name = data.get('name')
        if not name:
            return None
        
        # Проверяем, существует ли уже
        existing = TeamMember.objects.filter(
            signal_card=card,
            name=name
        ).first()
        
        if existing:
            return existing
        
        TeamMember.objects.create(
            signal_card=card,
            name=name,
            headline=data.get('headline', ''),
            twitter=data.get('twitter', ''),
            linkedin=data.get('linkedin', ''),
            email=data.get('email', ''),
        )

    def normalize_stage(self, stage):
        """Нормализует стадию к доступным значениям"""
        if not stage:
            return 'unknown'
        
        # Если stage - это словарь, извлекаем значение
        if isinstance(stage, dict):
            # Пробуем разные ключи, которые могут быть в словаре
            stage = stage.get('slug') or stage.get('name') or stage.get('value') or str(stage)
        
        # Преобразуем в строку, если это не строка
        if not isinstance(stage, str):
            stage = str(stage)
        
        stage_lower = stage.lower().replace(' ', '_').replace('-', '_')
        
        # Маппинг общих значений
        stage_mapping = {
            'pre_seed': 'pre_seed',
            'preseed': 'pre_seed',
            'seed': 'seed',
            'seed_plus': 'seed_plus',
            'series_a': 'series_a',
            'series_b': 'series_b',
            'series_c': 'series_c',
            'series_d': 'series_d',
            'series_e': 'series_e',
            'series_f': 'series_f',
            'angel': 'angel_round',
            'bootstrapped': 'bootstrapped',
        }
        
        if stage_lower in dict(STAGES):
            return stage_lower
        
        if stage_lower in stage_mapping:
            return stage_mapping[stage_lower]
        
        return 'unknown'

    def normalize_round(self, round_status):
        """Нормализует статус раунда к доступным значениям"""
        if not round_status:
            return 'unknown'
        
        # Если round_status - это словарь, извлекаем значение
        if isinstance(round_status, dict):
            # Пробуем разные ключи, которые могут быть в словаре
            round_status = round_status.get('slug') or round_status.get('name') or round_status.get('value') or str(round_status)
        
        # Преобразуем в строку, если это не строка
        if not isinstance(round_status, str):
            round_status = str(round_status)
        
        round_lower = round_status.lower().replace(' ', '_').replace('-', '_')
        
        # Маппинг общих значений
        round_mapping = {
            'just_raised': 'just_raised',
            'raising_now': 'raising_now',
            'about_to_raise': 'about_to_raise',
            'may_be_raising': 'may_be_raising',
            'acquired': 'acquired',
        }
        
        if round_lower in dict(ROUNDS):
            return round_lower
        
        if round_lower in round_mapping:
            return round_mapping[round_lower]
        
        return 'unknown'

    def parse_datetime(self, date_str):
        """Парсит ISO 8601 дату в datetime объект"""
        if not date_str:
            return None
        
        try:
            # Парсим ISO 8601 формат
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except (ValueError, AttributeError):
            return None

    def parse_date(self, date_str):
        """Парсит дату в формате YYYY-MM-DD"""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            return None

    def print_statistics(self):
        """Выводит статистику импорта"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 СТАТИСТИКА ИМПОРТА'))
        self.stdout.write('='*60)
        
        self.stdout.write(f"\n📦 Карточки:")
        self.stdout.write(f"  • Создано: {self.stats['cards_created']}")
        self.stdout.write(f"  • Обновлено: {self.stats['cards_updated']}")
        
        self.stdout.write(f"\n👥 Участники:")
        self.stdout.write(f"  • Создано: {self.stats['participants_created']}")
        self.stdout.write(f"  • Обновлено: {self.stats['participants_updated']}")
        
        self.stdout.write(f"\n📡 Сигналы:")
        self.stdout.write(f"  • Создано: {self.stats['signals_created']}")
        
        self.stdout.write(f"\n🏷️  Категории:")
        self.stdout.write(f"  • Создано: {self.stats['categories_created']}")
        
        if self.stats['errors']:
            self.stdout.write(f"\n❌ Ошибки ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Показываем первые 10
                self.stdout.write(f"  • {error}")
            if len(self.stats['errors']) > 10:
                self.stdout.write(f"  ... и еще {len(self.stats['errors']) - 10} ошибок")
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ Импорт завершен!'))
        self.stdout.write('='*60 + '\n')

