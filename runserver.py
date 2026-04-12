import sys
import logging
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication
from services.heartbeat_service import HeartbeatService
from utils.file_helper import load_access_token
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def setup_logging(log_path: str = "agent.log"):
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main():
    setup_logging()
    logging.info("Starting Printer Agent runserver")

    app = QApplication(sys.argv)

    # start heartbeat service (uses QTimer)
    hb = HeartbeatService()

    # choose which window to show depending on saved token
    token = load_access_token()
    if token:
        logging.info("Access token found — showing MainWindow")
        window = MainWindow()
    else:
        logging.info("No access token — showing LoginWindow")
        window = LoginWindow()

    window.show()

    logging.info("Entering event loop (GUI)")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
