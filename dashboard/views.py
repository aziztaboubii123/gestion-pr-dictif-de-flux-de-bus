import json
from django.shortcuts import render
from django.db import connection
from .models import Ligne, Arret, Bus

def get_last_speeds():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT ON (idbus) idbus, vitesse
            FROM donneetrafic
            ORDER BY idbus, timestamp DESC
        """)
        rows = cursor.fetchall()
        print(f"SQL retourne {len(rows)} lignes")  # Vérification
        return {row[0]: row[1] for row in rows}

def home(request):
    # ============================================================
    # 1. RÉCUPÉRATION DES LIGNES
    # ============================================================
    lignes = Ligne.objects.all()
    lignes_geojson = {"type": "FeatureCollection", "features": []}
    for ligne in lignes:
        coords = []
        if ligne.geometry:
            coords = list(ligne.geometry.coords)
        else:
            coords = [[10.1815, 36.8065], [10.1815, 36.8065]]
        lignes_geojson["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"idligne": str(ligne.idligne), "numero": str(ligne.numero)}
        })

    # ============================================================
    # 2. RÉCUPÉRATION DES ARRÊTS
    # ============================================================
    arrets = Arret.objects.all()
    arrets_geojson = {"type": "FeatureCollection", "features": []}
    for arret in arrets:
        if arret.geometry:
            arrets_geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [arret.geometry.x, arret.geometry.y]},
                "properties": {
                    "idarret": arret.idarret,
                    "nom": arret.nom,
                    "code": arret.code,
                    "idligne": arret.idligne,
                    "ordre": getattr(arret, 'ordre', arret.idarret),
                    "lat": arret.geometry.y,
                    "lng": arret.geometry.x
                }
            })

    # ============================================================
    # 3. RÉCUPÉRATION DES BUS AVEC LEUR DERNIÈRE VITESSE
    # ============================================================
    # Récupération du dictionnaire des vitesses
    try:
        last_speeds = get_last_speeds()
    except Exception as e:
        print(f"Erreur lecture des vitesses: {e}")
        last_speeds = {}

    bus_geojson = {"type": "FeatureCollection", "features": []}
    for bus in Bus.objects.all():
        if bus.geometry:
            vitesse = last_speeds.get(bus.idbus, 30)  # 30 par défaut
            bus_geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [bus.geometry.x, bus.geometry.y]},
                "properties": {
                    "idBus": bus.idbus,
                    "immatriculation": bus.immatriculation,
                    "modele": bus.modele,
                    "statut": bus.statut,
                    "kilometrage": bus.kilometrage,
                    "idLigne": str(bus.idligne) if bus.idligne else "",
                    "vitesse": vitesse
                }
            })

    context = {
        "lignes_geojson": json.dumps(lignes_geojson),
        "arrets_geojson": json.dumps(arrets_geojson),
        "bus_geojson": json.dumps(bus_geojson)
    }
    return render(request, "dashboard/dashboard.html", context)