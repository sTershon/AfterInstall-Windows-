import sys
import os
import subprocess
import ctypes
from typing import List

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QMovie
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton,
    QTextEdit, QProgressBar, QHBoxLayout, QMessageBox, QGroupBox, QGridLayout,
    QFileDialog, QSpacerItem, QSizePolicy
)

# --------------------------- Утилиты ---------------------------

def is_admin() -> bool:
    """Проверяем, запущен ли процесс от имени администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Пытаемся запустить текущий скрипт от имени администратора (повторно)"""
    params = ' '.join([f'"{arg}"' for arg in sys.argv])
    executable = sys.executable
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        return True
    except Exception as e:
        print("Не удалось запустить как администратор:", e)
        return False


# --------------------------- Worker ---------------------------
class Worker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, tasks: List[str], parent=None):
        super().__init__(parent)
        # tasks - список идентификаторов операций
        self.tasks = tasks
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        total = len(self.tasks)
        if total == 0:
            self.log_signal.emit("Нет выбранных задач. Прерывание.")
            self.progress_signal.emit(100)
            self.finished_signal.emit()
            return

        for i, task in enumerate(self.tasks, start=1):
            if self._stopped:
                self.log_signal.emit("Операция прервана пользователем.")
                break

            self.log_signal.emit(f"=== Выполняю: {task} ({i}/{total}) ===")
            try:
                if task == 'install_programs':
                    self._install_programs()
                elif task == 'clean_temp':
                    self._clean_temp()
                elif task == 'remove_bloatware':
                    self._remove_bloatware()
                elif task == 'optimize_services':
                    self._optimize_services()
                else:
                    self.log_signal.emit(f"Неизвестная задача: {task}")
            except Exception as e:
                self.log_signal.emit(f"Ошибка при выполнении {task}: {e}")

            pct = int(i / total * 100)
            self.progress_signal.emit(pct)

        self.log_signal.emit("Все выбранные задачи выполнены.")
        self.progress_signal.emit(100)
        self.finished_signal.emit()

    # ------------------ Реальные операции ------------------
    def _install_programs(self):
        apps = [
            "Google.Chrome",
            "Mozilla.Firefox",
            "7zip.7zip",
            "VideoLAN.VLC",
            "Notepad++.Notepad++",
            "Telegram.TelegramDesktop",
            "Discord.Discord"
        ]
        for app in apps:
            if self._stopped:
                break
            self.log_signal.emit(f"Установка: {app}")
            # winget может требовать подтверждений — используем флаги
            cmd = f"winget install --id {app} -e --accept-source-agreements --accept-package-agreements"
            self._run_cmd(cmd)

    def _clean_temp(self):
        # Удаляем содержимое TEMP и выполняем cleanmgr
        temp_path = os.getenv('TEMP') or r'C:\Windows\Temp'
        self.log_signal.emit(f"Очистка: {temp_path}")
        # Используем команду del через cmd, чтобы удалить файлы
        self._run_cmd(f"cmd /c del /q /f /s \"{temp_path}\\*\"")
        self._run_cmd("cleanmgr /verylowdisk")

    def _remove_bloatware(self):
        apps = [
            "Microsoft.XboxApp",
            "Microsoft.ZuneMusic",
            "Microsoft.ZuneVideo",
            "Microsoft.GetHelp",
            "Microsoft.MicrosoftOfficeHub",
            "Microsoft.Microsoft3DViewer",
            "Microsoft.MicrosoftSolitaireCollection"
        ]
        for app in apps:
            if self._stopped:
                break
            self.log_signal.emit(f"Удаление пакета: {app}")
            # Команда через PowerShell
            self._run_cmd(f"powershell -Command \"Get-AppxPackage -Name {app} -AllUsers | Remove-AppxPackage -ErrorAction SilentlyContinue\"")

    def _optimize_services(self):
        services = [
            ("DiagTrack", "Телеметрия (Connected User Experiences and Telemetry)"),
            ("MapsBroker", "Служба карт (MapsBroker)"),
            ("WSearch", "Индексатор поиска Windows (WSearch)")
        ]
        for svc, desc in services:
            if self._stopped:
                break
            self.log_signal.emit(f"Отключение службы: {svc} — {desc}")
            self._run_cmd(f"sc stop {svc}")
            self._run_cmd(f"sc config {svc} start= disabled")

    def _run_cmd(self, cmd: str):
        """Запуск команды с выводом логов в UI. Не бросаем исключения при ошибках — логируем."""
        self.log_signal.emit(f"Команда: {cmd}")
        try:
            # subprocess.run блокирует, но мы в потоке — нормально.
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            out = completed.stdout.strip()
            err = completed.stderr.strip()
            if out:
                self.log_signal.emit(out)
            if err:
                self.log_signal.emit("ERR: " + err)
            self.log_signal.emit(f"Код возврата: {completed.returncode}")
        except Exception as e:
            self.log_signal.emit(f"Исключение при запуске команды: {e}")


