from django.urls import path

from .views import AuthenticatedGraphQLView

app_name = 'graphql'

urlpatterns = [
    path('', AuthenticatedGraphQLView.as_view(), name='graphql'),
]