from django.urls import path
from .views import login_view, register_view, logout_view

urlpatterns = [
    
    path('', login_view, name='login'),        # racine de accounts/ → login
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
]