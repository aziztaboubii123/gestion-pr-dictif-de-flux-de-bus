from django.contrib.gis.db import models

class Ligne(models.Model):
    idligne = models.AutoField(primary_key=True, db_column='idligne')
    numero = models.CharField(max_length=20, db_column='numero', null=True, blank=True)
    frequence = models.IntegerField(db_column='frequence', null=True, blank=True)
    geometry = models.LineStringField(srid=4326, db_column='geometry', null=True, blank=True)
    
    class Meta:
        db_table = 'ligne'
        managed = False
        
    def __str__(self):
        return f"Ligne {self.numero}"

class Arret(models.Model):
    idarret = models.AutoField(primary_key=True, db_column='idarret')
    nom = models.CharField(max_length=100, db_column='nom', null=True, blank=True)
    code = models.CharField(max_length=20, db_column='code', null=True, blank=True)
    geometry = models.PointField(srid=4326, db_column='geometry', null=True, blank=True)
    idligne = models.IntegerField(db_column='idligne', null=True, blank=True)
    
    class Meta:
        db_table = 'arret'
        managed = False
        
    def __str__(self):
        return self.nom or f"Arrêt {self.code}"

class Bus(models.Model):
    idbus = models.AutoField(primary_key=True, db_column='idbus')
    immatriculation = models.CharField(max_length=50, db_column='immatriculation', null=True, blank=True)
    modele = models.CharField(max_length=50, db_column='modele', null=True, blank=True)
    statut = models.CharField(max_length=30, db_column='statut', null=True, blank=True)
    kilometrage = models.FloatField(db_column='kilometrage', null=True, blank=True)
    geometry = models.PointField(srid=4326, db_column='geometry', null=True, blank=True)
    idligne = models.IntegerField(db_column='idligne', null=True, blank=True)
    
    class Meta:
        db_table = 'bus'    
        managed = False
        
    def __str__(self):
        return f"Bus {self.immatriculation} - Ligne {self.idligne}"
class DonneeTraffic(models.Model):
    iddonne = models.AutoField(primary_key=True, db_column='iddonne')
    timestamp = models.DateTimeField(db_column='timestamp', null=True, blank=True)
    vitesse = models.FloatField(db_column='vitesse', null=True, blank=True)
    nombrepassagers = models.IntegerField(db_column='nombrepassagers', null=True, blank=True)
    tauxoccupation = models.FloatField(db_column='tauxoccupation', null=True, blank=True)
    idbus = models.IntegerField(db_column='idbus', null=True, blank=True)
    idarret = models.IntegerField(db_column='idarret', null=True, blank=True)
    idcapteur = models.IntegerField(db_column='idcapteur', null=True, blank=True)

    class Meta:
        db_table = 'donneetrafic'
        managed = False

    def __str__(self):
        return f"Donnée traffic {self.iddonne} - Bus {self.idbus} à {self.timestamp}"