# simulate_bus_movement.py
import psycopg2
import random
import time
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'transport_intelligent.settings')
django.setup()

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def simulate_bus_movements():
    print("="*50)
    print("SIMULATION DES MOUVEMENTS DES BUS")
    print("="*50)
    
    channel_layer = get_channel_layer()
    print("✓ Channel layer initialisé")
    
    iteration = 0
    
    while True:
        try:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            # Connexion directe à PostgreSQL
            conn = psycopg2.connect(
                host="localhost",
                database="transport_intelligent",
                user="postgres",
                password="tibou1234"
            )
            cursor = conn.cursor()
            
            # Récupérer tous les bus
            cursor.execute("""
                SELECT idbus, immatriculation, modele, statut, 
                       ST_X(geometry) as lng, ST_Y(geometry) as lat, 
                       kilometrage, idligne
                FROM bus
                WHERE geometry IS NOT NULL
            """)
            
            buses = cursor.fetchall()
            
            if not buses:
                print("❌ Aucun bus trouvé avec des coordonnées!")
                print("Exécutez d'abord: python insert_buses_sql.py")
                cursor.close()
                conn.close()
                time.sleep(5)
                continue
            
            for bus in buses:
                idbus, immatriculation, modele, statut, lng, lat, kilometrage, idligne = bus
                
                if lng is None or lat is None:
                    continue
                
                # Déplacer le bus
                new_lng = lng + random.uniform(-0.0005, 0.0005)
                new_lat = lat + random.uniform(-0.0005, 0.0005)
                
                # Mettre à jour dans la base
                wkt = f'POINT({new_lng} {new_lat})'
                cursor.execute("""
                    UPDATE bus 
                    SET geometry = ST_GeomFromText(%s, 4326),
                        kilometrage = kilometrage + %s
                    WHERE idbus = %s
                """, (wkt, abs(new_lng - lng) * 1000, idbus))
                
                # Préparer les données WebSocket
                bus_data = {
                    'id': idbus,
                    'immatriculation': immatriculation,
                    'modele': modele,
                    'statut': statut,
                    'lng': new_lng,
                    'lat': new_lat,
                    'kilometrage': kilometrage,
                    'idligne': idligne
                }
                
                # Envoyer via WebSocket
                try:
                    async_to_sync(channel_layer.group_send)(
                        'dashboard_group',
                        {
                            'type': 'bus_update',
                            'bus': bus_data
                        }
                    )
                    print(f"  ✓ {immatriculation}: ({new_lng:.4f}, {new_lat:.4f}) - {statut}")
                except Exception as e:
                    print(f"  ✗ Erreur WebSocket: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n🛑 Simulation arrêtée")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")
            time.sleep(5)

if __name__ == '__main__':
    simulate_bus_movements()