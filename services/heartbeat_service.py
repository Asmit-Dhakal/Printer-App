from PySide6.QtCore import QTimer
from services.api_service import APIService
from config import HEARTBEAT_INTERVAL_MS
import logging


class HeartbeatService:
    """
    Periodic heartbeat service to keep printer registered.
    
    Sends heartbeat every HEARTBEAT_INTERVAL_MS (default 30 seconds).
    Heartbeat endpoint is public (AllowAny) so no auth token required.
    """
    
    def __init__(self):
        self.api = APIService()
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_heartbeat)
        self.timer.start(HEARTBEAT_INTERVAL_MS)
        
        # Try to determine a printer identifier to include with heartbeats
        self.printer_identifier = None
        try:
            data = self.api.get_printers()
            results = data.get("results") if isinstance(data, dict) else data
            if results and isinstance(results, list) and len(results) > 0:
                p = results[0]
                # Prefer explicit id if present, otherwise use ip
                if p.get('id'):
                    self.printer_identifier = {'printer_id': p.get('id')}
                elif p.get('ip'):
                    self.printer_identifier = {'ip': p.get('ip'), 'port': p.get('port', 9100)}
        except Exception:
            logging.exception("Failed to load printers for heartbeat; will send without printer identifier")

        logging.info(
            "HeartbeatService started (interval=%dms, printer_identifier=%s)",
            HEARTBEAT_INTERVAL_MS, self.printer_identifier
        )

    def send_heartbeat(self):
        """Send heartbeat to server to mark printer as connected."""
        try:
            # Include printer identifier when available
            if self.printer_identifier:
                resp = self.api.send_heartbeat(payload=self.printer_identifier)
            else:
                resp = self.api.send_heartbeat()
            logging.debug(f"Heartbeat sent: status={getattr(resp, 'status_code', None)}")
        except Exception:
            logging.exception("Heartbeat failed")
