#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
import os
from datetime import datetime

# Локальные импорты
from core.pomodoro import PomodoroTimer, PomodoroState
from core.bitrix_client import BitrixClient
from core.activity_watch import ActivityWatchService
from core.workday import WorkdayManager
from ui.menu import MenuManager
from ui.statistics import StatisticsManager
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
        self.bitrix = BitrixClient(webhook_url)
        self.activity_watch = ActivityWatchService()
        self.workday = WorkdayManager(self.bitrix)
        self.menu_manager = MenuManager(self)
        self.statistics = StatisticsManager(self.activity_watch, self.bitrix)

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
            on_break_end=self.on_pomodoro_break_end
        )
        self.pomodoro_enabled = pomodoro_config.get('enabled', False)

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
            print(f"⚠️ Не удалось установить иконку: {e}")

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

    # === Pomodoro callbacks ===

    def on_pomodoro_state_change(self, state, remaining_seconds):
        """Callback при изменении состояния помодоро"""
        pass

    def on_pomodoro_break_start(self, break_state):
        """Callback при начале перерыва"""
        auto_pause = self.config.get('pomodoro', {}).get('auto_pause_bitrix', True)

        if auto_pause and self.workday.is_running and not self.workday.is_paused:
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
                print(f"Ошибка автопаузы Б24: {e}")

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
                print(f"Ошибка автопродолжения Б24: {e}")

        # Уведомление
        rumps.notification("Помодоро", "Перерыв окончен", f"Возвращаемся к работе! 🍅 {self.pomodoro.config.get('work_duration', 25)} мин")

    # === Pomodoro controls ===

    def toggle_pomodoro(self, sender):
        """Включить/выключить помодоро"""
        self.pomodoro_enabled = not self.pomodoro_enabled

        if self.pomodoro_enabled:
            self.pomodoro.start()
            sender.title = "🍅 Помодоро: Выкл"
            rumps.notification("Помодоро", "Помодоро включен", f"Рабочая сессия: {self.pomodoro.config.get('work_duration', 25)} мин")
        else:
            self.pomodoro.stop()
            sender.title = "🍅 Помодоро: Вкл"
            rumps.notification("Помодоро", "Помодоро выключен", "Таймер остановлен")

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
        """Настройки"""
        window = rumps.Window(
            message='Введите Bitrix24 webhook URL:',
            title='Настройки',
            default_text=self.bitrix.webhook_url,
            ok='Сохранить',
            cancel='Отмена',
            dimensions=(500, 24)
        )

        response = window.run()
        if response.clicked:
            self.bitrix.webhook_url = response.text
            self.config['webhook_url'] = response.text
            save_config(self.config)
            rumps.alert("Настройки", "Webhook URL сохранен")

    def open_activitywatch(self, _):
        """Открыть веб-интерфейс ActivityWatch"""
        import webbrowser
        webbrowser.open('http://localhost:5600')

    def quit_app(self, _):
        """Выход"""
        if self.workday.is_running:
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