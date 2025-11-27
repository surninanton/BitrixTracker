#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import json
from datetime import datetime


class Database:
    """Управление локальной базой данных SQLite"""

    def __init__(self, db_path=None):
        """
        Args:
            db_path: путь к файлу БД (по умолчанию tracker.db в корне проекта)
        """
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'tracker.db'
            )

        self.db_path = db_path
        self.conn = None
        self._init_db()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - гарантированно закрывает соединение"""
        self.close()
        return False

    def _init_db(self):
        """Инициализация БД и создание таблиц"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени

        cursor = self.conn.cursor()

        # Таблица настроек с историей изменений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_url TEXT,
                work_duration INTEGER DEFAULT 25,
                short_break INTEGER DEFAULT 5,
                long_break INTEGER DEFAULT 15,
                pomodoros_until_long_break INTEGER DEFAULT 4,
                start_pomodoro_with_workday BOOLEAN DEFAULT 0,
                start_workday_with_pomodoro BOOLEAN DEFAULT 0,
                bitrix_pause_mode TEXT DEFAULT 'all_breaks',
                check_interval INTEGER DEFAULT 5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица помодоро сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                type TEXT NOT NULL,  -- 'work', 'short_break', 'long_break'
                planned_duration INTEGER,
                actual_duration INTEGER,
                completed BOOLEAN DEFAULT 0,
                skipped BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pomodoro_date ON pomodoro_sessions(date)')

        self.conn.commit()
        print(f"✅ База данных инициализирована: {self.db_path}")

    # === Settings ===

    def save_settings(self, config_dict):
        """Сохранить настройки в БД (перезаписывает существующую запись)"""
        cursor = self.conn.cursor()

        # Извлекаем настройки помодоро
        pomodoro = config_dict.get('pomodoro', {})

        # Проверяем, есть ли уже запись
        cursor.execute('SELECT id FROM settings LIMIT 1')
        existing = cursor.fetchone()

        if existing:
            # Обновляем существующую запись
            cursor.execute('''
                UPDATE settings SET
                    webhook_url = ?,
                    work_duration = ?,
                    short_break = ?,
                    long_break = ?,
                    pomodoros_until_long_break = ?,
                    start_pomodoro_with_workday = ?,
                    start_workday_with_pomodoro = ?,
                    bitrix_pause_mode = ?,
                    check_interval = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (
                config_dict.get('webhook_url', ''),
                pomodoro.get('work_duration', 25),
                pomodoro.get('short_break', 5),
                pomodoro.get('long_break', 15),
                pomodoro.get('pomodoros_until_long_break', 4),
                1 if pomodoro.get('start_pomodoro_with_workday', False) else 0,
                1 if pomodoro.get('start_workday_with_pomodoro', False) else 0,
                pomodoro.get('bitrix_pause_mode', 'all_breaks'),
                config_dict.get('check_interval', 5),
                datetime.now().isoformat(),
                existing[0]
            ))
            print(f"✅ Настройки обновлены в БД (ID: {existing[0]})")
        else:
            # Создаем первую запись
            cursor.execute('''
                INSERT INTO settings (
                    webhook_url,
                    work_duration,
                    short_break,
                    long_break,
                    pomodoros_until_long_break,
                    start_pomodoro_with_workday,
                    start_workday_with_pomodoro,
                    bitrix_pause_mode,
                    check_interval,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_dict.get('webhook_url', ''),
                pomodoro.get('work_duration', 25),
                pomodoro.get('short_break', 5),
                pomodoro.get('long_break', 15),
                pomodoro.get('pomodoros_until_long_break', 4),
                1 if pomodoro.get('start_pomodoro_with_workday', False) else 0,
                1 if pomodoro.get('start_workday_with_pomodoro', False) else 0,
                pomodoro.get('bitrix_pause_mode', 'all_breaks'),
                config_dict.get('check_interval', 5),
                datetime.now().isoformat()
            ))
            print(f"✅ Настройки созданы в БД (ID: {cursor.lastrowid})")

        self.conn.commit()

    def get_latest_settings(self):
        """Получить последние настройки из БД. Returns: dict или None"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM settings
            ORDER BY updated_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            return {
                'webhook_url': row['webhook_url'],
                'check_interval': row['check_interval'],
                'pomodoro': {
                    'work_duration': row['work_duration'],
                    'short_break': row['short_break'],
                    'long_break': row['long_break'],
                    'pomodoros_until_long_break': row['pomodoros_until_long_break'],
                    'start_pomodoro_with_workday': bool(row['start_pomodoro_with_workday']),
                    'start_workday_with_pomodoro': bool(row['start_workday_with_pomodoro']),
                    'bitrix_pause_mode': row['bitrix_pause_mode']
                }
            }
        return None

    # === Pomodoro ===

    def start_pomodoro_session(self, session_type, planned_duration):
        """
        Начать помодоро сессию. Returns: session_id

        Args:
            session_type: 'work', 'short_break', 'long_break'
            planned_duration: планируемая длительность в секундах
        """
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        start_time = now.isoformat()

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO pomodoro_sessions (date, start_time, type, planned_duration)
            VALUES (?, ?, ?, ?)
        ''', (date, start_time, session_type, planned_duration))
        self.conn.commit()
        return cursor.lastrowid

    def end_pomodoro_session(self, session_id, completed=True, skipped=False):
        """Завершить помодоро сессию"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()

        # Получаем время начала
        cursor.execute('SELECT start_time FROM pomodoro_sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        if not row:
            return

        start_time = datetime.fromisoformat(row[0])
        end_time = datetime.fromisoformat(now)
        duration = int((end_time - start_time).total_seconds())

        cursor.execute('''
            UPDATE pomodoro_sessions
            SET end_time = ?, actual_duration = ?, completed = ?, skipped = ?
            WHERE id = ?
        ''', (now, duration, completed, skipped, session_id))
        self.conn.commit()

    # === Statistics ===

    def get_pomodoro_stats(self, date=None):
        """Получить статистику по помодоро за день"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) as total_sessions,
                SUM(CASE WHEN type = 'work' AND completed = 1 THEN 1 ELSE 0 END) as completed_work,
                SUM(CASE WHEN type = 'work' AND skipped = 1 THEN 1 ELSE 0 END) as skipped_work,
                SUM(CASE WHEN type = 'short_break' THEN 1 ELSE 0 END) as short_breaks,
                SUM(CASE WHEN type = 'long_break' THEN 1 ELSE 0 END) as long_breaks,
                SUM(CASE WHEN type = 'work' AND completed = 1 THEN actual_duration ELSE 0 END) as total_work_seconds
            FROM pomodoro_sessions
            WHERE date = ?
        ''', (date,))
        row = cursor.fetchone()
        return dict(row) if row else {}

    def get_weekly_pomodoro_stats(self):
        """Получить статистику по помодоро за неделю"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                date,
                COUNT(*) as total_sessions,
                SUM(CASE WHEN type = 'work' AND completed = 1 THEN 1 ELSE 0 END) as completed_pomodoros,
                SUM(CASE WHEN type = 'work' AND completed = 1 THEN actual_duration ELSE 0 END) as total_work_seconds
            FROM pomodoro_sessions
            WHERE date >= date('now', '-7 days')
            GROUP BY date
            ORDER BY date DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Закрыть соединение с БД"""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Деструктор"""
        self.close()