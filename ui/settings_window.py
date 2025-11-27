#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import AppKit
import objc
from Foundation import NSObject, NSMakeRect
import rumps
from utils.config import save_config


class SettingsWindow(NSObject):
    """Окно настроек с нормальными чекбоксами и инпутами"""

    def init(self):
        """Инициализация"""
        self = objc.super(SettingsWindow, self).init()
        if self is None:
            return None

        self.config = None
        self.app = None
        self.window = None
        self.controls = {}
        return self

    def initWithConfig_(self, config):
        """
        Args:
            config: текущая конфигурация
        """
        self = self.init()
        if self is None:
            return None

        self.config = config
        self.app = None
        return self

    def show(self):
        """Показать окно настроек"""
        # Создаем окно
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 500, 600),
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable |
            AppKit.NSWindowStyleMaskMiniaturizable,
            AppKit.NSBackingStoreBuffered,
            False
        )
        self.window.setTitle_("Настройки")

        # КРИТИЧНО: Окно НЕ должно освобождаться автоматически при закрытии
        # Мы управляем памятью вручную
        self.window.setReleasedWhenClosed_(False)

        # Устанавливаем делегата для обработки закрытия
        self.window.setDelegate_(self)

        self.window.center()

        # Контейнер для контролов
        content_view = self.window.contentView()

        y_offset = 560  # Начинаем сверху

        # === BITRIX24 ===
        label = self._create_label("BITRIX24", 20, y_offset, 460, 20, bold=True)
        content_view.addSubview_(label)
        y_offset -= 30

        # Webhook URL
        label = self._create_label("Webhook URL:", 20, y_offset, 120, 20)
        content_view.addSubview_(label)

        webhook_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(140, y_offset, 340, 24))
        webhook_field.setStringValue_(self.config.get('webhook_url', ''))
        content_view.addSubview_(webhook_field)
        self.controls['webhook_url'] = webhook_field
        y_offset -= 40

        # Разделитель
        separator1 = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(20, y_offset, 460, 1))
        separator1.setBoxType_(AppKit.NSBoxSeparator)
        content_view.addSubview_(separator1)
        y_offset -= 20

        # === ПОМОДОРО ТАЙМЕРЫ ===
        label = self._create_label("ПОМОДОРО ТАЙМЕРЫ", 20, y_offset, 460, 20, bold=True)
        content_view.addSubview_(label)
        y_offset -= 30

        pomodoro_config = self.config.get('pomodoro', {})

        # Рабочая сессия
        label = self._create_label("⏱ Рабочая сессия (мин):", 20, y_offset, 200, 20)
        content_view.addSubview_(label)
        work_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(220, y_offset, 60, 24))
        work_field.setStringValue_(str(pomodoro_config.get('work_duration', 25)))
        content_view.addSubview_(work_field)
        self.controls['work_duration'] = work_field
        y_offset -= 30

        # Короткий перерыв
        label = self._create_label("☕ Короткий перерыв (мин):", 20, y_offset, 200, 20)
        content_view.addSubview_(label)
        short_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(220, y_offset, 60, 24))
        short_field.setStringValue_(str(pomodoro_config.get('short_break', 5)))
        content_view.addSubview_(short_field)
        self.controls['short_break'] = short_field
        y_offset -= 30

        # Длинный перерыв
        label = self._create_label("🌴 Длинный перерыв (мин):", 20, y_offset, 200, 20)
        content_view.addSubview_(label)
        long_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(220, y_offset, 60, 24))
        long_field.setStringValue_(str(pomodoro_config.get('long_break', 15)))
        content_view.addSubview_(long_field)
        self.controls['long_break'] = long_field
        y_offset -= 30

        # Помодоро до длинного
        label = self._create_label("🔢 Помодоро до длинного:", 20, y_offset, 200, 20)
        content_view.addSubview_(label)
        count_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(220, y_offset, 60, 24))
        count_field.setStringValue_(str(pomodoro_config.get('pomodoros_until_long_break', 4)))
        content_view.addSubview_(count_field)
        self.controls['pomodoros_until_long_break'] = count_field
        y_offset -= 40

        # Разделитель
        separator2 = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(20, y_offset, 460, 1))
        separator2.setBoxType_(AppKit.NSBoxSeparator)
        content_view.addSubview_(separator2)
        y_offset -= 20

        # === АВТОЗАПУСК ===
        label = self._create_label("АВТОЗАПУСК", 20, y_offset, 460, 20, bold=True)
        content_view.addSubview_(label)
        y_offset -= 30

        # Запускать помодоро с рабочим днем
        checkbox1 = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(20, y_offset, 460, 24))
        checkbox1.setButtonType_(AppKit.NSButtonTypeSwitch)
        checkbox1.setTitle_("Запускать помодоро с рабочим днем")
        checkbox1.setState_(1 if pomodoro_config.get('start_pomodoro_with_workday', False) else 0)
        content_view.addSubview_(checkbox1)
        self.controls['start_pomodoro_with_workday'] = checkbox1
        y_offset -= 30

        # Запускать рабочий день с помодоро
        checkbox2 = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(20, y_offset, 460, 24))
        checkbox2.setButtonType_(AppKit.NSButtonTypeSwitch)
        checkbox2.setTitle_("Запускать рабочий день с помодоро")
        checkbox2.setState_(1 if pomodoro_config.get('start_workday_with_pomodoro', False) else 0)
        content_view.addSubview_(checkbox2)
        self.controls['start_workday_with_pomodoro'] = checkbox2
        y_offset -= 40

        # Разделитель
        separator3 = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(20, y_offset, 460, 1))
        separator3.setBoxType_(AppKit.NSBoxSeparator)
        content_view.addSubview_(separator3)
        y_offset -= 20

        # === АВТОПАУЗА В Б24 ===
        label = self._create_label("АВТОПАУЗА В Б24", 20, y_offset, 460, 20, bold=True)
        content_view.addSubview_(label)
        y_offset -= 30

        pause_mode = pomodoro_config.get('bitrix_pause_mode', 'all_breaks')

        # Radio buttons для режима паузы - используем NSMatrix для группировки
        radio_cell = AppKit.NSButtonCell.alloc().init()
        radio_cell.setButtonType_(AppKit.NSButtonTypeRadio)

        radio_matrix = AppKit.NSMatrix.alloc().initWithFrame_mode_prototype_numberOfRows_numberOfColumns_(
            NSMakeRect(20, y_offset - 70, 460, 90),
            AppKit.NSRadioModeMatrix,
            radio_cell,
            3,
            1
        )

        # Устанавливаем размер ячеек для корректного отображения текста
        radio_matrix.setCellSize_((460, 30))

        # Настраиваем ячейки радиокнопок
        cell0 = radio_matrix.cellAtRow_column_(0, 0)
        cell0.setTitle_("Никогда не ставить на паузу")

        cell1 = radio_matrix.cellAtRow_column_(1, 0)
        cell1.setTitle_("Только длинные перерывы")

        cell2 = radio_matrix.cellAtRow_column_(2, 0)
        cell2.setTitle_("Все перерывы")

        # Устанавливаем выбранную кнопку
        if pause_mode == 'never':
            radio_matrix.selectCellAtRow_column_(0, 0)
        elif pause_mode == 'long_breaks_only':
            radio_matrix.selectCellAtRow_column_(1, 0)
        else:  # all_breaks
            radio_matrix.selectCellAtRow_column_(2, 0)

        content_view.addSubview_(radio_matrix)
        self.controls['pause_mode'] = radio_matrix
        y_offset -= 100

        # === КНОПКИ ===
        # Кнопка Сохранить
        save_button = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(380, 20, 100, 32))
        save_button.setTitle_("Сохранить")
        save_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_button.setTarget_(self)
        save_button.setAction_(objc.selector(self.save_, signature=b'v@:@'))
        content_view.addSubview_(save_button)

        # Кнопка Отмена
        cancel_button = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(270, 20, 100, 32))
        cancel_button.setTitle_("Отмена")
        cancel_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_button.setTarget_(self)
        cancel_button.setAction_(objc.selector(self.cancel_, signature=b'v@:@'))
        content_view.addSubview_(cancel_button)

        # Показываем окно
        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def _create_label(self, text, x, y, width, height, bold=False):
        """Создать текстовый лейбл"""
        label = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, height))
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)

        if bold:
            font = AppKit.NSFont.boldSystemFontOfSize_(13)
            label.setFont_(font)

        return label

    @objc.signature(b'v@:@')
    def save_(self, sender):
        """Сохранить настройки"""
        try:
            # Собираем новую конфигурацию
            new_config = {
                'webhook_url': self.controls['webhook_url'].stringValue(),
                'pomodoro': {
                    'work_duration': int(self.controls['work_duration'].stringValue()),
                    'short_break': int(self.controls['short_break'].stringValue()),
                    'long_break': int(self.controls['long_break'].stringValue()),
                    'pomodoros_until_long_break': int(self.controls['pomodoros_until_long_break'].stringValue()),
                    'start_pomodoro_with_workday': bool(self.controls['start_pomodoro_with_workday'].state()),
                    'start_workday_with_pomodoro': bool(self.controls['start_workday_with_pomodoro'].state()),
                }
            }

            # Определяем выбранный режим паузы из NSMatrix
            radio_matrix = self.controls['pause_mode']
            selected_row = radio_matrix.selectedRow()

            if selected_row == 0:
                pause_mode = 'never'
            elif selected_row == 1:
                pause_mode = 'long_breaks_only'
            else:  # selected_row == 2
                pause_mode = 'all_breaks'

            new_config['pomodoro']['bitrix_pause_mode'] = pause_mode

            # Сохраняем старые значения, которые не редактируем
            if 'check_interval' in self.config:
                new_config['check_interval'] = self.config['check_interval']

            # ВАЖНО: Сохраняем enabled если есть
            if 'enabled' in self.config.get('pomodoro', {}):
                new_config['pomodoro']['enabled'] = self.config['pomodoro']['enabled']

            print(f"💾 Сохраняю конфиг: {new_config}")

            # Сохраняем в файл
            save_config(new_config)
            print("✅ Сохранено в файл")

            # Сохраняем в БД напрямую
            try:
                from core.database import Database
                with Database() as db:
                    db.save_settings(new_config)
                print("✅ Сохранено в БД")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить в БД: {e}")

            # Закрываем окно
            self.window.close()

            # Уведомление
            rumps.notification("Настройки", "Сохранено", "Настройки успешно сохранены")

        except ValueError as e:
            print(f"❌ Ошибка валидации: {e}")
            # Показываем ошибку
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Ошибка")
            alert.setInformativeText_("Проверьте правильность введенных значений. Все числа должны быть целыми.")
            alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
            alert.addButtonWithTitle_("OK")
            alert.runModal()
        except Exception as e:
            print(f"❌ Неожиданная ошибка при сохранении: {e}")
            import traceback
            traceback.print_exc()

    @objc.signature(b'v@:@')
    def cancel_(self, sender):
        """Отменить изменения"""
        self.window.close()

    @objc.signature(b'v@:@')
    def windowWillClose_(self, notification):
        """Callback когда окно закрывается - очищаем ресурсы"""
        print("🧹 Очистка окна настроек...")

        # Обнуляем делегата чтобы не было retain cycle
        if self.window:
            self.window.setDelegate_(None)

        # Очищаем ссылки на контролы
        self.controls = {}

        # Очищаем ссылку на окно
        self.window = None

        print("✅ Окно настроек очищено")