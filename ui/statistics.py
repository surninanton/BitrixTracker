#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
from datetime import datetime
from utils.time_parser import parse_bitrix_time, parse_time_leaks


class StatisticsManager:
    """Управление статистикой"""

    def __init__(self, activity_watch, bitrix):
        """
        Args:
            activity_watch: экземпляр ActivityWatchService
            bitrix: экземпляр BitrixClient
        """
        self.activity_watch = activity_watch
        self.bitrix = bitrix

    def show_hour_stats(self):
        """Показать статистику за последний час"""
        if not self.activity_watch.is_available():
            rumps.alert("ActivityWatch не доступен", "Убедитесь что ActivityWatch запущен")
            return

        try:
            stats = self.activity_watch.get_activity_stats(hours=1)
            self.display_stats(stats, "Статистика за последний час")
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")

    def show_day_stats(self):
        """Показать статистику за сегодня"""
        if not self.activity_watch.is_available():
            rumps.alert("ActivityWatch не доступен", "Убедитесь что ActivityWatch запущен")
            return

        try:
            bitrix_status = self.bitrix.get_status()

            now = datetime.now()
            hours_since_midnight = now.hour + (now.minute / 60)

            stats = self.activity_watch.get_activity_stats(hours=hours_since_midnight)
            self.display_stats(stats, "Статистика за сегодня", bitrix_status)
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")

    def display_stats(self, stats, title, bitrix_status=None):
        """Отобразить статистику"""
        if not stats:
            rumps.alert(title, "Нет данных за этот период")
            return

        message = ""

        # Добавляем информацию из Bitrix24
        if bitrix_status:
            message += self._format_bitrix_stats(bitrix_status)

        # Добавляем статистику ActivityWatch
        message += self._format_activity_stats(stats)

        rumps.alert(title, message)

    def _format_bitrix_stats(self, bitrix_status):
        """Форматировать статистику Bitrix24"""
        message = ""
        status_text = bitrix_status.get('STATUS', 'N/A')

        if status_text == 'OPENED':
            if bitrix_status.get('TIME_START'):
                time_start = parse_bitrix_time(bitrix_status.get('TIME_START'))
                time_leaks_seconds = parse_time_leaks(bitrix_status.get('TIME_LEAKS', '00:00:00'))

                total_seconds = (datetime.now() - time_start).total_seconds()
                total_hours = int(total_seconds // 3600)
                total_minutes = int((total_seconds % 3600) // 60)

                work_seconds = total_seconds - time_leaks_seconds
                work_hours = int(work_seconds // 3600)
                work_minutes = int((work_seconds % 3600) // 60)

                message += f"⏱  Общее время:\n"
                message += f"    {total_hours}ч {total_minutes}мин\n\n"
                message += f"📊  Рабочее время (Bitrix24):\n"
                message += f"    {work_hours}ч {work_minutes}мин\n\n"
        elif status_text == 'CLOSED' and bitrix_status.get('DURATION'):
            duration = bitrix_status.get('DURATION')
            message += f"📊  Рабочее время (Bitrix24):\n"
            message += f"    {duration}\n\n"

        time_leaks = bitrix_status.get('TIME_LEAKS', '00:00:00')
        if time_leaks and time_leaks != '00:00:00':
            message += f"⏸  Время паузы (Bitrix24):\n"
            message += f"    {time_leaks}\n\n"

        message += "━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += "ActivityWatch статистика:\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        return message

    def _format_activity_stats(self, stats):
        """Форматировать статистику ActivityWatch"""
        message = ""
        total_seconds = sum([s[1] for s in stats])

        for i, (app, seconds) in enumerate(stats[:10], 1):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            if hours > 0:
                message += f"{i}. {app}\n"
                message += f"   {hours}ч {minutes}мин ({percentage:.1f}%)\n"
            else:
                message += f"{i}. {app}\n"
                message += f"   {minutes}мин ({percentage:.1f}%)\n"

        total_hours = int(total_seconds // 3600)
        total_minutes = int((total_seconds % 3600) // 60)
        message += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"Всего (ActivityWatch):\n"
        message += f"{total_hours}ч {total_minutes}мин"

        return message