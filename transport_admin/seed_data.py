from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Crée un utilisateur administrateur par défaut'
    
    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@transport.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Utilisateur admin créé: admin / admin123'))
        else:
            self.stdout.write(self.style.WARNING('L\'utilisateur admin existe déjà'))