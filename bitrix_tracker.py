#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
import os
from datetime import datetime

# Настройка логирования FIRST - до импорта других модулей
from utils.logger import setup_logging, get_logger
setup_logging()
logger = get_logger('main')

# Локальные импорты
from core.pomodoro import PomodoroTimer, PomodoroState
from core.bitrix_client import BitrixClient
from core.activity_watch import ActivityWatchService
from core.workday import WorkdayManager
from core.database import Database
from ui.menu import MenuManager
from ui.statistics import StatisticsManager
from ui.settings_window import SettingsWindow
from utils.config import load_config, save_config
from utils.time_parser import parse_time_leaks


class BitrixWorkdayTracker(rumps.App):
    def __init__(self):
        super(BitrixWorkdayTracker, self).__init__(
            "⏱ 00:00:00",
            quit_button=None
        )

        # Устанавливаем иконку
        self._setup_icon()

        # Загружаем конфигурацию
        self.config = load_config()
        webhook_url = self.config.get('webhook_url', '')

        # Инициализируем сервисы
        self.db = Database()  # База данных для статистики
        self.bitrix = BitrixClient(webhook_url)
        self.activity_watch = ActivityWatchService()
        self.workday = WorkdayManager(self.bitrix, on_workday_start=self.on_workday_start)
        self.menu_manager = MenuManager(self)
        self.statistics = StatisticsManager(self.activity_watch, self.bitrix)

        # ID текущей помодоро сессии в БД
        self.current_pomodoro_session_id = None

        # Таймер для проверки настроек
        self.check_settings_timer = None

        # Pomodoro
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
            on_break_end=self.on_pomodoro_break_end,
            on_work_start=self.on_pomodoro_work_start,
            on_session_complete=self.on_pomodoro_session_complete,
            on_session_skip=self.on_pomodoro_session_skip
        )
        # При старте помодоро всегда выключен, независимо от конфига
        self.pomodoro_enabled = False

        # Таймер
        self.timer = rumps.Timer(self.update_timer, 1)
        self.timer.start()

        # Начальное меню
        self.menu_manager.update_for_stopped_workday()

    def _setup_icon(self):
        """Установить иконку приложения"""
        try:
            import AppKit
            app = AppKit.NSApplication.sharedApplication()
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
            if os.path.exists(icon_path):
                image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
                if image:
                    app.setApplicationIconImage_(image)
        except Exception as e:
            logger.warning(f"Не удалось установить иконку: {e}")

    # === Timer ===

    def update_timer(self, _):
        """Обновление таймера в menu bar"""
        # Обновляем помодоро таймер
        if self.pomodoro_enabled and self.pomodoro.is_running:
            self.pomodoro.tick()

        # Отображение в menu bar
        if self.pomodoro_enabled and self.pomodoro.is_running:
            self._update_pomodoro_title()
        elif self.workday.is_paused:
            self._update_pause_title()
        elif self.workday.is_running:
            self._update_work_title()
        else:
            self.title = "⏱ 00:00:00"

    def _update_pomodoro_title(self):
        """Обновить заголовок для помодоро"""
        emoji = self.pomodoro.get_emoji()
        time_str = self.pomodoro.get_display_time()
        progress = self.pomodoro.get_progress()
        self.title = f"{emoji} {progress} {time_str}"

    def _update_pause_title(self):
        """Обновить заголовок для паузы"""
        hours, minutes, seconds = self.workday.get_pause_time()
        self.title = f"⏸ {hours:02d}:{minutes:02d}:{seconds:02d}"

    def _update_work_title(self):
        """Обновить заголовок для рабочего времени"""
        hours, minutes, seconds = self.workday.get_work_time()
        self.title = f"⏱ {hours:02d}:{minutes:02d}:{seconds:02d}"

    # === Workday callbacks ===

    def start_workday(self, _):
        """Начать рабочий день"""
        self.workday.start(
            on_sync_paused=self.menu_manager.update_for_paused_workday,
            on_sync_running=self.menu_manager.update_for_running_workday,
            on_new_day=self.menu_manager.update_for_running_workday
        )

    def pause_workday(self, _):
        """Поставить рабочий день на паузу"""
        if self.workday.pause():
            self.menu_manager.update_for_paused_workday()

    def resume_workday(self, _):
        """Продолжить рабочий день"""
        if self.workday.resume():
            self.menu_manager.update_for_running_workday()

    def stop_workday(self, _):
        """Завершить рабочий день"""
        if self.workday.stop(on_stats=self.show_day_stats):
            self.menu_manager.update_for_stopped_workday()

    # === Statistics callbacks ===

    def show_hour_stats(self, _):
        """Показать статистику за час"""
        self.statistics.show_hour_stats()

    def show_day_stats(self, _=None):
        """Показать статистику за сегодня"""
        self.statistics.show_day_stats()

    # === Integration callbacks ===

    def on_workday_start(self):
        """Callback при успешном начале рабочего дня"""
        # Проверяем настройку автозапуска помодоро
        start_pomodoro = self.config.get('pomodoro', {}).get('start_pomodoro_with_workday', False)

        if start_pomodoro and not self.pomodoro_enabled:
            self.pomodoro_enabled = True
            self.pomodoro.start()
            rumps.notification("Помодоро", "Автозапуск", f"Помодоро запущен вместе с рабочим днем")

    def on_pomodoro_work_start(self):
        """Callback при начале рабочей сессии помодоро"""
        # Начинаем новую сессию в БД
        session_type = 'work'
        planned_duration = self.config.get('pomodoro', {}).get('work_duration', 25) * 60
        self.current_pomodoro_session_id = self.db.start_pomodoro_session(session_type, planned_duration)
        logger.info(f"Начата рабочая сессия помодоро (ID: {self.current_pomodoro_session_id})")

        # Проверяем настройку автозапуска рабочего дня
        start_workday = self.config.get('pomodoro', {}).get('start_workday_with_pomodoro', False)

        if start_workday:
            if not self.workday.is_running:
                # Рабочий день не запущен - запускаем
                self.start_workday(None)
                rumps.notification("Bitrix24", "Автозапуск", "Рабочий день начат вместе с помодоро")
            elif self.workday.is_paused:
                # Рабочий день на паузе - возобновляем
                self.resume_workday(None)
                rumps.notification("Bitrix24", "Автовозобновление", "Рабочий день возобновлен вместе с помодоро")

    # === Pomodoro callbacks ===

    def on_pomodoro_state_change(self, state, remaining_seconds):
        """Callback при изменении состояния помодоро"""
        pass

    def on_pomodoro_break_start(self, break_state):
        """Callback при начале перерыва"""
        # Начинаем сессию перерыва в БД
        if break_state == PomodoroState.SHORT_BREAK:
            session_type = 'short_break'
            planned_duration = self.config.get('pomodoro', {}).get('short_break', 5) * 60
        else:  # LONG_BREAK
            session_type = 'long_break'
            planned_duration = self.config.get('pomodoro', {}).get('long_break', 15) * 60

        self.current_pomodoro_session_id = self.db.start_pomodoro_session(session_type, planned_duration)
        logger.info(f"Начат перерыв помодоро (ID: {self.current_pomodoro_session_id}, тип: {session_type})")

        # Проверяем режим автопаузы
        pause_mode = self.config.get('pomodoro', {}).get('bitrix_pause_mode', 'all_breaks')
        should_pause = False

        if pause_mode == 'all_breaks':
            should_pause = True
        elif pause_mode == 'long_breaks_only':
            should_pause = (break_state == PomodoroState.LONG_BREAK)
        # если 'never', то should_pause остается False

        if should_pause and self.workday.is_running and not self.workday.is_paused:
            try:
                if self.bitrix.pause_workday():
                    status_after = self.bitrix.get_status()

                    if status_after and status_after.get('STATUS') == 'PAUSED':
                        self.workday.is_paused = True
                        self.workday.pause_start_time = datetime.now()

                        time_leaks_str = status_after.get('TIME_LEAKS', '00:00:00')
                        self.workday.time_leaks_seconds = parse_time_leaks(time_leaks_str)

                        self.menu_manager.update_for_paused_workday()
            except Exception as e:
                logger.error(f"Ошибка автопаузы Б24: {e}")

        # Уведомление
        if break_state == PomodoroState.SHORT_BREAK:
            rumps.notification("Помодоро", "Короткий перерыв", f"Время отдохнуть! ☕ {self.pomodoro.config.get('short_break', 5)} мин")
        elif break_state == PomodoroState.LONG_BREAK:
            rumps.notification("Помодоро", "Длинный перерыв", f"Заслуженный отдых! 🌴 {self.pomodoro.config.get('long_break', 15)} мин")

    def on_pomodoro_break_end(self):
        """Callback при окончании перерыва"""
        auto_pause = self.config.get('pomodoro', {}).get('auto_pause_bitrix', True)

        if auto_pause and self.workday.is_running and self.workday.is_paused:
            status = self.bitrix.get_status()

            try:
                if self.bitrix.resume_workday(status):
                    new_status = self.bitrix.get_status()

                    if new_status and new_status.get('STATUS') == 'OPENED':
                        self.workday.is_paused = False
                        self.workday.pause_start_time = None

                        time_leaks_str = new_status.get('TIME_LEAKS', '00:00:00')
                        self.workday.time_leaks_seconds = parse_time_leaks(time_leaks_str)

                        self.menu_manager.update_for_running_workday()
            except Exception as e:
                logger.error(f"Ошибка автопродолжения Б24: {e}")

        # Уведомление
        rumps.notification("Помодоро", "Перерыв окончен", f"Возвращаемся к работе! 🍅 {self.pomodoro.config.get('work_duration', 25)} мин")

    def on_pomodoro_session_complete(self, state):
        """Callback при завершении помодоро сессии"""
        # Закрываем сессию в БД (completed=True)
        if self.current_pomodoro_session_id:
            self.db.end_pomodoro_session(self.current_pomodoro_session_id, completed=True, skipped=False)
            logger.info(f"Сессия помодоро завершена (ID: {self.current_pomodoro_session_id}, тип: {state.value})")
            self.current_pomodoro_session_id = None

    def on_pomodoro_session_skip(self, state):
        """Callback при пропуске помодоро сессии"""
        # Закрываем сессию в БД (skipped=True)
        if self.current_pomodoro_session_id:
            self.db.end_pomodoro_session(self.current_pomodoro_session_id, completed=False, skipped=True)
            logger.info(f"Сессия помодоро пропущена (ID: {self.current_pomodoro_session_id}, тип: {state.value})")
            self.current_pomodoro_session_id = None

    # === Pomodoro controls ===

    def toggle_pomodoro(self, sender):
        """Включить/выключить помодоро"""
        self.pomodoro_enabled = not self.pomodoro_enabled

        if self.pomodoro_enabled:
            self.pomodoro.start()
            rumps.notification("Помодоро", "Помодоро запущен", f"Рабочая сессия: {self.pomodoro.config.get('work_duration', 25)} мин")
        else:
            self.pomodoro.stop()
            rumps.notification("Помодоро", "Помодоро остановлен", "Таймер остановлен")

        # Обновляем меню для корректного отображения состояния кнопки
        if self.workday.is_running:
            if self.workday.is_paused:
                self.menu_manager.update_for_paused_workday()
            else:
                self.menu_manager.update_for_running_workday()
        else:
            self.menu_manager.update_for_stopped_workday()

        if 'pomodoro' not in self.config:
            self.config['pomodoro'] = {}
        self.config['pomodoro']['enabled'] = self.pomodoro_enabled
        save_config(self.config)

    def skip_pomodoro(self, _):
        """Пропустить текущую сессию помодоро"""
        if self.pomodoro_enabled and self.pomodoro.is_running:
            self.pomodoro.skip()
            rumps.notification("Помодоро", "Сессия пропущена", "Переход к следующей")
        else:
            rumps.alert("Помодоро не активен", "Включите помодоро для использования этой функции")

    # === Settings ===

    def settings(self, _):
        """Открыть окно настроек"""
        # Перезагружаем конфиг перед открытием окна
        self.config = load_config()

        # Создаем и показываем окно
        logger.info("Открываю окно настроек")
        settings_win = SettingsWindow.alloc().initWithConfig_(self.config)

        # Сохраняем ссылку чтобы окно не уничтожилось сборщиком мусора
        self.current_settings_window = settings_win
        settings_win.show()

        # Создаем таймер для проверки закрытия окна и обновления конфига
        def check_settings_closed(_):
            # Перезагружаем конфиг после закрытия окна
            self.config = load_config()
            if hasattr(self, 'bitrix'):
                self.bitrix.webhook_url = self.config.get('webhook_url', '')
            if hasattr(self, 'pomodoro'):
                self.pomodoro.config = self.config.get('pomodoro', {})
            logger.info("Конфигурация обновлена в приложении")

        # Останавливаем предыдущий таймер если он есть
        if self.check_settings_timer:
            self.check_settings_timer.stop()

        # Запускаем новый таймер
        self.check_settings_timer = rumps.Timer(check_settings_closed, 1)
        self.check_settings_timer.start()

    def open_activitywatch(self, _):
        """Открыть веб-интерфейс ActivityWatch"""
        import webbrowser
        webbrowser.open('http://localhost:5600')

    def quit_app(self, _):
        """Выход с правильной очисткой ресурсов"""
        try:
            if self.workday.is_running:
                response = rumps.alert(
                    "Рабочий день активен",
                    "Завершить день и выйти?",
                    ok="Да",
                    cancel="Отмена"
                )
                if response == 1:
                    self.stop_workday(None)
                else:
                    return  # Отменили выход

            # Очищаем ресурсы
            if hasattr(self, 'timer') and self.timer:
                self.timer.stop()

            if hasattr(self, 'check_settings_timer') and self.check_settings_timer:
                self.check_settings_timer.stop()

            if hasattr(self, 'db') and self.db:
                self.db.close()

            rumps.quit_application()
        except Exception as e:
            logger.exception(f"Ошибка при выходе: {e}")
            rumps.quit_application()


if __name__ == "__main__":
    BitrixWorkdayTracker().run()