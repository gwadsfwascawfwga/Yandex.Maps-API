import sys
import os
import configparser
from PyQt6.QtWidgets import (QMainWindow, QMessageBox, QApplication, 
                            QLabel, QComboBox, QLineEdit, QPushButton)
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtCore import Qt, pyqtSignal
import requests


class MapAPI:
    """Класс для работы с API Яндекс.Карт"""
    def __init__(self, config_path='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        self.geocoder_key = self.config['API']['geocoder_key']
        self.places_key = self.config['API']['places_key']
        
        self.base_geocoder_url = "https://geocode-maps.yandex.ru/1.x"
        self.base_static_map_url = "http://static-maps.yandex.ru/1.x"
        self.base_places_url = "https://search-maps.yandex.ru/v1"

    def geocode(self, address, postal_code=False):
        params = {
            'geocode': address,
            'apikey': self.geocoder_key,
            'format': 'json',
            'lang': 'ru_RU'
        }
        
        response = requests.get(self.base_geocoder_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        feature = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
        pos = feature['Point']['pos'].split()
        lon, lat = map(float, pos)
        
        address_info = feature['metaDataProperty']['GeocoderMetaData']
        full_address = address_info['text']
        
        if postal_code:
            postal = address_info['Address'].get('postal_code', '')
            if postal:
                full_address += f", {postal}"
                
        return {
            'lon': lon,
            'lat': lat,
            'address': full_address
        }

    def get_map_image(self, lon, lat, zoom, map_type, points=None):
        params = {
            'll': f"{lon},{lat}",
            'z': zoom,
            'l': map_type,
            'size': '650,450'
        }
        
        if points:
            params['pt'] = '~'.join(
                [f"{p['lon']},{p['lat']},pm2{p.get('color', 'bl')}m" 
                 for p in points]
            )
        
        response = requests.get(self.base_static_map_url, params=params)
        response.raise_for_status()
        return response.content

    def search_places(self, lon, lat, text):
        params = {
            'apikey': self.places_key,
            'text': text,
            'lang': 'ru_RU',
            'll': f"{lon},{lat}",
            'type': 'biz',
            'results': 1
        }
        
        response = requests.get(self.base_places_url, params=params)
        response.raise_for_status()
        return response.json()


class MainWindow(QMainWindow):
    map_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_map()
        self.setup_connections()
        
        self.current_position = {'lon': 37.620070, 'lat': 55.753630}  # Москва по умолчанию
        self.zoom_level = 12
        self.map_type = 'map'
        self.postal_code = False
        self.points = []
        
        self.map_api = MapAPI()
        self.update_map()

    def setup_ui(self):
        self.setWindowTitle("Яндекс.Карты")
        self.setGeometry(100, 100, 800, 600)
        
        # Основные виджеты
        self.map_label = QLabel(self)
        self.map_label.setGeometry(10, 10, 780, 450)
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(['Схема', 'Спутник', 'Гибрид'])
        self.type_combo.move(10, 470)
        
        self.search_input = QLineEdit(self)
        self.search_input.setGeometry(150, 470, 300, 25)
        
        self.search_btn = QPushButton("Поиск", self)
        self.search_btn.setGeometry(460, 470, 80, 25)
        
        self.postal_combo = QComboBox(self)
        self.postal_combo.addItems(['Скрыть индекс', 'Показать индекс'])
        self.postal_combo.move(550, 470)
        
        self.address_label = QLabel("Адрес не указан", self)
        self.address_label.setGeometry(10, 510, 780, 20)
        
        self.status_label = QLabel(self)
        self.status_label.setGeometry(10, 540, 780, 20)

    def setup_map(self):
        self.temp_map_file = 'temp_map.png'
        self.map_label.setStyleSheet("border: 1px solid #999;")
        
    def setup_connections(self):
        self.type_combo.currentTextChanged.connect(self.change_map_type)
        self.postal_combo.currentTextChanged.connect(self.toggle_postal_code)
        self.search_btn.clicked.connect(self.search_location)
        self.search_input.returnPressed.connect(self.search_location)
        self.map_updated.connect(self.update_display)

    def change_map_type(self, map_type):
        type_mapping = {
            'Схема': 'map',
            'Спутник': 'sat',
            'Гибрид': 'sat,skl'
        }
        self.map_type = type_mapping.get(map_type, 'map')
        self.update_map()

    def toggle_postal_code(self, state):
        self.postal_code = (state == 'Показать индекс')
        if self.points:
            self.update_map()

    def search_location(self):
        query = self.search_input.text()
        if not query:
            return
            
        try:
            result = self.map_api.geocode(query, self.postal_code)
            self.current_position = {
                'lon': result['lon'],
                'lat': result['lat']
            }
            self.points = [{
                'lon': result['lon'],
                'lat': result['lat'],
                'color': 'db'
            }]
            self.address_label.setText(result['address'])
            self.zoom_level = 15
            self.update_map()
            
        except Exception as e:
            self.show_error("Ошибка поиска", str(e))

    def update_map(self):
        try:
            map_image = self.map_api.get_map_image(
                self.current_position['lon'],
                self.current_position['lat'],
                self.zoom_level,
                self.map_type,
                self.points
            )
            
            with open(self.temp_map_file, 'wb') as f:
                f.write(map_image)
                
            self.map_updated.emit()
            
        except Exception as e:
            self.show_error("Ошибка карты", str(e))

    def update_display(self):
        pixmap = QPixmap(self.temp_map_file)
        self.map_label.setPixmap(pixmap)
        self.status_label.setText(
            f"Координаты: {self.current_position['lon']:.5f}, "
            f"{self.current_position['lat']:.5f} | Масштаб: {self.zoom_level}"
        )

    def keyPressEvent(self, event):
        step = 0.2 * (1 / self.zoom_level)
        
        if event.key() == Qt.Key.Key_Left:
            self.current_position['lon'] -= step
        elif event.key() == Qt.Key.Key_Right:
            self.current_position['lon'] += step
        elif event.key() == Qt.Key.Key_Up:
            self.current_position['lat'] += step
        elif event.key() == Qt.Key.Key_Down:
            self.current_position['lat'] -= step
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_PageUp):
            self.zoom_level = min(self.zoom_level + 1, 23)
        elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_PageDown):
            self.zoom_level = max(self.zoom_level - 1, 1)
        else:
            return
            
        self.update_map()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_level = min(self.zoom_level + 1, 23)
        else:
            self.zoom_level = max(self.zoom_level - 1, 1)
        self.update_map()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.handle_left_click(event)
        elif event.button() == Qt.MouseButton.RightButton:
            self.handle_right_click(event)

    def handle_left_click(self, event):
        # Конвертация координат клика в географические
        img_x = event.pos().x() - self.map_label.x()
        img_y = event.pos().y() - self.map_label.y()
        
        if not (0 <= img_x <= 780 and 0 <= img_y <= 450):
            return
            
        lon = self.current_position['lon'] + (img_x - 390) * (0.002 * (19 - self.zoom_level))
        lat = self.current_position['lat'] - (img_y - 225) * (0.001 * (19 - self.zoom_level))
        
        try:
            result = self.map_api.geocode(f"{lon},{lat}", self.postal_code)
            self.points.append({
                'lon': result['lon'],
                'lat': result['lat'],
                'color': 'db'
            })
            self.address_label.setText(result['address'])
            self.update_map()
            
        except Exception as e:
            self.show_error("Ошибка геокодирования", str(e))

    def handle_right_click(self, event):
        # Поиск организаций
        if not self.points:
            return
            
        try:
            places = self.map_api.search_places(
                self.current_position['lon'],
                self.current_position['lat'],
                self.address_label.text()
            )
            
            if places['features']:
                place = places['features'][0]
                name = place['properties']['name']
                QMessageBox.information(
                    self, 
                    "Найдена организация", 
                    f"Название: {name}\nАдрес: {place['properties']['description']}"
                )
                
        except Exception as e:
            self.show_error("Ошибка поиска", str(e))

    def show_error(self, title, message):
        QMessageBox.critical(self, title, 
            f"{message}\nПроверьте подключение к интернету и попробуйте снова.")

    def closeEvent(self, event):
        if os.path.exists(self.temp_map_file):
            os.remove(self.temp_map_file)
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
