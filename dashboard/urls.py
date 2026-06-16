from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard_index'),
    path('api/filters/', views.api_filters, name='api_filters'),
    path('api/data/', views.api_data, name='api_data'),
    path('api/report/', views.api_report, name='api_report'),
]
