import requests
import logging
from config import BASE_URL, API_TIMEOUT_SECONDS
from utils.file_helper import load_access_token, perform_logout_ui


class APIService:
    """
    API client for Printer Agent.
    
    Implements all endpoints documented in PRINTER_API.md:
    - Heartbeat: mark printer connected
    - Printers: CRUD operations (vendor only)
    - Printer Types: CRUD operations (vendor only)
    - Print Jobs: list, retrieve, poll, acknowledge
    - Printer Order Items: get order details for printing
    """
    
    BASE_URL = BASE_URL
    TIMEOUT = API_TIMEOUT_SECONDS

    def __init__(self):
        token = load_access_token()
        self.token = token
        logging.info(f"APIService init, token present={bool(self.token)}")

    def _auth_headers(self) -> dict:
        """Return headers including Authorization only when token is present."""
        headers = {}
        token = self.token or load_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _log_response(self, r: requests.Response):
        """Log status and summary of the API response."""
        logging.info(f"API {r.request.method} {r.url} -> Status: {r.status_code}")
        logging.debug(f"Response Body: {r.text[:1000]}")

    def reload_token(self) -> None:
        """Reload token from storage into this service instance."""
        try:
            token = load_access_token()
            if token != self.token:
                logging.info("APIService token reloaded (present=%s)", bool(token))
            self.token = token
        except Exception:
            logging.exception("Failed to reload token")

    def _handle_401(self, endpoint: str) -> None:
        """Handle 401 Unauthorized response."""
        logging.warning(f"{endpoint} returned 401; reloading token and performing logout")
        self.reload_token()
        perform_logout_ui()

    # ============================================================================
    # Heartbeat (Public endpoint - AllowAny)
    # ============================================================================

    def send_heartbeat(self, payload: dict | None = None) -> requests.Response:
        """
        POST /api/heartbeat/
        
        Register or mark printer connected. Public endpoint.
        
        Payload (one of):
        - { "printer_id": "<printer_pk>" }
        - { "ip": "192.0.2.10", "port": 9100 }
        
        Response on success (200):
        {
          "status": "ok",
          "printer": {
            "id": "...",
            "name": "Kitchen Left",
            "ip": "192.0.2.10",
            "port": 9100,
            "location": "Kitchen",
            "is_connected": true,
            "last_heartbeat": "2026-04-20T12:34:56Z"
          }
        }
        """
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            r = requests.post(
                f"{self.BASE_URL}/api/heartbeat/",
                headers=headers,
                json=payload or {},
                timeout=self.TIMEOUT
            )

            if r.status_code == 401:
                logging.warning("send_heartbeat returned 401; reloading token and retrying")
                self.reload_token()
                headers = dict(self._auth_headers())
                headers.setdefault("Content-Type", "application/json")
                if headers.get("Authorization"):
                    r = requests.post(
                        f"{self.BASE_URL}/api/heartbeat/",
                        headers=headers,
                        json=payload or {},
                        timeout=self.TIMEOUT
                    )
                    if r.status_code == 401:
                        self._handle_401("send_heartbeat")
                        return r

            if r.status_code >= 400:
                logging.warning(f"send_heartbeat returned {r.status_code}: {r.text}")
            self._log_response(r)
            return r
        except Exception:
            logging.exception("send_heartbeat failed")
            raise

    # ============================================================================
    # Printers (CRUD - vendor only)
    # ============================================================================

    def get_printers(self) -> dict | list:
        """
        GET /api/printers/
        
        List all printers. Vendor only.
        
        Returns:
            Response with results list containing printer objects with fields:
            id, name, type, ip, port, location, is_connected, last_heartbeat
        """
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/printers/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            if r.status_code == 401:
                logging.warning("get_printers returned 401; performing logout")
                self._handle_401("get_printers")
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception("get_printers failed")
            raise

    def get_printer(self, printer_id: str) -> dict:
        """
        GET /api/printers/{id}/
        
        Retrieve single printer details. Vendor only.
        """
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/printers/{printer_id}/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception(f"get_printer({printer_id}) failed")
            raise

    def create_printer(self, data: dict) -> dict:
        """
        POST /api/printers/
        
        Create new printer. Vendor only.
        
        Body example:
        {
          "name": "Kitchen Left",
          "type": "<printer_type_id>",
          "ip": "192.0.2.10",
          "port": 9100,
          "location": "Kitchen"
        }
        """
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            r = requests.post(
                f"{self.BASE_URL}/api/printers/",
                headers=headers,
                json=data,
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception("create_printer failed")
            raise

    def update_printer(self, printer_id: str, data: dict) -> dict:
        """
        PUT/PATCH /api/printers/{id}/
        
        Update printer. Vendor only.
        """
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            r = requests.patch(
                f"{self.BASE_URL}/api/printers/{printer_id}/",
                headers=headers,
                json=data,
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception(f"update_printer({printer_id}) failed")
            raise

    def delete_printer(self, printer_id: str) -> None:
        """
        DELETE /api/printers/{id}/
        
        Delete printer. Vendor only.
        """
        try:
            r = requests.delete(
                f"{self.BASE_URL}/api/printers/{printer_id}/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            logging.info(f"delete_printer({printer_id}) successful")
        except Exception:
            logging.exception(f"delete_printer({printer_id}) failed")
            raise

    # ============================================================================
    # Printer Types (CRUD - vendor only)
    # ============================================================================

    def get_printer_types(self) -> dict | list:
        """
        GET /api/printer-types/
        
        List all printer types. Vendor only.
        """
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/printer-types/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception("get_printer_types failed")
            raise

    def create_printer_type(self, name: str, description: str = "") -> dict:
        """
        POST /api/printer-types/
        
        Create new printer type. Vendor only.
        """
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            r = requests.post(
                f"{self.BASE_URL}/api/printer-types/",
                headers=headers,
                json={"name": name, "description": description},
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception("create_printer_type failed")
            raise

    # ============================================================================
    # Print Jobs (List / Retrieve / Poll / Ack)
    # ============================================================================

    def get_print_jobs(self, status: str | None = None, printer_id: str | None = None,
                      order_id: str | None = None, limit: int = 10) -> dict | list:
        """
        GET /api/printjobs/
        
        List print jobs with optional filters. Staff/vendor only.
        
        Query params:
        - status: PENDING|SENT|PRINTED|FAILED
        - printer_id: filter by printer
        - order_id: filter by order
        - limit: max results (default 10)
        """
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status
            if printer_id:
                params["printer_id"] = printer_id
            if order_id:
                params["order_id"] = order_id

            r = requests.get(
                f"{self.BASE_URL}/api/printjobs/",
                headers=self._auth_headers(),
                params=params,
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception("get_print_jobs failed")
            raise

    def get_print_job(self, print_job_id: str) -> dict:
        """
        GET /api/printjobs/{print_job_id}/
        
        Retrieve single print job. Staff/vendor only.
        
        Response includes:
        - id, order_id, printer_id, payload, format, status, attempts, 
          last_error, created_at, printed_at
        """
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/printjobs/{print_job_id}/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception(f"get_print_job({print_job_id}) failed")
            raise

    def poll_print_jobs(self, printer_id: str | None = None, limit: int = 10,
                       claim: bool = True) -> list:
        """
        GET /api/printjobs/poll/
        
        Poll for pending print jobs. Staff/vendor only.
        
        Recommended: use claim=true to avoid duplicate printing from multiple devices.
        When claiming, jobs are atomically marked as SENT and assigned to printer.
        
        Query params:
        - printer_id: restrict to specific printer (optional)
        - limit: max jobs to return (default 10)
        - claim: if true, mark returned jobs as SENT (default True)
        
        Returns list of pending print jobs with fields:
        - id, order_id, printer_id, payload, format, status, attempts, 
          last_error, created_at
        """
        try:
            params = {"limit": limit}
            if printer_id:
                params["printer_id"] = printer_id
            if claim:
                params["claim"] = "true"

            r = requests.get(
                f"{self.BASE_URL}/api/printjobs/poll/",
                headers=self._auth_headers(),
                params=params,
                timeout=self.TIMEOUT
            )
            if r.status_code == 404:
                logging.error("Polling endpoint not found (404). Check if '/api/printjobs/poll/' is correctly configured on the server.")
                raise requests.exceptions.HTTPError("Server endpoint not found (404). Please check backend URL configuration.", response=r)
            
            r.raise_for_status()
            self._log_response(r)
            result = r.json()
            # Handle both list and paginated responses
            if isinstance(result, dict):
                jobs = result.get("results", [])
            else:
                jobs = result if isinstance(result, list) else []
            
            # Log detailed job information
            if jobs:
                logging.info(f"POLL RESULT: Received {len(jobs)} job(s)")
                for job in jobs:
                    logging.info(f"  ├─ Job ID: {job.get('id')}")
                    logging.info(f"  ├─ Order ID: {job.get('order_id')}")
                    logging.info(f"  ├─ Status: {job.get('status')}")
                    logging.info(f"  └─ Format: {job.get('format')}")
            else:
                logging.info("POLL RESULT: No pending jobs")
            
            return jobs
        except Exception:
            logging.exception("poll_print_jobs failed")
            raise

    def ack_print_job(self, print_job_id: str, status: str = "OK", error: str | None = None) -> dict:
        """
        POST /api/printjobs/{print_job_id}/ack/
        
        Acknowledge print job completion. Public endpoint (AllowAny).
        
        Body:
        - Success: { "status": "OK" }
        - Failure: { "status": "FAILED", "error": "Paper jam" }
        
        Response on success (200):
        { "ok": true, "status": "PRINTED" }
        
        Response on failure (400):
        { "ok": false, "status": "FAILED", "error": "Paper jam" }
        
        Security Note: Currently open (AllowAny). For production, consider:
        - Device API keys stored in Printer record
        - HMAC signatures
        - IP whitelisting for printer network ranges
        """
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            
            payload = {"status": status}
            if error:
                payload["error"] = error

            r = requests.post(
                f"{self.BASE_URL}/api/printjobs/{print_job_id}/ack/",
                headers=headers,
                json=payload,
                timeout=self.TIMEOUT
            )
            # ack endpoint may return different status codes
            if r.status_code >= 400:
                logging.warning(f"ack_print_job({print_job_id}) returned {r.status_code}: {r.text}")
            self._log_response(r)
            return r.json() if r.text and r.status_code != 204 else {}
        except Exception:
            logging.exception(f"ack_print_job({print_job_id}) failed")
            raise

    # ============================================================================
    # Printer Order Items (compact order details)
    # ============================================================================

    def get_printer_order_items(self, order_id: str) -> dict:
        """
        GET /api/printer-order-items/{order_id}/
        
        Get compact, printer-friendly order details. Staff/vendor only.
        Good for kitchen/bar apps that only need item + qty + table number.
        
        Response example:
        {
          "order_id": "3b9f2e11-...",
          "table_number": "T12",
          "items": [
            {"item_id": "a1b2", "name": "Margherita Pizza", "quantity": 1},
            {"item_id": "c3d4", "name": "Fries", "quantity": 2}
          ]
        }
        """
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/printer-order-items/{order_id}/",
                headers=self._auth_headers(),
                timeout=self.TIMEOUT
            )
            r.raise_for_status()
            self._log_response(r)
            return r.json()
        except Exception:
            logging.exception(f"get_printer_order_items({order_id}) failed")
            raise
