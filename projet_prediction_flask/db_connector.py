#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Connecteur vers la base de données PostgreSQL
Version CORRIGÉE avec gestion des transactions
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnector:
    """Gère la connexion et les requêtes vers PostgreSQL"""

    def __init__(self):
        self.connection = None
        self.distances_cache = {}
        self.stops_cache = {}
        self.connect()

    def connect(self):
        """Établit la connexion à PostgreSQL"""
        try:
            # Fermer l'ancienne connexion si elle existe
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            
            self.connection = psycopg2.connect(
                host=Config.DB_CONFIG['host'],
                port=Config.DB_CONFIG['port'],
                database=Config.DB_CONFIG['database'],
                user=Config.DB_CONFIG['user'],
                password=Config.DB_CONFIG['password']
            )
            # Auto-commit pour éviter les transactions bloquées
            self.connection.autocommit = True
            logger.info("✅ Connexion PostgreSQL établie avec succès")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur de connexion PostgreSQL: {e}")
            self.connection = None
            return False

    def _execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Exécute une requête SQL avec gestion d'erreur et reconnection"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.connection or self.connection.closed:
                    self.connect()
                
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params or ())
                    
                    if fetch_one:
                        result = cursor.fetchone()
                    elif fetch_all:
                        result = cursor.fetchall()
                    else:
                        result = None
                    
                    # Commit si nécessaire (même si autocommit est True)
                    if not self.connection.autocommit:
                        self.connection.commit()
                    
                    return result
                    
            except psycopg2.OperationalError as e:
                logger.warning(f"Erreur opérationnelle (tentative {attempt+1}/{max_retries}): {e}")
                self.connect()
                if attempt == max_retries - 1:
                    logger.error(f"Échec après {max_retries} tentatives")
                    return None
            except Exception as e:
                logger.error(f"Erreur requête: {e}")
                # Annuler la transaction en cours
                try:
                    self.connection.rollback()
                except:
                    pass
                return None
        
        return None

    # ============================================================
    # CALCUL DE DISTANCE (Haversine)
    # ============================================================

    def calculate_distance_haversine(self, lat1, lon1, lat2, lon2):
        """Calcule la distance en km entre deux points GPS"""
        R = 6371
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    # ============================================================
    # RÉCUPÉRATION DES LIGNES (CORRIGÉE)
    # ============================================================

    def get_all_routes(self):
        """Récupère TOUTES les lignes de bus de la base"""
        query = """
            SELECT 
                idligne,
                numero as route_id,
                frequence,
                ST_Length(geometry::geography) as longueur_km
            FROM ligne
            WHERE numero IS NOT NULL AND numero != ''
            ORDER BY numero
        """
        
        result = self._execute_query(query, fetch_all=True)
        
        if result is None:
            logger.warning("Aucune ligne trouvée ou erreur de connexion")
            return []
        
        routes = []
        for r in result:
            routes.append({
                'route_id': r['route_id'],
                'idligne': r['idligne'],
                'frequence': r['frequence'],
                'longueur_km': float(r['longueur_km']) if r['longueur_km'] else 0
            })
        
        logger.info(f"📋 {len(routes)} lignes récupérées depuis la base")
        return routes

    # ============================================================
    # RÉCUPÉRATION DES ARRÊTS (CORRIGÉE)
    # ============================================================

    def get_route_stops(self, route_id):
        """Récupère TOUS les arrêts d'une ligne avec leurs coordonnées"""
        if route_id in self.stops_cache:
            return self.stops_cache[route_id]

        query = """
            SELECT 
                a.idarret,
                a.nom,
                a.code,
                ST_X(a.geometry) as longitude,
                ST_Y(a.geometry) as latitude,
                a.idligne
            FROM arret a
            JOIN ligne l ON a.idligne = l.idligne
            WHERE l.numero = %s
            ORDER BY a.idarret
        """
        
        stops_data = self._execute_query(query, (route_id,), fetch_all=True)
        
        if stops_data is None:
            return []
        
        result = []
        for s in stops_data:
            if s['nom'] and s['longitude'] and s['latitude']:
                result.append({
                    'idarret': s['idarret'],
                    'nom': s['nom'],
                    'code': s['code'] or '',
                    'longitude': float(s['longitude']),
                    'latitude': float(s['latitude'])
                })

        self.stops_cache[route_id] = result
        logger.info(f"📍 {len(result)} arrêts pour la ligne {route_id}")
        return result

    # ============================================================
    # RÉCUPÉRATION DES BUS (CORRIGÉE)
    # ============================================================

    def get_active_buses(self):
        """Récupère tous les bus actifs avec leur position et ligne"""
        query = """
            SELECT 
                b.idbus,
                b.immatriculation,
                b.modele,
                b.statut,
                b.kilometrage,
                ST_X(b.geometry) as longitude,
                ST_Y(b.geometry) as latitude,
                b.idligne,
                l.numero as ligne_numero
            FROM bus b
            LEFT JOIN ligne l ON b.idligne = l.idligne
            WHERE (b.statut = 'en_service' OR b.statut IS NULL)
              AND b.geometry IS NOT NULL
        """
        
        buses = self._execute_query(query, fetch_all=True)
        
        if buses is None:
            logger.warning("Aucun bus trouvé")
            return []
        
        logger.info(f"🚌 {len(buses)} bus actifs récupérés")
        return buses

    def get_bus_speed(self, bus_id):
        """Récupère la vitesse actuelle d'un bus (km/h)"""
        query = """
            SELECT vitesse, timestamp
            FROM donneetrafic
            WHERE idbus = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        
        result = self._execute_query(query, (bus_id,), fetch_one=True)

        if result and result['vitesse']:
            return float(result['vitesse'])
        return 30

    def get_bus_positions(self):
        """Récupère toutes les positions des bus avec leurs vitesses"""
        buses = self.get_active_buses()
        if not buses:
            return []
        
        result = []
        for bus in buses:
            speed = self.get_bus_speed(bus['idbus'])
            if bus['latitude'] and bus['longitude']:
                result.append({
                    'bus_id': bus['idbus'],
                    'route_id': bus.get('ligne_numero') or 'UNKNOWN',
                    'latitude': float(bus['latitude']),
                    'longitude': float(bus['longitude']),
                    'current_speed': speed,
                    'status': bus.get('statut', 'en_service'),
                    'immatriculation': bus.get('immatriculation', ''),
                    'last_update': datetime.now().isoformat()
                })

        return result

    # ============================================================
    # CALCUL DES DISTANCES ENTRE ARRÊTS
    # ============================================================

    def calculate_distance_between_stops(self, route_id, start_stop_name, end_stop_name):
        """Calcule la distance entre deux arrêts d'une même ligne"""
        cache_key = f"{route_id}:{start_stop_name}:{end_stop_name}"

        if cache_key in self.distances_cache:
            return self.distances_cache[cache_key]

        stops = self.get_route_stops(route_id)
        if not stops:
            return 0

        start_stop = None
        end_stop = None

        for stop in stops:
            if stop['nom'] == start_stop_name:
                start_stop = stop
            if stop['nom'] == end_stop_name:
                end_stop = stop

        if not start_stop or not end_stop:
            return 0

        distance = self.calculate_distance_haversine(
            start_stop['latitude'], start_stop['longitude'],
            end_stop['latitude'], end_stop['longitude']
        )

        self.distances_cache[cache_key] = distance
        return distance

    def build_routes_distances(self):
        """Construit le dictionnaire complet des distances pour toutes les lignes"""
        routes = self.get_all_routes()
        routes_distances = {}

        for route in routes:
            route_id = route['route_id']
            stops = self.get_route_stops(route_id)

            if len(stops) >= 2:
                distances_dict = {}
                cumulative_distance = 0
                previous_stop = None

                for i, stop in enumerate(stops):
                    stop_name = stop['nom']

                    if i == 0:
                        distances_dict[stop_name] = 0
                    else:
                        dist = self.calculate_distance_between_stops(
                            route_id, previous_stop, stop_name
                        )
                        cumulative_distance += dist
                        distances_dict[stop_name] = cumulative_distance

                    previous_stop = stop_name

                routes_distances[route_id] = distances_dict
                logger.info(f"📏 Ligne {route_id}: {len(distances_dict)} arrêts, {cumulative_distance:.2f} km")

        return routes_distances

    # ============================================================
    # ARRÊT LE PLUS PROCHE
    # ============================================================

    def find_nearest_stop(self, latitude, longitude, route_id):
        """Trouve l'arrêt le plus proche d'un bus sur sa ligne"""
        stops = self.get_route_stops(route_id)
        if not stops:
            return None

        min_distance = float('inf')
        nearest_stop = None

        for stop in stops:
            dist = self.calculate_distance_haversine(
                latitude, longitude,
                stop['latitude'], stop['longitude']
            )
            if dist < min_distance:
                min_distance = dist
                nearest_stop = stop

        if nearest_stop:
            logger.info(f"📍 Bus à {min_distance:.2f} km de l'arrêt {nearest_stop['nom']}")
            return nearest_stop
        return None

    def find_next_stop(self, current_stop_name, route_id):
        """Trouve l'arrêt suivant sur la ligne"""
        stops = self.get_route_stops(route_id)
        if not stops:
            return None

        stop_names = [s['nom'] for s in stops]
        try:
            current_index = stop_names.index(current_stop_name)
            if current_index + 1 < len(stop_names):
                return stops[current_index + 1]
        except ValueError:
            pass
        return stops[0] if stops else None

    # ============================================================
    # SAUVEGARDE DES PRÉDICTIONS
    # ============================================================

    def save_prediction(self, prediction_data, bus_id=None, arret_id=None):
        """Enregistre une prédiction dans la base de données"""
        query = """
            INSERT INTO prediction (
                typeprediction, valeur, timestamp, 
                intervalleconfiance, idmodele, idarret
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        self._execute_query(query, (
            'arrivee_bus',
            prediction_data.get('predicted_total_time_min', 0),
            datetime.now(),
            prediction_data.get('confidence_interval', 5),
            1,
            arret_id
        ))
        
        logger.info(f"💾 Prédiction enregistrée (bus: {bus_id})")
        return True

    def save_batch_predictions(self, predictions):
        """Enregistre plusieurs prédictions en batch"""
        count = 0
        for pred in predictions:
            if self.save_prediction(pred, pred.get('bus_id'), pred.get('arret_id')):
                count += 1
        logger.info(f"💾 {count} prédictions enregistrées en batch")
        return count

    def close(self):
        """Ferme la connexion"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Connexion PostgreSQL fermée")
            except:
                pass


db_connector = DatabaseConnector()