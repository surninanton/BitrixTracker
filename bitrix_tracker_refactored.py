#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bitrix24 Workday Tracker - macOS menu bar приложение для отслеживания рабочего времени
"""

import rumps
import requests
import json
import os
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from dateutil import parser as date_parser
from aw_client import ActivityWatchClient


# ============================================================================
# Константы
# ============================================================================

class Constants:
    """Константы приложения"""
    APP_NAME = "Bitrix24 Tracker"
    TIMER_INTERVAL = 1  # секунд
    REQUEST_TIMEOUT = 10  # секунд

    # Иконки для таймера
    ICON_TIMER = "⏱"
    ICON_PAUSE = "⏸"
    ICON_STATS = "📊"
    ICON_CLOCK = "⏱"

    # Статусы Bitrix24
    STATUS_OPENED = "OPENED"
    STATUS_PAUSED = "PAUSED"
    STATUS_CLOSED = "CLOSED"

    # Формат времени
    TIME_FORMAT = "{hours:02d}:{minutes:02d}:{seconds:02d}"


# ============================================================================
# Bitrix24 API клиент
# ============================================================================

class Bitrix24Client:
    """Клиент для работы с Bitrix24 API"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def get_status(self) -> Optional[Dict]:
        """Получить статус рабочего дня"""
        try:
            response = requests.get(
                f"{self.webhook_url}timeman.status",
                timeout=Constants.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                return response.json().get('result', {})

            print(f"Ошибка получения статуса: {response.status_code}")
            return None

        except Exception as e:
            print(f"Ошибка подключения к Bitrix24: {e}")
            return None

    def open_workday(self) -> bool:
        """Открыть рабочий день"""
        return self._make_request("timeman.open")

    def close_workday(self) -> bool:
        """Закрыть рабочий день"""
        return self._make_request("timeman.close")

    def pause_workday(self) -> bool:
        """Поставить рабочий день на паузу / снять с паузы"""
        return self._make_request("timeman.pause")

    def _make_request(self, method: str) -> bool:
        """Выполнить запрос к API"""
        try:
            response = requests.post(
                f"{self.webhook_url}{method}",
                timeout=Constants.REQUEST_TIMEOUT
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка выполнения {method}: {e}")
            return False


# ============================================================================
# Утилиты для работы со временем
# ============================================================================

class TimeUtils:
    """Утилиты для работы со временем"""

    @staticmethod
    def parse_bitrix_time(time_str: str) -> datetime:
        """Преобразовать время из формата Bitrix24 в локальное datetime"""
        dt_with_tz = date_parser.parse(time_str)
        local_dt = dt_with_tz.astimezone()
        return local_dt.replace(tzinfo=None)

    @staticmethod
    def parse_time_leaks(time_leaks_str: str) -> int:
        """Преобразовать TIME_LEAKS (HH:MM:SS) в секунды"""
        if not time_leaks_str:
            return 0

        try:
            hours, minutes, seconds = map(int, time_leaks_str.split(':'))
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    def format_seconds(seconds: float) -> Tuple[int, int, int]:
        """Преобразовать секунды в часы, минуты, секунды"""
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return hours, minutes, secs

    @staticmethod
    def is_time_expired(time_start: datetime, hours: int = 24) -> bool:
        """Проверить истекло ли время с момента time_start"""
        elapsed = (datetime.now() - time_start).total_seconds() / 3600
        return elapsed > hours


# ============================================================================
# Менеджер меню
# ============================================================================

class MenuManager:
    """Менеджер для управления меню приложения"""

    def __init__(self, app):
        self.app = app

    def create_menu_items(self) -> Dict[str, rumps.MenuItem]:
        """Создать все пункты меню"""
        return {
            'start': rumps.MenuItem("Начать рабочий день", callback=self.app.start_workday),
            'pause': rumps.MenuItem("Поставить на паузу", callback=self.app.pause_workday),
            'resume': rumps.MenuItem("Продолжить рабочий день", callback=self.app.resume_workday),
            'stop': rumps.MenuItem("Завершить рабочий день", callback=self.app.stop_workday),
            'stats_today': rumps.MenuItem("Статистика за сегодня", callback=self.app.show_day_stats),
            'stats_hour': rumps.MenuItem("Статистика за час", callback=self.app.show_hour_stats),
            'settings': rumps.MenuItem("Настройки", callback=self.app.settings),
            'aw_open': rumps.MenuItem("Открыть ActivityWatch", callback=self.app.open_activitywatch),
            'quit': rumps.MenuItem("Выход", callback=self.app.quit_app),
        }

    def set_menu_for_state(self, state: str):
        """Установить меню в зависимости от состояния"""
        items = self.create_menu_items()

        if state == 'stopped':
            menu_list = [
                items['start'], None,
                items['stats_today'], items['stats_hour'], None,
                items['settings'], items['aw_open'], None,
                items['quit']
            ]
        elif state == 'running':
            menu_list = [
                items['pause'], items['stop'], None,
                items['stats_today'], items['stats_hour'], None,
                items['settings'], items['aw_open'], None,
                items['quit']
            ]
        elif state == 'paused':
            menu_list = [
                items['resume'], items['stop'], None,
                items['stats_today'], items['stats_hour'], None,
                items['settings'], items['aw_open'], None,
                items['quit']
            ]
        else:
            return

        self.app.menu.clear()
        self.app.menu = menu_list


# ============================================================================
# Главное приложение
# ============================================================================

class BitrixWorkdayTracker(rumps.App):
    """Главное приложение для отслеживания рабочего дня"""

    def __init__(self):
        super().__init__(
            f"{Constants.ICON_TIMER} 00:00:00",
            quit_button=None
        )

        # Инициализация компонентов
        self._setup_icon()
        self._load_configuration()
        self._init_state()
        self._init_activity_watch()

        # Менеджер меню
        self.menu_manager = MenuManager(self)
        self.menu_manager.set_menu_for_state('stopped')

        # Запуск таймера
        self.timer = rumps.Timer(self._update_timer, Constants.TIMER_INTERVAL)
        self.timer.start()

    def _setup_icon(self):
        """Установить кастомную иконку"""
        try:
            import AppKit
            app = AppKit.NSApplication.sharedApplication()
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')

            if os.path.exists(icon_path):
                image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
                if image:
                    app.setApplicationIconImage_(image)
        except Exception as e:
            print(f"⚠️ Не удалось установить иконку: {e}")

    def _load_configuration(self):
        """Загрузить конфигурацию"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

        self.webhook_url = self.config.get('webhook_url', '')
        self.bitrix_client = Bitrix24Client(self.webhook_url) if self.webhook_url else None

    def _save_configuration(self):
        """Сохранить конфигурацию"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _init_state(self):
        """Инициализировать состояние приложения"""
        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.time_leaks_seconds = 0
        self.pause_start_time = None

    def _init_activity_watch(self):
        """Инициализировать ActivityWatch клиент"""
        try:
            self.aw_client = ActivityWatchClient("bitrix-tracker", testing=False)
            self.aw_available = True
            print("✅ ActivityWatch подключен")
        except Exception as e:
            self.aw_available = False
            print(f"⚠️ ActivityWatch не доступен: {e}")

    def _reset_state(self):
        """Сбросить состояние"""
        self.start_time = None
        self.time_leaks_seconds = 0
        self.pause_start_time = None
        self.is_running = False
        self.is_paused = False

    # ========================================================================
    # Обновление таймера
    # ========================================================================

    def _update_timer(self, _):
        """Обновление таймера в menu bar"""
        if self.is_paused and self.pause_start_time:
            self._show_pause_timer()
        elif self.is_running and self.start_time:
            self._show_work_timer()
        else:
            self.title = f"{Constants.ICON_TIMER} 00:00:00"

    def _show_pause_timer(self):
        """Показать таймер паузы"""
        pause_elapsed = (datetime.now() - self.pause_start_time).total_seconds()
        total_pause_seconds = self.time_leaks_seconds + pause_elapsed
        hours, minutes, seconds = TimeUtils.format_seconds(total_pause_seconds)
        self.title = f"{Constants.ICON_PAUSE} {Constants.TIME_FORMAT.format(hours=hours, minutes=minutes, seconds=seconds)}"

    def _show_work_timer(self):
        """Показать таймер рабочего времени"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        work_seconds = elapsed - self.time_leaks_seconds
        hours, minutes, seconds = TimeUtils.format_seconds(work_seconds)
        self.title = f"{Constants.ICON_TIMER} {Constants.TIME_FORMAT.format(hours=hours, minutes=minutes, seconds=seconds)}"

    # ========================================================================
    # Управление рабочим днем
    # ========================================================================

    def start_workday(self, _):
        """Начать рабочий день"""
        if not self.bitrix_client:
            rumps.alert("Ошибка", "Настройте webhook URL в настройках")
            return

        try:
            status = self.bitrix_client.get_status()

            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус из Bitrix24")
                return

            # Проверяем статус и TIME_START
            if self._should_sync_with_existing_day(status):
                self._sync_with_existing_day(status)
            else:
                self._open_new_workday()

        except Exception as e:
            rumps.alert("Ошибка", str(e))

    def _should_sync_with_existing_day(self, status: Dict) -> bool:
        """Проверить нужно ли синхронизироваться с существующим днем"""
        if not status.get('TIME_START'):
            return False

        current_status = status.get('STATUS')

        # Если день закрыт - не синхронизируемся
        if current_status == Constants.STATUS_CLOSED:
            return False

        # Если TIME_START старше 24 часов - не синхронизируемся
        time_start = TimeUtils.parse_bitrix_time(status.get('TIME_START'))
        if TimeUtils.is_time_expired(time_start, hours=24):
            return False

        return current_status in [Constants.STATUS_OPENED, Constants.STATUS_PAUSED]

    def _sync_with_existing_day(self, status: Dict):
        """Синхронизироваться с существующим рабочим днем"""
        time_start = TimeUtils.parse_bitrix_time(status.get('TIME_START'))
        time_leaks = status.get('TIME_LEAKS', '00:00:00')
        is_paused = status.get('STATUS') == Constants.STATUS_PAUSED

        self.start_time = time_start
        self.time_leaks_seconds = TimeUtils.parse_time_leaks(time_leaks)
        self.is_running = True

        if is_paused:
            self.is_paused = True
            self.pause_start_time = datetime.now()
            rumps.notification(Constants.APP_NAME, "Синхронизация", "Рабочий день на паузе")
            self.menu_manager.set_menu_for_state('paused')
        else:
            self.is_paused = False
            rumps.notification(Constants.APP_NAME, "Синхронизация", "Рабочий день продолжается")
            self.menu_manager.set_menu_for_state('running')

    def _open_new_workday(self):
        """Открыть новый рабочий день"""
        if not self.bitrix_client.open_workday():
            rumps.alert("Ошибка", "Не удалось открыть рабочий день")
            return

        # Получаем новый статус
        status = self.bitrix_client.get_status()

        if status and status.get('TIME_START'):
            self.start_time = TimeUtils.parse_bitrix_time(status.get('TIME_START'))
            self.time_leaks_seconds = TimeUtils.parse_time_leaks(status.get('TIME_LEAKS', '00:00:00'))
        else:
            self.start_time = datetime.now()
            self.time_leaks_seconds = 0

        self.is_running = True
        self.is_paused = False

        rumps.notification(Constants.APP_NAME, "Рабочий день начат", "ActivityWatch собирает статистику")
        self.menu_manager.set_menu_for_state('running')

    def pause_workday(self, _):
        """Поставить рабочий день на паузу"""
        if not self.bitrix_client:
            return

        try:
            # Получаем текущий TIME_LEAKS
            status = self.bitrix_client.get_status()
            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус")
                return

            if not self.bitrix_client.pause_workday():
                rumps.alert("Ошибка", "Не удалось поставить на паузу")
                return

            self.is_paused = True
            self.pause_start_time = datetime.now()
            self.time_leaks_seconds = TimeUtils.parse_time_leaks(status.get('TIME_LEAKS', '00:00:00'))

            rumps.notification(Constants.APP_NAME, "Пауза", "Рабочий день поставлен на паузу")
            self.menu_manager.set_menu_for_state('paused')

        except Exception as e:
            rumps.alert("Ошибка", str(e))

    def resume_workday(self, _):
        """Продолжить рабочий день после паузы"""
        if not self.bitrix_client:
            return

        try:
            if not self.bitrix_client.pause_workday():
                rumps.alert("Ошибка", "Не удалось продолжить работу")
                return

            # Обновляем TIME_LEAKS
            status = self.bitrix_client.get_status()
            if status:
                self.time_leaks_seconds = TimeUtils.parse_time_leaks(status.get('TIME_LEAKS', '00:00:00'))

            self.is_paused = False
            self.pause_start_time = None

            rumps.notification(Constants.APP_NAME, "Работа продолжена", "Рабочий день продолжен")
            self.menu_manager.set_menu_for_state('running')

        except Exception as e:
            rumps.alert("Ошибка", str(e))

    def stop_workday(self, _):
        """Завершить рабочий день"""
        if not self.bitrix_client:
            return

        try:
            if not self.bitrix_client.close_workday():
                rumps.alert("Ошибка", "Не удалось завершить рабочий день")
                return

            # Подсчитываем отработанное время
            if self.start_time:
                elapsed_seconds = (datetime.now() - self.start_time).total_seconds()
                hours, minutes, _ = TimeUtils.format_seconds(elapsed_seconds)
            else:
                hours, minutes = 0, 0

            # Показываем статистику
            self.show_day_stats()

            # Уведомление
            rumps.notification(
                Constants.APP_NAME,
                "Рабочий день завершен",
                f"Отработано: {hours}ч {minutes}мин"
            )

            # Сбрасываем состояние
            self._reset_state()
            self.menu_manager.set_menu_for_state('stopped')

        except Exception as e:
            rumps.alert("Ошибка", str(e))

    # ========================================================================
    # Статистика
    # ========================================================================

    def show_day_stats(self, _=None):
        """Показать статистику за сегодня"""
        if not self.aw_available:
            rumps.alert("ActivityWatch не доступен", "Убедитесь что ActivityWatch запущен")
            return

        try:
            bitrix_status = self.bitrix_client.get_status() if self.bitrix_client else None

            now = datetime.now()
            hours_since_midnight = now.hour + (now.minute / 60)

            stats = self._get_activity_stats(hours=hours_since_midnight)
            self._display_stats(stats, "Статистика за сегодня", bitrix_status)
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")

    def show_hour_stats(self, _):
        """Показать статистику за последний час"""
        if not self.aw_available:
            rumps.alert("ActivityWatch не доступен", "Убедитесь что ActivityWatch запущен")
            return

        try:
            stats = self._get_activity_stats(hours=1)
            self._display_stats(stats, "Статистика за последний час")
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")

    def _get_activity_stats(self, hours: float):
        """Получить статистику активности из ActivityWatch"""
        hostname = self.aw_client.client_hostname
        bucket_id = f"aw-watcher-window_{hostname}"

        buckets = self.aw_client.get_buckets()
        if bucket_id not in buckets:
            raise Exception("Bucket aw-watcher-window не найден. Запустите ActivityWatch.")

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        events = self.aw_client.get_events(bucket_id, limit=10000)

        # Группируем по приложениям
        app_times = {}
        for event in events:
            if event.timestamp < start:
                continue

            app = event.data.get('app', 'Unknown')
            duration = event.duration.total_seconds()
            app_times[app] = app_times.get(app, 0) + duration

        return sorted(app_times.items(), key=lambda x: x[1], reverse=True)

    def _display_stats(self, stats, title: str, bitrix_status: Optional[Dict] = None):
        """Отобразить статистику"""
        if not stats:
            rumps.alert(title, "Нет данных за этот период")
            return

        message_parts = []

        # Добавляем информацию из Bitrix24
        if bitrix_status:
            message_parts.append(self._format_bitrix_stats(bitrix_status))
            message_parts.append("━━━━━━━━━━━━━━━━━━━━━━━")
            message_parts.append("ActivityWatch статистика:")
            message_parts.append("━━━━━━━━━━━━━━━━━━━━━━━\n")

        # Добавляем статистику ActivityWatch
        total_seconds = sum(s[1] for s in stats)

        for i, (app, seconds) in enumerate(stats[:10], 1):
            hours, minutes, _ = TimeUtils.format_seconds(seconds)
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            if hours > 0:
                message_parts.append(f"{i}. {app}\n   {hours}ч {minutes}мин ({percentage:.1f}%)")
            else:
                message_parts.append(f"{i}. {app}\n   {minutes}мин ({percentage:.1f}%)")

        # Итого
        total_hours, total_minutes, _ = TimeUtils.format_seconds(total_seconds)
        message_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━")
        message_parts.append(f"Всего (ActivityWatch):\n{total_hours}ч {total_minutes}мин")

        rumps.alert(title, "\n".join(message_parts))

    def _format_bitrix_stats(self, status: Dict) -> str:
        """Форматировать статистику из Bitrix24"""
        parts = []
        current_status = status.get('STATUS')

        if current_status == Constants.STATUS_OPENED and status.get('TIME_START'):
            time_start = TimeUtils.parse_bitrix_time(status.get('TIME_START'))
            time_leaks_seconds = TimeUtils.parse_time_leaks(status.get('TIME_LEAKS', '00:00:00'))

            # Общее время
            total_seconds = (datetime.now() - time_start).total_seconds()
            total_hours, total_minutes, _ = TimeUtils.format_seconds(total_seconds)
            parts.append(f"⏱  Общее время:\n    {total_hours}ч {total_minutes}мин\n")

            # Рабочее время
            work_seconds = total_seconds - time_leaks_seconds
            work_hours, work_minutes, _ = TimeUtils.format_seconds(work_seconds)
            parts.append(f"📊  Рабочее время (Bitrix24):\n    {work_hours}ч {work_minutes}мин\n")

        elif current_status == Constants.STATUS_CLOSED and status.get('DURATION'):
            duration = status.get('DURATION')
            parts.append(f"📊  Рабочее время (Bitrix24):\n    {duration}\n")

        # Время паузы
        time_leaks = status.get('TIME_LEAKS', '00:00:00')
        if time_leaks and time_leaks != '00:00:00':
            parts.append(f"⏸  Время паузы (Bitrix24):\n    {time_leaks}\n")

        return "".join(parts)

    # ========================================================================
    # Настройки и утилиты
    # ========================================================================

    def settings(self, _):
        """Настройки"""
        window = rumps.Window(
            message='Введите Bitrix24 webhook URL:',
            title='Настройки',
            default_text=self.webhook_url,
            ok='Сохранить',
            cancel='Отмена',
            dimensions=(500, 24)
        )

        response = window.run()
        if response.clicked:
            self.webhook_url = response.text
            self.config['webhook_url'] = self.webhook_url
            self._save_configuration()
            self.bitrix_client = Bitrix24Client(self.webhook_url)
            rumps.alert("Настройки", "Webhook URL сохранен")

    def open_activitywatch(self, _):
        """Открыть веб-интерфейс ActivityWatch"""
        webbrowser.open('http://localhost:5600')

    def quit_app(self, _):
        """Выход"""
        if self.is_running:
            response = rumps.alert(
                "Рабочий день активен",
                "Завершить день и выйти?",
                ok="Да",
                cancel="Отмена"
            )
            if response == 1:
                self.stop_workday(None)
                rumps.quit_application()
        else:
            rumps.quit_application()


# ============================================================================
# Точка входа
# ============================================================================

if __name__ == "__main__":
    BitrixWorkdayTracker().run()