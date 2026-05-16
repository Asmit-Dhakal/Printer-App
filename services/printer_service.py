import os
import subprocess
import socket
import logging
import tempfile


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
        # append form-feed and cut command to flush and cut the job on many printers
        # ESC/POS cut command: \x1d\x56\x41 (partial cut) or \x1d\x56\x00 (full cut)
        data = (text + "\x0c" + "\x1d\x56\x41").encode(encoding)
        try:
            # Prefer raw socket printing (works on many JetDirect printers)
            with socket.create_connection((ip, int(port)), timeout=10) as s:
                s.sendall(data)
                return
        except Exception as e:
            logging.debug("print_text raw socket failed for %s:%s; will try IPP fallback if applicable", ip, port, exc_info=True)

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
                except Exception as ipp_e:
                    logging.error("IPP fallback print failed for %s:%s", ip, port)
                    raise ConnectionError(f"Printing failed on {ip}:{port} (tried Raw TCP and IPP).") from ipp_e
            else:
                raise ConnectionError(f"Connection to printer at {ip}:{port} timed out. Please check if the printer is ON and connected to the network.") from e

    def print_raw(self, ip: str, port: int, data: bytes) -> None:
        try:
            with socket.create_connection((ip, int(port)), timeout=10) as s:
                s.sendall(data)
        except Exception:
            logging.exception("print_raw failed for %s:%s", ip, port)
            raise

    def cut_paper(self, ip: str, port: int) -> None:
        """Send ESC/POS cut command to the printer.
        
        Uses GS V 65 0 (Feed and partial cut).
        """
        # ESC/POS cut command: \x1d\x56\x41\x00
        # \x1d\x56 is GS V
        # \x41 (65) is function A (Feed paper to cutting position and partial cut)
        # \x00 (0) is the feed distance (0 means default)
        data = b"\x1d\x56\x41\x00"
        try:
            with socket.create_connection((ip, int(port)), timeout=5) as s:
                s.sendall(data)
            logging.info("Sent cut command to printer at %s:%s", ip, port)
        except Exception:
            logging.exception("cut_paper failed for %s:%s", ip, port)
            # We don't necessarily want to raise here, as the print might have succeeded
            # but cutting failed (e.g. paper jam or cutter not supported)
