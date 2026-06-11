from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/login/')),  # racine redirige vers login
    path('login/', include('accounts.urls')),        # login + register + logout
    path('dashboard/', include('dashboard.urls')),   # dashboard
]