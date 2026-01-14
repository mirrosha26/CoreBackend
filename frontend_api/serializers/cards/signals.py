from django.db.models import Prefetch
from signals.models import Signal, Category
from frontend_api.serializers.utils import build_absolute_image_url
from .participant import serialize_participant, serialize_linkedin_data


def serialize_signal_source(source):
    return {
        "type": str(source.source_type),
        "slug": source.slug,
        "link": source.get_profile_link()
    }

def serialize_participant_info(signal, absolute_image_url):
    # Check if participant exists
    if signal.participant is None:
        return None
    
    return {
        "sources": [serialize_signal_source(source) for source in signal.participant.sources.all()],
        "participant_id": signal.participant.id,
        "participant_name": signal.participant.name,
        "participant_about": signal.participant.about,
        "participant_image": build_absolute_image_url(signal.participant, absolute_image_url),
        "participant_slug": signal.participant.slug,
        "participant_signal_created_at": signal.created_at.strftime("%Y-%m-%d")
    }

def serialize_founder_data(source_signal_card, signal, absolute_image_url):
    """
    Serialize founder signal data (source_signal_card).
    
    Args:
        source_signal_card: The SignalCard that represents the founder
        signal: The Signal object
        absolute_image_url: Whether to use absolute URLs
    
    Returns:
        dict: Serialized founder data
    """
    return {
        "type": "founder",
        "founder_id": source_signal_card.id,
        "founder_name": source_signal_card.name,
        "founder_slug": source_signal_card.slug,
        "founder_image": build_absolute_image_url(source_signal_card, absolute_image_url),
        "founder_description": source_signal_card.description,
        "founder_url": source_signal_card.url,
        "founder_signal_created_at": signal.created_at.strftime("%Y-%m-%d"),
        "more": []
    }

def update_participant_more_info(participant_data, more_info):
    if "more" not in participant_data:
        participant_data["more"] = []

    existing_participant_ids = {info["participant_id"] for info in participant_data["more"]}

    if more_info["participant_id"] not in existing_participant_ids:
        participant_data["more"].append(more_info)
    else:
        existing_idx = next(
            i for i, m in enumerate(participant_data["more"])
            if m["participant_id"] == more_info["participant_id"]
        )
        existing_date = participant_data["more"][existing_idx]["participant_signal_created_at"]
        new_date = more_info["participant_signal_created_at"]

        if new_date < existing_date:
            participant_data["more"][existing_idx] = more_info

def serialize_signals(signals, saved_participant_ids, absolute_image_url, limit=None): 
    unique_participants = {}
    unique_linkedin_data = {}
    unique_founder_data = {}

    for signal in signals:
        # Handle LinkedIn data signals
        if signal.linkedin_data:
            linkedin_id = signal.linkedin_data.id
            if linkedin_id not in unique_linkedin_data:
                unique_linkedin_data[linkedin_id] = serialize_linkedin_data(signal.linkedin_data, signal, absolute_image_url)
            continue
        
        # Handle founder signals (source_signal_card)
        if signal.source_signal_card:
            founder_id = signal.source_signal_card.id
            if founder_id not in unique_founder_data:
                unique_founder_data[founder_id] = serialize_founder_data(signal.source_signal_card, signal, absolute_image_url)
            continue
        
        # Handle participant signals (existing logic)
        associated_participant = signal.associated_participant if hasattr(signal, 'associated_participant') else signal.participant

        if not associated_participant:
            continue

        participant_id = associated_participant.id

        if participant_id not in unique_participants:
            unique_participants[participant_id] = serialize_participant(associated_participant, signal, absolute_image_url, saved_participant_ids)

        if signal.id != participant_id and signal.participant and signal.participant.id != associated_participant.id:
            more_info = serialize_participant_info(signal, absolute_image_url)
            if more_info is not None:
                update_participant_more_info(unique_participants[participant_id], more_info)

    # Sort participants
    for participant in unique_participants.values():
        participant["more"].sort(key=lambda x: x["participant_signal_created_at"], reverse=True)

    # Combine participants, LinkedIn data, and founder data
    all_data = list(unique_participants.values()) + list(unique_linkedin_data.values()) + list(unique_founder_data.values())
    
    # Sort by creation date
    sorted_data = sorted(
        all_data,
        key=lambda p: (
            p["more"][0]["participant_signal_created_at"] if p.get("more") else 
            p.get("associated_signal_created_at") or 
            p.get("linkedin_signal_created_at") or
            p.get("founder_signal_created_at", "")
        ),
        reverse=True
    )
    
    # Apply limit if specified
    if limit is not None:
        sorted_data = sorted_data[:limit]
    
    return sorted_data