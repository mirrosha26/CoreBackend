from django_filters import rest_framework as filters
from .models import Signal, Source, SignalCard, Participant, Category
from .models import STAGES, ROUNDS

class ParticipantFilter(filters.FilterSet):
    slug = filters.CharFilter(lookup_expr='iexact')
    associated_with = filters.CharFilter(field_name='associated_with__slug', lookup_expr='iexact')
    associated_with_id = filters.NumberFilter(field_name='associated_with__id', lookup_expr='exact')
    type = filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = Participant
        fields = ['slug', 'associated_with', 'associated_with_id', 'type']

class SourceFilter(filters.FilterSet):
    slug = filters.CharFilter(lookup_expr='iexact')
    source_type = filters.CharFilter(field_name='source_type__slug', lookup_expr='iexact')
    participant_id = filters.NumberFilter(field_name='participant__id', lookup_expr='exact')
    participant_slug = filters.CharFilter(field_name='participant__slug', lookup_expr='iexact')
    tracking_enabled = filters.BooleanFilter(field_name='tracking_enabled', lookup_expr='exact')
    social_network_id = filters.CharFilter(field_name='social_network_id', lookup_expr='exact')

    class Meta:
        model = Source
        fields = ['slug', 'source_type', 'participant_id', 'participant_slug', 'tracking_enabled', 'social_network_id']

class SignalFilter(filters.FilterSet):
    source_id = filters.NumberFilter(field_name='source__id')
    source_slug = filters.CharFilter(field_name='source__slug', lookup_expr='iexact')
    
    signal_type_id = filters.NumberFilter(field_name='signal_type__id')
    signal_type_slug = filters.CharFilter(field_name='signal_type__slug', lookup_expr='iexact')
    
    signal_card_id = filters.NumberFilter(field_name='signal_card__id')
    signal_card_slug = filters.CharFilter(field_name='signal_card__slug', lookup_expr='iexact')
    
    participant_id = filters.NumberFilter(field_name='participant__id')
    participant_slug = filters.CharFilter(field_name='participant__slug', lookup_expr='iexact')
    
    associated_participant_id = filters.NumberFilter(field_name='associated_participant__id')
    associated_participant_slug = filters.CharFilter(field_name='associated_participant__slug', lookup_expr='iexact')

    class Meta:
        model = Signal
        fields = [
            'source_id', 'source_slug', 
            'signal_type_id', 'signal_type_slug', 
            'signal_card_id', 'signal_card_slug', 
            'participant_id', 'participant_slug', 
            'associated_participant_id', 'associated_participant_slug'
        ]

class SignalCardFilter(filters.FilterSet):
    tags = filters.CharFilter(field_name='tags__slug', lookup_expr='iexact')
    tags_multiple = filters.BaseInFilter(field_name='tags__id', lookup_expr='in')
    name = filters.CharFilter(field_name="name", lookup_expr='icontains')
    slug = filters.CharFilter(lookup_expr='icontains')
    categories = filters.CharFilter(field_name='categories__slug', lookup_expr='iexact')
    categories_multiple = filters.BaseInFilter(field_name='categories__id', lookup_expr='in', distinct=True)
    stage = filters.ChoiceFilter(choices=STAGES)
    is_open = filters.BooleanFilter()
    featured = filters.BooleanFilter()
    round_status = filters.ChoiceFilter(choices=ROUNDS)
    created_at = filters.DateFromToRangeFilter(field_name='created_at')
    class Meta:
        model = SignalCard
        fields = [
            'slug', 'stage', 'is_open', 'featured', 'round_status', "created_at"
        ]
    