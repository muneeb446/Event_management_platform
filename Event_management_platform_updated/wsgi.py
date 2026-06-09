# ── WSGI file for PythonAnywhere ──
# Copy this content into your PythonAnywhere WSGI configuration file
# Replace YOURUSERNAME with your actual PythonAnywhere username

import sys
import os

sys.path.insert(0, '/home/YOURUSERNAME/Event_management_platform_updated')
os.environ['DB_PATH'] = '/home/YOURUSERNAME/Event_management_platform_updated/event.db'

from app import app as application
