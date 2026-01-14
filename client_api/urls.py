from django.urls import path, include
from .views import (
    APIVersionsView,
    TokenValidationView, 
    CardListView, 
    CardDetailView, 
    CardInteractionsView,
    CardCategoriesMetaView,
    CardStagesMetaView,
    CardRoundsMetaView,
    ParticipantListView,
    ParticipantDetailView,
    ParticipantBatchView,
    ParticipantTypesMetaView,
    CardFoldersMetaView,
    CardFiltersMetaView
)

# Маршруты для v1 API
v1_urlpatterns = [
    path('token/validate/', TokenValidationView.as_view(), name='client-api-token-validate'),
    path('cards/', CardListView.as_view(), name='client-api-cards'),
    path('cards/categories/', CardCategoriesMetaView.as_view(), name='client-api-cards-categories'),
    path('cards/stages/', CardStagesMetaView.as_view(), name='client-api-cards-stages'),
    path('cards/rounds/', CardRoundsMetaView.as_view(), name='client-api-cards-rounds'),
    path('cards/folders/', CardFoldersMetaView.as_view(), name='client-api-cards-folders'),
    path('cards/filters/', CardFiltersMetaView.as_view(), name='client-api-cards-filters'),
    path('cards/<slug:slug>/', CardDetailView.as_view(), name='client-api-card-detail'),
    path('cards/<slug:slug>/interactions/', CardInteractionsView.as_view(), name='client-api-card-interactions'),
    path('participants/', ParticipantListView.as_view(), name='client-api-participants'),
    path('participants/types/', ParticipantTypesMetaView.as_view(), name='client-api-participants-types'),
    path('participants/batch/', ParticipantBatchView.as_view(), name='client-api-participants-batch'),
    path('participants/<slug:slug>/', ParticipantDetailView.as_view(), name='client-api-participant-detail'),
]

urlpatterns = [
    path('', APIVersionsView.as_view(), name='client-api-versions'),
    path('v1/', include(v1_urlpatterns)),
]
