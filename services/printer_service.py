import os
import subprocess
import socket
import logging
import tempfile
import subprocess


class PrinterService:
    def print_file(self, file_path):
        # Windows
        if os.name == "nt":
            try:
                os.startfile(file_path, "print")
            except Exception:
                raise
        else:
            # Try lpr on Unix-like systems
            try:
                subprocess.run(["lpr", file_path], check=True)
            except FileNotFoundError:
                raise RuntimeError("No printing command found (lpr missing)")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Printing failed: {e}")

    def test_connection(self, ip: str, port: int, timeout: int = 5) -> bool:
        try:
            with socket.create_connection((ip, int(port)), timeout=timeout):
                return True
        except Exception:
            logging.exception("test_connection failed for %s:%s", ip, port)
            return False

    def print_text(self, ip: str, port: int, text: str, encoding: str = "utf-8") -> None:
        """Send plain text to a network printer (raw TCP on port 9100 / JetDirect).

        This is a minimal implementation suitable for small test prints like "Hello World".
        """
        # append form-feed to try to flush the job on many printers
        data = (text + "\x0c").encode(encoding)
        try:
            # Prefer raw socket printing (works on many JetDirect printers)
            with socket.create_connection((ip, int(port)), timeout=10) as s:
                s.sendall(data)
                return
        except Exception:
            logging.exception("print_text raw socket failed for %s:%s; will try IPP fallback if applicable", ip, port)

        # If port is 631 (IPP) try submitting via IPP using curl as a fallback
        if int(port) == 631:
            try:
                with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
                    tf.write(data)
                    tf.flush()
                    tmpname = tf.name
                # Use curl to submit the file to the printer's IPP endpoint.
                uri = f"ipp://{ip}:631/ipp/print"
                subprocess.run(["curl", "-sS", "-T", tmpname, uri], check=True)
                return
            except Exception:
                logging.exception("IPP fallback print failed for %s:%s", ip, port)
                raise
        else:
            raise

    def print_raw(self, ip: str, port: int, data: bytes) -> None:
        try:
            with socket.create_connection((ip, int(port)), timeout=10) as s:
                s.sendall(data)
        except Exception:
            logging.exception("print_raw failed for %s:%s", ip, port)
            raise
