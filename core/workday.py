#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
from datetime import datetime
from utils.time_parser import parse_bitrix_time, parse_time_leaks


class WorkdayManager:
    """Управление рабочим днем"""

    def __init__(self, bitrix):
        """
        Args:
            bitrix: экземпляр BitrixClient
        """
        self.bitrix = bitrix
        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.time_leaks_seconds = 0
        self.pause_start_time = None

    def start(self, on_sync_paused=None, on_sync_running=None, on_new_day=None):
        """
        Начать рабочий день

        Args:
            on_sync_paused: callback при синхронизации с паузой
            on_sync_running: callback при синхронизации с работающим днем
            on_new_day: callback при начале нового дня

        Returns:
            bool: успешность операции
        """
        if not self.bitrix.webhook_url:
            rumps.alert("Ошибка", "Настройте webhook URL в настройках")
            return False

        try:
            status = self.bitrix.get_status()
            should_open_new_day = False

            if status and status.get('TIME_START'):
                time_start_str = status.get('TIME_START')
                time_start = parse_bitrix_time(time_start_str)
                hours_since_start = (datetime.now() - time_start).total_seconds() / 3600
                current_status = status.get('STATUS')

                if current_status == 'CLOSED' or hours_since_start > 24:
                    should_open_new_day = True
                else:
                    # Синхронизируем с существующим днем
                    time_leaks_str = status.get('TIME_LEAKS', '00:00:00')
                    is_paused_in_bitrix = current_status == 'PAUSED'

                    self.start_time = time_start
                    self.time_leaks_seconds = parse_time_leaks(time_leaks_str)
                    self.is_running = True

                    if is_paused_in_bitrix:
                        self.is_paused = True
                        self.pause_start_time = datetime.now()
                        rumps.notification("Bitrix24 Tracker", "Синхронизация", "Рабочий день на паузе")
                        if on_sync_paused:
                            on_sync_paused()
                        return True
                    else:
                        self.is_paused = False
                        rumps.notification("Bitrix24 Tracker", "Синхронизация", "Рабочий день продолжается")
                        if on_sync_running:
                            on_sync_running()
                        return True
            else:
                should_open_new_day = True

            if should_open_new_day:
                if self.bitrix.open_workday():
                    new_status = self.bitrix.get_status()

                    if new_status and new_status.get('TIME_START'):
                        time_start = parse_bitrix_time(new_status.get('TIME_START'))
                        time_leaks_str = new_status.get('TIME_LEAKS', '00:00:00')
                        self.start_time = time_start
                        self.time_leaks_seconds = parse_time_leaks(time_leaks_str)
                    else:
                        self.start_time = datetime.now()
                        self.time_leaks_seconds = 0

                    self.is_running = True
                    self.is_paused = False

                    rumps.notification("Bitrix24 Tracker", "Рабочий день начат", "ActivityWatch собирает статистику")
                    if on_new_day:
                        on_new_day()
                    return True
                else:
                    rumps.alert("Ошибка", "Не удалось начать рабочий день в Bitrix24")
                    return False

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))
            return False

    def pause(self):
        """Поставить рабочий день на паузу"""
        try:
            status = self.bitrix.get_status()
            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус из Bitrix24")
                return False

            if self.bitrix.pause_workday():
                self.is_paused = True
                self.pause_start_time = datetime.now()

                time_leaks_str = status.get('TIME_LEAKS', '00:00:00')
                self.time_leaks_seconds = parse_time_leaks(time_leaks_str)

                rumps.notification("Bitrix24 Tracker", "Пауза", "Рабочий день поставлен на паузу")
                return True
            else:
                rumps.alert("Ошибка", "Не удалось поставить на паузу в Bitrix24")
                return False

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))
            return False

    def resume(self):
        """Продолжить рабочий день после паузы"""
        try:
            status_before = self.bitrix.get_status()

            if self.bitrix.resume_workday(status_before):
                status_after = self.bitrix.get_status()
                current_status = status_after.get('STATUS') if status_after else None

                if current_status == 'OPENED':
                    if status_after:
                        time_leaks_str = status_after.get('TIME_LEAKS', '00:00:00')
                        self.time_leaks_seconds = parse_time_leaks(time_leaks_str)

                    self.is_paused = False
                    self.pause_start_time = None

                    rumps.notification("Bitrix24 Tracker", "Работа продолжена", "Рабочий день продолжен")
                    return True
                else:
                    rumps.alert("Ошибка", f"Не удалось продолжить работу. Статус: {current_status}")
                    return False
            else:
                rumps.alert("Ошибка", "Не удалось продолжить работу в Bitrix24")
                return False

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))
            return False

    def stop(self, on_stats=None):
        """
        Завершить рабочий день

        Args:
            on_stats: callback для показа статистики

        Returns:
            bool: успешность операции
        """
        try:
            status = self.bitrix.get_status()
            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус из Bitrix24")
                return False

            current_status = status.get('STATUS')
            if current_status == 'CLOSED':
                rumps.alert("День уже завершен", "Рабочий день уже был завершен в Bitrix24")
                self.reset()
                return True

            if self.bitrix.close_workday():
                # Сохраняем время
                if self.start_time:
                    elapsed = datetime.now() - self.start_time
                    hours = int(elapsed.total_seconds() // 3600)
                    minutes = int((elapsed.total_seconds() % 3600) // 60)
                else:
                    hours = 0
                    minutes = 0

                self.is_running = False
                self.is_paused = False

                # Показываем статистику
                if on_stats:
                    on_stats()

                # Уведомление
                rumps.notification("Bitrix24 Tracker", "Рабочий день завершен", f"Отработано: {hours}ч {minutes}мин")

                self.reset()
                return True
            else:
                # Возможно день уже закрыт
                rumps.alert("День уже завершен", "Рабочий день уже был завершен в Bitrix24")
                self.reset()
                return True

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))
            return False

    def reset(self):
        """Сбросить состояние рабочего дня"""
        self.start_time = None
        self.time_leaks_seconds = 0
        self.pause_start_time = None

    def get_work_time(self):
        """
        Получить текущее рабочее время

        Returns:
            tuple: (hours, minutes, seconds)
        """
        if not self.is_running or not self.start_time:
            return (0, 0, 0)

        total_elapsed = datetime.now() - self.start_time
        work_seconds = total_elapsed.total_seconds() - self.time_leaks_seconds

        if work_seconds < 0:
            work_seconds = 0

        hours = int(work_seconds // 3600)
        minutes = int((work_seconds % 3600) // 60)
        seconds = int(work_seconds % 60)

        return (hours, minutes, seconds)

    def get_pause_time(self):
        """
        Получить текущее время паузы

        Returns:
            tuple: (hours, minutes, seconds)
        """
        if not self.is_paused or not self.pause_start_time:
            return (0, 0, 0)

        pause_elapsed = datetime.now() - self.pause_start_time
        pause_seconds = self.time_leaks_seconds + pause_elapsed.total_seconds()

        hours = int(pause_seconds // 3600)
        minutes = int((pause_seconds % 3600) // 60)
        seconds = int(pause_seconds % 60)

        return (hours, minutes, seconds)