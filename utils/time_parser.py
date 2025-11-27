#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil import parser
from utils.logger import get_logger

logger = get_logger('time_parser')


def parse_bitrix_time(time_str):
    """Преобразовать время из формата Bitrix24 в локальное datetime"""
    # Формат: "2025-11-26T09:13:20+05:00"

    # Парсим время с timezone
    dt_with_tz = parser.parse(time_str)

    # Конвертируем в локальное время (системную временную зону)
    local_dt = dt_with_tz.astimezone()

    # Возвращаем naive datetime в локальной временной зоне
    return local_dt.replace(tzinfo=None)


def parse_time_leaks(time_leaks_str):
    """
    Преобразовать TIME_LEAKS в секунды

    Args:
        time_leaks_str (str): Строка формата "ЧЧ:ММ:СС" (например, "01:41:26")

    Returns:
        int: Количество секунд или 0 при ошибке
    """
    if not time_leaks_str or not isinstance(time_leaks_str, str):
        return 0

    try:
        parts = time_leaks_str.split(':')
        if len(parts) != 3:
            logger.warning(f"Неверный формат time_leaks: {time_leaks_str} (ожидается ЧЧ:ММ:СС)")
            return 0

        hours, minutes, seconds = map(int, parts)

        # Валидация
        if hours < 0 or minutes < 0 or seconds < 0:
            logger.warning(f"Отрицательные значения в time_leaks: {time_leaks_str}")
            return 0

        if minutes >= 60 or seconds >= 60:
            logger.warning(f"Недопустимые значения минут/секунд: {time_leaks_str}")
            return 0

        return hours * 3600 + minutes * 60 + seconds

    except ValueError as e:
        logger.warning(f"Не удалось распарсить time_leaks '{time_leaks_str}': {e}")
        return 0
    except Exception as e:
        logger.exception(f"Неожиданная ошибка при парсинге time_leaks '{time_leaks_str}': {e}")
        return 0