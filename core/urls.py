from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/trips/', views.api_trips, name='api_trips'),
    path('api/buses/', views.api_buses, name='api_buses'),
    path('api/alerts/', views.api_alerts, name='api_alerts'),
    path('api/lines/', views.api_lines, name='api_lines'),
    path('api/resolve-alert/', views.resolve_alert, name='resolve_alert'),
    path('api/save-bus/', views.save_bus, name='save_bus'),
    path('export/', views.export_data, name='export'),
]