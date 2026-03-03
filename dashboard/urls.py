
from django.urls import path
from .views import dashboard_home, dashboard_charts_api

urlpatterns = [
    path('', dashboard_home, name='dashboard_home'),
    path('charts/', dashboard_charts_api, name='dashboard_charts_api'),
]
