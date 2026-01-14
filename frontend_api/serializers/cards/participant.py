from rest_framework import serializers
from signals.models import Participant
from signals.utils import get_image_url
from frontend_api.serializers.utils import build_absolute_image_url

def serialize_participant(participant, signal, absolute_image_url, saved_participant_ids):
    sources = participant.sources.all()
    source_list = []
    for source in sources:
        source_data = {
            "type": str(source.source_type), 
            "slug": source.slug, 
            "link": source.get_profile_link()
        }
        source_list.append(source_data)
        
    return {
        "sources": source_list,
        "associated_id": participant.id,
        "associated_saved": participant.id in saved_participant_ids,
        "associated_slug": participant.slug,
        "associated_about": participant.about,
        "associated_name": participant.name,
        "associated_email": participant.email,
        "associated_linkedin_url": participant.linkedin_url,
        "associated_image": build_absolute_image_url(participant, absolute_image_url=absolute_image_url),
        "associated_signal_created_at": signal.created_at.strftime("%Y-%m-%d"),
        "more": []
    }

def serialize_linkedin_data(linkedin_data, signal, absolute_image_url):
    """Serialize LinkedIn data for signal cards"""
    return {
        "sources": [{
            "type": "LinkedIn",
            "slug": f"linkedin_{linkedin_data.id}",
            "link": linkedin_data.linkedin_profile_url
        }],
        "linkedinData": {
            "name": linkedin_data.name,
            "linkedinProfileUrl": linkedin_data.linkedin_profile_url,
            "classification": linkedin_data.classification,
            "tags": linkedin_data.tags if linkedin_data.tags else [],
            "summary": linkedin_data.summary,
            "experience": linkedin_data.experience if linkedin_data.experience else [],
            "education": linkedin_data.education if linkedin_data.education else [],
            "notableAchievements": linkedin_data.notable_achievements,
            "oneLiner": linkedin_data.one_liner,
            "location": linkedin_data.location,
            "createdAt": linkedin_data.created_at.isoformat() if linkedin_data.created_at else None,
            "updatedAt": linkedin_data.updated_at.isoformat() if linkedin_data.updated_at else None,
            "signalType": signal.signal_type.slug if signal.signal_type else "linkedin"
        },
        "linkedin_signal_created_at": signal.created_at.strftime("%Y-%m-%d"),
        "more": []
    }

# ParticipantRequestSerializer удален - ParticipantRequest больше не используется

class ParticipantSerializer(serializers.ModelSerializer):
    full_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = ['id', 'name', 'additional_name', 'about',
                 'image', 'slug', 'full_image_url']

    def get_full_image_url(self, obj):
        return build_absolute_image_url(obj, absolute_image_url=True) 