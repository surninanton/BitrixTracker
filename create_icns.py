#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
import os
import subprocess

# Создаем iconset директорию
iconset_dir = 'icon.iconset'
os.makedirs(iconset_dir, exist_ok=True)

# Открываем нашу PNG иконку
img = Image.open('icon.png')

# Создаем все необходимые размеры для .icns
sizes = [
    (16, 'icon_16x16.png'),
    (32, 'icon_16x16@2x.png'),
    (32, 'icon_32x32.png'),
    (64, 'icon_32x32@2x.png'),
    (128, 'icon_128x128.png'),
    (256, 'icon_128x128@2x.png'),
    (256, 'icon_256x256.png'),
    (512, 'icon_256x256@2x.png'),
    (512, 'icon_512x512.png'),
    (1024, 'icon_512x512@2x.png'),
]

for size, filename in sizes:
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(os.path.join(iconset_dir, filename))

# Конвертируем iconset в icns используя iconutil
subprocess.run(['iconutil', '-c', 'icns', iconset_dir])

print("✅ Файл icon.icns создан!")

# Удаляем временную директорию
import shutil
shutil.rmtree(iconset_dir)