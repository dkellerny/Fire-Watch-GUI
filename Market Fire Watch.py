import sys
import json
import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QFrame, QFormLayout, QAction, QMenuBar, QMenu, QSpinBox, QScrollArea
)
from PyQt5.QtGui import QFont, QLinearGradient, QColor, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import yfinance as yf
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.widgets import Cursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from auth import Auth
import pandas as pd
import numpy as np


class DraggableLabel(QLabel):
    dragged = pyqtSignal(int, int)

    def __init__(self, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            distance = (event.pos() - self.drag_start_position).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self.dragged.emit(self.index, self.y())
                event.accept()
        else:
            event.ignore()


class GradientLabel(QLabel):
    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 165, 0))
        painter.setPen(QPen(gradient, 0))
        painter.drawText(rect, Qt.AlignCenter, self.text())
        self.setStyleSheet("color: transparent;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Fire Watch")
        self.setGeometry(100, 100, 1200, 800)
        self.current_mode = 'dark'
        self.setStyleSheet(self.get_stylesheet())

        self.auth = Auth()
        self.watchlist = [] 

        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.login_page = LoginPage(self)
        self.home_page = HomePage(self)
        self.stock_details_page = StockDetailsPage(self)
        self.settings_page = SettingsPage(self)

        self.central_widget.addWidget(self.login_page)
        self.central_widget.addWidget(self.home_page)
        self.central_widget.addWidget(self.stock_details_page)
        self.central_widget.addWidget(self.settings_page)

        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.show_settings_page)

        self.logout_action = QAction("Logout", self)
        self.logout_action.triggered.connect(self.logout)

        self.close_action = QAction("Close App", self)
        self.close_action.triggered.connect(self.close_app)

        self.init_menu()

        self.last_page = None

    def init_menu(self):
        self.menu = QMenu("Menu", self)
        self.menu_bar.addMenu(self.menu)

        self.update_menu_for_login_page()

    def update_menu_for_login_page(self):
        self.menu.clear()
        self.menu.addAction(self.close_action)

    def update_menu_for_home_page(self):
        self.menu.clear()
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.logout_action)
        self.menu.addAction(self.close_action)

    def logout(self):
        self.auth.current_user = None
        self.show_login_page()

    def close_app(self):
        QApplication.quit()

    def show_login_page(self):
        self.update_menu_for_login_page()
        self.central_widget.setCurrentWidget(self.login_page)

    def show_home_page(self):
        self.update_menu_for_home_page()
        self.central_widget.setCurrentWidget(self.home_page)
        self.home_page.update_watchlist_display()

    def show_stock_details(self, stock):
        self.last_page = self.stock_details_page
        self.stock_details_page.display_stock(stock)
        self.central_widget.setCurrentWidget(self.stock_details_page)

    def show_settings_page(self):
        self.last_page = self.settings_page
        self.central_widget.setCurrentWidget(self.settings_page)

    def navigate_back(self):
        if self.last_page == self.stock_details_page:
            self.show_stock_details(self.stock_details_page.stock_entry.text())
        else:
            self.show_home_page()

    def load_watchlist(self, username):
        filepath = f"{username}_watchlist.json"
        if os.path.exists(filepath):
            with open(filepath, "r") as file:
                self.watchlist = json.load(file)
        else:
            self.watchlist = []

    def save_watchlist(self, username):
        filepath = f"{username}_watchlist.json"
        with open(filepath, "w") as file:
            json.dump(self.watchlist, file)

    def change_mode(self, mode):
        self.current_mode = mode
        self.setStyleSheet(self.get_stylesheet())
        self.home_page.update_stylesheet()
        self.stock_details_page.update_stylesheet()
        self.settings_page.update_stylesheet()

    def get_stylesheet(self):
        if self.current_mode == 'dark':
            return """
                QMainWindow {
                    background-color: #2E3B4E;
                    color: white;
                }
                QLabel, QLineEdit, QComboBox, QPushButton {
                    color: white;
                    background-color: #3B4B61;
                }
                QFrame {
                    background-color: #3B4B61;
                }
                QListWidget {
                    background-color: #2E3B4E;
                    color: white;
                }
            """
        else:
            return """
                QMainWindow {
                    background-color: #F0F0F0;
                    color: black;
                }
                QLabel, QLineEdit, QComboBox, QPushButton {
                    color: black;
                    background-color: #FFFFFF;
                }
                QFrame {
                    background-color: #E0E0E0;
                }
                QListWidget {
                    background-color: #F0F0F0;
                    color: black;
                }
            """


class LoginPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        self.top_layout = QHBoxLayout()
        self.top_layout.setAlignment(Qt.AlignRight)
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(QApplication.quit)
        self.top_layout.addWidget(self.quit_button)
        self.layout.addLayout(self.top_layout)

        title_label = GradientLabel("Market Fire Watch")
        title_label.setFont(QFont("Helvetica", 24, QFont.Bold))
        self.layout.addWidget(title_label)

        self.form_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.form_layout.addRow("Username:", self.username_input)
        self.form_layout.addRow("Password:", self.password_input)

        self.layout.addLayout(self.form_layout)

        self.show_password_button = QPushButton("Show Password", self)
        self.show_password_button.setCheckable(True)
        self.show_password_button.toggled.connect(self.toggle_password_visibility)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.login)

        self.register_button = QPushButton("Register")
        self.register_button.clicked.connect(self.register)

        self.button_layout = QHBoxLayout()
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.button_layout.addWidget(self.show_password_button)
        self.button_layout.addWidget(self.login_button)
        self.button_layout.addWidget(self.register_button)

        self.layout.addLayout(self.button_layout)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.layout.addWidget(self.error_label)

        self.contact_info = QLabel("© 2024 Daniel Keller. All rights reserved. | dkellerny@outlook.com")
        self.contact_info.setFont(QFont("Helvetica", 10))
        self.contact_info.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.contact_info)

    def toggle_password_visibility(self, checked):
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self.show_password_button.setText("Hide Password")
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self.show_password_button.setText("Show Password")

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if self.main_window.auth.login(username, password):
            self.error_label.setText("")
            self.main_window.auth.current_user = username
            self.main_window.load_watchlist(username)
            self.main_window.show_home_page()
        else:
            self.error_label.setText("Invalid username or password.")

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if self.main_window.auth.register(username, password):
            self.error_label.setStyleSheet("color: green;")
            self.error_label.setText("Registration successful. Please login.")
        else:
            self.error_label.setText("Username already taken.")

# API key needed for news functionality and display
class NewsFetcher:
    def __init__(self):
        pass

    def get_news(self, query="stock market"):
        url = f"https://newsapi.org/v2/everything?q={query}"
        response = requests.get(url)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            return [(article.get("title", "No title"), article.get("url", "")) for article in articles]
        return []


class HomePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        title_label = GradientLabel("Market Fire Watch")
        title_label.setFont(QFont("Helvetica", 24, QFont.Bold))
        self.layout.addWidget(title_label)

        self.news_title_label = QLabel("Latest News")
        self.news_title_label.setFont(QFont("Helvetica", 14))
        self.layout.addWidget(self.news_title_label)

        self.news_frame = QFrame(self)
        self.news_layout = QVBoxLayout(self.news_frame)
        self.layout.addWidget(self.news_frame)

        self.news_labels = []
        self.news_timer = QTimer(self)
        self.news_timer.timeout.connect(self.rotate_news_headlines)
        self.current_news_index = 0

        self.update_news_display()

        self.watchlist_title_label = QLabel("Stock Watchlist")
        self.watchlist_title_label.setFont(QFont("Helvetica", 16))
        self.layout.addWidget(self.watchlist_title_label)

        self.search_frame = QFrame(self)
        self.search_layout = QVBoxLayout(self.search_frame)
        self.search_layout.setAlignment(Qt.AlignTop)
        self.layout.addWidget(self.search_frame)

        self.stock_entry = QLineEdit(self)
        self.stock_entry.setPlaceholderText("Search Stock Symbols (comma-separated, up to 5)")
        self.search_layout.addWidget(self.stock_entry)

        self.add_button = QPushButton("Add to Watchlist", self)
        self.add_button.clicked.connect(self.add_to_watchlist_from_entry)
        self.search_layout.addWidget(self.add_button)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.search_layout.addWidget(self.error_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(400)
        self.layout.addWidget(self.scroll_area)

        self.watchlist_frame = QFrame(self)
        self.scroll_layout = QVBoxLayout(self.watchlist_frame)
        self.watchlist_frame.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.watchlist_frame)

        self.update_watchlist_display()

        self.max_stocks_label = QLabel("Maximum number of stocks: 25")
        self.max_stocks_label.setFont(QFont("Helvetica", 10))
        self.max_stocks_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.max_stocks_label)

        self.contact_info = QLabel("© 2024 Daniel Keller. All rights reserved. | dkellerny@outlook.com")
        self.contact_info.setFont(QFont("Helvetica", 10))
        self.contact_info.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.contact_info)

    def add_to_watchlist_from_entry(self):
        tickers = self.stock_entry.text().upper().split(',')
        tickers = [ticker.strip() for ticker in tickers if ticker.strip()]
        if len(tickers) > 5:
            self.error_label.setText("You can add up to 5 tickers at a time.")
            return
        
        invalid_tickers = []

        for ticker in tickers:
            if len(ticker) > 0 and ticker not in self.main_window.watchlist and len(self.main_window.watchlist) < 25:
                if self.is_valid_ticker(ticker):
                    self.main_window.watchlist.append(ticker)
                else:
                    invalid_tickers.append(ticker)

        if invalid_tickers:
            self.error_label.setText(f"Invalid ticker(s): {', '.join(invalid_tickers)}, try again.")
        else:
            self.error_label.setText("")

        self.main_window.save_watchlist(self.main_window.auth.current_user)
        self.update_watchlist_display()

    def is_valid_ticker(self, ticker):
        try:
            data = yf.download(ticker, period="1d", interval="1m")
            return not data.empty
        except Exception as e:
            print(f"Error validating ticker {ticker}: {e}")
            return False

    def update_watchlist_display(self):
        for i in reversed(range(self.scroll_layout.count())):
            widget_to_remove = self.scroll_layout.itemAt(i).widget()
            self.scroll_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        sorted_watchlist = sorted(self.main_window.watchlist)
        for index, stock in enumerate(sorted_watchlist, start=1):
            stock_frame = QFrame(self)
            stock_layout = QHBoxLayout(stock_frame)

            stock_label = QLabel(f"{index}. {stock}", self)
            stock_label.setFont(QFont("Helvetica", 10, QFont.Bold))
            stock_layout.addWidget(stock_label)

            stock_frame.setLayout(stock_layout)
            self.show_stock_glimpse(stock_frame, stock)
            self.scroll_layout.addWidget(stock_frame)

    def show_stock_glimpse(self, frame, stock):
        data = yf.download(stock, period="1d", interval="1m")
        if not data.empty:
            last_price = data['Close'].iloc[-1]
                        
            if isinstance(last_price, pd.Series):
                last_price = last_price.iloc[0]  # Extract the first value
            
            prev_close = data['Open'].iloc[0]
            change = last_price - prev_close
            color = 'green' if (change > 0).all() else 'red'
            volume = data['Volume'].iloc[-1]

            price_text = f"Price: ${last_price:.2f}"
            change_text = f"Change: {change:+.2f}%"
            volume_text = f"Volume: {volume:,}"

            details_label = QLabel(f"{price_text}\n{change_text}\n{volume_text}")
            details_label.setStyleSheet(f"color: {color};")
            frame.layout().addWidget(details_label)

            figure = plt.Figure(figsize=(2, 1), dpi=80)
            ax = figure.add_subplot(111)
            ax.plot(data['Close'], label=stock, color='green' if change > 0 else 'red')
            ax.set_facecolor('dimgrey')
            ax.axis('off')

            canvas = FigureCanvas(figure)
            frame.layout().addWidget(canvas)

            view_button = QPushButton("View Details", self)
            view_button.clicked.connect(lambda: self.view_details(stock))
            frame.layout().addWidget(view_button)

            remove_button = QPushButton("Remove", self)
            remove_button.setFixedSize(60, 30)
            remove_button.clicked.connect(lambda: self.remove_from_watchlist(stock))
            frame.layout().addWidget(remove_button)

            self.scroll_layout.addWidget(frame)

    def remove_from_watchlist(self, stock):
        if stock in self.main_window.watchlist:
            self.main_window.watchlist.remove(stock)
            self.main_window.save_watchlist(self.main_window.auth.current_user)
            self.update_watchlist_display()

    def view_details(self, stock):
        self.main_window.show_stock_details(stock)

    def update_news_display(self):
        news_fetcher = NewsFetcher()
        news_articles = news_fetcher.get_news()
        if not news_articles:
            self.news_layout.addWidget(QLabel("No news available"))
        else:
            for title, link in news_articles:
                news_frame = QFrame(self)
                news_layout = QHBoxLayout(news_frame)

                text_layout = QVBoxLayout()
                title_label = QLabel(f"<a href='{link}'>{title}</a>")
                title_label.setOpenExternalLinks(True)
                text_layout.addWidget(title_label)

                news_layout.addLayout(text_layout)
                self.news_layout.addWidget(news_frame)
                self.news_labels.append(news_frame)

            if self.news_labels:
                self.news_timer.start(5000)

    def rotate_news_headlines(self):
        if self.news_labels:
            self.news_labels[self.current_news_index].setVisible(False)
            self.current_news_index = (self.current_news_index + 1) % len(self.news_labels)
            self.news_labels[self.current_news_index].setVisible(True)

    def update_stylesheet(self):
        self.setStyleSheet(self.main_window.get_stylesheet())
        for child in self.findChildren(QWidget):
            child.setStyleSheet(self.main_window.get_stylesheet())


class StockDetailsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        self.home_button = QPushButton("Home", self)
        self.home_button.clicked.connect(self.main_window.show_home_page)
        self.layout.addWidget(self.home_button)

        self.stock_entry = QLineEdit(self)
        self.layout.addWidget(self.stock_entry)

        self.time_frame = QComboBox(self)
        self.time_frame.addItems([
            "1 day", "1 month", "3 months", "6 months", "ytd", "ttm", "5 years", "max"
        ])
        self.layout.addWidget(self.time_frame)

        self.sma_spinbox = QSpinBox(self)
        self.sma_spinbox.setRange(0, 200)
        self.sma_spinbox.setValue(0)
        self.sma_spinbox.setPrefix("SMA: ")
        self.layout.addWidget(self.sma_spinbox)

        self.ema_spinbox = QSpinBox(self)
        self.ema_spinbox.setRange(0, 50)
        self.ema_spinbox.setValue(0)
        self.ema_spinbox.setPrefix("EMA: ")
        self.layout.addWidget(self.ema_spinbox)

        self.fetch_button = QPushButton("Refresh", self)
        self.fetch_button.clicked.connect(self.fetch_data)
        self.layout.addWidget(self.fetch_button)

        self.figure = plt.Figure()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas, stretch=8)

        self.figure_secondary = plt.Figure()
        self.canvas_secondary = FigureCanvas(self.figure_secondary)
        self.layout.addWidget(self.canvas_secondary, stretch=2)
        self.canvas_secondary.setVisible(False)

        self.rsi_button = QPushButton("Toggle RSI", self)
        self.rsi_button.clicked.connect(self.toggle_rsi)
        self.layout.addWidget(self.rsi_button)

        self.adx_button = QPushButton("Toggle ADX", self)
        self.adx_button.clicked.connect(self.toggle_adx)
        self.layout.addWidget(self.adx_button)

        self.info_label = QLabel("", self)
        self.layout.addWidget(self.info_label)

        self.button_frame = QFrame(self)
        self.button_layout = QHBoxLayout(self.button_frame)
        self.layout.addWidget(self.button_frame)

        self.sma_50_button = QPushButton("50-day SMA", self)
        self.sma_50_button.clicked.connect(lambda: self.toggle_line('50-day SMA'))
        self.button_layout.addWidget(self.sma_50_button)

        self.sma_200_button = QPushButton("200-day SMA", self)
        self.sma_200_button.clicked.connect(lambda: self.toggle_line('200-day SMA'))
        self.button_layout.addWidget(self.sma_200_button)

        self.ema_12_button = QPushButton("12-day EMA", self)
        self.ema_12_button.clicked.connect(lambda: self.toggle_line('12-day EMA'))
        self.button_layout.addWidget(self.ema_12_button)

        self.upper_bb_button = QPushButton("Upper BB", self)
        self.upper_bb_button.clicked.connect(lambda: self.toggle_line('Upper Bollinger Band'))
        self.button_layout.addWidget(self.upper_bb_button)

        self.lower_bb_button = QPushButton("Lower BB", self)
        self.lower_bb_button.clicked.connect(lambda: self.toggle_line('Lower Bollinger Band'))
        self.button_layout.addWidget(self.lower_bb_button)

        self.displayed_lines = {
            'Close Price': True, '50-day SMA': False, '200-day SMA': False, '12-day EMA': False,
            'Upper Bollinger Band': False, 'Lower Bollinger Band': False
        }

        self.show_rsi = False
        self.show_adx = False

    def display_stock(self, stock):
        self.stock_entry.setText(stock)
        self.fetch_data()

    def fetch_data(self):
        stock_symbol = self.stock_entry.text()
        time_frame = self.time_frame.currentText()

        if time_frame == "1 day":
            period = "1d"
            interval = "1m"
        elif time_frame == "1 month":
            period = "1mo"
            interval = "30m"
        elif time_frame == "3 months":
            period = "3mo"
            interval = "1h"
        elif time_frame == "6 months":
            period = "6mo"
            interval = "1d"
        elif time_frame == "ytd":
            period = "ytd"
            interval = "1d"
        elif time_frame == "ttm":
            period = "1y"
            interval = "1d"
        elif time_frame == "5 years":
            period = "5y"
            interval = "1wk"
        elif time_frame == "max":
            period = "max"
            interval = "1mo"
        else:
            period = "1y"
            interval = "1d"

        self.data = yf.download(stock_symbol, period=period, interval=interval)

        if not self.data.empty:
            self.plot_data()
        else:
            print("No data found for the given stock symbol.")
            self.data = None

    def plot_data(self):
        if self.data is None or self.data.empty:
            return

        data = self.data.copy()

        sma_period = self.sma_spinbox.value()
        ema_period = self.ema_spinbox.value()

        if sma_period > 0:
            data[f'SMA_{sma_period}'] = data['Close'].rolling(window=sma_period).mean()
        else:
            data[f'SMA_{sma_period}'] = pd.Series(dtype=float)

        if ema_period > 0:
            data[f'EMA_{ema_period}'] = data['Close'].ewm(span=ema_period, adjust=False).mean()
        else:
            data[f'EMA_{ema_period}'] = pd.Series(dtype=float)

        if len(data) >= 50:
            data['SMA_50'] = data['Close'].rolling(window=50).mean()
        else:
            data['SMA_50'] = pd.Series(dtype=float)

        if len(data) >= 200:
            data['SMA_200'] = data['Close'].rolling(window=200).mean()
        else:
            data['SMA_200'] = pd.Series(dtype=float)

        if len(data) >= 12:
            data['EMA_12'] = data['Close'].ewm(span=12, adjust=False).mean()
        else:
            data['EMA_12'] = pd.Series(dtype=float)

        if len(data) >= 14:
            data['RSI'] = self.calculate_rsi(data['Close'], 14)
            data['ADX'], data['+DI'], data['-DI'] = self.calculate_adx(data, 14)
        else:
            data['RSI'] = pd.Series(dtype=float)
            data['ADX'], data['+DI'], data['-DI'] = pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)

        if len(data) >= 20:
            data['Upper_BB'], data['Lower_BB'] = self.calculate_bollinger_bands(data['Close'])
        else:
            data['Upper_BB'], data['Lower_BB'] = pd.Series(dtype=float), pd.Series(dtype=float)

        self.figure.clf()

        # Determine the layout based on whether RSI or ADX is toggled
        if self.show_rsi or self.show_adx:
            gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
            ax1 = self.figure.add_subplot(gs[0])
            ax2 = self.figure.add_subplot(gs[1], sharex=ax1)
        else:
            gs = gridspec.GridSpec(1, 1)
            ax1 = self.figure.add_subplot(gs[0])
            ax2 = None  

        if self.main_window.current_mode == 'dark':
            ax1.set_facecolor('dimgrey')
            title_color = 'grey'
            colors = {
                'Close Price': 'indigo', '50-day SMA': 'magenta', '200-day SMA': 'yellow',
                '12-day EMA': 'lime', 'Upper Bollinger Band': 'lime', 'Lower Bollinger Band': 'orange',
                f'SMA_{sma_period}': 'blue', f'EMA_{ema_period}': 'purple'
            }
        else:
            ax1.set_facecolor('white')
            title_color = 'dimgrey'
            colors = {
                'Close Price': 'indigo', '50-day SMA': 'red', '200-day SMA': 'green',
                '12-day EMA': 'purple', 'Upper Bollinger Band': 'red', 'Lower Bollinger Band': 'brown',
                f'SMA_{sma_period}': 'orange', f'EMA_{ema_period}': 'pink'
            }

        if self.displayed_lines['Close Price']:
            line, = ax1.plot(data.index, data['Close'], label='Close Price', color=colors['Close Price'])
        if self.displayed_lines['50-day SMA'] and not data['SMA_50'].isna().all():
            ax1.plot(data['SMA_50'], label='50-day SMA', color=colors['50-day SMA'])
        if self.displayed_lines['200-day SMA'] and not data['SMA_200'].isna().all():
            ax1.plot(data['SMA_200'], label='200-day SMA', color=colors['200-day SMA'])
        if self.displayed_lines['12-day EMA'] and not data['EMA_12'].isna().all():
            ax1.plot(data['EMA_12'], label='12-day EMA', color=colors['12-day EMA'])
        if self.displayed_lines['Upper Bollinger Band'] and not data['Upper_BB'].isna().all():
            ax1.plot(data['Upper_BB'], label='Upper Bollinger Band', linestyle='--', color=colors['Upper Bollinger Band'])
        if self.displayed_lines['Lower Bollinger Band'] and not data['Lower_BB'].isna().all():
            ax1.plot(data['Lower_BB'], label='Lower Bollinger Band', linestyle='--', color=colors['Lower Bollinger Band'])
        if sma_period > 0 and not data[f'SMA_{sma_period}'].isna().all():
            ax1.plot(data[f'SMA_{sma_period}'], label=f'SMA_{sma_period}', color=colors[f'SMA_{sma_period}'])
        if ema_period > 0 and not data[f'EMA_{ema_period}'].isna().all():
            ax1.plot(data[f'EMA_{ema_period}'], label=f'EMA_{ema_period}', color=colors[f'EMA_{ema_period}'])

        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

        ax1.set_ylim(data['Close'].min(), data['Close'].max())
        ax1.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        
        ax1.xaxis.set_minor_locator(ticker.NullLocator())
        ax1.yaxis.set_minor_locator(ticker.NullLocator())

        # Customizations for main price plot
        ax1.tick_params(axis='x', colors='black' if self.main_window.current_mode == 'light' else 'black')
        ax1.tick_params(axis='y', colors='black' if self.main_window.current_mode == 'light' else 'black')
        ax1.spines['bottom'].set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.spines['top'].set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.spines['left'].set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.spines['right'].set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.yaxis.label.set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.xaxis.label.set_color('gainsboro' if self.main_window.current_mode == 'light' else 'gainsboro')
        ax1.title.set_color(title_color)

        time_frame = self.time_frame.currentText()
        ax1.set_title(f'{time_frame} {self.stock_entry.text()} Trends', color=title_color)
        ax1.set_ylabel('Price', color='black' if self.main_window.current_mode == 'light' else 'black')
        ax1.legend(facecolor='white' if self.main_window.current_mode == 'light' else 'grey', edgecolor='black' if self.main_window.current_mode == 'light' else 'grey', loc='upper left')

        ax1.tick_params(axis='x', rotation=45)

        if self.show_rsi or self.show_adx:
            self.canvas_secondary.setVisible(True)
        else:
            self.canvas_secondary.setVisible(False)

        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        if self.show_rsi or self.show_adx:
            self.canvas_secondary.setVisible(True)
            ax2.clear()
            if self.show_rsi:
                ax2.set_facecolor(color = 'dimgrey' if self.main_window.current_mode == 'dark' else 'white')
                ax2.plot(data['RSI'], label='RSI', color='indigo' if self.main_window.current_mode == 'light' else 'indigo')
                ax2.axhline(y=70, color = 'peru')
                ax2.axhline(y=30, color = 'greenyellow')
                ax2.set_ylim(0, 100)
                ax2.set_ylabel('RSI Value', color='black' if self.main_window.current_mode == 'light' else 'grey')
            elif self.show_adx:
                ax2.set_facecolor(color = 'dimgrey' if self.main_window.current_mode == 'dark' else 'white')
                ax2.plot(data['ADX'], label='ADX', color='indigo' if self.main_window.current_mode == 'light' else 'indigo')
                ax2.plot(data['+DI'], label='+DI', color='olivedrab' if self.main_window.current_mode == 'light' else 'lime')
                ax2.plot(data['-DI'], label='-DI', color='gold')
                ax2.set_ylabel('ADX Value', color='black' if self.main_window.current_mode == 'light' else 'grey')

            ax2.tick_params(axis='x', colors='black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.tick_params(axis='y', colors='black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.spines['bottom'].set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.spines['top'].set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.spines['left'].set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.spines['right'].set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.yaxis.label.set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.xaxis.label.set_color('black' if self.main_window.current_mode == 'light' else 'grey')
            ax2.legend(facecolor='white' if self.main_window.current_mode == 'light' else 'grey', edgecolor='black' if self.main_window.current_mode == 'light' else 'grey', loc='upper left')
            self.figure_secondary.tight_layout()
        else:
            self.canvas_secondary.setVisible(False)

        self.figure.tight_layout()
        self.canvas.draw()
        self.canvas_secondary.draw()

        # Adding cursor and hover functionality
        cursor = Cursor(ax1, useblit=True, color='white', linewidth=1)

        # Annotation for hover
        annot = ax1.annotate("", xy=(0,0), xytext=(20,20),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w"),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = data.index[ind["ind"][0]], data['Close'].iloc[ind["ind"][0]]
            annot.xy = (x, y)
            text = f"{x.strftime('%Y-%m-%d')}\n{y:.2f}"
            annot.set_text(text)
            annot.get_bbox_patch().set_facecolor('yellow' if self.main_window.current_mode == 'dark' else 'dimgrey')
            annot.get_bbox_patch().set_alpha(0.7)

        def on_hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax1:
                cont, ind = line.contains(event)
                if cont:
                    update_annot(ind)
                    annot.set_visible(True)
                    self.canvas.draw_idle()
                else:
                    if vis:
                        annot.set_visible(False)
                        self.canvas.draw_idle()

        self.canvas.mpl_connect("motion_notify_event", on_hover)
        

    def toggle_line(self, line_name):
        button_styles = {
            '50-day SMA': self.sma_50_button,
            '200-day SMA': self.sma_200_button,
            '12-day EMA': self.ema_12_button,
            'Upper Bollinger Band': self.upper_bb_button,
            'Lower Bollinger Band': self.lower_bb_button
        }

        if self.displayed_lines[line_name]:
            self.displayed_lines[line_name] = False
            button_styles[line_name].setStyleSheet("background-color: #3B4B61; color: white;")
        else:
            active_lines = sum(self.displayed_lines.values())
            if active_lines < 3:
                self.displayed_lines[line_name] = True
                button_styles[line_name].setStyleSheet("background-color: grey; color: white;")
            else:
                print("You can display up to three lines at a time.")

        self.plot_data()

    def toggle_rsi(self):
        self.show_rsi = not self.show_rsi
        if self.show_rsi:
            self.show_adx = False
        self.plot_data()

    def toggle_adx(self):
        self.show_adx = not self.show_adx
        if self.show_adx:
            self.show_rsi = False
        self.plot_data()

    def calculate_rsi(self, series, period):
        delta = series.diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_adx(self, data, period):
        high = data['High']
        low = data['Low']
        close = data['Close']
        
        # Calculate True Range (TR)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate Average True Range (ATR)
        atr = tr.rolling(window=period, min_periods=1).mean()
        
        # Calculate Directional Movement (DM)
        plus_dm = high.diff().clip(lower=0)
        minus_dm = low.diff().clip(upper=0).abs()
        
        # Calculate Smoothed DM
        smoothed_plus_dm = plus_dm.rolling(window=period, min_periods=1).mean()
        smoothed_minus_dm = minus_dm.rolling(window=period, min_periods=1).mean()
        
        # Calculate Plus DI and Minus DI
        plus_di = 100 * smoothed_plus_dm / atr
        minus_di = 100 * smoothed_minus_dm / atr
        
        # Calculate DX
        dx = 100 * abs((plus_di - minus_di) / (plus_di + minus_di))
        
        # Smooth DX to get ADX
        adx = dx.rolling(window=period, min_periods=1).mean()
        
        adx = adx.replace([np.inf, -np.inf], np.nan).fillna(0)
        plus_di = plus_di.replace([np.inf, -np.inf], np.nan).fillna(0)
        minus_di = minus_di.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        return adx, plus_di, minus_di

    def calculate_bollinger_bands(self, series, window=20, num_std_dev=2):
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std()
        upper_band = rolling_mean + (rolling_std * num_std_dev)
        lower_band = rolling_mean - (rolling_std * num_std_dev)
        return upper_band, lower_band

    def update_stylesheet(self):
        self.setStyleSheet(self.main_window.get_stylesheet())
        for child in self.findChildren(QWidget):
            child.setStyleSheet(self.main_window.get_stylesheet())


class SettingsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        self.back_button = QPushButton("Home", self)
        self.back_button.clicked.connect(self.main_window.navigate_back)
        self.layout.addWidget(self.back_button)

        title_label = QLabel("Settings")
        title_label.setFont(QFont("Helvetica", 16))
        self.layout.addWidget(title_label)

        self.mode_button = QPushButton("Switch to Light Mode", self)
        self.mode_button.clicked.connect(self.toggle_mode)
        self.layout.addWidget(self.mode_button)

    def toggle_mode(self):
        if self.main_window.current_mode == 'dark':
            self.main_window.change_mode('light')
            self.mode_button.setText("Switch to Dark Mode")
        else:
            self.main_window.change_mode('dark')
            self.mode_button.setText("Switch to Light Mode")

    def update_stylesheet(self):
        self.setStyleSheet(self.main_window.get_stylesheet())
        for child in self.findChildren(QWidget):
            child.setStyleSheet(self.main_window.get_stylesheet())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
