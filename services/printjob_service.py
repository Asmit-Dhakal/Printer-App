import logging
import json
from typing import Optional, Callable
from PySide6.QtCore import QTimer, Signal, QObject
from services.api_service import APIService
from services.printer_service import PrinterService
from config import POLL_INTERVAL_MS, POLL_LIMIT, POLL_CLAIM_JOBS


class PrintJobService(QObject):
    """
    Manages print job polling, processing, and acknowledgment.
    
    Workflow:
    1. Poll for pending jobs from /api/printjobs/poll/
    2. Process each job locally (format payload, send to printer)
    3. Acknowledge job completion via /api/printjobs/{id}/ack/
    
    Signals:
    - jobs_received(jobs): emitted when new jobs are polled
    - job_printed(job_id): emitted when job is successfully printed
    - job_failed(job_id, error): emitted when job printing fails
    - poll_error(error): emitted on polling errors
    """

    # Signals
    jobs_received = Signal(list)  # list of job dicts
    job_printed = Signal(str)  # job_id
    job_failed = Signal(str, str)  # job_id, error_msg
    poll_error = Signal(str)  # error message

    def __init__(self, printer_id: Optional[str] = None):
        super().__init__()
        self.api = APIService()
        self.printer = PrinterService()
        self.printer_id = printer_id
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_jobs)
        
        # Job processing queue
        self.pending_jobs = []
        self.job_callbacks = {}  # track callbacks for async processing

        logging.info(
            "PrintJobService initialized (printer_id=%s, interval=%dms, limit=%d, claim=%s)",
            printer_id, POLL_INTERVAL_MS, POLL_LIMIT, POLL_CLAIM_JOBS
        )

    def start(self):
        """Start polling for print jobs."""
        self.timer.start(POLL_INTERVAL_MS)
        logging.info("PrintJobService started (polling interval=%dms)", POLL_INTERVAL_MS)
        # Run initial poll immediately
        self.poll_jobs()

    def stop(self):
        """Stop polling for print jobs."""
        self.timer.stop()
        logging.info("PrintJobService stopped")

    def poll_jobs(self):
        """
        Poll for pending print jobs.
        
        This calls GET /api/printjobs/poll/ with claim=true to atomically
        claim jobs and mark them as SENT, preventing duplicate printing
        from multiple printer devices.
        """
        try:
            logging.info("\n" + "="*60)
            logging.info("POLL SESSION START")
            logging.info("="*60)
            
            jobs = self.api.poll_print_jobs(
                printer_id=self.printer_id,
                limit=POLL_LIMIT,
                claim=POLL_CLAIM_JOBS
            )
            
            if not jobs:
                logging.info("✗ No pending jobs available")
                logging.info("="*60)
                return

            logging.info(f"✓ PRINT SESSION ACTIVE: {len(jobs)} job(s) available")
            logging.info("-"*60)
            logging.info("ORDERS TO PRINT:")
            for i, job in enumerate(jobs, 1):
                order_id = job.get('order_id', 'N/A')
                job_id = job.get('id', 'N/A')
                logging.info(f"\n[Job {i}]")
                logging.info(f"  Job ID: {job_id}")
                logging.info(f"  Order ID: {order_id}")
                logging.info(f"  Status: {job.get('status', 'N/A')}")
                logging.info(f"  Format: {job.get('format', 'N/A')}")
                
                # Show payload preview
                payload = job.get('payload', {})
                if isinstance(payload, dict):
                    if 'table_number' in payload:
                        logging.info(f"  Table: {payload['table_number']}")
                    if 'items' in payload:
                        logging.info(f"  Items: {len(payload['items'])} item(s)")
                        for item in payload['items']:
                            name = item.get('name', 'Unknown')
                            qty = item.get('quantity', 1)
                            logging.info(f"    - {qty}x {name}")
            
            logging.info("\n" + "-"*60)
            self.pending_jobs.extend(jobs)
            self.jobs_received.emit(jobs)
            
            # Process jobs sequentially
            self._process_next_job()
            logging.info("="*60 + "\n")

        except Exception as e:
            error_msg = f"Poll error: {str(e)}"
            logging.error(f"\n✗ POLL SESSION FAILED: {error_msg}")
            logging.exception(error_msg)
            self.poll_error.emit(error_msg)

    def _process_next_job(self):
        """Process the next job in the queue."""
        if not self.pending_jobs:
            return

        job = self.pending_jobs.pop(0)
        self._process_job(job)

    def _process_job(self, job: dict):
        """
        Process a single print job.
        
        Extracts job details, formats data, sends to printer, then acknowledges.
        """
        job_id = job.get("id")
        order_id = job.get("order_id")
        printer_id = job.get("printer_id")
        payload = job.get("payload")
        format_type = job.get("format", "json")
        
        logging.info(
            "Processing job: id=%s, order_id=%s, format=%s, printer=%s",
            job_id, order_id, format_type, printer_id
        )

        try:
            logging.info(f"TASK START: Processing job {job_id} for order {order_id}")
            # --- Resolve Printer Connection Info ---
            ip = job.get("ip")
            port = job.get("port")
            
            if (not ip or not port) and printer_id:
                logging.info("IP/Port missing in job; fetching printer info for %s", printer_id)
                printer_info = self.api.get_printer(printer_id)
                ip = printer_info.get("ip")
                port = printer_info.get("port")

            if not ip or not port:
                raise ValueError("Printer IP/port not available (checked job and printer profile)")

            # --- Resolve Payload (Order Details) ---
            # If it's an order job, fetch the printer-friendly items as requested
            if order_id:
                logging.info("Fetching printer-friendly items for order %s", order_id)
                payload = self.api.get_printer_order_items(order_id)
                format_type = "json"

            # --- Format Data ---
            if format_type == "json":
                if isinstance(payload, str):
                    payload = json.loads(payload)
                
                # Use professional receipt formatter for dict payloads
                if isinstance(payload, dict):
                    formatted_data = self._format_receipt(payload)
                else:
                    formatted_data = json.dumps(payload, indent=2)
            elif format_type == "text":
                formatted_data = str(payload)
            elif format_type == "escpos":
                formatted_data = payload.encode("utf-8") if isinstance(payload, str) else payload
            else:
                formatted_data = str(payload)

            # --- Send to Printer ---
            data_to_send = formatted_data.encode() if isinstance(formatted_data, str) else formatted_data
            self.printer.print_raw(ip, port, data_to_send)

            # Cut paper after each order
            try:
                self.printer.cut_paper(ip, port)
            except Exception:
                logging.warning("Failed to cut paper for job %s, continuing...", job_id)

            # Acknowledge success
            self.api.ack_print_job(job_id, status="OK")
            logging.info("TASK COMPLETE: Job %s printed and acknowledged", job_id)
            self.job_printed.emit(job_id)

        except Exception as e:
            error_msg = f"{str(e)}"
            logging.error(f"TASK FAILED: Job {job_id} error: {error_msg}")
            
            try:
                # Acknowledge failure
                self.api.ack_print_job(job_id, status="FAILED", error=error_msg)
                logging.info("Job %s acknowledged as FAILED: %s", job_id, error_msg)
            except Exception as ack_error:
                logging.exception(f"Failed to acknowledge job {job_id}: {ack_error}")

            self.job_failed.emit(job_id, error_msg)

        finally:
            # Process next job
            self._process_next_job()

    def _format_receipt(self, payload: dict, width: int = 32) -> str:
        """
        Create a receipt using the "Thermal Precision" 80mm layout style.
        Authoritative centered design with asterisk headers and dashed dividers.
        """
        lines = []
        star_line = "*" * width
        dash_line = "-" * width
        
        # 1. Branding Header (Asterisk Canvas)
        lines.append("")
        lines.append(star_line)
        
        rest_name = payload.get("restaurant_name") or \
                    payload.get("restaurant", {}).get("name") or \
                    "TEA SHOP"
        
        lines.append(rest_name.upper().center(width))
        
        business_type = payload.get("restaurant", {}).get("business_type")
        if business_type:
            lines.append(f"({business_type.title()})".center(width))
            
        lines.append(star_line)
        
        # 2. Transaction Information
        lines.append(dash_line)
        order_id = str(payload.get("order_id", "N/A"))
        if len(order_id) > 8:
            order_id = order_id[:8]
        lines.append(f"Order ID: {order_id}".center(width))
        
        table = payload.get("table_number")
        if table:
            lines.append(f"Table Reference: {table}".center(width))
            
        created_at = payload.get("created_at", "")
        if created_at:
            try:
                date_part = created_at.split('T')[0]
                time_part = created_at.split('T')[1][:5]
                lines.append(f"Date: {date_part}  Time: {time_part}".center(width))
            except:
                pass
        lines.append(dash_line)
        
        # 3. Section Label
        lines.append("ITEMIZED LISTING".center(width))
        lines.append(dash_line)
        
        # 4. Itemized List (Single line: Qty*Item -Var +Addon Price)
        for item in payload.get("items", []):
            qty = item.get("quantity", 1)
            detail = item.get("detail", {})
            
            # Use Category as primary, fallback to name
            item_main = detail.get("category") or detail.get("food_name") or item.get("name")
            var_name = detail.get("variation", {}).get("name")
            price = str(item.get("line_total") or item.get("final_unit_price") or "0.00")
            
            # Build description: "Item -Variation +Addon1 +Addon2"
            desc = item_main
            if var_name:
                desc += f" -{var_name}"
            for addon in item.get("add_ons", []):
                desc += f" +{addon.get('name')}"
            
            # Format line: "1*Desc....Price"
            prefix = f"{qty}*{desc}"
            # Ensure price is right-aligned on the same line
            if len(prefix) + len(price) + 1 > width:
                # If too long, truncate description but keep price
                prefix = prefix[:(width - len(price) - 2)] + ".."
            
            line = prefix.ljust(width - len(price)) + price
            lines.append(line)
            lines.append(dash_line) # Divider between each item
            
        # 5. Totals Section
        lines.append(dash_line)
        total_amt = payload.get("order_total", "0.00")
        lines.append(f"TOTAL AMOUNT: {total_amt}".center(width))
        lines.append(dash_line)
        
        # 6. Footer (Minimal)
        lines.append(star_line)
        lines.append("\n\n") # Feed for cutting
        
        return "\n".join(lines)

    def get_order_details(self, order_id: str) -> dict:
        """
        Fetch detailed order information for display/printing.
        
        Calls GET /api/printer-order-items/{order_id}/
        
        Returns compact order representation with items and table number.
        """
        try:
            details = self.api.get_printer_order_items(order_id)
            logging.info("Fetched order details for %s", order_id)
            return details
        except Exception:
            logging.exception(f"Failed to fetch order details for {order_id}")
            raise

    def get_job_status(self, job_id: str) -> dict:
        """
        Fetch current status of a specific print job.
        
        Calls GET /api/printjobs/{job_id}/
        """
        try:
            job = self.api.get_print_job(job_id)
            logging.info("Fetched job %s status: %s", job_id, job.get("status"))
            return job
        except Exception:
            logging.exception(f"Failed to fetch job {job_id}")
            raise

    def get_print_session_status(self) -> dict:
        """
        Get current print session status.
        
        Returns dict with:
        - pending_jobs: number of jobs waiting to be processed
        - session_active: whether there are jobs to print
        - jobs: list of pending jobs
        """
        return {
            "pending_jobs": len(self.pending_jobs),
            "session_active": len(self.pending_jobs) > 0,
            "jobs": self.pending_jobs.copy()
        }

    def list_jobs(self, status: Optional[str] = None, limit: int = 20) -> list:
        """
        List all print jobs with optional status filter.
        
        Status options: PENDING, SENT, PRINTED, FAILED
        """
        try:
            result = self.api.get_print_jobs(
                status=status,
                printer_id=self.printer_id,
                limit=limit
            )
            # Handle both list and paginated responses
            if isinstance(result, dict):
                jobs = result.get("results", [])
            else:
                jobs = result if isinstance(result, list) else []
            logging.info("Listed %d job(s) with status=%s", len(jobs), status)
            return jobs
        except Exception:
            logging.exception("Failed to list jobs")
            raise
