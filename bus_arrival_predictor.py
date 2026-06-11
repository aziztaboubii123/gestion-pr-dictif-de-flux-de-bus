#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modèle de prédiction d'arrivée des bus avec XGBoost
Version COMPLÈTE avec prédiction sur TOUTES les lignes
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import joblib
import os
from datetime import datetime
import logging
import threading
import time
from db_connector import db_connector
from realtime_data_collector import data_collector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BusArrivalPredictor:
    """Prédicteur d'arrivée des bus avec XGBoost"""

    def __init__(self, dataset_path='data/raw/realtime_data.csv', model_type='xgboost'):
        self.dataset_path = dataset_path
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.encoder_weather = LabelEncoder()
        self.encoder_event = LabelEncoder()
        self.encoder_route = LabelEncoder()
        self.encoder_stop = LabelEncoder()
        self.feature_columns = None
        self.is_fitted = False
        self.last_training_time = None
        self.metrics = {}
        self.feature_importance = None
        self.training_lock = threading.Lock()
        self.training_in_progress = False
        self.encoders_fitted = False
        self.auto_train_enabled = True

        # Distances des arrêts (sera mis à jour depuis la base)
        self.routes_distances = {}

        # Retards
        self.weather_delays = {
            'clear': 0, 'cloudy': 3, 'rain': 10, 'fog': 15, 'storm': 25
        }
        self.event_delays = {
            'none': 0, 'festival': 15, 'match_sport': 20, 'manifestation': 30,
            'marathon': 35, 'foire': 18, 'congres': 12, 'greve_transport': 60, 'holiday': 10
        }

        # Créer les dossiers
        os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)
        os.makedirs('data/models', exist_ok=True)

        # Mettre à jour les distances depuis la base
        self.update_routes_distances_from_db()

        self._ensure_dataset_exists()
        self.start_continuous_training()

    # ============================================================
    # GESTION DES DISTANCES DEPUIS LA BASE
    # ============================================================

    def update_routes_distances_from_db(self):
        """Met à jour les distances des routes depuis la base de données"""
        try:
            db_distances = db_connector.build_routes_distances()
            if db_distances:
                self.routes_distances.update(db_distances)
                logger.info(f"✅ Distances mises à jour pour {len(db_distances)} lignes depuis la base")
                return True
        except Exception as e:
            logger.error(f"Erreur mise à jour distances: {e}")
        return False

    def calculate_distance(self, route_id, start_stop, end_stop):
        """Calcule la distance entre deux arrêts"""
        # Essayer d'abord depuis les distances chargées
        distances = self.routes_distances.get(route_id, {})
        start_dist = distances.get(start_stop, None)
        end_dist = distances.get(end_stop, None)

        if start_dist is not None and end_dist is not None:
            return max(0, end_dist - start_dist)

        # Sinon calculer via la base
        return db_connector.calculate_distance_between_stops(route_id, start_stop, end_stop)

    def get_all_route_stops(self, route_id):
        """Récupère tous les arrêts d'une ligne"""
        stops = db_connector.get_route_stops(route_id)
        return [s['nom'] for s in stops]

    # ============================================================
    # DATASET ET ENTRAÎNEMENT
    # ============================================================

    def _ensure_dataset_exists(self):
        if not os.path.exists(self.dataset_path):
            self._create_enhanced_dataset()

    def _create_enhanced_dataset(self):
        """Crée un dataset enrichi de 5000 échantillons"""
        np.random.seed(42)

        # Récupérer les vraies lignes depuis la base
        routes_from_db = db_connector.get_all_routes()
        route_ids = [r['route_id'] for r in routes_from_db]

        if not route_ids:
            route_ids = ['TUN-01', 'TUN-02', 'TUN-03']

        data = []

        for i in range(5000):
            route = np.random.choice(route_ids)

            # Récupérer les arrêts de cette ligne
            stops = self.get_all_route_stops(route)
            if len(stops) < 2:
                stops = ["Depart", "Arrivee"]

            start_idx = np.random.randint(0, len(stops) - 1)
            end_idx = np.random.randint(start_idx + 1, len(stops))
            start_stop = stops[start_idx]
            end_stop = stops[end_idx]

            speed = np.random.uniform(10, 60)

            weather = np.random.choice(
                list(self.weather_delays.keys()),
                p=[0.50, 0.25, 0.12, 0.08, 0.05]
            )

            traffic = np.random.uniform(10, 100)

            event = np.random.choice(
                list(self.event_delays.keys()),
                p=[0.65, 0.10, 0.07, 0.05, 0.04, 0.03, 0.03, 0.02, 0.01]
            )

            temp = np.random.uniform(8, 40)
            hour = np.random.randint(0, 24)
            day = np.random.randint(0, 7)
            month = np.random.randint(1, 13)

            distance = self.calculate_distance(route, start_stop, end_stop)
            if distance <= 0:
                distance = np.random.uniform(1, 15)

            theoretical = (distance / speed) * 60

            delay = self.weather_delays[weather]
            delay += (traffic / 100) * 30
            delay += self.event_delays[event]

            if (hour >= 7 and hour <= 9) or (hour >= 17 and hour <= 19):
                delay += 15
            elif (hour >= 12 and hour <= 14):
                delay += 8

            if speed < 20:
                delay += (20 - speed) * 1.2
            elif speed > 50:
                delay -= 3

            if temp > 35:
                delay += 8
            elif temp < 10:
                delay += 5

            if day >= 5:
                delay *= 0.8

            actual_time = theoretical + delay + np.random.normal(0, 3)
            actual_time = max(5, min(180, actual_time))

            data.append([
                datetime.now().isoformat(), route, start_stop, end_stop, speed,
                weather, traffic, event, temp, day, month, hour, actual_time, distance
            ])

        df = pd.DataFrame(data, columns=[
            'timestamp', 'route_id', 'start_stop', 'end_stop', 'current_speed_kmh',
            'weather', 'traffic_level', 'event', 'temperature',
            'day_of_week', 'month', 'hour', 'actual_time_min', 'distance_km'
        ])

        df.to_csv(self.dataset_path, index=False, encoding='utf-8')
        logger.info(f"📊 Dataset enrichi créé: {len(df)} échantillons")

    def load_dataset(self):
        try:
            if os.path.exists(self.dataset_path):
                df = pd.read_csv(self.dataset_path, on_bad_lines='skip')

                expected_columns = ['timestamp', 'route_id', 'start_stop', 'end_stop', 'current_speed_kmh',
                                    'weather', 'traffic_level', 'event', 'temperature',
                                    'day_of_week', 'month', 'hour', 'actual_time_min', 'distance_km']

                existing_columns = [col for col in expected_columns if col in df.columns]
                df = df[existing_columns]
                df = df.dropna()
                logger.info(f"📊 Dataset chargé: {len(df)} échantillons valides")
                return df
            else:
                logger.warning("⚠️ Dataset non trouvé")
                return None
        except Exception as e:
            logger.error(f"❌ Erreur chargement: {e}")
            try:
                os.remove(self.dataset_path)
            except:
                pass
            return None

    def _fit_encoders(self, df):
        try:
            self.encoder_weather.fit(df['weather'].unique())
            self.encoder_event.fit(df['event'].unique())
            self.encoder_route.fit(df['route_id'].unique())
            all_stops = pd.concat([df['start_stop'], df['end_stop']]).unique()
            self.encoder_stop.fit(all_stops)
            self.encoders_fitted = True
            logger.info("✅ Encodeurs entraînés")
        except Exception as e:
            logger.error(f"❌ Erreur encodeurs: {e}")

    def _safe_transform(self, encoder, values, default=None):
        try:
            return encoder.transform(values)
        except:
            if default:
                try:
                    return np.array([encoder.transform([default])[0]] * len(values))
                except:
                    pass
            return np.zeros(len(values))

    def preprocess_data(self, df, fit_encoders=True):
        df_processed = df.copy()
        df_processed = df_processed.dropna()

        if 'distance_km' not in df_processed.columns:
            df_processed['distance_km'] = df_processed.apply(
                lambda row: self.calculate_distance(row['route_id'], row['start_stop'], row['end_stop']), axis=1)

        df_processed['current_speed_kmh'] = df_processed['current_speed_kmh'].replace(0, 1)
        df_processed['theoretical_time'] = (df_processed['distance_km'] / df_processed['current_speed_kmh']) * 60
        df_processed['theoretical_time'] = df_processed['theoretical_time'].replace([np.inf, -np.inf], 60).fillna(60)

        # Features temporelles
        df_processed['hour_sin'] = np.sin(2 * np.pi * df_processed['hour'] / 24)
        df_processed['hour_cos'] = np.cos(2 * np.pi * df_processed['hour'] / 24)
        df_processed['day_sin'] = np.sin(2 * np.pi * df_processed['day_of_week'] / 7)
        df_processed['day_cos'] = np.cos(2 * np.pi * df_processed['day_of_week'] / 7)
        df_processed['month_sin'] = np.sin(2 * np.pi * df_processed['month'] / 12)
        df_processed['month_cos'] = np.cos(2 * np.pi * df_processed['month'] / 12)

        # Périodes
        df_processed['is_peak_hour'] = ((df_processed['hour'] >= 7) & (df_processed['hour'] <= 9)) | \
                                       ((df_processed['hour'] >= 17) & (df_processed['hour'] <= 19)).astype(int)
        df_processed['is_morning_peak'] = ((df_processed['hour'] >= 7) & (df_processed['hour'] <= 9)).astype(int)
        df_processed['is_evening_peak'] = ((df_processed['hour'] >= 17) & (df_processed['hour'] <= 19)).astype(int)
        df_processed['is_lunch_hour'] = ((df_processed['hour'] >= 12) & (df_processed['hour'] <= 14)).astype(int)
        df_processed['is_night'] = ((df_processed['hour'] >= 22) | (df_processed['hour'] <= 5)).astype(int)

        # Saisons
        df_processed['is_summer'] = df_processed['month'].isin([6, 7, 8, 9]).astype(int)
        df_processed['is_winter'] = df_processed['month'].isin([12, 1, 2]).astype(int)
        df_processed['is_spring'] = df_processed['month'].isin([3, 4, 5]).astype(int)
        df_processed['is_autumn'] = df_processed['month'].isin([9, 10, 11]).astype(int)

        df_processed['is_weekend'] = df_processed['day_of_week'].isin([5, 6]).astype(int)

        # Features dérivées
        df_processed['speed_squared'] = df_processed['current_speed_kmh'] ** 2
        df_processed['distance_speed_ratio'] = df_processed['distance_km'] / (df_processed['current_speed_kmh'] + 0.1)
        df_processed['traffic_speed_interaction'] = df_processed['traffic_level'] * df_processed['current_speed_kmh']

        if 'actual_time_min' in df_processed.columns:
            target = df_processed['actual_time_min']
        else:
            weather_delay = df_processed['weather'].map(self.weather_delays).fillna(0)
            traffic_delay = (df_processed['traffic_level'] / 100) * 30
            event_delay = df_processed['event'].map(self.event_delays).fillna(0)
            peak_delay = df_processed['is_peak_hour'] * 15
            speed_delay = np.maximum(0, (25 - df_processed['current_speed_kmh']) / 25 * 20)
            target = df_processed['theoretical_time'] + weather_delay + traffic_delay + event_delay + peak_delay + speed_delay

        target = target.replace([np.inf, -np.inf], np.nan)
        valid_mask = ~target.isna()
        df_processed = df_processed[valid_mask]
        target = target[valid_mask]
        target = target.clip(lower=5, upper=150)

        if len(df_processed) == 0:
            raise ValueError("Aucune donnée valide après nettoyage")

        if fit_encoders:
            self._fit_encoders(df_processed)

        if self.encoders_fitted:
            df_processed['weather_encoded'] = self._safe_transform(self.encoder_weather, df_processed['weather'], 'clear')
            df_processed['event_encoded'] = self._safe_transform(self.encoder_event, df_processed['event'], 'none')
            df_processed['route_encoded'] = self._safe_transform(self.encoder_route, df_processed['route_id'], 'TUN-01')
            df_processed['start_encoded'] = self._safe_transform(self.encoder_stop, df_processed['start_stop'], 'Depart')
            df_processed['end_encoded'] = self._safe_transform(self.encoder_stop, df_processed['end_stop'], 'Arrivee')
            df_processed['weather_temp'] = df_processed['weather_encoded'] * df_processed['temperature']
        else:
            df_processed['weather_encoded'] = 0
            df_processed['event_encoded'] = 0
            df_processed['route_encoded'] = 0
            df_processed['start_encoded'] = 0
            df_processed['end_encoded'] = 0
            df_processed['weather_temp'] = 0

        self.feature_columns = [
            'distance_km', 'current_speed_kmh', 'temperature', 'traffic_level',
            'hour_sin', 'hour_cos', 'day_sin', 'day_cos', 'month_sin', 'month_cos',
            'weather_encoded', 'event_encoded', 'route_encoded',
            'start_encoded', 'end_encoded',
            'is_peak_hour', 'is_morning_peak', 'is_evening_peak', 'is_lunch_hour', 'is_night',
            'is_summer', 'is_winter', 'is_spring', 'is_autumn',
            'is_weekend', 'speed_squared', 'distance_speed_ratio', 'traffic_speed_interaction', 'weather_temp'
        ]

        X = df_processed[self.feature_columns].values.astype(np.float32)
        y = target.values.astype(np.float32)

        if np.any(np.isnan(X)):
            valid_idx = ~np.isnan(X).any(axis=1)
            X = X[valid_idx]
            y = y[valid_idx]

        if fit_encoders:
            X = self.scaler.fit_transform(X)
        else:
            X = self.scaler.transform(X)

        logger.info(f"✅ Prétraitement terminé: {len(X)} échantillons")
        return X, y

    def _get_model(self):
        if self.model_type == 'xgboost':
            return xgb.XGBRegressor(
                n_estimators=300, max_depth=8, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                random_state=42, n_jobs=-1, verbosity=0, eval_metric='mae'
            )
        elif self.model_type == 'random_forest':
            return RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
        else:
            return GradientBoostingRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42)

    def train_model(self):
        with self.training_lock:
            if self.training_in_progress:
                return False
            self.training_in_progress = True
            logger.info(f"🔄 Auto-entraînement du modèle {self.model_type.upper()}...")
            try:
                df = self.load_dataset()
                if df is None or len(df) == 0:
                    self._create_enhanced_dataset()
                    df = self.load_dataset()

                if df is None or len(df) == 0:
                    return False

                X, y = self.preprocess_data(df, fit_encoders=True)

                if len(X) < 50:
                    self._create_enhanced_dataset()
                    df = self.load_dataset()
                    if df is not None and len(df) > 0:
                        X, y = self.preprocess_data(df, fit_encoders=True)
                    else:
                        return False

                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                self.model = self._get_model()

                try:
                    cv_scores = cross_val_score(self.model, X_train, y_train, cv=3, scoring='neg_mean_absolute_error')
                    cv_mae = -np.mean(cv_scores)
                    logger.info(f"📊 Cross-validation MAE: {cv_mae:.2f} min")
                except:
                    cv_mae = 0

                self.model.fit(X_train, y_train)
                self.is_fitted = True
                self.last_training_time = datetime.now()
                y_pred = self.model.predict(X_test)

                self.metrics = {
                    'mae': float(mean_absolute_error(y_test, y_pred)),
                    'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
                    'r2': float(r2_score(y_test, y_pred)),
                    'cv_mae': float(cv_mae),
                    'model_type': self.model_type,
                    'samples': len(df),
                    'valid_samples': len(X),
                    'features_count': len(self.feature_columns),
                    'last_training': self.last_training_time.isoformat()
                }

                accuracy = max(0, min(100, self.metrics['r2'] * 100))
                if self.metrics['mae'] < 3:
                    accuracy = min(100, accuracy + 10)
                elif self.metrics['mae'] > 10:
                    accuracy = max(0, accuracy - 10)
                self.metrics['accuracy_percentage'] = round(accuracy, 1)

                logger.info(f"✅ Entraînement terminé! MAE: {self.metrics['mae']:.2f} min, R²: {self.metrics['r2']:.3f}")
                self.save_model()
                return True
            except Exception as e:
                logger.error(f"❌ Erreur entraînement: {e}")
                return False
            finally:
                self.training_in_progress = False

    def start_continuous_training(self):
        def continuous_train_loop():
            time.sleep(10)
            self.train_model()

            while True:
                try:
                    time.sleep(30 * 60)
                    if self.auto_train_enabled:
                        self.update_routes_distances_from_db()
                        self.train_model()
                except Exception as e:
                    logger.error(f"Erreur thread: {e}")
                    time.sleep(60)

        training_thread = threading.Thread(target=continuous_train_loop, daemon=True)
        training_thread.start()
        logger.info("🚀 Auto-entraînement démarré (toutes les 30 minutes)")

    def calculate_delays(self, weather, traffic_level, event, hour, current_speed, temperature=22):
        weather_delay = self.weather_delays.get(weather, 0)
        traffic_delay = (traffic_level / 100) * 30
        event_delay = self.event_delays.get(event, 0)

        peak_hours = (hour >= 7 and hour <= 9) or (hour >= 17 and hour <= 19)
        peak_delay = 15 if peak_hours else 0

        if hour >= 22 or hour <= 5:
            peak_delay = -5

        speed_delay = max(0, (25 - current_speed) / 25 * 20) if current_speed > 0 else 20
        temp_delay = 8 if temperature > 35 else (5 if temperature < 10 else 0)

        total_delay = weather_delay + traffic_delay + event_delay + peak_delay + speed_delay + temp_delay

        return {
            'weather_delay': float(weather_delay),
            'traffic_delay': float(traffic_delay),
            'event_delay': float(event_delay),
            'peak_delay': float(peak_delay),
            'speed_delay': float(speed_delay),
            'temp_delay': float(temp_delay),
            'total_delay': float(max(0, total_delay))
        }

    def predict_arrival_time(self, route_id, start_stop, end_stop, current_speed,
                             weather, traffic_level, event, temperature,
                             day_of_week, month, hour):
        distance = self.calculate_distance(route_id, start_stop, end_stop)
        if distance <= 0:
            return {'error': 'Distance invalide'}

        theoretical_time = (distance / current_speed) * 60 if current_speed > 0 else distance * 3
        delays = self.calculate_delays(weather, traffic_level, event, hour, current_speed, temperature)

        if self.is_fitted and self.model is not None and self.encoders_fitted:
            try:
                df_input = pd.DataFrame({
                    'distance_km': [distance], 'current_speed_kmh': [current_speed],
                    'temperature': [temperature], 'traffic_level': [traffic_level],
                    'hour': [hour], 'day_of_week': [day_of_week], 'month': [month],
                    'weather': [weather], 'event': [event],
                    'route_id': [route_id], 'start_stop': [start_stop], 'end_stop': [end_stop]
                })

                df_input['hour_sin'] = np.sin(2 * np.pi * hour / 24)
                df_input['hour_cos'] = np.cos(2 * np.pi * hour / 24)
                df_input['day_sin'] = np.sin(2 * np.pi * day_of_week / 7)
                df_input['day_cos'] = np.cos(2 * np.pi * day_of_week / 7)
                df_input['month_sin'] = np.sin(2 * np.pi * month / 12)
                df_input['month_cos'] = np.cos(2 * np.pi * month / 12)

                df_input['is_peak_hour'] = 1 if ((hour >= 7 and hour <= 9) or (hour >= 17 and hour <= 19)) else 0
                df_input['is_morning_peak'] = 1 if (hour >= 7 and hour <= 9) else 0
                df_input['is_evening_peak'] = 1 if (hour >= 17 and hour <= 19) else 0
                df_input['is_lunch_hour'] = 1 if (hour >= 12 and hour <= 14) else 0
                df_input['is_night'] = 1 if (hour >= 22 or hour <= 5) else 0

                df_input['is_summer'] = 1 if month in [6, 7, 8, 9] else 0
                df_input['is_winter'] = 1 if month in [12, 1, 2] else 0
                df_input['is_spring'] = 1 if month in [3, 4, 5] else 0
                df_input['is_autumn'] = 1 if month in [9, 10, 11] else 0

                df_input['is_weekend'] = 1 if day_of_week in [5, 6] else 0
                df_input['speed_squared'] = current_speed ** 2
                df_input['distance_speed_ratio'] = distance / (current_speed + 0.1)
                df_input['traffic_speed_interaction'] = traffic_level * current_speed

                df_input['weather_encoded'] = self._safe_transform(self.encoder_weather, df_input['weather'], 'clear')
                df_input['event_encoded'] = self._safe_transform(self.encoder_event, df_input['event'], 'none')
                df_input['route_encoded'] = self._safe_transform(self.encoder_route, df_input['route_id'], 'TUN-01')
                df_input['start_encoded'] = self._safe_transform(self.encoder_stop, df_input['start_stop'], 'Depart')
                df_input['end_encoded'] = self._safe_transform(self.encoder_stop, df_input['end_stop'], 'Arrivee')
                df_input['weather_temp'] = df_input['weather_encoded'] * temperature

                X = df_input[self.feature_columns].values.astype(np.float32)
                X_scaled = self.scaler.transform(X)
                predicted_time = float(self.model.predict(X_scaled)[0])
            except Exception as e:
                logger.warning(f"Erreur prédiction: {e}")
                predicted_time = theoretical_time + delays['total_delay']
        else:
            predicted_time = theoretical_time + delays['total_delay']

        predicted_time = max(5, min(150, predicted_time))

        current_minute = datetime.now().minute
        current_time = hour + current_minute / 60
        arrival_time = current_time + predicted_time / 60
        arrival_hour = int(arrival_time) % 24
        arrival_minute = int((arrival_time - int(arrival_time)) * 60)

        if predicted_time - theoretical_time < 5:
            confidence = "Très élevée"
        elif predicted_time - theoretical_time < 10:
            confidence = "Élevée"
        elif predicted_time - theoretical_time < 20:
            confidence = "Moyenne"
        else:
            confidence = "Faible"

        return {
            'route_id': route_id,
            'start_stop': start_stop,
            'end_stop': end_stop,
            'distance_km': float(round(distance, 2)),
            'current_speed_kmh': float(round(current_speed, 1)),
            'theoretical_time_min': float(round(theoretical_time, 0)),
            'predicted_delay_min': float(round(max(0, predicted_time - theoretical_time), 0)),
            'predicted_total_time_min': float(round(predicted_time, 0)),
            'predicted_arrival_time': f"{arrival_hour:02d}:{arrival_minute:02d}",
            'delays_breakdown': delays,
            'confidence': confidence,
            'confidence_level': 'high' if confidence in ['Très élevée', 'Élevée'] else ('medium' if confidence == 'Moyenne' else 'low'),
            'model_used': self.model_type,
            'model_accuracy': self.metrics.get('accuracy_percentage', 70)
        }

    # ============================================================
    # PRÉDICTION SUR TOUTES LES LIGNES ET TOUS LES BUS
    # ============================================================

    def predict_for_all_routes(self):
        """Effectue des prédictions pour TOUTES les lignes de la base"""
        routes = db_connector.get_all_routes()
        if not routes:
            logger.warning("Aucune ligne trouvée dans la base")
            return []

        self.update_routes_distances_from_db()

        weather_data = data_collector.get_weather('tunis')
        events_data = data_collector.get_events('tunis')
        now = datetime.now()

        all_predictions = []

        for route in routes:
            route_id = route['route_id']
            stops = db_connector.get_route_stops(route_id)

            if len(stops) < 2:
                continue

            # Prendre le premier et dernier arrêt
            start_stop = stops[0]['nom']
            end_stop = stops[-1]['nom']

            traffic_data = data_collector.get_traffic(route_id)
            default_speed = traffic_data.get('current_speed', 30)

            prediction = self.predict_arrival_time(
                route_id=route_id,
                start_stop=start_stop,
                end_stop=end_stop,
                current_speed=default_speed,
                weather=weather_data['weather'],
                traffic_level=traffic_data['level'],
                event=events_data['event_type'],
                temperature=weather_data['temperature'],
                day_of_week=now.weekday(),
                month=now.month,
                hour=now.hour
            )

            if 'error' not in prediction:
                prediction['ligne_info'] = {
                    'idligne': route['idligne'],
                    'frequence': route['frequence'],
                    'longueur_km': route['longueur_km']
                }
                all_predictions.append(prediction)

        logger.info(f"📊 Prédictions générées pour {len(all_predictions)} lignes")
        return all_predictions

    def predict_for_active_buses(self):
        """Effectue des prédictions pour tous les bus actifs"""
        buses = db_connector.get_bus_positions()
        if not buses:
            logger.warning("Aucun bus actif trouvé")
            return []

        weather_data = data_collector.get_weather('tunis')
        events_data = data_collector.get_events('tunis')
        now = datetime.now()

        predictions = []
        routes_cache = {}

        for bus in buses:
            route_id = bus['route_id']
            if route_id == 'UNKNOWN':
                continue

            # Récupérer les arrêts de la ligne (avec cache)
            if route_id not in routes_cache:
                routes_cache[route_id] = db_connector.get_route_stops(route_id)

            stops = routes_cache[route_id]
            if len(stops) < 2:
                continue

            # Trouver l'arrêt le plus proche du bus
            nearest_stop = db_connector.find_nearest_stop(
                bus['latitude'], bus['longitude'], route_id
            )

            if nearest_stop:
                # Trouver l'arrêt suivant
                next_stop = db_connector.find_next_stop(nearest_stop['nom'], route_id)
                if not next_stop and len(stops) > 1:
                    next_stop = stops[1]

                end_stop = next_stop['nom'] if next_stop else stops[-1]['nom']
                start_stop = nearest_stop['nom']
            else:
                start_stop = stops[0]['nom']
                end_stop = stops[-1]['nom']

            traffic_data = data_collector.get_traffic(route_id)

            prediction = self.predict_arrival_time(
                route_id=route_id,
                start_stop=start_stop,
                end_stop=end_stop,
                current_speed=bus['current_speed'],
                weather=weather_data['weather'],
                traffic_level=traffic_data['level'],
                event=events_data['event_type'],
                temperature=weather_data['temperature'],
                day_of_week=now.weekday(),
                month=now.month,
                hour=now.hour
            )

            if 'error' not in prediction:
                prediction['bus_info'] = {
                    'bus_id': bus['bus_id'],
                    'immatriculation': bus['immatriculation'],
                    'latitude': bus['latitude'],
                    'longitude': bus['longitude'],
                    'current_speed': bus['current_speed']
                }
                predictions.append(prediction)

                # Sauvegarder en base
                db_connector.save_prediction(prediction, bus['bus_id'], nearest_stop['idarret'] if nearest_stop else None)

        logger.info(f"🚍 Prédictions générées pour {len(predictions)} bus")
        return predictions

    def get_all_predictions_summary(self):
        """Résumé des prédictions pour toutes les lignes et tous les bus"""
        return {
            'timestamp': datetime.now().isoformat(),
            'lines_predictions': self.predict_for_all_routes(),
            'buses_predictions': self.predict_for_active_buses(),
            'model_accuracy': self.metrics.get('accuracy_percentage', 70),
            'total_lines': len(db_connector.get_all_routes()),
            'total_active_buses': len(db_connector.get_active_buses())
        }

    def save_model(self, path='data/models/bus_arrival_model.pkl'):
        try:
            data = {
                'model': self.model, 'model_type': self.model_type, 'scaler': self.scaler,
                'encoder_weather': self.encoder_weather, 'encoder_event': self.encoder_event,
                'encoder_route': self.encoder_route, 'encoder_stop': self.encoder_stop,
                'feature_columns': self.feature_columns, 'is_fitted': self.is_fitted,
                'encoders_fitted': self.encoders_fitted, 'last_training_time': self.last_training_time,
                'metrics': self.metrics, 'feature_importance': self.feature_importance,
                'weather_delays': self.weather_delays, 'event_delays': self.event_delays,
                'routes_distances': self.routes_distances
            }
            joblib.dump(data, path)
            logger.info(f"✅ Modèle sauvegardé: {path}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")

    def load_model(self, path='data/models/bus_arrival_model.pkl'):
        try:
            if os.path.exists(path):
                data = joblib.load(path)
                self.model = data.get('model')
                self.model_type = data.get('model_type', 'xgboost')
                self.scaler = data.get('scaler', StandardScaler())
                self.encoder_weather = data.get('encoder_weather', LabelEncoder())
                self.encoder_event = data.get('encoder_event', LabelEncoder())
                self.encoder_route = data.get('encoder_route', LabelEncoder())
                self.encoder_stop = data.get('encoder_stop', LabelEncoder())
                self.feature_columns = data.get('feature_columns')
                self.is_fitted = data.get('is_fitted', False)
                self.encoders_fitted = data.get('encoders_fitted', False)
                self.last_training_time = data.get('last_training_time')
                self.metrics = data.get('metrics', {})
                self.weather_delays = data.get('weather_delays', self.weather_delays)
                self.event_delays = data.get('event_delays', self.event_delays)
                if data.get('routes_distances'):
                    self.routes_distances = data.get('routes_distances')
                if self.is_fitted:
                    logger.info(f"✅ Modèle chargé avec succès")
                return self.is_fitted
            return False
        except Exception as e:
            logger.error(f"Erreur chargement: {e}")
            return False

    def get_metrics(self):
        return self.metrics

    def get_accuracy_percentage(self):
        return self.metrics.get('accuracy_percentage', 0)

    def get_reliability_message(self):
        accuracy = self.get_accuracy_percentage()
        if accuracy >= 85:
            return "🟢 Excellente fiabilité - Modèle très précis"
        elif accuracy >= 75:
            return "🟢 Bonne fiabilité - Prédictions généralement justes"
        elif accuracy >= 60:
            return "🟡 Fiabilité moyenne - Prédictions à prendre avec précaution"
        else:
            return "🔴 Modèle en apprentissage - Revenez plus tard"