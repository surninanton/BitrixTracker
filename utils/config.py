#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os


def load_config():
    """Загрузить конфигурацию"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_config(config):
    """Сохранить конфигурацию"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)