#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API REST avec auto-entraînement continu
Prédiction sur TOUTES les lignes de la base
"""

import os
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

from bus_arrival_predictor import BusArrivalPredictor
from realtime_data_collector import data_collector
from db_connector import db_connector

app = Flask(__name__)
CORS(app)

# Initialiser le prédicteur
predictor = BusArrivalPredictor(model_type='xgboost')

# Charger le modèle
if not predictor.load_model():
    print("🚀 Création et entraînement initial du modèle...")
    predictor.train_model()
else:
    print("✅ Modèle XGBoost chargé avec succès")

# Mettre à jour les distances depuis la base
predictor.update_routes_distances_from_db()


# ============================================================
# ROUTES PRINCIPALES
# ============================================================

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Bus Arrival Prediction API',
        'version': '3.0',
        'endpoints': [
            '/api/predict',
            '/api/predict/realtime',
            '/api/predict/all-lines',
            '/api/predict/all-buses',
            '/api/predict/summary',
            '/api/realtime',
            '/api/metrics',
            '/api/routes',
            '/api/routes/<route_id>/stops',
            '/api/buses/active',
            '/api/status',
            '/api/model/accuracy'
        ]
    })


# ============================================================
# PRÉDICTIONS
# ============================================================

@app.route('/api/predict', methods=['POST'])
def predict():
    """Prédiction sur mesure avec paramètres fournis"""
    try:
        data = request.json
        result = predictor.predict_arrival_time(
            route_id=data['route_id'],
            start_stop=data['start_stop'],
            end_stop=data['end_stop'],
            current_speed=float(data.get('speed', 25)),
            weather=data.get('weather', 'clear'),
            traffic_level=float(data.get('traffic', 45)),
            event=data.get('event', 'none'),
            temperature=float(data.get('temperature', 22)),
            day_of_week=int(data.get('day_of_week', datetime.now().weekday())),
            month=int(data.get('month', datetime.now().month)),
            hour=int(data.get('hour', datetime.now().hour))
        )

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        def convert_to_native(obj):
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(i) for i in obj]
            elif isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            else:
                return obj

        result = convert_to_native(result)
        db_connector.save_prediction(result)

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predict/realtime', methods=['GET'])
def predict_realtime():
    """Prédiction avec données temps réel (météo, trafic)"""
    try:
        route_id = request.args.get('route', 'TUN-01')
        start_stop = request.args.get('start', None)
        end_stop = request.args.get('end', None)
        speed = float(request.args.get('speed', 30))

        weather = data_collector.get_weather('tunis')
        traffic = data_collector.get_traffic(route_id)
        events = data_collector.get_events('tunis')
        now = datetime.now()

        # Si pas d'arrêts spécifiés, prendre premier et dernier
        if not start_stop or not end_stop:
            stops = db_connector.get_route_stops(route_id)
            if stops and len(stops) >= 2:
                start_stop = stops[0]['nom']
                end_stop = stops[-1]['nom']
            else:
                start_stop = "Place Barcelone"
                end_stop = "Ariana Terminus"

        result = predictor.predict_arrival_time(
            route_id=route_id,
            start_stop=start_stop,
            end_stop=end_stop,
            current_speed=speed,
            weather=weather['weather'],
            traffic_level=traffic['level'],
            event=events['event_type'],
            temperature=weather['temperature'],
            day_of_week=now.weekday(),
            month=now.month,
            hour=now.hour
        )

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        result['weather_data'] = {
            'condition': weather['weather'],
            'temperature': weather['temperature'],
            'humidity': weather.get('humidity')
        }
        result['traffic_data'] = {
            'level': traffic['level'],
            'source': traffic.get('source')
        }

        db_connector.save_prediction(result)

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predict/all-lines', methods=['GET'])
def predict_all_lines():
    """Prédiction pour TOUTES les lignes de la base"""
    try:
        predictions = predictor.predict_for_all_routes()
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predict/all-buses', methods=['GET'])
def predict_all_buses():
    """Prédiction pour tous les bus actifs"""
    try:
        predictions = predictor.predict_for_active_buses()
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predict/summary', methods=['GET'])
def predict_summary():
    """Résumé complet des prédictions (lignes + bus)"""
    try:
        summary = predictor.get_all_predictions_summary()
        return jsonify({
            'success': True,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# DONNÉES TEMPS RÉEL
# ============================================================

@app.route('/api/realtime', methods=['GET'])
def get_realtime_data():
    """Récupère les données temps réel (météo, trafic, événements)"""
    try:
        route_id = request.args.get('route', 'TUN-01')
        city = request.args.get('city', 'tunis')

        weather = data_collector.get_weather(city)
        traffic = data_collector.get_traffic(route_id)
        events = data_collector.get_events(city)

        return jsonify({
            'success': True,
            'weather': weather,
            'traffic': traffic,
            'events': events,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# MÉTRIQUES ET STATUT
# ============================================================

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    return jsonify({
        'success': True,
        'metrics': predictor.get_metrics(),
        'is_fitted': predictor.is_fitted,
        'model_type': predictor.model_type,
        'last_training': predictor.last_training_time.isoformat() if predictor.last_training_time else None
    })


@app.route('/api/status', methods=['GET'])
def status():
    routes = db_connector.get_all_routes()
    buses = db_connector.get_active_buses()

    return jsonify({
        'success': True,
        'status': 'online',
        'model_ready': predictor.is_fitted,
        'model_type': predictor.model_type,
        'db_connected': db_connector.connection is not None,
        'total_routes': len(routes),
        'total_active_buses': len(buses),
        'metrics': predictor.get_metrics(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/model/accuracy', methods=['GET'])
def get_model_accuracy():
    return jsonify({
        'success': True,
        'accuracy_percentage': predictor.get_accuracy_percentage(),
        'reliability_message': predictor.get_reliability_message(),
        'metrics': predictor.get_metrics()
    })


# ============================================================
# DONNÉES DE LA BASE (LIGNES, ARRÊTS, BUS)
# ============================================================

@app.route('/api/routes', methods=['GET'])
def get_routes():
    """Récupère TOUTES les lignes depuis la base"""
    routes = db_connector.get_all_routes()
    return jsonify({
        'success': True,
        'routes': routes,
        'count': len(routes),
        'source': 'database'
    })


@app.route('/api/routes/<route_id>/stops', methods=['GET'])
def get_stops(route_id):
    """Récupère les arrêts d'une ligne"""
    stops = db_connector.get_route_stops(route_id)
    return jsonify({
        'success': True,
        'route_id': route_id,
        'stops': stops,
        'count': len(stops),
        'source': 'database'
    })


