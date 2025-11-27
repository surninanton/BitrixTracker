#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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