# --------------------------- GUI ---------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AfterInstall — Настройка Windows")
        self.setMinimumSize(QSize(760, 560))
        self.setWindowIcon(QIcon())

        # Поля для загрузчика
        self.use_gif = False
        self.gif_path = None
        self.movie = None

        self._create_ui()
        self.worker = None

        # Проверка прав
        if not is_admin():
            self.admin_label.setText("⚠️ Рекомендуется запустить от имени администратора")
            self.elevate_btn.setEnabled(True)
        else:
            self.admin_label.setText("✅ Запущено с правами администратора")
            self.elevate_btn.setEnabled(False)

    def _create_ui(self):
        main_layout = QVBoxLayout()

        header = QLabel("<h2>Настройка Windows после установки</h2>")
        header.setTextFormat(Qt.TextFormat.RichText)
        main_layout.addWidget(header)

        subtitle = QLabel("Выберите действия и нажмите ▶ Запустить")
        main_layout.addWidget(subtitle)

        # Панель выбора задач
        tasks_group = QGroupBox("Задачи")
        tasks_layout = QGridLayout()

        self.chk_install = QCheckBox("Установить программы (winget)")
        self.chk_clean = QCheckBox("Очистить временные файлы")
        self.chk_remove = QCheckBox("Удалить предустановленные приложения (bloatware)")
        self.chk_services = QCheckBox("Оптимизировать/отключить службы")

        tasks_layout.addWidget(self.chk_install, 0, 0)
        tasks_layout.addWidget(self.chk_clean, 0, 1)
        tasks_layout.addWidget(self.chk_remove, 1, 0)
        tasks_layout.addWidget(self.chk_services, 1, 1)

        tasks_group.setLayout(tasks_layout)
        main_layout.addWidget(tasks_group)

        # Настройки загрузчика (GIF / точки)
        loader_group = QGroupBox("Анимация загрузки")
        loader_layout = QHBoxLayout()
        self.chk_use_gif = QCheckBox("Использовать GIF-анимацию (если выбран файл)")
        self.chk_use_gif.stateChanged.connect(self.on_toggle_use_gif)
        self.btn_load_gif = QPushButton("Загрузить GIF...")
        self.btn_load_gif.clicked.connect(self.on_load_gif)
        self.btn_load_gif.setToolTip("Выберите .gif файл для анимации загрузки")
        loader_layout.addWidget(self.chk_use_gif)
        loader_layout.addWidget(self.btn_load_gif)
        loader_group.setLayout(loader_layout)
        main_layout.addWidget(loader_group)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ Запустить")
        self.run_btn.clicked.connect(self.on_run)
        self.stop_btn = QPushButton("■ Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.on_stop)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)

        # Elevation
        self.elevate_btn = QPushButton("Запустить от имени администратора")
        self.elevate_btn.clicked.connect(self.on_elevate)
        btn_layout.addWidget(self.elevate_btn)

        # Spacer
        btn_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        main_layout.addLayout(btn_layout)

        # Анимация / индикатор
        self.loader_label = QLabel("")             # сюда будет GIF или текст анимации
        self.loader_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loader_label.setFixedHeight(120)
        main_layout.addWidget(self.loader_label)

        # Прогресс и метка прав
        self.progress = QProgressBar()
        self.progress.setValue(0)
        main_layout.addWidget(self.progress)

        self.admin_label = QLabel("")
        main_layout.addWidget(self.admin_label)

        # Лог
        log_group = QGroupBox("Лог выполнения")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Подвал с подсказками
        footer_layout = QHBoxLayout()
        help_label = QLabel("Будьте внимательны: операции изменяют систему. Создайте точку восстановления перед запуском.")
        footer_layout.addWidget(help_label)
        main_layout.addLayout(footer_layout)

        self.setLayout(main_layout)

        # Стилизация (базовый тёмный стиль через CSS)
        self.setStyleSheet("""
            QWidget { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #0f1115, stop:1 #1b1f24); color: #dbe6f1; }
            QGroupBox { border: 1px solid #2b2f36; border-radius: 8px; margin-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QPushButton { padding: 8px 14px; border-radius: 8px; background: #2b6ea3; }
            QPushButton:pressed { background: #1f567f; }
            QProgressBar { height: 16px; border-radius: 8px; text-align: center; }
            QTextEdit { background: #0b0d10; border: 1px solid #2b2f36; }
            QLabel { color: #e6eef8; }
        """)

        # Встроенная анимация точек
        self.loading_texts = ["Загрузка.", "Загрузка..", "Загрузка...", "Загрузка"]
        self.loading_index = 0
        self.dot_timer = QTimer(self)
        self.dot_timer.setInterval(400)
        self.dot_timer.timeout.connect(self._animate_dots)

    # ------------------ Слоты ------------------
    def on_elevate(self):
        ans = QMessageBox.question(self, "Запуск от администратора",
                                   "Приложение будет перезапущено с правами администратора. Продолжить?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            run_as_admin()

    def on_load_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите GIF файл", "", "GIF files (*.gif);;All files (*)")
        if path:
            self.gif_path = path
            self.chk_use_gif.setChecked(True)
            self.append_log(f"GIF выбран: {path}")

    def on_toggle_use_gif(self, state):
        self.use_gif = (state == Qt.CheckState.Checked)
        if self.use_gif and not self.gif_path:
            # подсказка: открыть диалог выбора
            self.on_load_gif()

    def on_run(self):
        tasks = []
        if self.chk_install.isChecked():
            tasks.append('install_programs')
        if self.chk_clean.isChecked():
            tasks.append('clean_temp')
        if self.chk_remove.isChecked():
            tasks.append('remove_bloatware')
        if self.chk_services.isChecked():
            tasks.append('optimize_services')

        if not tasks:
            QMessageBox.information(self, "Ничего не выбрано", "Пожалуйста, выберите хотя бы одну задачу.")
            return

        # Блокируем интерфейс
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_text.clear()
        self.progress.setValue(2)

        # Запускаем анимацию
        self._start_loader()

        # Создаём и запускаем воркер
        self.worker = Worker(tasks)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_stop(self):
        if self.worker:
            self.worker.stop()
            self.append_log("Запрос на остановку отправлен...")
            self.stop_btn.setEnabled(False)
            # Остановим анимацию — worker сам остановится вскоре
            self._stop_loader()

    def on_finished(self):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.append_log("Задачи завершены.")
        # Остановим анимацию
        self._stop_loader()
        self.progress.setValue(100)

    def append_log(self, text: str):
        self.log_text.append(text)
        # Автоскролл
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    # ------------------ Анимация загрузки ------------------
    def _start_loader(self):
        """Показываем либо GIF, либо встроенную анимацию точек"""
        if self.use_gif and self.gif_path and os.path.exists(self.gif_path):
            # Отображение GIF через QMovie
            try:
                self.movie = QMovie(self.gif_path)
                self.loader_label.setMovie(self.movie)
                self.movie.start()
            except Exception as e:
                self.append_log(f"Не удалось запустить GIF: {e}")
                self.loader_label.setText("Загрузка...")
                self.dot_timer.start()
        else:
            # Запускаем точечную анимацию
            self.loader_label.setText(self.loading_texts[self.loading_index])
            self.dot_timer.start()

    def _stop_loader(self):
        """Останавливаем анимацию"""
        if self.movie:
            try:
                self.movie.stop()
            except Exception:
                pass
            self.loader_label.clear()
            self.movie = None
        if self.dot_timer.isActive():
            self.dot_timer.stop()
        # Коротко показать сообщение о завершении
        self.loader_label.setText("✅ Готово")
        QTimer.singleShot(1500, lambda: self.loader_label.clear())

    def _animate_dots(self):
        self.loading_index = (self.loading_index + 1) % len(self.loading_texts)
        self.loader_label.setText(self.loading_texts[self.loading_index])


# --------------------------- Запуск приложения ---------------------------

def main():
    app = QApplication(sys.argv)

    # Простой аргумент --help
    if '--help' in sys.argv or '-h' in sys.argv:
        print("GUI приложение AfterInstall на PyQt6")
        sys.exit(0)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
