from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QScrollArea, QFrame, QMessageBox
)
from services.heartbeat_service import HeartbeatService
from services.printjob_service import PrintJobService
from services.api_service import APIService
from services.printer_service import PrinterService
import logging


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printer Agent")
        self.resize(600, 320)

        layout = QVBoxLayout()

        header = QHBoxLayout()
        header.addWidget(QLabel("Available Printers"))
        header.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_printers)
        header.addWidget(self.refresh_btn)
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.clicked.connect(self.logout)
        header.addWidget(self.logout_btn)
        layout.addLayout(header)

        # Scroll area to contain vCard items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(6, 6, 6, 6)
        self.cards_container.setLayout(self.cards_layout)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll)

        self.setLayout(layout)

        self.heartbeat = HeartbeatService()
        self.api = APIService()
        
        # Initialize and start the automatic background printing service
        self.print_job_manager = PrintJobService()
        self._setup_print_signals()
        self.print_job_manager.start()

        # initial load
        self.refresh_printers()

    def _setup_print_signals(self):
        """Connect signals from the print service to handle logs or UI updates."""
        self.print_job_manager.job_printed.connect(
            lambda job_id: logging.info(f"Background: Successfully printed job {job_id}")
        )
        self.print_job_manager.job_failed.connect(
            lambda job_id, err: logging.error(f"Background: Job {job_id} failed: {err}")
        )

    def refresh_printers(self):
        try:
            data = self.api.get_printers()
            logging.info("Fetched printers: %s", data)
        except Exception as e:
            logging.exception("Failed to fetch printers")
            QMessageBox.warning(self, "Error", f"Failed to load printers: {e}")
            return

        results = data.get("results") if isinstance(data, dict) else data
        if results is None:
            results = data

        if not isinstance(results, list) or len(results) == 0:
            QMessageBox.information(self, "Info", "No printers available")
            # clear existing
            while self.cards_layout.count():
                w = self.cards_layout.takeAt(0).widget()
                if w:
                    w.deleteLater()
            return

        # clear existing cards
        while self.cards_layout.count():
            w = self.cards_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        # create vCard-like frames
        for item in results:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setObjectName("printerCard")
            card_layout = QHBoxLayout()
            card_layout.setSpacing(12)

            # left: main info
            left = QVBoxLayout()
            name = item.get('name') or 'Unnamed printer'
            name_label = QLabel(name)
            name_label.setObjectName('cardName')
            name_label.setStyleSheet('font-weight: 600; font-size: 14px;')
            left.addWidget(name_label)

            type_text = item.get('type') or '—'
            loc_text = item.get('location') or '—'
            left.addWidget(QLabel(f"Type: {type_text}"))
            left.addWidget(QLabel(f"Location: {loc_text}"))

            # right: network + actions
            right = QVBoxLayout()
            ip_text = item.get('ip') or '—'
            port_text = item.get('port') or '—'
            connected = item.get('is_connected')
            right.addWidget(QLabel(f"IP: {ip_text}"))
            right.addWidget(QLabel(f"Port: {port_text}"))
            right.addWidget(QLabel(f"Connected: {'Yes' if connected else 'No'}"))
            test_btn = QPushButton("Test Print")
            test_btn.setObjectName('testBtn')
            # capture item in default arg for lambda
            def _on_test(_, i=item):
                ip = i.get('ip')
                port = i.get('port')
                name = i.get('name') or i.get('id')
                if not ip or not port:
                    QMessageBox.warning(self, "Error", f"Printer {name} missing IP or port")
                    return
                ps = PrinterService()
                try:
                    ps.print_text(ip, port, "\n Hello Test\n")
                    QMessageBox.information(self, "Print", f"Sent 'Hello Test' to {name}")
                    logging.info("Test print sent to %s (%s:%s)", name, ip, port)
                except Exception as e:
                    logging.exception("Test print failed for %s", name)
                    QMessageBox.warning(self, "Print Failed", f"Failed to send print to {name}: {e}")

            test_btn.clicked.connect(_on_test)
            right.addStretch()
            right.addWidget(test_btn)

            card_layout.addLayout(left)
            card_layout.addLayout(right)
            card.setLayout(card_layout)

            # styling for readability
            card.setMinimumHeight(80)
            card.setStyleSheet("""
                QFrame#printerCard { border: 1px solid #999; border-radius: 6px; padding: 10px; background: #ffffff; }
                QLabel { color: #111; }
                QPushButton#testBtn { padding: 6px 10px; }
            """)

            self.cards_layout.addWidget(card)

    def logout(self):
        # clear stored tokens and return to login
        try:
            from utils.file_helper import delete_tokens
            delete_tokens()
            logging.info("User logged out: tokens cleared")
        except Exception:
            logging.exception("Failed clearing tokens on logout")

        # stop heartbeat
        try:
            if hasattr(self, 'heartbeat') and getattr(self.heartbeat, 'timer', None):
                self.heartbeat.timer.stop()
        except Exception:
            logging.exception("Failed to stop heartbeat on logout")
            
        # stop printing service
        try:
            if hasattr(self, 'print_job_manager'):
                self.print_job_manager.stop()
        except Exception:
            logging.exception("Failed to stop print service on logout")

        # show login window and close main window
        try:
            from ui.login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()
        except Exception:
            logging.exception("Failed to open LoginWindow after logout")

        self.close()
