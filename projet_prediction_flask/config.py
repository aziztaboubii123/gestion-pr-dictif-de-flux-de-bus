#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration centralisée - À MODIFIER AVEC VOS VALEURS
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ============================================================
    # BASE DE DONNÉES POSTGRESQL
    # ============================================================
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'transport_intelligent'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'tibou1234'),
    }
    
    # ============================================================
    # CLÉS API
    # ============================================================
    OPENWEATHER_KEY = os.getenv('OPENWEATHER_KEY', "621c2a4729dd45e3d3ba314c130eb1c8")
    TOMTOM_KEY = os.getenv('TOMTOM_KEY', "H5IueqtPC5bRcXo8zXOb7oqlLscRk0Vu")
    
    # ============================================================
    # PARAMÈTRES DU MODÈLE
    # ============================================================
    MODEL_PATH = 'data/models/bus_arrival_model.pkl'
    DATASET_PATH = 'data/raw/realtime_data.csv'
    
    # ============================================================
    # CONFIGURATION FLASK
    # ============================================================
    FLASK_PORT = 5001
    FLASK_HOST = '0.0.0.0'
    DEBUG = False