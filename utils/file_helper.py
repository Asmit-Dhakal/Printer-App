import json
from pathlib import Path
import logging


ROOT = Path(__file__).resolve().parent.parent
AUTH_PATH = ROOT / "auth.json"
KEYRING_SERVICE = "novatech_printer_app"


def _use_keyring() -> bool:
    try:
        import keyring  # type: ignore

        return True
    except Exception:
        return False


def save_tokens(access: str, refresh: str = ""):
    """Save tokens to OS keyring when available, otherwise to a local file with
    restricted permissions (0600). We never log token contents, only presence.
    """
    if _use_keyring():
        try:
            import keyring  # type: ignore

            keyring.set_password(KEYRING_SERVICE, "vendor_access", access)
            if refresh:
                keyring.set_password(KEYRING_SERVICE, "vendor_refresh", refresh)
            else:
                # ensure any previous refresh token is cleared
                try:
                    keyring.delete_password(KEYRING_SERVICE, "vendor_refresh")
                except Exception:
                    pass
            logging.info("Saved auth tokens to keyring (access_present=%s, refresh_present=%s)", bool(access), bool(refresh))
            return
        except Exception:
            logging.exception("Keyring save failed; falling back to file storage")

    # Fallback: write to auth.json with restrictive permissions
    try:
        data = {"vendor_access": access}
        if refresh:
            data["vendor_refresh"] = refresh
        AUTH_PATH.write_text(json.dumps(data, indent=2))
        try:
            AUTH_PATH.chmod(0o600)
        except Exception:
            # Not fatal; ensure at least we attempted to tighten perms
            logging.debug("Failed to chmod auth.json to 600")
        logging.info("Saved auth tokens to %s (access_present=%s, refresh_present=%s)", AUTH_PATH, bool(access), bool(refresh))
    except Exception:
        logging.exception("Failed to save auth tokens to file")


def load_tokens() -> dict:
    """Load tokens from keyring if available, otherwise from file.

    Returns a dict with keys present for the values found. Does not log token
    contents, only which keys are available.
    """
    if _use_keyring():
        try:
            import keyring  # type: ignore

            access = keyring.get_password(KEYRING_SERVICE, "vendor_access")
            refresh = keyring.get_password(KEYRING_SERVICE, "vendor_refresh")
            result = {}
            if access:
                result["vendor_access"] = access
            if refresh:
                result["vendor_refresh"] = refresh
            logging.info("Loaded auth tokens from keyring (keys=%s)", list(result.keys()))
            return result
        except Exception:
            logging.exception("Keyring load failed; falling back to file storage")

    try:
        if not AUTH_PATH.exists():
            return {}
        data = json.loads(AUTH_PATH.read_text())
        logging.info("Loaded auth tokens from %s (keys=%s)", AUTH_PATH, list(data.keys()))
        return data
    except Exception:
        logging.warning("Failed to load auth tokens from %s", AUTH_PATH)
        return {}


def load_access_token() -> str:
    return load_tokens().get("vendor_access", "")


# Backwards-compatible simple wrappers
def save_token(token: str):
    save_tokens(token)


def load_token() -> str:
    return load_access_token()


def delete_tokens():
    try:
        if _use_keyring():
            try:
                import keyring  # type: ignore

                try:
                    keyring.delete_password(KEYRING_SERVICE, "vendor_access")
                except Exception:
                    pass
                try:
                    keyring.delete_password(KEYRING_SERVICE, "vendor_refresh")
                except Exception:
                    pass
                logging.info("Cleared tokens from keyring")
                return
            except Exception:
                logging.exception("Failed clearing keyring tokens; falling back to file")

        if AUTH_PATH.exists():
            AUTH_PATH.write_text(json.dumps({}))
            try:
                AUTH_PATH.chmod(0o600)
            except Exception:
                logging.debug("Failed to chmod auth.json to 600 after clearing")
            logging.info("Cleared tokens in %s", AUTH_PATH)
    except Exception:
        logging.exception("Failed to delete tokens")


def perform_logout_ui():
    """Clear stored tokens and try to return the app to the login window.

    This attempts to clear tokens (keyring/file) and, if a Qt application is
    running, close top-level windows and show the `LoginWindow`.
    """
    delete_tokens()
    try:
        # Import PySide only when available / running in UI process
        from PySide6.QtWidgets import QApplication
        from ui.login_window import LoginWindow

        app = QApplication.instance()
        if app:
            # Close all top-level widgets
            for w in list(app.topLevelWidgets()):
                try:
                    w.close()
                except Exception:
                    logging.exception("Failed closing window during logout")

            # Show login window
            try:
                login = LoginWindow()
                login.show()
            except Exception:
                logging.exception("Failed to open LoginWindow during logout")
    except Exception:
        # Not running in a UI context or PySide unavailable — just clear tokens
        logging.info("Performed token clear; UI unavailable to show login window")
