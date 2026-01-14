from django.utils import timezone
from django.db.models import Q, Exists, OuterRef, Count, Case, When, Value, IntegerField
from datetime import timedelta


def get_date_range(date_filter):
    """
    Helper function to get date range based on filter
    
    Args:
        date_filter: String filter ('today', 'this_week', 'last_week', 'this_month')
        
    Returns:
        Tuple of (start_date, end_date) or (None, None)
    """
    now = timezone.now()
    
    if date_filter == 'today':
        return now - timedelta(days=1), now
    elif date_filter == 'this_week' or date_filter == 'last_week':
        return now - timedelta(days=7), now
    elif date_filter == 'this_month':
        return now - timedelta(days=31), now
    
    return None, None


def get_image_url(model_instance, absolute_image_url=False, base_url="https://app.theveck.com:8000/"):
    """
    Get image URL from model instance
    
    Args:
        model_instance: Model instance with image field
        absolute_image_url: Boolean to return absolute URL
        base_url: Base URL for absolute path
        
    Returns:
        Image URL string or None
    """
    if hasattr(model_instance, 'image') and model_instance.image:
        image_url = model_instance.image.url
        if absolute_image_url:
            image_url = base_url.rstrip("/") + "/" + image_url.lstrip("/")
        return image_url
    
    return None


def apply_search_query_filters(signal_cards, search_query):
    """
    Apply search filters to signal cards queryset
    Searches in: signal card name, description, team members, and LinkedIn data
    
    Args:
        signal_cards: QuerySet of SignalCard objects or list
        search_query: Search query string
        
    Returns:
        Tuple of (filtered queryset or list, use_relevance_sorting boolean)
    """
    # If search query is empty, return original queryset
    if not search_query or search_query.strip() == '':
        return signal_cards, False
    
    # Handle list input
    if isinstance(signal_cards, list):
        filtered_cards = [
            card for card in signal_cards 
            if (search_query.lower() in card.name.lower() or 
                (card.description and search_query.lower() in card.description.lower()))
        ]
        return filtered_cards, False
    
    # Import models to avoid circular imports
    from signals.models import TeamMember, Signal
    
    # Use EXISTS subqueries for better performance
    team_member_match = Exists(
        TeamMember.objects.filter(
            signal_card=OuterRef('pk'),
            name__icontains=search_query
        )
    )
    
    linkedin_match = Exists(
        Signal.objects.filter(
            signal_card=OuterRef('pk'),
            linkedin_data__name__icontains=search_query
        )
    )
    
    # Filter signal cards
    filtered_cards = signal_cards.annotate(
        team_member_match=team_member_match,
        linkedin_match=linkedin_match
    ).filter(
        Q(name__icontains=search_query) | 
        Q(description__icontains=search_query) |
        Q(team_member_match=True) |
        Q(linkedin_match=True)
    )
    
    # Annotate for relevance sorting
    filtered_cards = filtered_cards.annotate(
        search_relevance=Case(
            When(name__iexact=search_query, then=Value(100)),
            When(name__icontains=search_query, then=Value(75)),
            When(team_member_match=True, then=Value(60)),
            When(linkedin_match=True, then=Value(50)),
            When(description__icontains=search_query, then=Value(25)),
            default=Value(0),
            output_field=IntegerField()
        )
    )
    
    return filtered_cards, True


def apply_signal_count_filters(queryset, min_sig=1, max_sig=None, unique=False):
    """
    Apply signal count filtering to a queryset
    
    Args:
        queryset: Base queryset of SignalCards
        min_sig: Minimum number of signals required (default: 1)
        max_sig: Maximum number of signals allowed (default: None)
        unique: If True, count only signals with unique parent participants
    """
    # Skip filtering if min_sig is 1 and max_sig is None
    if min_sig <= 1 and max_sig is None:
        return queryset

    if unique:
        # Count signals with unique parent participants
        queryset = queryset.annotate(
            signal_count=Count(
                Case(
                    When(
                        signals__participant__associated_with__isnull=False,
                        then='signals__participant__associated_with'
                    ),
                    default='signals__participant',
                ),
                distinct=True
            )
        )
    else:
        # Count signals from unique participants
        queryset = queryset.annotate(
            signal_count=Count('signals__participant', distinct=True)
        )
    
    # Apply min_sig filter
    if min_sig > 1:
        queryset = queryset.filter(signal_count__gte=min_sig)
    
    # Apply max_sig filter
    if max_sig is not None:
        queryset = queryset.filter(signal_count__lte=max_sig)
    
    return queryset
