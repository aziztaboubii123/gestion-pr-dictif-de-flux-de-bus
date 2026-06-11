from django.contrib import admin
from .models import Alerte, Arret, Bus, Capteur, DonneTrafic, Ligne, Prediction

@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ['idalerte', 'message', 'niveau', 'dateemmision']
    list_filter = ['niveau']

@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ['idbus', 'immatriculation', 'modele', 'statut', 'kilometrage']
    list_filter = ['statut']

@admin.register(Ligne)
class LigneAdmin(admin.ModelAdmin):
    list_display = ['idligne', 'numero', 'frequence']

@admin.register(Arret)
class ArretAdmin(admin.ModelAdmin):
    list_display = ['idarret', 'nom', 'code', 'idligne']

@admin.register(Capteur)
class CapteurAdmin(admin.ModelAdmin):
    list_display = ['idcapteur', 'type', 'statut', 'idbus']

@admin.register(DonneTrafic)
class DonneTraficAdmin(admin.ModelAdmin):
    list_display = ['iddonne', 'timestamp', 'vitesse', 'nombrepassager', 'idbus']
    date_hierarchy = 'timestamp'