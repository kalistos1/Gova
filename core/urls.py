from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
   
    path('', views.index, name='index'),
    path('dashboard/citizen/', views.citizen_dashboard, name='citizen_dashboard'),
    path('dashboard/citizen/reports/', views.user_reports_list, name='user_reports_list'),
    path('dashboard/citizen/deadlines/', views.user_deadlines_list, name='user_deadlines_list'),
]
