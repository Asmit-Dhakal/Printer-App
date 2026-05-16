#!/usr/bin/env python3
"""
Quick script to check the current print session status and list pending orders.
Run this while the printer agent is running to see what jobs are available.
"""

import logging
import sys
from services.api_service import APIService
from services.printjob_service import PrintJobService
from config import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

def check_session():
    """Check current print session status."""
    print("\n" + "="*70)
    print("PRINT SESSION STATUS CHECK")
    print("="*70)
    
    try:
        # Initialize API service
        api = APIService()
        
        # Get pending jobs
        logger.info("\n📋 Checking for pending print jobs...")
        jobs = api.poll_print_jobs(limit=20, claim=False)  # Don't claim, just check
        
        if not jobs:
            print("\n✗ NO PENDING JOBS")
            print("  The printer is idle - no orders to print")
            return
        
        print(f"\n✓ PRINT SESSION ACTIVE")
        print(f"  {len(jobs)} pending order(s) ready to print\n")
        print("-"*70)
        
        # Display each order
        for i, job in enumerate(jobs, 1):
            print(f"\n📦 ORDER #{i}")
            print(f"   Job ID:    {job.get('id', 'N/A')}")
            print(f"   Order ID:  {job.get('order_id', 'N/A')}")
            print(f"   Status:    {job.get('status', 'N/A')}")
            print(f"   Format:    {job.get('format', 'N/A')}")
            
            # Show order details if available
            payload = job.get('payload', {})
            if isinstance(payload, dict):
                if 'table_number' in payload:
                    print(f"   Table:     {payload['table_number']}")
                
                if 'items' in payload:
                    print(f"   Items ({len(payload['items'])}):")
                    for item in payload['items']:
                        name = item.get('name', 'Unknown')
                        qty = item.get('quantity', 1)
                        print(f"     ├─ {qty}x {name}")
        
        print("\n" + "="*70)
        print(f"TOTAL: {len(jobs)} order(s) pending")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Failed to check session: {e}")
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)

def check_service_status():
    """Check if PrintJobService is running and show its status."""
    print("\n" + "="*70)
    print("PRINT JOB SERVICE STATUS")
    print("="*70)
    
    try:
        job_service = PrintJobService()
        status = job_service.get_print_session_status()
        
        print(f"\nPending Jobs: {status['pending_jobs']}")
        print(f"Session Active: {'✓ YES' if status['session_active'] else '✗ NO'}")
        
        if status['jobs']:
            print("\nQueued Jobs:")
            for job in status['jobs']:
                print(f"  - {job.get('id', 'N/A')} (Order: {job.get('order_id', 'N/A')})")
        
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Failed to check service status: {e}")

if __name__ == "__main__":
    print("\n🖨️  PRINTER AGENT - SESSION CHECK\n")
    check_session()
    check_service_status()
