# transport_intelligent/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'transport_intelligent.settings')

# Initialiser Django
django_asgi_app = get_asgi_application()

# Importer channels APRÈS django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# Importer le consumer
from dashboard.consumers import DashboardConsumer

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/dashboard/', DashboardConsumer.as_asgi()),
        ])
    ),
})