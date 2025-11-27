#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import get_logger

logger = get_logger('bitrix_client')


class BitrixClient:
    """Клиент для работы с Bitrix24 API с поддержкой retry"""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.session = self._create_session_with_retries()

    def _create_session_with_retries(self):
        """Создать сессию с автоматическими retry для временных ошибок"""
        session = requests.Session()

        # Настройка retry стратегии
        retry_strategy = Retry(
            total=3,  # Максимум 3 попытки
            status_forcelist=[429, 500, 502, 503, 504],  # Повторять для этих HTTP кодов
            allowed_methods=["GET", "POST"],  # Повторять GET и POST
            backoff_factor=1  # Экспоненциальная задержка: 1s, 2s, 4s
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_status(self):
        """Получить статус рабочего дня из Bitrix24"""
        try:
            response = self.session.get(
                f"{self.webhook_url}timeman.status",
                timeout=10
            )
            response.raise_for_status()  # Выбрасывает исключение для 4xx/5xx

            data = response.json()
            return data.get('result', {})

        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания ответа от Bitrix24")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Не удалось подключиться к Bitrix24")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка: {e.response.status_code}")
            return None
        except ValueError:  # JSON decode error
            logger.error("Некорректный JSON ответ от Bitrix24")
            return None
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при получении статуса: {e}")
            return None

    def open_workday(self):
        """Открыть рабочий день"""
        try:
            response = self.session.post(
                f"{self.webhook_url}timeman.open",
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при открытии рабочего дня")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Ошибка открытия рабочего дня: {e.response.status_code}")
            return False
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при открытии рабочего дня: {e}")
            return False

    def close_workday(self):
        """Закрыть рабочий день"""
        try:
            response = self.session.post(
                f"{self.webhook_url}timeman.close",
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при закрытии рабочего дня")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Ошибка закрытия рабочего дня: {e.response.status_code}")
            return False
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при закрытии рабочего дня: {e}")
            return False

    def pause_workday(self):
        """Поставить/снять рабочий день на паузу (toggle)"""
        try:
            response = self.session.post(
                f"{self.webhook_url}timeman.pause",
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при паузе рабочего дня")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Ошибка паузы рабочего дня: {e.response.status_code}")
            return False
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при паузе рабочего дня: {e}")
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

            response = self.session.post(
                f"{self.webhook_url}{api_method}",
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания при продолжении рабочего дня")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Ошибка продолжения рабочего дня: {e.response.status_code}")
            return False
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при продолжении рабочего дня: {e}")
            return False