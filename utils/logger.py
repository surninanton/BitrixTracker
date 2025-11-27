#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir=None, log_level=logging.INFO):
    """
    Настроить централизованное логирование

    Args:
        log_dir: Директория для лог-файлов (по умолчанию ~/.bitrix_tracker/logs)
        log_level: Уровень логирования (по умолчанию INFO)

    Returns:
        logging.Logger: Настроенный logger
    """
    # Определяем директорию для логов
    if log_dir is None:
        log_dir = os.path.expanduser('~/.bitrix_tracker/logs')

    # Создаем директорию если её нет
    os.makedirs(log_dir, exist_ok=True)

    # Путь к лог-файлу
    log_file = os.path.join(log_dir, 'bitrix_tracker.log')

    # Создаем logger
    logger = logging.getLogger('BitrixTracker')
    logger.setLevel(log_level)

    # Предотвращаем дублирование handlers при повторном вызове
    if logger.handlers:
        return logger

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler с ротацией (5 файлов по 5MB)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler для отладки
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # В консоль только WARNING и выше
    console_handler.setFormatter(formatter)

    # Добавляем handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 80)
    logger.info("BitrixTracker logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)

    return logger


def get_logger(name=None):
    """
    Получить logger для модуля

    Args:
        name: Имя модуля (по умолчанию используется корневой BitrixTracker logger)

    Returns:
        logging.Logger: Logger для модуля
    """
    if name:
        return logging.getLogger(f'BitrixTracker.{name}')
    return logging.getLogger('BitrixTracker')