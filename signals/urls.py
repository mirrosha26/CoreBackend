from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    SourceTypeViewSet,
    SourceViewSet,
    SignalTypeViewSet,
    CategoryViewSet,
    SignalCardViewSet,
    SignalViewSet,
    TeamMemberViewSet,
    ParticipantViewSet,
    SignalRawViewSet,
    get_stages,
    get_rounds
)

router = DefaultRouter()

# Register viewsets
router.register(r'source-types', SourceTypeViewSet, basename='sourcetype')
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'signal-types', SignalTypeViewSet, basename='signaltype')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'signal-cards', SignalCardViewSet, basename='signalcard')
router.register(r'signals', SignalViewSet, basename='signal')
router.register(r'team-members', TeamMemberViewSet, basename='teammember')
router.register(r'participants', ParticipantViewSet, basename='participant')
router.register(r'signals-raw', SignalRawViewSet, basename='signalraw')

urlpatterns = [
    path('', include(router.urls)),
    path('token-auth/', obtain_auth_token, name='api-token-auth'),
    path('stages/', get_stages, name='get-stages'),
    path('rounds/', get_rounds, name='get-rounds'),
]
