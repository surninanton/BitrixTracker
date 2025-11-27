#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os


def load_config():
    """
    Загрузить конфигурацию из config.json

    Returns:
        dict: Конфигурация или пустой dict при ошибке
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Файл конфигурации не найден: {config_path}")
        print("ℹ️  Используются настройки по умолчанию")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON в {config_path}: {e}")
        print("ℹ️  Проверьте корректность файла конфигурации")
        return {}
    except PermissionError:
        print(f"❌ Нет прав для чтения файла: {config_path}")
        return {}
    except Exception as e:
        print(f"❌ Неожиданная ошибка при загрузке конфига: {e}")
        return {}


def save_config(config):
    """
    Сохранить конфигурацию в config.json

    Args:
        config (dict): Конфигурация для сохранения

    Raises:
        ValueError: Если config не является dict
        IOError: Если не удалось записать файл
    """
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a dict, got {type(config)}")

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except PermissionError:
        raise IOError(f"Нет прав для записи файла: {config_path}")
    except OSError as e:
        raise IOError(f"Ошибка записи файла {config_path}: {e}")