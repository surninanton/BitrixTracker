#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps


class MenuManager:
    """Управление меню приложения"""

    def __init__(self, app):
        """
        Args:
            app: экземпляр BitrixWorkdayTracker
        """
        self.app = app

    def update_current_menu(self):
        """Обновить текущее меню в зависимости от состояния"""
        if self.app.workday.is_running:
            if self.app.workday.is_paused:
                self.update_for_paused_workday()
            else:
                self.update_for_running_workday()
        else:
            self.update_for_stopped_workday()

    def update_for_running_workday(self):
        """Обновить меню для активного рабочего дня"""
        self.app.menu.clear()

        pause_item = rumps.MenuItem("Поставить на паузу", callback=self.app.pause_workday)
        stop_item = rumps.MenuItem("Завершить рабочий день", callback=self.app.stop_workday)

        # Помодоро - показываем текущее состояние и действие
        if self.app.pomodoro_enabled:
            pomodoro_title = "🍅 Остановить Помодоро"
        else:
            pomodoro_title = "🍅 Запустить Помодоро"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.app.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.app.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.app.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.app.show_hour_stats)

        # Единое окно настроек
        settings_item = rumps.MenuItem("⚙️ Настройки", callback=self.app.settings)

        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.app.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.app.quit_app)

        self.app.menu = [
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

    def update_for_paused_workday(self):
        """Обновить меню для паузы рабочего дня"""
        self.app.menu.clear()

        resume_item = rumps.MenuItem("Продолжить рабочий день", callback=self.app.resume_workday)
        stop_item = rumps.MenuItem("Завершить рабочий день", callback=self.app.stop_workday)

        # Помодоро - показываем текущее состояние и действие
        if self.app.pomodoro_enabled:
            pomodoro_title = "🍅 Остановить Помодоро"
        else:
            pomodoro_title = "🍅 Запустить Помодоро"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.app.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.app.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.app.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.app.show_hour_stats)

        # Единое окно настроек
        settings_item = rumps.MenuItem("⚙️ Настройки", callback=self.app.settings)

        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.app.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.app.quit_app)

        self.app.menu = [
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

    def update_for_stopped_workday(self):
        """Обновить меню для остановленного рабочего дня"""
        self.app.menu.clear()

        start_item = rumps.MenuItem("Начать рабочий день", callback=self.app.start_workday)

        # Помодоро - показываем текущее состояние и действие
        if self.app.pomodoro_enabled:
            pomodoro_title = "🍅 Остановить Помодоро"
        else:
            pomodoro_title = "🍅 Запустить Помодоро"
        pomodoro_item = rumps.MenuItem(pomodoro_title, callback=self.app.toggle_pomodoro)
        skip_pomodoro_item = rumps.MenuItem("⏭ Пропустить помодоро", callback=self.app.skip_pomodoro)

        stats_today = rumps.MenuItem("Статистика за сегодня", callback=self.app.show_day_stats)
        stats_hour = rumps.MenuItem("Статистика за час", callback=self.app.show_hour_stats)

        # Единое окно настроек
        settings_item = rumps.MenuItem("⚙️ Настройки", callback=self.app.settings)

        aw_item = rumps.MenuItem("Открыть ActivityWatch", callback=self.app.open_activitywatch)
        quit_item = rumps.MenuItem("Выход", callback=self.app.quit_app)

        self.app.menu = [
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