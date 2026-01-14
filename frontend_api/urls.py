from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenRefreshView, 
    TokenVerifyView, 
    TokenBlacklistView
)

from .views import (
    RegisterView, 
    LoginView, 
    ProfileView,
    RegistrationMetaView,
    ProfileUpdateView,
    PasswordChangeView,
    TicketContactView,
    InvestorView,
    CardListView,
    CardFavoriteView,
    CardNoteView,
    CardDetailView,
    CardDeleteView,
    DigestSettingsView,
    UserSavedFiltersView,
    UserSavedParticipantsView,
    UserFoldersView,
    OnboardingStatusView,
    UserGroupUpdateView
)
from .views.auth import (
    ClientAPITokenListView,
    ClientAPITokenCreateView,
    ClientAPITokenDeleteView
)

from .views.cards import (
    PublicCardPreviewView,
    PublicCardDetailView,
    CardGroupMembersView
)

from frontend_api.views.folders import (
    FolderListView, 
    FolderDetailView, 
    CardFoldersView,
    FolderExportView,
)

from frontend_api.views.feeds import (
    AllSignalsView,
    UserFeedView
)

from frontend_api.views.filters import (
    AllSignalsFilterView,
    FeedFilterView
)

auth_patterns = [
    path('registration-meta/', RegistrationMetaView.as_view()),
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('refresh/', TokenRefreshView.as_view()),
    path('verify/', TokenVerifyView.as_view()),
    path('logout/', TokenBlacklistView.as_view()),
    # Client API Token management (более специфичные маршруты должны быть раньше)
    path('client-tokens/create/', ClientAPITokenCreateView.as_view(), name='api-client-token-create'),
    path('client-tokens/<int:token_id>/delete/', ClientAPITokenDeleteView.as_view(), name='api-client-token-delete'),
    path('client-tokens/', ClientAPITokenListView.as_view(), name='api-client-token-list'),
]

profile_patterns = [
    path('profile/', ProfileView.as_view()),
    path('profile/update/', ProfileUpdateView.as_view()),
    path('password/change/', PasswordChangeView.as_view()),
    path('digest-settings/', DigestSettingsView.as_view(), name='api-digest-settings'),
    path('digest-settings/saved-filters/', UserSavedFiltersView.as_view(), name='api-user-saved-filters'),
    path('digest-settings/saved-participants/', UserSavedParticipantsView.as_view(), name='api-user-saved-participants'),
    path('digest-settings/folders/', UserFoldersView.as_view(), name='api-user-folders'),
    path('onboarding/', OnboardingStatusView.as_view(), name='api-user-onboarding'),
    path('group/update/', UserGroupUpdateView.as_view(), name='api-user-group-update'),
]

investor_patterns = [
    path('', InvestorView.as_view()),
]

card_patterns = [
    path('', CardListView.as_view()),
    path('<int:card_id>/favorite/', CardFavoriteView.as_view()),
    path('<int:card_id>/delete/', CardDeleteView.as_view()),
    path('<int:card_id>/note/', CardNoteView.as_view()),
    path('<int:card_id>/folders/', CardFoldersView.as_view(), name='api-card-folders'),
    path('<int:card_id>/group-members/', CardGroupMembersView.as_view(), name='api-card-group-members'),
    path('<int:card_id>/', CardDetailView.as_view()),
]

feed_patterns = [
    path('all-signals/', AllSignalsView.as_view(), name='api-all-signals'),
    path('personal/', UserFeedView.as_view(), name='api-user-feed'),
]

filter_patterns = [
    path('all-signals/', AllSignalsFilterView.as_view(), name='api-all-signals-filter'),
    path('personal/', FeedFilterView.as_view(), name='api-user-feed-filter'),
]

public_card_patterns = [
    path('<str:identifier>/preview/', PublicCardPreviewView.as_view(), name='api-public-card-preview'),
    path('<str:identifier>/detail/', PublicCardDetailView.as_view(), name='api-public-card-detail'),
]

urlpatterns = [
    path('auth/', include(auth_patterns)),
    path('user/', include(profile_patterns)),  
    path('tickets/', TicketContactView.as_view()),
    path('investors/', include(investor_patterns)),
    path('cards/', include(card_patterns)),
    path('public/', include(public_card_patterns)),
    path('folders/', FolderListView.as_view(), name='api-folders-list'),
    path('folders/<int:folder_id>/', FolderDetailView.as_view(), name='api-folder-detail'),
    path('folders/export/', FolderExportView.as_view(), name='api-universal-export'),
    path('feeds/', include(feed_patterns)),
    path('filters/', include(filter_patterns)),
]