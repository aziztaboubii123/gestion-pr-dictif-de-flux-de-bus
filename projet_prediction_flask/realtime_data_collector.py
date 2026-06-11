#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Collecteur de données en temps réel depuis APIs
"""

import requests
import numpy as np
from datetime import datetime
import time
import logging
import os
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeDataCollector:
    """Collecte des données en temps réel depuis APIs"""

    def __init__(self):
        self.openweather_key = Config.OPENWEATHER_KEY
        self.tomtom_key = Config.TOMTOM_KEY
        
        self.weather_url = "https://api.openweathermap.org/data/2.5/weather"
        self.tomtom_traffic_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        
        self.cities = {
            "tunis": {"lat": 36.8065, "lon": 10.1815},
            "ariana": {"lat": 36.8250, "lon": 10.1500},
            "mourouj": {"lat": 36.7400, "lon": 10.2000},
            "la_marsa": {"lat": 36.8750, "lon": 10.2100},
        }
        
        self.traffic_points = {
            "TUN-01": {"lat": 36.8120, "lon": 10.1650},
            "TUN-02": {"lat": 36.7700, "lon": 10.1920},
            "TUN-03": {"lat": 36.8450, "lon": 10.1950}
        }
        
        self.cache = {}
        self.cache_duration = 300
        
        os.makedirs('data/raw', exist_ok=True)
    
    def get_weather(self, city="tunis", use_cache=True):
        """Récupère la météo depuis OpenWeatherMap ou simulation"""
        cache_key = f"weather_{city}"
        
        if use_cache and cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return cache_data
        
        try:
            if self.openweather_key and self.openweather_key != "621c2a4729dd45e3d3ba314c130eb1c8":
                params = {
                    'lat': self.cities[city]["lat"],
                    'lon': self.cities[city]["lon"],
                    'appid': self.openweather_key,
                    'units': 'metric',
                    'lang': 'fr'
                }
                response = requests.get(self.weather_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                result = {
                    'city': city,
                    'temperature': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'weather': self._translate_weather(data['weather'][0]['main']),
                    'description': data['weather'][0]['description'],
                    'wind_speed': data['wind']['speed'],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'OpenWeatherMap'
                }
                logger.info(f"🌤️ Météo: {result['weather']}, {result['temperature']}°C")
            else:
                result = self._simulate_weather(city)
            
            self.cache[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            logger.error(f"❌ Erreur météo: {e}")
            return self._simulate_weather(city)
    
    def _translate_weather(self, weather_code):
        translation = {
            'Clear': 'clear', 'Clouds': 'cloudy', 'Rain': 'rain',
            'Drizzle': 'rain', 'Thunderstorm': 'storm', 'Snow': 'rain',
            'Mist': 'fog', 'Fog': 'fog'
        }
        return translation.get(weather_code, 'clear')
    
    def _simulate_weather(self, city):
        hour = datetime.now().hour
        month = datetime.now().month
        
        if month in [6, 7, 8, 9]:
            base_temp = 30
            weather_probs = [0.7, 0.2, 0.05, 0.03, 0.02]
        elif month in [12, 1, 2]:
            base_temp = 15
            weather_probs = [0.4, 0.3, 0.15, 0.1, 0.05]
        else:
            base_temp = 22
            weather_probs = [0.5, 0.3, 0.1, 0.07, 0.03]
        
        weather_types = ['clear', 'cloudy', 'rain', 'fog', 'storm']
        weather = np.random.choice(weather_types, p=weather_probs)
        temp_variation = np.sin((hour - 14) * np.pi / 12) * 5
        temperature = base_temp + temp_variation + np.random.uniform(-2, 2)
        
        return {
            'city': city,
            'temperature': round(temperature, 1),
            'humidity': np.random.randint(40, 90),
            'weather': weather,
            'description': f"Météo {weather}",
            'wind_speed': round(np.random.uniform(0, 30), 1),
            'timestamp': datetime.now().isoformat(),
            'source': 'simulation'
        }
    
    def get_traffic(self, route_id="TUN-01", use_cache=True):
        """Récupère le niveau de trafic"""
        cache_key = f"traffic_{route_id}"
        
        if use_cache and cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return cache_data
        
        try:
            if self.tomtom_key and self.tomtom_key != "H5IueqtPC5bRcXo8zXOb7oqlLscRk0Vu":
                point = self.traffic_points.get(route_id, self.traffic_points["TUN-01"])
                params = {
                    'key': self.tomtom_key,
                    'point': f"{point['lat']},{point['lon']}",
                    'unit': 'KMPH'
                }
                response = requests.get(self.tomtom_traffic_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'flowSegmentData' in data:
                    flow = data['flowSegmentData']
                    current_speed = flow.get('currentSpeed', 30)
                    free_flow_speed = flow.get('freeFlowSpeed', 50)
                    
                    if free_flow_speed > 0:
                        traffic_level = (1 - current_speed / free_flow_speed) * 100
                        traffic_level = min(100, max(0, traffic_level))
                    else:
                        traffic_level = 50
                    
                    result = {
                        'level': round(traffic_level, 1),
                        'current_speed': current_speed,
                        'route_id': route_id,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'TomTom'
                    }
                    logger.info(f"🚗 Trafic {route_id}: {traffic_level:.0f}%")
                else:
                    result = self._simulate_traffic(route_id)
            else:
                result = self._simulate_traffic(route_id)
            
            self.cache[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            logger.error(f"❌ Erreur trafic: {e}")
            return self._simulate_traffic(route_id)
    
    def _simulate_traffic(self, route_id="TUN-01"):
        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()
        
        if (7 <= hour <= 9) or (17 <= hour <= 19):
            base_traffic = 75
        elif (12 <= hour <= 14):
            base_traffic = 55
        else:
            base_traffic = 35
        
        if day_of_week >= 5:
            base_traffic *= 0.7
        
        # Variation par ligne
        route_hash = hash(route_id) % 100 / 100.0
        traffic = min(100, max(0, base_traffic + np.random.randint(-15, 15) + (route_hash - 0.5) * 20))
        
        return {
            'level': round(traffic, 1),
            'route_id': route_id,
            'timestamp': datetime.now().isoformat(),
            'source': 'simulation'
        }
    
    def get_events(self, city="tunis"):
        """Récupère les événements spéciaux"""
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        
        events_db = {
            'tunis': [
                {'name': 'Festival Carthage', 'date_start': '2025-07-01', 'date_end': '2025-08-15', 'type': 'festival', 'impact': 15},
                {'name': 'Match Espérance - Club Africain', 'date_start': '2025-04-20', 'date_end': '2025-04-20', 'type': 'match_sport', 'impact': 25},
                {'name': 'Marathon de Tunis', 'date_start': '2025-05-01', 'date_end': '2025-05-01', 'type': 'marathon', 'impact': 35},
            ],
        }
        
        events_today = []
        total_impact = 0
        
        for event in events_db.get(city, []):
            if event['date_start'] <= current_date <= event['date_end']:
                events_today.append(event)
                total_impact += event['impact']
        
        event_type = 'none'
        if events_today:
            event_type = events_today[0]['type']
        
        return {
            'city': city,
            'events': events_today,
            'event_type': event_type,
            'impact': total_impact,
            'timestamp': now.isoformat(),
            'source': 'local_db'
        }


data_collector = RealtimeDataCollector()