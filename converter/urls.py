from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/start/', views.start_conversion, name='start_conversion'),
    path('api/status/<uuid:task_id>/', views.get_status, name='get_status'),
]
