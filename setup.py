"""
Setup script для создания macOS приложения
"""
from setuptools import setup

APP = ['bitrix_tracker.py']
DATA_FILES = ['icon.png', 'config.json']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Bitrix24 Tracker',
        'CFBundleDisplayName': 'Bitrix24 Tracker',
        'CFBundleIdentifier': 'com.bitrix.tracker',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': False,
        'NSHighResolutionCapable': True,
    },
    'packages': [
        'rumps',
        'requests',
        'dateutil',
        'aw_client',
        'aw_core',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3',
        'AppKit',
        'Foundation',
        'objc',
        'pkg_resources',
        'setuptools',
    ],
    'includes': [
        'rumps',
        'requests',
        'json',
        'os',
        'datetime',
        'aw_client',
        'dateutil.parser',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'more_itertools',
    ],
    'excludes': [
        'tkinter',
        'test',
        'unittest',
        'distutils',
    ],
    'strip': False,  # Не удаляем отладочную информацию
    'semi_standalone': False,
    'site_packages': True,
}

setup(
    name='Bitrix24 Tracker',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)