#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, timezone
from aw_client import ActivityWatchClient


class ActivityWatchService:
    """Сервис для работы с ActivityWatch"""

    def __init__(self):
        try:
            self.client = ActivityWatchClient("bitrix-tracker", testing=False)
            self.available = True
            print("✅ ActivityWatch подключен")
        except Exception as e:
            self.client = None
            self.available = False
            print(f"⚠️ ActivityWatch не доступен: {e}")

    def is_available(self):
        """Проверить доступность ActivityWatch"""
        return self.available

    def get_activity_stats(self, hours=8):
        """
        Получить статистику активности из ActivityWatch

        Args:
            hours: количество часов для анализа

        Returns:
            list: список кортежей (app_name, seconds)
        """
        if not self.available:
            raise Exception("ActivityWatch не доступен")

        # Получаем имя bucket
        hostname = self.client.client_hostname
        bucket_id = f"aw-watcher-window_{hostname}"

        # Проверяем что bucket существует
        buckets = self.client.get_buckets()
        if bucket_id not in buckets:
            raise Exception("Bucket aw-watcher-window не найден. Запустите ActivityWatch.")

        # Временной период
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        # Получаем события
        events = self.client.get_events(bucket_id, limit=10000)

        # Фильтруем по времени и группируем по приложениям
        app_times = {}

        for event in events:
            if event.timestamp < start:
                continue

            app = event.data.get('app', 'Unknown')
            duration = event.duration.total_seconds()

            if app in app_times:
                app_times[app] += duration
            else:
                app_times[app] = duration

        # Сортируем по времени
        sorted_stats = sorted(
            app_times.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_stats