from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox,
    QHBoxLayout, QSpacerItem, QSizePolicy, QFrame
)
import requests
import json
from config import BASE_URL
from utils.file_helper import save_tokens
from ui.main_window import MainWindow
import logging
import logging


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printer Agent Login")
        self.resize(360, 240)

        # Main vertical layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header / logo area
        header = QHBoxLayout()
        title = QLabel("Printer Agent")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Sign in to continue")
        subtitle.setObjectName("subtitleLabel")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        layout.addWidget(subtitle)

        # Form
        form_frame = QFrame()
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone")
        self.phone_input.setObjectName("phoneInput")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setObjectName("passwordInput")

        form_layout.addWidget(self.phone_input)
        form_layout.addWidget(self.password_input)
        form_frame.setLayout(form_layout)
        layout.addWidget(form_frame)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.login_button = QPushButton("Sign In")
        self.login_button.setObjectName("primaryBtn")
        self.login_button.clicked.connect(self.login)
        btn_row.addWidget(self.login_button)
        layout.addLayout(btn_row)

        # Footer note
        footer = QLabel("Need help? Contact support.")
        footer.setObjectName("footerLabel")
        layout.addWidget(footer)

        self.setLayout(layout)

        # Styles
        self.setStyleSheet("""
        #titleLabel { font-size: 18px; font-weight: 600; }
        #subtitleLabel { color: #666; margin-bottom: 8px; }
        QLineEdit { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        QPushButton#primaryBtn { background-color: #2b8aef; color: white; padding: 8px 14px; border-radius: 4px; }
        QPushButton#primaryBtn:hover { background-color: #1677d2; }
        #footerLabel { color: #888; font-size: 11px; margin-top: 8px; }
        """)


    def login(self):
        phone = self.phone_input.text().strip()
        password = self.password_input.text()

        if not phone or not password:
            QMessageBox.warning(self, "Error", "Please enter phone and password")
            return
        logging.info("Login attempt: phone=%s", phone)
        logging.info("Sending login request to %s", f"{BASE_URL}/api/vendor/login")
        try:
            response = requests.post(
                f"{BASE_URL}/api/auth/create-token/",
                json={"phone": phone, "password": password},
            )
        except Exception as e:
            logging.exception("Network error during login")
            QMessageBox.warning(self, "Error", f"Network error: {e}")
            return

        if response.status_code == 200:
            logging.info("Login response status: %s", response.status_code)
            try:
                data = response.json()
                logging.info("Login response keys: %s", list(data.keys()))
                access = data.get("access")
                refresh = data.get("refresh")
                if access:
                    logging.info("vendor_access received (len=%d)", len(access))
            except Exception:
                logging.exception("Failed to parse login response as JSON")
                data = {}
                access = None
                refresh = None
            if not access:
                logging.warning("Login failed: no access token in response")
                QMessageBox.warning(self, "Error", "No access token received")
                return

            save_tokens(access, refresh or "")
            logging.info("Saved tokens to auth.json")

            QMessageBox.information(self, "Success", "Login successful!")
            # show main window
            try:
                self.main_window = MainWindow()
                self.main_window.show()
            except Exception:
                logging.exception("Failed to open MainWindow after login")
            self.close()
        else:
            logging.info("Login response status: %s", response.status_code)
            # attempt to capture server message
            try:
                err = response.json()
                logging.info("Login error response: %s", err)
            except Exception:
                logging.info("Login error response text: %s", response.text)
            QMessageBox.warning(self, "Error", "Invalid credentials")
