import requests
import logging
from config import BASE_URL
from utils.file_helper import load_access_token, perform_logout_ui


class APIService:
    BASE_URL = BASE_URL

    def __init__(self):
        token = load_access_token()
        self.token = token
        logging.info(f"APIService init, token present={bool(self.token)}")

        # Do not store headers permanently — build them per-request so we
        # pick up token changes (refresh/login) and avoid sending malformed
        # Authorization headers when token is empty.

    def get_printers(self):
        try:
            r = requests.get(f"{self.BASE_URL}/api/printers/", headers=self._auth_headers())
            if r.status_code == 401:
                # immediate logout on unauthorized
                logging.warning("get_printers returned 401; performing logout")
                try:
                    perform_logout_ui()
                finally:
                    r.raise_for_status()
            r.raise_for_status()
            return r.json()
        except Exception:
            logging.exception("get_printers failed")
            raise

    # def get_print_jobs(self):
    #     try:
    #         r = requests.get(f"{self.BASE_URL}/print-jobs", headers=self.headers)
    #         r.raise_for_status()
    #         return r.json()
    #     except Exception:
    #         logging.exception("get_print_jobs failed")
    #         raise

    def _auth_headers(self) -> dict:
        """Return headers including Authorization only when token is present."""
        headers = {}
        token = self.token or load_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def reload_token(self) -> None:
        """Reload token from storage into this service instance."""
        try:
            token = load_access_token()
            if token != self.token:
                logging.info("APIService token reloaded (present=%s)", bool(token))
            self.token = token
        except Exception:
            logging.exception("Failed to reload token")

    def send_heartbeat(self, payload: dict | None = None):
        try:
            headers = dict(self._auth_headers())
            headers.setdefault("Content-Type", "application/json")
            r = requests.post(f"{self.BASE_URL}/api/heartbeat/", headers=headers, json=payload or {}, timeout=10)

            # If unauthorized, try reloading token once (maybe it was refreshed by login)
            if r.status_code == 401:
                logging.warning("send_heartbeat returned 401; reloading token and retrying")
                self.reload_token()
                headers = dict(self._auth_headers())
                headers.setdefault("Content-Type", "application/json")
                if headers.get("Authorization"):
                    r2 = requests.post(f"{self.BASE_URL}/api/heartbeat/", headers=headers, json=payload or {}, timeout=10)
                    if r2.status_code == 401:
                        logging.warning("send_heartbeat retry also returned 401; performing logout")
                        try:
                            perform_logout_ui()
                        finally:
                            if r2.status_code >= 400:
                                logging.warning("send_heartbeat retry returned %s: %s", r2.status_code, r2.text)
                            return r2
                    if r2.status_code >= 400:
                        logging.warning("send_heartbeat retry returned %s: %s", r2.status_code, r2.text)
                    return r2

            if r.status_code >= 400:
                logging.warning("send_heartbeat returned %s: %s", r.status_code, r.text)
            return r
        except Exception:
            logging.exception("send_heartbeat failed")
            raise
