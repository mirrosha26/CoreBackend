from django.db.models import Q, Exists, OuterRef, Max, Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from frontend_api.serializers.utils import build_absolute_image_url


from signals.models import (
    SignalCard,
    Participant, 
    Signal,
    Category,
    STAGES,
    ROUNDS,
)
from profile.models import (
    DeletedCard,
    SavedParticipant,
    UserFeed,
)


class AllSignalsFilterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        # Получаем параметры фильтрации из query_params
        category_slugs = request.query_params.getlist('category', [])
        stage_slugs = request.query_params.getlist('stage', [])
        round_slugs = request.query_params.getlist('round', [])
        participant_slugs = request.query_params.getlist('participant', [])

        data_geted = (category_slugs or stage_slugs or round_slugs or participant_slugs)
        
        deleted_card_ids = DeletedCard.objects.filter(user=user).values_list('signal_card_id', flat=True)

        acceptable_signals = Signal.objects.filter(
            signal_card=OuterRef('pk')
        )

        init_query = SignalCard.objects.annotate(
            has_acceptable_signal=Exists(acceptable_signals),
            latest_signal_date=Max('signals__created_at')
        ).filter(
            has_acceptable_signal=True
        ).exclude(id__in=deleted_card_ids)

        # Всегда показываем все сигналы (ALL)

        base_query = init_query

        if not data_geted:
            # Используем фильтры из сессии, если они есть
            session_filters = request.session.get('current_filters', {})
            category_slugs = []
            stage_slugs = []
            round_slugs = []
            participant_slugs = []
            
            # Можно добавить логику получения из сессии, если нужно

        category_filter = Q()
        stage_filter = Q()
        round_filter = Q()
        participant_filter = Q()

        if category_slugs:
            category_filter = Q(categories__slug__in=category_slugs)
            base_query = base_query.filter(category_filter)

        if participant_slugs:
            participant_filter = Q(signals__participant__slug__in=participant_slugs) | Q(signals__associated_participant__slug__in=participant_slugs)
            base_query = base_query.filter(participant_filter)

        stages_or_rounds_filter = Q()
        if stage_slugs:
            stage_filter = Q(stage__in=stage_slugs)
            stages_or_rounds_filter |= stage_filter

        if round_slugs:
            round_filter = Q(round_status__in=round_slugs)
            stages_or_rounds_filter |= round_filter

        base_query = base_query.filter(stages_or_rounds_filter)

        # Применение логики И для категорий со всеми остальными фильтрами
        base_query = base_query.filter(category_filter & participant_filter & stages_or_rounds_filter)

        if not data_geted and not base_query.exists():
            base_query = init_query.filter(participant_filter)
            
            # Определяем, какие категории показывать в зависимости от предпочтений пользователя
            if False:  # Удалено: всегда показываем все
                web3_category = Category.objects.filter(slug='web3').first()
                if web3_category:
                    available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category=web3_category).distinct()
                else:
                    available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category__isnull=True).distinct()
            else:
                available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category__isnull=True).distinct()
                
            available_stages = {stage[0]: stage[1] for stage in STAGES if base_query.filter(stage=stage[0]).exists() and stage[0] != 'worth_following'}
            available_rounds = {round[0]: round[1] for round in ROUNDS if base_query.filter(round_status=round[0]).exists()}
            participant_ids_in_init_query = base_query.values_list('signals__associated_participant__id')
            category_slugs = []
            stage_slugs = []
            round_slugs = []
            participant_slugs = participant_slugs

        else:
            # Определяем, какие категории показывать в зависимости от предпочтений пользователя
            if False:  # Удалено: всегда показываем все
                web3_category = Category.objects.filter(slug='web3').first()
                if web3_category:
                    available_categories = Category.objects.filter(
                        signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                        parent_category=web3_category
                    ).distinct() if category_slugs else Category.objects.filter(
                        signal_cards__in=base_query,
                        parent_category=web3_category
                    ).distinct()
                else:
                    available_categories = Category.objects.filter(
                        signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                        parent_category__isnull=True
                    ).distinct().exclude(slug='web3') if category_slugs else Category.objects.filter(
                        signal_cards__in=base_query,
                        parent_category__isnull=True
                    ).distinct().exclude(slug='web3')
            else:
                available_categories = Category.objects.filter(
                    signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                    parent_category__isnull=True
                ).distinct() if category_slugs else Category.objects.filter(
                    signal_cards__in=base_query,
                    parent_category__isnull=True
                ).distinct()

            available_stages = {stage[0]: stage[1] for stage in STAGES if init_query.filter(
                category_filter & participant_filter
            ).filter(stage=stage[0]).exists()} if stage_slugs else {stage[0]: stage[1] for stage in STAGES if base_query.filter(stage=stage[0]).exists()}

            available_rounds = {round[0]: round[1] for round in ROUNDS if init_query.filter(
                category_filter & participant_filter
            ).filter(round_status=round[0]).exists()} if round_slugs else {round[0]: round[1] for round in ROUNDS if base_query.filter(round_status=round[0]).exists()}

            participant_ids_in_init_query = init_query.filter(
                category_filter & stages_or_rounds_filter
            ).values_list('signals__associated_participant__id') if participant_slugs else base_query.values_list('signals__associated_participant__id')

            
        available_participants = Participant.objects.filter(id__in=participant_ids_in_init_query).distinct()
        response_data = {
            'success': True,
            'stages': [
                {'slug': slug, 'name': name, 'active': slug in stage_slugs} 
                for slug, name in available_stages.items()
            ],
            'rounds': [
                {'slug': slug, 'name': name, 'active': slug in round_slugs} 
                for slug, name in available_rounds.items()
            ],
            'participants': sorted([
                {
                    'name': participant.name, 
                    'image': build_absolute_image_url(participant, True), 
                    'slug': participant.slug, 
                    'active': participant.slug in participant_slugs
                } 
                for participant in available_participants
            ], key=lambda x: x['name']),
            'categories': sorted([
                {'name': category.name, 'slug': category.slug, 'active': category.slug in category_slugs} 
                for category in available_categories
            ], key=lambda x: x['name'])
        }
        return Response(response_data)
    
    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Получаем данные из тела запроса
        category_slugs = request.data.get('categories', [])
        stage_slugs = request.data.get('stages', [])
        # Исключаем worth_following из опций фильтра по стадиям
        stage_slugs = [stage for stage in stage_slugs if stage != 'worth_following']
        round_slugs = request.data.get('rounds', [])
        participant_slugs = request.data.get('participants', [])
        
        # Сохраняем фильтры в сессию
        request.session['current_filters'] = {
            'categories': category_slugs,
            'stages': stage_slugs,
            'round_statuses': round_slugs,
            'participants': participant_slugs
        }
        
        return Response({'success': True, 'message': 'Feed filters updated successfully'})
    
class FeedFilterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        # Получаем параметры фильтрации из query_params
        category_slugs = request.query_params.getlist('category', [])
        stage_slugs = request.query_params.getlist('stage', [])
        round_slugs = request.query_params.getlist('round', [])
        participant_slugs = request.query_params.getlist('participant', [])

        data_geted = (category_slugs or stage_slugs or round_slugs or participant_slugs)

        saved_participant_ids = SavedParticipant.objects.filter(user=user).values_list('participant_id', flat=True)
        deleted_card_ids = DeletedCard.objects.filter(user=user).values_list('signal_card_id', flat=True)
        init_query = SignalCard.objects.filter(
            Q(signals__associated_participant__id__in=saved_participant_ids) | 
            Q(signals__participant__id__in=saved_participant_ids),
            is_open=True
        ).exclude(id__in=deleted_card_ids).annotate(signals_count=Count('signals')).filter(signals_count__gt=0).distinct()
        
        # Всегда показываем все сигналы (ALL)
        
        base_query = init_query

        if not data_geted:
            user_feed, created = UserFeed.objects.get_or_create(user=user)
            category_slugs = list(user_feed.categories.values_list('slug', flat=True)) if user_feed.categories.exists() else []
            stage_slugs = user_feed.stages if user_feed.stages else []
            # Исключаем worth_following из опций фильтра по стадиям
            stage_slugs = [stage for stage in stage_slugs if stage != 'worth_following']
            round_slugs = user_feed.round_statuses if user_feed.round_statuses else []
            participant_slugs = list(user_feed.participants.values_list('slug', flat=True)) if user_feed.participants.exists() else []

        category_filter = Q()
        stage_filter = Q()
        round_filter = Q()
        participant_filter = Q()

        if category_slugs:
            category_filter = Q(categories__slug__in=category_slugs) | Q(categories__parent_category__slug__in=category_slugs)
            base_query = base_query.filter(category_filter)

        if participant_slugs:
            participant_filter = Q(signals__participant__slug__in=participant_slugs) | Q(signals__associated_participant__slug__in=participant_slugs)
            base_query = base_query.filter(participant_filter)

        stages_or_rounds_filter = Q()
        if stage_slugs:
            stage_filter = Q(stage__in=stage_slugs)
            stages_or_rounds_filter |= stage_filter

        if round_slugs:
            round_filter = Q(round_status__in=round_slugs)
            stages_or_rounds_filter |= round_filter
        base_query = base_query.filter(stages_or_rounds_filter)

        private_participants = Participant.objects.filter(
            saved_by_users__user=user,
        ).filter(
            Q(signals__isnull=False) | Q(associated_signals__isnull=False)
        ).distinct()

        non_private_participants = Participant.objects.filter(
            id__in=saved_participant_ids,
        ).distinct()

        all_participants = private_participants | non_private_participants

        if not data_geted and not base_query.exists():
            base_query = init_query.filter(participant_filter)
            
            # Определяем, какие категории показывать в зависимости от предпочтений пользователя
            if False:  # Удалено: всегда показываем все
                web3_category = Category.objects.filter(slug='web3').first()
                if web3_category:
                    available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category=web3_category).distinct()
                else:
                    available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category__isnull=True).distinct()
            else:
                available_categories = Category.objects.filter(signal_cards__in=base_query, parent_category__isnull=True).distinct()
                
            available_stages = {stage[0]: stage[1] for stage in STAGES if base_query.filter(stage=stage[0]).exists() and stage[0] != 'worth_following'}
            available_rounds = {round[0]: round[1] for round in ROUNDS if base_query.filter(round_status=round[0]).exists()}
            participant_ids_in_init_query = base_query.values_list('signals__associated_participant__id')
            category_slugs = []
            stage_slugs = []
            round_slugs = []
            participant_slugs = participant_slugs

        else:
            # Определяем, какие категории показывать в зависимости от предпочтений пользователя
            if False:  # Удалено: всегда показываем все
                web3_category = Category.objects.filter(slug='web3').first()
                if web3_category:
                    available_categories = Category.objects.filter(
                        signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                        parent_category=web3_category
                    ).distinct() if category_slugs else Category.objects.filter(
                        signal_cards__in=base_query,
                        parent_category=web3_category
                    ).distinct()
                else:
                    available_categories = Category.objects.filter(
                        signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                        parent_category__isnull=True
                    ).distinct().exclude(slug='web3') if category_slugs else Category.objects.filter(
                        signal_cards__in=base_query,
                        parent_category__isnull=True
                    ).distinct().exclude(slug='web3')
            else:
                available_categories = Category.objects.filter(
                    signal_cards__in=init_query.filter(participant_filter & stages_or_rounds_filter),
                    parent_category__isnull=True
                ).distinct() if category_slugs else Category.objects.filter(
                    signal_cards__in=base_query,
                    parent_category__isnull=True
                ).distinct()

            available_stages = {stage[0]: stage[1] for stage in STAGES if init_query.filter(
                category_filter & participant_filter
            ).filter(stage=stage[0]).exists()} if stage_slugs else {stage[0]: stage[1] for stage in STAGES if base_query.filter(stage=stage[0]).exists()}

            available_rounds = {round[0]: round[1] for round in ROUNDS if init_query.filter(
                category_filter & participant_filter
            ).filter(round_status=round[0]).exists()} if round_slugs else {round[0]: round[1] for round in ROUNDS if base_query.filter(round_status=round[0]).exists()}

            participant_ids_in_init_query = init_query.filter(
                category_filter & stages_or_rounds_filter
            ).values_list('signals__associated_participant__id') if participant_slugs else base_query.values_list('signals__associated_participant__id')

        participant_ids = set(id for ids in participant_ids_in_init_query for id in ids if id)
        available_participants = all_participants.filter(id__in=participant_ids)

        response_data = {
            'success': True,
            'stages': [
                {'slug': slug, 'name': name, 'active': slug in stage_slugs} 
                for slug, name in available_stages.items()
            ],
            'rounds': [
                {'slug': slug, 'name': name, 'active': slug in round_slugs} 
                for slug, name in available_rounds.items()
            ],
            'participants': sorted([
                {
                    'name': participant.name, 
                    'image': build_absolute_image_url(participant, True), 
                    'slug': participant.slug, 
                    'active': participant.slug in participant_slugs
                } 
                for participant in available_participants
            ], key=lambda x: x['name']),
            'categories': sorted([
                {'name': category.name, 'slug': category.slug, 'active': category.slug in category_slugs} 
                for category in available_categories
            ], key=lambda x: x['name'])
        }
        return Response(response_data)

    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Получаем данные из тела запроса
        category_slugs = request.data.get('categories', [])
        stage_slugs = request.data.get('stages', [])
        # Исключаем worth_following из опций фильтра по стадиям
        stage_slugs = [stage for stage in stage_slugs if stage != 'worth_following']
        round_slugs = request.data.get('rounds', [])
        participant_slugs = request.data.get('participants', [])
        
        # Создаем пустую запись фильтра, если она не существует
        user_feed, created = UserFeed.objects.get_or_create(user=user)

        if category_slugs:
            categories = Category.objects.filter(slug__in=category_slugs)
            if not categories.exists():
                return Response({'success': False, 'error': 'Categories not found'}, status=status.HTTP_404_NOT_FOUND)
            user_feed.categories.set(categories)
        else:
            user_feed.categories.clear()

        user_feed.stages = stage_slugs if stage_slugs else []
        user_feed.round_statuses = round_slugs if round_slugs else []

        if participant_slugs:
            participants = Participant.objects.filter(slug__in=participant_slugs)
            if not participants.exists():
                return Response({'success': False, 'error': 'Participants not found'}, status=status.HTTP_404_NOT_FOUND)
            user_feed.participants.set(participants)
        else:
            user_feed.participants.clear()

        user_feed.save()
