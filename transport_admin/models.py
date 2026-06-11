from django.db import models

class Alerte(models.Model):
    class Meta:
        db_table = 'alerte'
        managed = False
    
    idalerte = models.AutoField(primary_key=True, db_column='idalerte')
    message = models.CharField(max_length=500, db_column='message')
    niveau = models.CharField(max_length=50, db_column='niveau')
    dateemmision = models.DateTimeField(db_column='dateemmision')

class Arret(models.Model):
    class Meta:
        db_table = 'arret'
        managed = False
    
    idarret = models.AutoField(primary_key=True, db_column='idarret')
    nom = models.CharField(max_length=100, db_column='nom')
    code = models.CharField(max_length=50, db_column='code')
    geometry = models.TextField(blank=True, null=True, db_column='geometry')
    idligne = models.IntegerField(db_column='idligne')

class Bus(models.Model):
    class Meta:
        db_table = 'bus'
        managed = False
    
    idbus = models.AutoField(primary_key=True, db_column='idbus')
    immatriculation = models.CharField(max_length=50, db_column='immatriculation')
    modele = models.CharField(max_length=100, db_column='modele')
    statut = models.CharField(max_length=50, db_column='statut')
    kilometrage = models.FloatField(default=0, db_column='kilometrage')
    geometry = models.TextField(blank=True, null=True, db_column='geometry')
    idligne = models.IntegerField(db_column='idligne')

class Capteur(models.Model):
    class Meta:
        db_table = 'capteur'
        managed = False
    
    idcapteur = models.AutoField(primary_key=True, db_column='idcapteur')
    type = models.CharField(max_length=50, db_column='type')
    statut = models.CharField(max_length=50, db_column='statut')
    idbus = models.IntegerField(db_column='idbus')

class DonneTrafic(models.Model):
    class Meta:
        db_table = 'donnetrafic'
        managed = False
    
    iddonne = models.AutoField(primary_key=True, db_column='iddonne')
    timestamp = models.DateTimeField(db_column='timestamp')
    vitesse = models.FloatField(default=0, db_column='vitesse')
    nombrepassager = models.IntegerField(default=0, db_column='nombrepassager')
    tauxoccupation = models.FloatField(default=0, db_column='tauxoccupation')
    idbus = models.IntegerField(db_column='idbus')
    idarret = models.IntegerField(blank=True, null=True, db_column='idarret')
    idcapteur = models.IntegerField(blank=True, null=True, db_column='idcapteur')

class Ligne(models.Model):
    class Meta:
        db_table = 'ligne'
        managed = False
    
    idligne = models.AutoField(primary_key=True, db_column='idligne')
    numero = models.CharField(max_length=50, db_column='numero')
    frequence = models.IntegerField(default=0, db_column='frequence')
    geometry = models.TextField(blank=True, null=True, db_column='geometry')

class Prediction(models.Model):
    class Meta:
        db_table = 'predection'
        managed = False
    
    idprediction = models.AutoField(primary_key=True, db_column='idprediction')
    typeprediction = models.CharField(max_length=50, db_column='typeprediction')
    valeur = models.FloatField(db_column='valeur')
    timestamp = models.DateTimeField(db_column='timestamp')
    intervalleconfiance = models.FloatField(default=0, db_column='intervalleconfiance')
    idmodele = models.IntegerField(db_column='idmodele')
    idarret = models.IntegerField(db_column='idarret')