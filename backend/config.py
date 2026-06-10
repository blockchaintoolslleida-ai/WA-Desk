"""
Configuration module for WhatsApp Business Desk (Local Edition)
"""
import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database Configuration (local SQLite — no Supabase needed)
DB_PATH = os.environ.get('DB_PATH', str(ROOT_DIR / 'local.db'))

# WhatsApp Configuration
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_API_URL = 'https://graph.facebook.com/v25.0'

# Business phone number — used to detect messages sent from the mobile WhatsApp Business app
WHATSAPP_BUSINESS_PHONE_NUMBER = os.environ.get('WHATSAPP_BUSINESS_PHONE_NUMBER', '')

# JWT Configuration (local — no longer depends on Supabase)
JWT_SECRET = os.environ.get('JWT_SECRET', 'local-dev-secret-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# CORS Configuration
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

# Google Calendar Integration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/calendar/oauth2callback')
GOOGLE_POLLING_INTERVAL_MINUTES = int(os.environ.get('GOOGLE_POLLING_INTERVAL_MINUTES', '15'))

# App Settings
APP_NAME = "WhatsApp Business Desk"
APP_VERSION = "1.0.0"
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
