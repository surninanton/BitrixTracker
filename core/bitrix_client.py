#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests


class BitrixClient:
    """Клиент для работы с Bitrix24 API"""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def get_status(self):
        """Получить статус рабочего дня из Bitrix24"""
        try:
            response = requests.get(
                f"{self.webhook_url}timeman.status",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('result', {})
            else:
                print(f"Ошибка получения статуса: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ошибка подключения к Bitrix24: {e}")
            return None

    def open_workday(self):
        """Открыть рабочий день"""
        try:
            response = requests.post(
                f"{self.webhook_url}timeman.open",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка открытия рабочего дня: {e}")
            return False

    def close_workday(self):
        """Закрыть рабочий день"""
        try:
            response = requests.post(
                f"{self.webhook_url}timeman.close",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка закрытия рабочего дня: {e}")
            return False

    def pause_workday(self):
        """Поставить/снять рабочий день на паузу (toggle)"""
        try:
            response = requests.post(
                f"{self.webhook_url}timeman.pause",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка паузы рабочего дня: {e}")
            return False

    def resume_workday(self, status):
        """
        Продолжить рабочий день после паузы.

        ВАЖНО: timeman.pause работает как toggle ТОЛЬКО если TIME_FINISH не установлен.
        Если TIME_FINISH установлен - нужен timeman.open.

        Args:
            status: текущий статус из get_status()
        """
        try:
            # Определяем нужный API метод
            if status and status.get('TIME_FINISH'):
                api_method = "timeman.open"
            else:
                api_method = "timeman.pause"

            response = requests.post(
                f"{self.webhook_url}{api_method}",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка продолжения рабочего дня: {e}")
            return False