#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Script de lancement unique - Lance l'API de prédiction"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)