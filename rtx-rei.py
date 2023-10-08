import sys
import os
import requests
import zipfile
import shutil
import subprocess
import json
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QStyle,
)
from PyQt5.QtGui import QColor, QPalette, QPainter, QIcon

class DownloadThread(QThread):
    download_progress = pyqtSignal(int)

    def __init__(self, url, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            downloaded = 0

            with open(self.save_path, 'wb') as file:
                for data in response.iter_content(block_size):
                    file.write(data)
                    downloaded += len(data)
                    self.download_progress.emit(int(100 * downloaded / total_size))

            self.download_progress.emit(100)
        except Exception as e:
            self.download_progress.emit(-1)

class StyledButton(QPushButton):
    def __init__(self, text, icon=None):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1c1c1c;
                border: 1px solid #00FF00;
                color: #00FF00;
                padding: 5px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #252525;
            }
            QPushButton:pressed {
                background-color: #141414;
                border: 1px solid #009900;
            }
        """)
        if icon:
            self.setIcon(icon)

class RTXRemixInstaller(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RTX Remix Downloader/Installer")
        self.setGeometry(100, 100, 400, 400)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.download_button = StyledButton("Download RTX Remix", self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.extract_button = StyledButton("Extract RTX Remix", self.style().standardIcon(QStyle.SP_FileDialogInfoView))
        self.install_button = StyledButton("Install RTX Remix to Game", self.style().standardIcon(QStyle.SP_DialogYesButton))
        self.open_directory_button = StyledButton("Open RTX Remix Directory", self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.choose_directory_button = StyledButton("Choose Game Directory", self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.download_progress = QProgressBar()
        self.game_list = QListWidget()
        self.autofind_button = StyledButton("Autofind Games with d3d9.dll")
        self.available_games_list = QListWidget()

        layout.addWidget(self.download_button)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.install_button)
        layout.addWidget(self.open_directory_button)
        layout.addWidget(self.choose_directory_button)
        layout.addWidget(self.download_progress)
        layout.addWidget(self.game_list)
        layout.addWidget(self.autofind_button)
        layout.addWidget(self.available_games_list)

        self.download_button.clicked.connect(self.download_rtx_remix)
        self.extract_button.clicked.connect(self.extract_rtx_remix)
        self.install_button.clicked.connect(self.install_rtx_remix)
        self.open_directory_button.clicked.connect(self.open_rtx_remix_directory)
        self.choose_directory_button.clicked.connect(self.choose_game_directory)
        self.game_list.itemClicked.connect(self.open_installed_game_directory)
        self.autofind_button.clicked.connect(self.autofind_games)
        self.available_games_list.itemClicked.connect(self.open_available_game_directory)

        self.set_dark_theme()

        # Initialize variables
        self.download_thread = None
        self.game_directory = None
        self.download_url = self.get_latest_release_url("NVIDIAGameWorks/rtx-remix")
        self.zip_file_path = "rtx_remix.zip"
        self.extracted_dir = "rtx_remix"

        # Create a grid background
        self.grid_colors = [QColor(0, 0, 0) for _ in range(25)]  # Initialize grid colors
        self.grid_hovered = -1  # Track the hovered grid cell

        # Load installed games and paths from JSON files
        self.installed_games = self.load_json_data("installed_games.json")
        self.installed_paths = self.load_json_data("installed_paths.json")
        self.update_game_list()
        

    def paintEvent(self, event):
        painter = QPainter(self)
        cell_size = 20  # Size of each grid cell
        num_rows = 5  # Number of rows in the grid
        num_cols = 5  # Number of columns in the grid

        for row in range(num_rows):
            for col in range(num_cols):
                index = row * num_cols + col
                color = self.grid_colors[index]

                # Highlight the cell if it's hovered
                if index == self.grid_hovered:
                    color = color.lighter(150)

                painter.fillRect(
                    col * cell_size, row * num_cols, cell_size, cell_size, color
                )

    def mouseMoveEvent(self, event):
        cell_size = 20  # Size of each grid cell
        num_cols = 5  # Number of columns in the grid

        x = event.x() // cell_size
        y = event.y() // cell_size
        self.grid_hovered = y * num_cols + x
        self.update()

    def mouseLeaveEvent(self, event):
        self.grid_hovered = -1
        self.update()

    def choose_game_directory(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        selected_directory = QFileDialog.getExistingDirectory(self, "Select Game Directory", options=options)
        if selected_directory:
            self.game_directory = selected_directory

    def download_rtx_remix(self):
        self.download_button.setEnabled(False)

        try:
            self.download_thread = DownloadThread(self.download_url, self.zip_file_path)
            self.download_thread.download_progress.connect(self.update_download_progress)
            self.download_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to start download. Please check your internet connection.")

    def update_download_progress(self, value):
        self.download_progress.setValue(value)

        if value == 100:
            QMessageBox.information(self, "Download Complete", "RTX Remix downloaded successfully!")
            self.download_button.setEnabled(True)

    def extract_rtx_remix(self):
        try:
            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                zip_ref.extractall(self.extracted_dir)
            QMessageBox.information(self, "Extraction Complete", "RTX Remix extracted successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to extract RTX Remix: {str(e)}")

    def install_rtx_remix(self):
        if not self.game_directory:
            QMessageBox.warning(self, "Warning", "Please select a game directory before installing RTX Remix.")
            return

        if os.path.exists(self.extracted_dir):
            try:
                source_dir = self.find_source_directory(self.extracted_dir)
                if source_dir:
                    destination_dir = os.path.join(self.game_directory)

                    if not os.path.exists(destination_dir):
                        os.makedirs(destination_dir)

                    for root, dirs, files in os.walk(source_dir):
                        relative_path = os.path.relpath(root, source_dir)
                        destination_root = os.path.join(destination_dir, relative_path)
                        os.makedirs(destination_root, exist_ok=True)

                        for file in files:
                            source_path = os.path.join(root, file)
                            destination_path = os.path.join(destination_root, file)
                            shutil.copy(source_path, destination_path)

                    game_name = os.path.basename(self.game_directory)

                    # Save the installed game name and path to JSON files
                    self.installed_games[game_name] = True
                    self.installed_paths[game_name] = self.game_directory
                    self.save_json_data("installed_games.json", self.installed_games)
                    self.save_json_data("installed_paths.json", self.installed_paths)

                    self.update_game_list()

                    QMessageBox.information(self, "Installation Complete", "RTX Remix installed to the game directory successfully!")
                else:
                    QMessageBox.critical(self, "Error", "Unable to find RTX Remix directory with CRC.txt.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to install RTX Remix to the game: {str(e)}")
        else:
            QMessageBox.critical(self, "Error", "RTX Remix directory does not exist. Please extract it first.")

    def open_rtx_remix_directory(self):
        try:
            if os.path.exists(self.extracted_dir):
                subprocess.Popen(["explorer", self.extracted_dir], shell=True)
            else:
                QMessageBox.critical(self, "Error", "RTX Remix directory does not exist.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open RTX Remix directory: {str(e)}")

    def open_installed_game_directory(self, item):
        game_name = item.text()
        if game_name in self.installed_paths:
            game_directory = self.installed_paths[game_name]
            if os.path.exists(game_directory):
                os.startfile(game_directory)  # Try using os.startfile to open the directory
            else:
                QMessageBox.critical(self, "Error", "Game directory does not exist.")
        else:
            QMessageBox.critical(self, "Error", "Game not found in the list of installed games.")

    def open_available_game_directory(self, item):
        game_name = item.text()
        if game_name in self.available_game_paths:
            game_directory = self.available_game_paths[game_name]
            if os.path.exists(game_directory):
                os.startfile(game_directory)  # Try using os.startfile to open the directory
                self.game_directory = game_directory  # Set the current game directory
            else:
                QMessageBox.critical(self, "Error", "Game directory does not exist.")
        else:
            QMessageBox.critical(self, "Error", "Game not found in the list of available games.")

    def set_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(28, 28, 28))  # Dark gray background
        palette.setColor(QPalette.WindowText, Qt.white)  # Text color
        palette.setColor(QPalette.Button, QColor(28, 28, 28))  # Button color
        palette.setColor(QPalette.ButtonText, Qt.white)  # Button text color
        palette.setColor(QPalette.Highlight, QColor(0, 128, 0))  # Highlight color
        palette.setColor(QPalette.HighlightedText, Qt.black)  # Highlighted text color
        self.setPalette(palette)

    def load_json_data(self, filename):
        try:
            with open(filename, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_json_data(self, filename, data):
        with open(filename, "w") as file:
            json.dump(data, file, indent=4)

    def update_game_list(self):
        self.game_list.clear()
        for game_name, _ in self.installed_games.items():
            item = QListWidgetItem(game_name)
            self.game_list.addItem(item)

    def find_source_directory(self, root_directory):
        for root, dirs, files in os.walk(root_directory):
            if "CRC.txt" in files:
                return root
        return None

    def autofind_games(self):
        if not self.game_directory:
            QMessageBox.warning(self, "Warning", "Please select a game directory first.")
            return

        installed_games = set(self.installed_games.keys())  # Get a set of installed game names

        self.available_game_paths = {}  # Dictionary to store available game paths

        for root, dirs, files in os.walk(self.game_directory):
            if "d3d9.dll" in files and "symbols" not in root:
                game_directory = os.path.abspath(root)
                game_name = os.path.basename(game_directory)

                if game_name not in installed_games:
                    self.available_game_paths[game_name] = game_directory

                # Stop searching subfolders once the file is found
                break

        if not self.available_game_paths:
            QMessageBox.information(
                self, "Autofind Results", "No games with 'd3d9.dll' found in the selected directory."
            )
            return

        self.available_games_list.clear()
        for game_name, game_path in self.available_game_paths.items():
            item = QListWidgetItem(game_name)
            self.available_games_list.addItem(item)

        self.available_games_list.setCurrentRow(0)  # Select the first item in the list by default

    def get_latest_release_url(self, repo_url):
        try:
            api_url = f"https://api.github.com/repos/{repo_url}/releases/latest"
            response = requests.get(api_url)
            if response.status_code == 200:
                release_info = response.json()
                assets = release_info.get("assets", [])
                for asset in assets:
                    asset_name = asset.get("name", "")
                    if "symbols" not in asset_name:
                        return asset.get("browser_download_url", "")
        except Exception as e:
            pass
        return "https://github.com/NVIDIAGameWorks/rtx-remix/releases/latest/download/remix.zip"

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = RTXRemixInstaller()
    main_window.show()
    sys.exit(app.exec_())
