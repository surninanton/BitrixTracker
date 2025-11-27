#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from aw_client import ActivityWatchClient
from AppKit import NSWorkspace, NSApp, NSApplication
from Foundation import NSObject
from enum import Enum

class PomodoroState(Enum):
    """Состояния помодоро таймера"""
    STOPPED = "stopped"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"

class PomodoroTimer:
    """Таймер Pomodoro"""

    def __init__(self, config, on_state_change=None, on_break_start=None, on_break_end=None):
        """
        Args:
            config: словарь с настройками pomodoro
            on_state_change: callback при смене состояния (state, remaining_seconds)
            on_break_start: callback при начале перерыва
            on_break_end: callback при окончании перерыва
        """
        self.config = config
        self.on_state_change = on_state_change
        self.on_break_start = on_break_start
        self.on_break_end = on_break_end

        self.state = PomodoroState.STOPPED
        self.remaining_seconds = 0
        self.pomodoro_count = 0  # Счетчик завершенных помодоро
        self.is_running = False

    def start(self):
        """Запустить помодоро (начать рабочую сессию)"""
        self.state = PomodoroState.WORK
        self.remaining_seconds = self.config.get('work_duration', 25) * 60
        self.is_running = True
        if self.on_state_change:
            self.on_state_change(self.state, self.remaining_seconds)

    def stop(self):
        """Остановить помодоро"""
        self.state = PomodoroState.STOPPED
        self.remaining_seconds = 0
        self.is_running = False
        self.pomodoro_count = 0
        if self.on_state_change:
            self.on_state_change(self.state, self.remaining_seconds)

    def skip(self):
        """Пропустить текущую сессию"""
        if self.state == PomodoroState.WORK:
            # Переходим к перерыву
            self._start_break()
        elif self.state in [PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK]:
            # Возвращаемся к работе
            self._end_break()

    def tick(self):
        """Обновление таймера (вызывать каждую секунду)"""
        if not self.is_running:
            return

        self.remaining_seconds -= 1

        if self.remaining_seconds <= 0:
            # Время истекло
            if self.state == PomodoroState.WORK:
                # Рабочая сессия завершена
                self.pomodoro_count += 1
                self._start_break()
            elif self.state in [PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK]:
                # Перерыв завершен
                self._end_break()

        if self.on_state_change:
            self.on_state_change(self.state, self.remaining_seconds)

    def _start_break(self):
        """Начать перерыв"""
        # Определяем тип перерыва
        pomodoros_until_long = self.config.get('pomodoros_until_long_break', 4)

        if self.pomodoro_count % pomodoros_until_long == 0:
            # Длинный перерыв
            self.state = PomodoroState.LONG_BREAK
            self.remaining_seconds = self.config.get('long_break', 15) * 60
        else:
            # Короткий перерыв
            self.state = PomodoroState.SHORT_BREAK
            self.remaining_seconds = self.config.get('short_break', 5) * 60

        # Вызываем callback начала перерыва
        if self.on_break_start:
            self.on_break_start(self.state)

    def _end_break(self):
        """Завершить перерыв и начать новую рабочую сессию"""
        # Вызываем callback окончания перерыва
        if self.on_break_end:
            self.on_break_end()

        # Начинаем новую рабочую сессию
        self.state = PomodoroState.WORK
        self.remaining_seconds = self.config.get('work_duration', 25) * 60

    def get_display_time(self):
        """Получить время для отображения в формате MM:SS"""
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_emoji(self):
        """Получить эмодзи для текущего состояния"""
        if self.state == PomodoroState.WORK:
            return "🍅"
        elif self.state == PomodoroState.SHORT_BREAK:
            return "☕"
        elif self.state == PomodoroState.LONG_BREAK:
            return "🌴"
        return "⏱"

    def get_progress(self):
        """Получить прогресс помодоро (N/M)"""
        pomodoros_until_long = self.config.get('pomodoros_until_long_break', 4)
        current = self.pomodoro_count % pomodoros_until_long
        if current == 0 and self.pomodoro_count > 0:
            current = pomodoros_until_long
        return f"{current}/{pomodoros_until_long}"

