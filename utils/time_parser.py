#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil import parser


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