@app.route('/api/buses/active', methods=['GET'])
def get_active_buses():
    """Récupère tous les bus actifs avec leurs positions"""
    try:
        buses = db_connector.get_bus_positions()
        return jsonify({
            'success': True,
            'buses': buses,
            'count': len(buses),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'db': 'connected' if db_connector.connection else 'disconnected',
        'model': 'loaded' if predictor.is_fitted else 'not_loaded'
    })


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚍 API DE PRÉDICTION - VERSION COMPLÈTE")
    print("=" * 70)
    print("✅ Auto-entraînement toutes les 30 minutes")
    print(f"✅ Modèle: {predictor.model_type.upper()}")
    print(f"✅ Prêt: {predictor.is_fitted}")
    print(f"✅ Base PostgreSQL: {'Connectée' if db_connector.connection else 'Déconnectée'}")

    # Afficher les lignes trouvées
    routes = db_connector.get_all_routes()
    print(f"✅ Lignes trouvées: {len(routes)}")
    for r in routes[:5]:
        print(f"   - {r['route_id']} ({r.get('longueur_km', 0):.1f} km)")

    buses = db_connector.get_active_buses()
    print(f"✅ Bus actifs: {len(buses)}")

    if predictor.metrics:
        print(f"📊 MAE: {predictor.metrics.get('mae', 0):.2f} min")
        print(f"📊 R²: {predictor.metrics.get('r2', 0):.3f}")
        print(f"📊 Précision: {predictor.metrics.get('accuracy_percentage', 0):.1f}%")

    print("\n🌐 API disponible sur: http://localhost:5001")
    print("=" * 70 + "\n")

    app.run(debug=False, host='0.0.0.0', port=5001)