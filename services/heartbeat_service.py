from PySide6.QtCore import QTimer
from services.api_service import APIService
import logging


class HeartbeatService:
    def __init__(self):
        self.api = APIService()
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_heartbeat)
        self.timer.start(30000)  # every 30 seconds
        # try to determine a printer identifier to include with heartbeats
        self.printer_identifier = None
        try:
            data = self.api.get_printers()
            results = data.get("results") if isinstance(data, dict) else data
            if results and isinstance(results, list) and len(results) > 0:
                p = results[0]
                # prefer explicit id if present, otherwise use ip
                if p.get('id'):
                    self.printer_identifier = {'printer_id': p.get('id')}
                elif p.get('ip'):
                    self.printer_identifier = {'ip': p.get('ip')}
        except Exception:
            logging.exception("Failed to load printers for heartbeat; will send without printer identifier")

        logging.info("HeartbeatService started (interval=30s) printer_identifier=%s", self.printer_identifier)

    def send_heartbeat(self):
        try:
            # include printer identifier when available
            if self.printer_identifier:
                resp = self.api.send_heartbeat(payload=self.printer_identifier)
            else:
                resp = self.api.send_heartbeat()
            logging.info(f"Heartbeat sent: status={getattr(resp, 'status_code', None)}")
        except Exception:
            logging.exception("Heartbeat failed")
