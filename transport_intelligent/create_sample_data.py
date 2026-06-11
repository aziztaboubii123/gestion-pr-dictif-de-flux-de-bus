# insert_buses_sql.py
import psycopg2
import random

def insert_buses():
    print("="*50)
    print("INSERTION DES BUS (SANS GDAL)")
    print("="*50)
    
    # Connexion à PostgreSQL
    conn = psycopg2.connect(
        host="localhost",
        database="transport_intelligent",
        user="postgres",
        password="tibou1234"
    )
    cursor = conn.cursor()
    
    # 1. Vérifier les lignes existantes
    cursor.execute("SELECT idligne, numero FROM ligne")
    lignes = cursor.fetchall()
    
    if not lignes:
        print("❌ Aucune ligne trouvée dans la table 'ligne'")
        print("\nCréez d'abord des lignes dans votre base PostgreSQL")
        cursor.close()
        conn.close()
        return
    
    print(f"\n✓ Lignes trouvées: {len(lignes)}")
    for ligne in lignes:
        print(f"   - Ligne {ligne[1]} (ID: {ligne[0]})")
    
    # 2. Compter les bus existants
    cursor.execute("SELECT COUNT(*) FROM bus")
    count_before = cursor.fetchone()[0]
    print(f"\n✓ Bus existants: {count_before}")
    
    # 3. Supprimer les anciens bus (optionnel)
    # cursor.execute("DELETE FROM bus")
    # print("✓ Anciens bus supprimés")
    
    # 4. Coordonnées autour de Tunis
    positions = [
        (10.1815, 36.8065, "Centre Tunis"),
        (10.1650, 36.8020, "Bab Saadoun"),
        (10.1900, 36.8600, "Ariana"),
        (10.2300, 36.8500, "Carthage"),
        (10.2500, 36.8700, "Sidi Bou Said"),
        (10.2100, 36.8180, "La Goulette"),
        (10.1760, 36.7994, "Place Barcelone"),
        (10.1550, 36.8100, "Cité El Khadra"),
    ]
    
    modeles = ['Iveco Urbanway', 'MAN Lion\'s City', 'Mercedes Citaro', 'Solaris Urbino']
    statuts = ['en_service', 'en_service', 'en_service', 'en_service', 'incendie']
    
    # 5. Insérer des bus
    bus_inseres = 0
    for i in range(1, 11):
        ligne = random.choice(lignes)
        lng, lat, lieu = random.choice(positions)
        
        # Ajouter une variation
        lng += random.uniform(-0.008, 0.008)
        lat += random.uniform(-0.008, 0.008)
        
        immatriculation = f'BUS-{i:03d}'
        modele = random.choice(modeles)
        statut = random.choice(statuts)
        kilometrage = random.randint(5000, 150000)
        idligne = ligne[0]
        
        # Créer la géométrie en WKT
        wkt_geometry = f'POINT({lng} {lat})'
        
        # Vérifier si le bus existe déjà
        cursor.execute("SELECT idbus FROM bus WHERE immatriculation = %s", (immatriculation,))
        exists = cursor.fetchone()
        
        if exists:
            # Mettre à jour
            cursor.execute("""
                UPDATE bus 
                SET modele = %s, statut = %s, kilometrage = %s, 
                    geometry = ST_GeomFromText(%s, 4326), idligne = %s
                WHERE immatriculation = %s
            """, (modele, statut, kilometrage, wkt_geometry, idligne, immatriculation))
            print(f"  🔄 {immatriculation} - mis à jour")
        else:
            # Insérer
            cursor.execute("""
                INSERT INTO bus (immatriculation, modele, statut, kilometrage, geometry, idligne)
                VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s)
            """, (immatriculation, modele, statut, kilometrage, wkt_geometry, idligne))
            bus_inseres += 1
            print(f"  ✅ {immatriculation} - Ligne {ligne[1]} - {lieu} - {statut}")
    
    # 6. Valider
    conn.commit()
    
    # 7. Vérifier le résultat
    cursor.execute("SELECT COUNT(*) FROM bus")
    count_after = cursor.fetchone()[0]
    
    print(f"\n{'='*50}")
    print(f"RÉSULTAT")
    print(f"{'='*50}")
    print(f"✓ Nouveaux bus insérés: {bus_inseres}")
    print(f"✓ Total des bus: {count_after}")
    
    # 8. Afficher les bus avec leurs positions
    print(f"\n📋 Liste des bus:")
    cursor.execute("""
        SELECT b.immatriculation, b.statut, l.numero, ST_X(b.geometry), ST_Y(b.geometry)
        FROM bus b
        LEFT JOIN ligne l ON b.idligne = l.idligne
        LIMIT 10
    """)
    
    for bus in cursor.fetchall():
        statut_icon = "🔥" if bus[1] == "incendie" else "✅"
        print(f"  {statut_icon} {bus[0]} - Ligne {bus[2]} - ({bus[3]:.4f}, {bus[4]:.4f})")
    
    cursor.close()
    conn.close()
    
    print(f"\n✅ Terminé!")

if __name__ == '__main__':
    insert_buses()