class BitrixWorkdayTracker(rumps.App):
    def __init__(self):
        # Используем только текст без иконки PNG (чтобы избежать проблем с путями)
        super(BitrixWorkdayTracker, self).__init__(
            "⏱ 00:00:00",
            quit_button=None  # Убираем стандартную кнопку Quit
        )

        # Устанавливаем кастомную иконку для уведомлений
        try:
            import AppKit
            app = AppKit.NSApplication.sharedApplication()
            # Загружаем иконку
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
            if os.path.exists(icon_path):
                image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
                if image:
                    app.setApplicationIconImage_(image)
        except Exception as e:
            print(f"⚠️ Не удалось установить иконку: {e}")
        
        # Загружаем конфигурацию
        self.config = self.load_config()
        self.webhook_url = self.config.get('webhook_url', '')
        
        # Время работы
        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.time_leaks_seconds = 0  # Время простоев в секундах
        self.pause_start_time = None  # Время начала паузы
        
        # ActivityWatch клиент
        try:
            self.aw_client = ActivityWatchClient("bitrix-tracker", testing=False)
            self.aw_available = True
            print("✅ ActivityWatch подключен")
        except Exception as e:
            self.aw_available = False
            print(f"⚠️ ActivityWatch не доступен: {e}")

        # Pomodoro таймер
        pomodoro_config = self.config.get('pomodoro', {
            'enabled': False,
            'work_duration': 25,
            'short_break': 5,
            'long_break': 15,
            'pomodoros_until_long_break': 4,
            'auto_pause_bitrix': True
        })
        self.pomodoro = PomodoroTimer(
            config=pomodoro_config,
            on_state_change=self.on_pomodoro_state_change,
            on_break_start=self.on_pomodoro_break_start,
            on_break_end=self.on_pomodoro_break_end
        )
        self.pomodoro_enabled = pomodoro_config.get('enabled', False)

        # Таймер для обновления времени
        self.timer = rumps.Timer(self.update_timer, 1)
        self.timer.start()

        # Начальное меню (рабочий день не начат)
        self.update_menu_for_stopped_workday()
    
    def load_config(self):
        """Загрузить конфигурацию"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_config(self):
        """Сохранить конфигурацию"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_timeman_status(self):
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

    def parse_bitrix_time(self, time_str):
        """Преобразовать время из формата Bitrix24 в локальное datetime"""
        # Формат: "2025-11-26T09:13:20+05:00"
        from dateutil import parser

        # Парсим время с timezone
        dt_with_tz = parser.parse(time_str)

        # Конвертируем в локальное время (системную временную зону)
        local_dt = dt_with_tz.astimezone()

        # Возвращаем naive datetime в локальной временной зоне
        return local_dt.replace(tzinfo=None)

    def parse_time_leaks(self, time_leaks_str):
        """Преобразовать TIME_LEAKS в секунды"""
        # Формат: "01:41:26" (ЧЧ:ММ:СС)
        if not time_leaks_str:
            return 0

        try:
            parts = time_leaks_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except:
            return 0

        return 0

    def update_menu_for_running_workday(self):
        """Обновить меню для активного рабочего дня"""
        self.menu.clear()
        pause_item = rumps.MenuItem("Поставить на паузу", callback=self.pause_workday)
        stop_item = rumps.MenuItem("Завершить рабочий день", callback=self.stop_workday)

        # Помодоро
        pomodoro_title = "🍅 Помодоро: Выкл" if self.pomodoro_enabled else "🍅 Помодоро: Вкл"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.show_hour_stats)
        settings_item = rumps.MenuItem("Настройки", callback=self.settings)
        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.quit_app)

        self.menu = [
            pause_item,
            stop_item,
            None,
            pomodoro_item,
            skip_pomodoro_item,
            None,
            stats_today,
            stats_hour,
            None,
            settings_item,
            aw_item,
            None,
            quit_item
        ]

    def update_menu_for_paused_workday(self):
        """Обновить меню для паузы рабочего дня"""
        self.menu.clear()
        resume_item = rumps.MenuItem("Продолжить рабочий день", callback=self.resume_workday)
        stop_item = rumps.MenuItem("Завершить рабочий день", callback=self.stop_workday)

        # Помодоро
        pomodoro_title = "🍅 Помодоро: Выкл" if self.pomodoro_enabled else "🍅 Помодоро: Вкл"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.show_hour_stats)
        settings_item = rumps.MenuItem("Настройки", callback=self.settings)
        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.quit_app)

        self.menu = [
            resume_item,
            stop_item,
            None,
            pomodoro_item,
            skip_pomodoro_item,
            None,
            stats_today,
            stats_hour,
            None,
            settings_item,
            aw_item,
            None,
            quit_item
        ]

    def update_menu_for_stopped_workday(self):
        """Обновить меню для остановленного рабочего дня"""
        self.menu.clear()
        start_item = rumps.MenuItem("Начать рабочий день", callback=self.start_workday)

        # Помодоро
        pomodoro_title = "🍅 Помодоро: Выкл" if self.pomodoro_enabled else "🍅 Помодоро: Вкл"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.show_hour_stats)
        settings_item = rumps.MenuItem("Настройки", callback=self.settings)
        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.quit_app)

        self.menu = [
            start_item,
            None,
            pomodoro_item,
            skip_pomodoro_item,
            None,
            stats_today,
            stats_hour,
            None,
            settings_item,
            aw_item,
            None,
            quit_item
        ]

    def update_timer(self, _):
        """Обновление таймера в menu bar"""
        # Обновляем помодоро таймер
        if self.pomodoro_enabled and self.pomodoro.is_running:
            self.pomodoro.tick()

        # Отображение в menu bar
        if self.pomodoro_enabled and self.pomodoro.is_running:
            # Показываем помодоро таймер
            emoji = self.pomodoro.get_emoji()
            time_str = self.pomodoro.get_display_time()
            progress = self.pomodoro.get_progress()
            self.title = f"{emoji} {progress} {time_str}"
        elif self.is_paused and self.pause_start_time:
            # Показываем таймер паузы - начинается с TIME_LEAKS и тикает вверх
            pause_elapsed = datetime.now() - self.pause_start_time
            pause_seconds = self.time_leaks_seconds + pause_elapsed.total_seconds()

            hours = int(pause_seconds // 3600)
            minutes = int((pause_seconds % 3600) // 60)
            seconds = int(pause_seconds % 60)
            self.title = f"⏸ {hours:02d}:{minutes:02d}:{seconds:02d}"
        elif self.is_running and self.start_time:
            # Показываем рабочее время - общее время минус простои
            total_elapsed = datetime.now() - self.start_time
            work_seconds = total_elapsed.total_seconds() - self.time_leaks_seconds

            if work_seconds < 0:
                work_seconds = 0

            hours = int(work_seconds // 3600)
            minutes = int((work_seconds % 3600) // 60)
            seconds = int(work_seconds % 60)
            self.title = f"⏱ {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            self.title = "⏱ 00:00:00"

    def start_workday(self, _):
        """Начать рабочий день"""
        if not self.webhook_url:
            rumps.alert("Ошибка", "Настройте webhook URL в настройках")
            return

        try:
            # Сначала проверяем статус
            status = self.get_timeman_status()

            should_open_new_day = False

            if status and status.get('TIME_START'):
                # Есть TIME_START - проверяем его возраст и статус
                time_start_str = status.get('TIME_START')
                time_start = self.parse_bitrix_time(time_start_str)
                hours_since_start = (datetime.now() - time_start).total_seconds() / 3600
                current_status = status.get('STATUS')

                # Если день закрыт (CLOSED) или TIME_START старше 24 часов - открываем новый день
                if current_status == 'CLOSED' or hours_since_start > 24:
                    should_open_new_day = True
                else:
                    # День открыт (OPENED или PAUSED) и TIME_START в пределах сегодня - синхронизируем
                    time_leaks_str = status.get('TIME_LEAKS', '00:00:00')
                    is_paused_in_bitrix = current_status == 'PAUSED'

                    self.start_time = time_start
                    self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)
                    self.is_running = True

                    # Проверяем, стоит ли день на паузе
                    if is_paused_in_bitrix:
                        self.is_paused = True
                        self.pause_start_time = datetime.now()
                        rumps.notification(
                            "Bitrix24 Tracker",
                            "Синхронизация",
                            "Рабочий день на паузе"
                        )
                        self.update_menu_for_paused_workday()
                        return
                    else:
                        self.is_paused = False

                    rumps.notification(
                        "Bitrix24 Tracker",
                        "Синхронизация",
                        "Рабочий день продолжается"
                    )
            else:
                # Нет TIME_START - нужно открыть день
                should_open_new_day = True

            # Если нужно открыть день
            if should_open_new_day:
                response = requests.post(
                    f"{self.webhook_url}timeman.open",
                    timeout=10
                )

                if response.status_code == 200:
                    # После открытия получаем TIME_START и TIME_LEAKS
                    new_status = self.get_timeman_status()

                    if new_status and new_status.get('TIME_START'):
                        time_start = self.parse_bitrix_time(new_status.get('TIME_START'))
                        time_leaks_str = new_status.get('TIME_LEAKS', '00:00:00')

                        self.start_time = time_start
                        self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)
                    else:
                        self.start_time = datetime.now()
                        self.time_leaks_seconds = 0

                    self.is_running = True
                    self.is_paused = False

                    rumps.notification(
                        "Bitrix24 Tracker",
                        "Рабочий день начат",
                        "ActivityWatch собирает статистику"
                    )
                else:
                    rumps.alert("Ошибка", f"Bitrix24 вернул код: {response.status_code}")
                    return

            # Обновляем меню (не очищаем полностью, а обновляем элементы)
            self.update_menu_for_running_workday()

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))

    def pause_workday(self, _):
        """Поставить рабочий день на паузу"""
        try:
            # Сначала получаем текущий статус для TIME_LEAKS
            status = self.get_timeman_status()

            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус из Bitrix24")
                return

            # Ставим на паузу в Bitrix24
            response = requests.post(
                f"{self.webhook_url}timeman.pause",
                timeout=10
            )

            if response.status_code == 200:
                self.is_paused = True
                self.pause_start_time = datetime.now()

                # Сохраняем текущее значение TIME_LEAKS
                time_leaks_str = status.get('TIME_LEAKS', '00:00:00')
                self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)

                rumps.notification(
                    "Bitrix24 Tracker",
                    "Пауза",
                    "Рабочий день поставлен на паузу"
                )

                # Обновляем меню
                self.update_menu_for_paused_workday()
            else:
                rumps.alert("Ошибка", f"Bitrix24 вернул код: {response.status_code}")

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))

    def resume_workday(self, _):
        """Продолжить рабочий день после паузы"""
        try:
            # Проверяем текущий статус
            status_before = self.get_timeman_status()

            # Если установлен TIME_FINISH, значит день был закрыт - нужно открыть заново
            # Если просто PAUSED без TIME_FINISH - используем timeman.pause для переключения
            if status_before and status_before.get('TIME_FINISH'):
                api_method = "timeman.open"
            else:
                api_method = "timeman.pause"

            # Вызываем соответствующий API метод
            response = requests.post(
                f"{self.webhook_url}{api_method}",
                timeout=10
            )

            if response.status_code == 200:
                # Проверяем статус ПОСЛЕ вызова
                status_after = self.get_timeman_status()
                current_status = status_after.get('STATUS') if status_after else None

                # Если статус изменился на OPENED - успех
                if current_status == 'OPENED':
                    if status_after:
                        time_leaks_str = status_after.get('TIME_LEAKS', '00:00:00')
                        self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)

                    self.is_paused = False
                    self.pause_start_time = None

                    rumps.notification(
                        "Bitrix24 Tracker",
                        "Работа продолжена",
                        "Рабочий день продолжен"
                    )

                    # Обновляем меню
                    self.update_menu_for_running_workday()
                else:
                    rumps.alert("Ошибка", f"Не удалось продолжить работу. Статус: {current_status}")
            else:
                rumps.alert("Ошибка", f"Bitrix24 вернул код: {response.status_code}")

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))

    def stop_workday(self, _):
        """Завершить рабочий день"""
        try:
            # Проверяем статус перед завершением
            status = self.get_timeman_status()

            if not status:
                rumps.alert("Ошибка", "Не удалось получить статус из Bitrix24")
                return

            # Проверяем, не закрыт ли день уже
            current_status = status.get('STATUS')
            if current_status == 'CLOSED':
                rumps.alert("День уже завершен", "Рабочий день уже был завершен в Bitrix24")

                # Сбрасываем локальное состояние
                self.is_running = False
                self.is_paused = False
                self.start_time = None
                self.time_leaks_seconds = 0
                self.pause_start_time = None

                # Обновляем меню
                self.update_menu_for_stopped_workday()
                return

            # Закрываем день в Bitrix24
            response = requests.post(
                f"{self.webhook_url}timeman.close",
                timeout=10
            )

            if response.status_code == 200:
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
                self.show_day_stats()

                # Уведомление
                rumps.notification(
                    "Bitrix24 Tracker",
                    "Рабочий день завершен",
                    f"Отработано: {hours}ч {minutes}мин"
                )

                # Сбрасываем все переменные состояния
                self.start_time = None
                self.time_leaks_seconds = 0
                self.pause_start_time = None

                # Обновляем меню
                self.update_menu_for_stopped_workday()
            elif response.status_code == 400:
                # Ошибка 400 обычно означает, что день уже закрыт
                rumps.alert("День уже завершен", "Рабочий день уже был завершен в Bitrix24")

                # Сбрасываем локальное состояние
                self.is_running = False
                self.is_paused = False
                self.start_time = None
                self.time_leaks_seconds = 0
                self.pause_start_time = None

                # Обновляем меню
                self.update_menu_for_stopped_workday()
            else:
                rumps.alert("Ошибка", f"Bitrix24 вернул код: {response.status_code}")

        except Exception as e:
            rumps.alert("Ошибка подключения", str(e))

    def show_hour_stats(self, _):
        """Показать статистику за последний час"""
        if not self.aw_available:
            rumps.alert("ActivityWatch не доступен", 
                       "Убедитесь что ActivityWatch запущен")
            return
        
        try:
            stats = self.get_activity_stats(hours=1)
            self.display_stats(stats, "Статистика за последний час")
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")
    
    def show_day_stats(self, _=None):
        """Показать статистику за сегодня"""
        if not self.aw_available:
            rumps.alert("ActivityWatch не доступен",
                       "Убедитесь что ActivityWatch запущен")
            return

        try:
            # Получаем статус из Bitrix24
            bitrix_status = self.get_timeman_status()

            # Считаем от начала дня
            now = datetime.now()
            hours_since_midnight = now.hour + (now.minute / 60)

            stats = self.get_activity_stats(hours=hours_since_midnight)
            self.display_stats(stats, "Статистика за сегодня", bitrix_status)
        except Exception as e:
            rumps.alert("Ошибка", f"Не удалось получить статистику: {e}")
    
    def get_activity_stats(self, hours=8):
        """Получить статистику активности из ActivityWatch"""
        # Получаем имя bucket
        hostname = self.aw_client.client_hostname
        bucket_id = f"aw-watcher-window_{hostname}"
        
        # Проверяем что bucket существует
        buckets = self.aw_client.get_buckets()
        if bucket_id not in buckets:
            raise Exception("Bucket aw-watcher-window не найден. Запустите ActivityWatch.")
        
        # Временной период
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        
        # Получаем события
        events = self.aw_client.get_events(bucket_id, limit=10000)
        
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
    
    def display_stats(self, stats, title, bitrix_status=None):
        """Отобразить статистику"""
        if not stats:
            rumps.alert(title, "Нет данных за этот период")
            return

        # Формируем текст
        message = ""

        # Добавляем информацию из Bitrix24
        if bitrix_status:
            status_text = bitrix_status.get('STATUS', 'N/A')

            # Общее время и рабочее время
            if status_text == 'OPENED':
                # Рассчитываем времена
                if bitrix_status.get('TIME_START'):
                    time_start = self.parse_bitrix_time(bitrix_status.get('TIME_START'))
                    time_leaks_seconds = self.parse_time_leaks(bitrix_status.get('TIME_LEAKS', '00:00:00'))

                    # Общее время (от TIME_START до сейчас)
                    total_seconds = (datetime.now() - time_start).total_seconds()
                    total_hours = int(total_seconds // 3600)
                    total_minutes = int((total_seconds % 3600) // 60)

                    # Рабочее время (общее - паузы)
                    work_seconds = total_seconds - time_leaks_seconds
                    work_hours = int(work_seconds // 3600)
                    work_minutes = int((work_seconds % 3600) // 60)

                    message += f"⏱  Общее время:\n"
                    message += f"    {total_hours}ч {total_minutes}мин\n\n"
                    message += f"📊  Рабочее время (Bitrix24):\n"
                    message += f"    {work_hours}ч {work_minutes}мин\n\n"
            elif status_text == 'CLOSED' and bitrix_status.get('DURATION'):
                # День закрыт - показываем DURATION
                duration = bitrix_status.get('DURATION')
                message += f"📊  Рабочее время (Bitrix24):\n"
                message += f"    {duration}\n\n"

            # Время паузы
            time_leaks = bitrix_status.get('TIME_LEAKS', '00:00:00')
            if time_leaks and time_leaks != '00:00:00':
                message += f"⏸  Время паузы (Bitrix24):\n"
                message += f"    {time_leaks}\n\n"

            message += "━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += "ActivityWatch статистика:\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"

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

        # Итого
        total_hours = int(total_seconds // 3600)
        total_minutes = int((total_seconds % 3600) // 60)
        message += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"Всего (ActivityWatch):\n"
        message += f"{total_hours}ч {total_minutes}мин"

        # Показываем окно без поля ввода
        rumps.alert(title, message)

    # === Pomodoro callbacks ===

    def on_pomodoro_state_change(self, state, remaining_seconds):
        """Callback при изменении состояния помодоро"""
        # Обновление отображается в update_timer
        pass

    def on_pomodoro_break_start(self, break_state):
        """Callback при начале перерыва"""
        # Автопауза в Bitrix24, если включена
        auto_pause = self.config.get('pomodoro', {}).get('auto_pause_bitrix', True)

        if auto_pause and self.is_running and not self.is_paused:
            try:
                response = requests.post(
                    f"{self.webhook_url}timeman.pause",
                    timeout=10
                )

                if response.status_code == 200:
                    # Проверяем статус ПОСЛЕ вызова
                    status_after = self.get_timeman_status()

                    if status_after and status_after.get('STATUS') == 'PAUSED':
                        self.is_paused = True
                        self.pause_start_time = datetime.now()

                        # Получаем TIME_LEAKS
                        time_leaks_str = status_after.get('TIME_LEAKS', '00:00:00')
                        self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)

                        # Обновляем меню
                        self.update_menu_for_paused_workday()
            except Exception as e:
                print(f"Ошибка автопаузы Б24: {e}")

        # Уведомление
        if break_state == PomodoroState.SHORT_BREAK:
            rumps.notification(
                "Помодоро",
                "Короткий перерыв",
                f"Время отдохнуть! ☕ {self.pomodoro.config.get('short_break', 5)} мин"
            )
        elif break_state == PomodoroState.LONG_BREAK:
            rumps.notification(
                "Помодоро",
                "Длинный перерыв",
                f"Заслуженный отдых! 🌴 {self.pomodoro.config.get('long_break', 15)} мин"
            )

    def on_pomodoro_break_end(self):
        """Callback при окончании перерыва"""
        # Автопродолжение работы в Bitrix24
        auto_pause = self.config.get('pomodoro', {}).get('auto_pause_bitrix', True)

        if auto_pause and self.is_running and self.is_paused:
            # Проверяем статус в Б24
            status = self.get_timeman_status()

            try:
                # ВАЖНО: timeman.pause работает как toggle ТОЛЬКО если TIME_FINISH не установлен
                # Если TIME_FINISH установлен (день "закрыт" для паузы) - нужен timeman.open
                if status and status.get('TIME_FINISH'):
                    api_method = "timeman.open"
                else:
                    api_method = "timeman.pause"

                response = requests.post(
                    f"{self.webhook_url}{api_method}",
                    timeout=10
                )

                if response.status_code == 200:
                    # Проверяем результат
                    new_status = self.get_timeman_status()

                    if new_status and new_status.get('STATUS') == 'OPENED':
                        self.is_paused = False
                        self.pause_start_time = None

                        # Обновляем TIME_LEAKS
                        time_leaks_str = new_status.get('TIME_LEAKS', '00:00:00')
                        self.time_leaks_seconds = self.parse_time_leaks(time_leaks_str)

                        # Обновляем меню
                        self.update_menu_for_running_workday()
            except Exception as e:
                print(f"Ошибка автопродолжения Б24: {e}")

        # Уведомление
        rumps.notification(
            "Помодоро",
            "Перерыв окончен",
            f"Возвращаемся к работе! 🍅 {self.pomodoro.config.get('work_duration', 25)} мин"
        )

    # === Pomodoro controls ===

    def toggle_pomodoro(self, sender):
        """Включить/выключить помодоро"""
        self.pomodoro_enabled = not self.pomodoro_enabled

        if self.pomodoro_enabled:
            self.pomodoro.start()
            sender.title = "🍅 Помодоро: Выкл"
            rumps.notification(
                "Помодоро",
                "Помодоро включен",
                f"Рабочая сессия: {self.pomodoro.config.get('work_duration', 25)} мин"
            )
        else:
            self.pomodoro.stop()
            sender.title = "🍅 Помодоро: Вкл"
            rumps.notification(
                "Помодоро",
                "Помодоро выключен",
                "Таймер остановлен"
            )

        # Сохраняем настройку
        if 'pomodoro' not in self.config:
            self.config['pomodoro'] = {}
        self.config['pomodoro']['enabled'] = self.pomodoro_enabled
        self.save_config()

    def skip_pomodoro(self, _):
        """Пропустить текущую сессию помодоро"""
        if self.pomodoro_enabled and self.pomodoro.is_running:
            self.pomodoro.skip()
            rumps.notification(
                "Помодоро",
                "Сессия пропущена",
                "Переход к следующей"
            )
        else:
            rumps.alert("Помодоро не активен", "Включите помодоро для использования этой функции")

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
            self.save_config()
            rumps.alert("Настройки", "Webhook URL сохранен")
    
    def open_activitywatch(self, _):
        """Открыть веб-интерфейс ActivityWatch"""
        import webbrowser
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

if __name__ == "__main__":
    BitrixWorkdayTracker().run()
