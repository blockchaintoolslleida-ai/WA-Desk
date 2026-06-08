"""
WhatsApp Business Desk - Main FastAPI Application
"""
from fastapi import FastAPI, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from routers import auth, conversations, messages, webhook, dashboard, agents, setup, cases, media, contacts, window, admin_platform, templates, contacts_import, media_proxy

app = FastAPI(
    title="WhatsApp Business Desk",
    description="Panel centralizado de atencion de WhatsApp Business",
    version="1.0.0"
)

api_router = APIRouter(prefix="/api")

@api_router.get("/")
async def root():
    return {"message": "WhatsApp Business Desk API", "status": "operational"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-business-desk"}

@api_router.api_route("/privacy-policy", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def privacy_policy():
    base_url = os.environ.get('BASE_URL', '')
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta property="og:title" content="Privacy Policy - WADesk CRM" />
<meta property="og:description" content="Privacy Policy for WADesk CRM - WhatsApp Business Helpdesk Platform" />
<meta property="og:type" content="website" />
<meta property="og:url" content="{base_url}/api/privacy-policy" />
<meta property="og:image" content="https://static.prod-images.emergentagent.com/jobs/6cd5edfd-a3a7-42a3-9e30-4a893e9eeacf/images/77baa2ddd5e7166bb4000c4a9dc50e54ab2b62af8f34a4771045d90266737c0e.png" />
<title>Privacy Policy - WADesk</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;padding:40px 20px;color:#334155;line-height:1.7}h1{color:#0F172A;font-size:28px}h2{color:#0F172A;font-size:20px;margin-top:32px}h3{font-size:15px;color:#0F172A}ul{padding-left:24px}li{margin-bottom:4px}p{margin:8px 0}.date{color:#94A3B8;font-size:14px}.contact{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-top:8px}</style>
</head>
<body>
<h1>Privacy Policy</h1>
<p class="date">Last updated: April 8, 2026</p>

<h2>1. Introduction</h2>
<p>WADesk ("we", "our", "us") is a multi-tenant WhatsApp Business helpdesk platform that enables businesses to manage customer communications through the WhatsApp Business API. This Privacy Policy describes how we collect, use, store, and protect information when you use our application.</p>

<h2>2. Information We Collect</h2>
<h3>2.1 Account Information</h3>
<p>When you register and use WADesk, we collect:</p>
<ul>
<li>Full name, email address, and phone number</li>
<li>Organization/company name and identifier</li>
<li>User role and permissions within the platform</li>
</ul>
<h3>2.2 WhatsApp Business Data</h3>
<p>To provide our helpdesk services, we process:</p>
<ul>
<li>WhatsApp Business Account configuration (Phone Number ID, account name)</li>
<li>API Access Tokens (stored encrypted using AES-256/Fernet encryption)</li>
<li>Incoming and outgoing WhatsApp messages (text, images, documents, audio, video)</li>
<li>Contact information of end-users who communicate via WhatsApp (phone number, profile name)</li>
<li>Message metadata (timestamps, delivery status, read receipts)</li>
<li>WhatsApp message templates</li>
</ul>
<h3>2.3 Usage Data</h3>
<p>We automatically collect:</p>
<ul>
<li>Admin action audit logs (configuration changes, login events)</li>
<li>Agent activity within the helpdesk (case assignments, response times)</li>
</ul>

<h2>3. How We Use Information</h2>
<p>We use the collected information exclusively to:</p>
<ul>
<li><strong>Provide the helpdesk service:</strong> Receive, display, and send WhatsApp messages between businesses and their customers</li>
<li><strong>Manage conversations:</strong> Organize messages into conversations and support cases for efficient customer service</li>
<li><strong>Enforce messaging policies:</strong> Implement WhatsApp's 24-hour messaging window and template message requirements</li>
<li><strong>Multi-tenant isolation:</strong> Ensure each business can only access their own data, contacts, and conversations</li>
<li><strong>Administration:</strong> Allow business administrators to configure their WhatsApp Business Account, manage agents, and review audit logs</li>
<li><strong>Service improvement:</strong> Monitor platform reliability and performance</li>
</ul>

<h2>4. Data Storage and Security</h2>
<ul>
<li><strong>Database:</strong> All data is stored in Supabase (PostgreSQL) with encrypted connections</li>
<li><strong>Credentials encryption:</strong> WhatsApp API tokens and secrets are encrypted at rest using AES-256 (Fernet) encryption. Plain-text tokens are never stored or logged</li>
<li><strong>Tenant isolation:</strong> Each business tenant's data is logically isolated. Agents and administrators can only access data belonging to their own organization</li>
<li><strong>Media files:</strong> WhatsApp media (images, documents) are stored in encrypted cloud storage with access controls</li>
<li><strong>Audit trail:</strong> All administrative actions are logged for security and compliance purposes</li>
</ul>

<h2>5. Data Sharing</h2>
<p>We do not sell, rent, or share personal data with third parties except:</p>
<ul>
<li><strong>Meta (WhatsApp Business API):</strong> Messages are transmitted through Meta's WhatsApp Business API as required to deliver the messaging service</li>
<li><strong>Cloud infrastructure:</strong> Data is stored in secure cloud infrastructure hosted in the EU</li>
<li><strong>Legal requirements:</strong> We may disclose information if required by law or legal process</li>
</ul>

<h2>6. Data Retention</h2>
<ul>
<li>Messages and conversation data are retained for as long as the business account is active</li>
<li>Audit logs are retained for 12 months</li>
<li>Upon account deletion, all associated data (messages, contacts, configurations) is permanently removed within 30 days</li>
</ul>

<h2>7. User Rights</h2>
<p>In accordance with applicable data protection regulations (including GDPR), you have the right to:</p>
<ul>
<li><strong>Access:</strong> Request a copy of your personal data</li>
<li><strong>Rectification:</strong> Correct inaccurate personal data</li>
<li><strong>Erasure:</strong> Request deletion of your personal data</li>
<li><strong>Portability:</strong> Receive your data in a structured, machine-readable format</li>
<li><strong>Restriction:</strong> Request restriction of processing</li>
<li><strong>Objection:</strong> Object to processing of your personal data</li>
</ul>
<p>To exercise these rights, contact us at the email address provided below.</p>

<h2>8. Data Deletion</h2>
<p>Users can request the deletion of their personal data at any time by contacting our Data Protection team. Upon receiving a valid deletion request, we will:</p>
<ul>
<li>Verify the identity of the requester</li>
<li>Delete all personal data associated with the account within 30 days</li>
<li>Confirm the deletion to the requester via email</li>
</ul>
<p>Alternatively, account administrators can delete agent accounts and associated data directly from the application's administration panel.</p>

<h2>9. WhatsApp Business API Compliance</h2>
<p>Our use of the WhatsApp Business API complies with:</p>
<ul>
<li>Meta's WhatsApp Business API Terms of Service</li>
<li>WhatsApp Business Messaging Policy (including the 24-hour messaging window)</li>
<li>Meta Platform Terms and Developer Policies</li>
</ul>
<p>We only send messages to users who have initiated a conversation or have explicitly opted in to receive communications. We enforce the 24-hour customer service window and require approved message templates for any communication outside this window.</p>

<h2>10. Cookies and Tracking</h2>
<p>WADesk uses only essential cookies required for authentication (session tokens). We do not use tracking cookies, analytics, or advertising technologies.</p>

<h2>11. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. Any changes will be reflected on this page with an updated "Last updated" date. Continued use of the service after changes constitutes acceptance of the revised policy.</p>

<h2>12. Contact</h2>
<p>For questions about this Privacy Policy, data deletion requests, or to exercise your data rights:</p>
<div class="contact">
<strong>WADesk - Data Protection</strong><br>
Email: info@blockchaintools.es
</div>
</body>
</html>"""

@api_router.api_route("/data-deletion", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def data_deletion():
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Data Deletion - WADesk CRM</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;padding:40px 20px;color:#334155;line-height:1.7}h1{color:#0F172A;font-size:28px}h2{color:#0F172A;font-size:20px;margin-top:32px}ul{padding-left:24px}li{margin-bottom:4px}p{margin:8px 0}.contact{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-top:12px}</style>
</head>
<body>
<h1>Data Deletion Instructions</h1>

<h2>How to Request Data Deletion</h2>
<p>If you want to delete your personal data from WADesk CRM, you can do so in two ways:</p>

<h2>Option 1: Contact Us Directly</h2>
<p>Send an email to our Data Protection team requesting the deletion of your data. Please include:</p>
<ul>
<li>Your full name</li>
<li>The email address associated with your account</li>
<li>Your organization/company name</li>
<li>A clear statement that you want your data deleted</li>
</ul>
<div class="contact">
<strong>Email:</strong> info@blockchaintools.es<br>
<strong>Subject:</strong> Data Deletion Request - WADesk CRM
</div>

<h2>Option 2: Through Your Administrator</h2>
<p>If you are an agent, ask your organization's administrator to delete your account from the Agents management panel in WADesk CRM.</p>

<h2>What Happens After a Deletion Request</h2>
<ul>
<li>We will verify your identity within 48 hours</li>
<li>All personal data associated with your account will be permanently deleted within 30 days</li>
<li>This includes: profile information, conversation history, and any stored preferences</li>
<li>You will receive a confirmation email once the deletion is complete</li>
</ul>

<h2>Data We Cannot Delete</h2>
<p>We may retain certain data as required by law or legitimate business interests, such as:</p>
<ul>
<li>Audit logs required for security compliance (anonymized after 12 months)</li>
<li>Data required to comply with legal obligations</li>
</ul>

<h2>Contact</h2>
<div class="contact">
<strong>BlockchainTools SL - Data Protection</strong><br>
Email: info@blockchaintools.es
</div>
</body>
</html>"""

@api_router.api_route("/terms-of-service", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def terms_of_service():
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Terms of Service - WADesk CRM</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;padding:40px 20px;color:#334155;line-height:1.7}h1{color:#0F172A;font-size:28px}h2{color:#0F172A;font-size:20px;margin-top:32px}ul{padding-left:24px}li{margin-bottom:4px}p{margin:8px 0}.date{color:#94A3B8;font-size:14px}.contact{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-top:8px}</style>
</head>
<body>
<h1>Terms of Service</h1>
<p class="date">Last updated: April 8, 2026</p>

<h2>1. Acceptance of Terms</h2>
<p>By accessing or using WADesk CRM ("the Service"), operated by BlockchainTools SL ("we", "our", "us"), you agree to be bound by these Terms of Service. If you do not agree to these terms, you may not use the Service.</p>

<h2>2. Description of the Service</h2>
<p>WADesk CRM is a multi-tenant WhatsApp Business helpdesk platform that allows businesses to:</p>
<ul>
<li>Receive and manage customer messages via the WhatsApp Business API</li>
<li>Organize conversations into support cases</li>
<li>Manage agents, contacts, and customer communications</li>
<li>Configure WhatsApp Business Account settings</li>
<li>Send template messages in compliance with Meta's messaging policies</li>
</ul>

<h2>3. Eligibility</h2>
<p>To use the Service, you must:</p>
<ul>
<li>Be at least 18 years of age</li>
<li>Have the legal authority to bind your organization to these terms</li>
<li>Have a valid WhatsApp Business Account approved by Meta</li>
<li>Comply with Meta's WhatsApp Business API Terms of Service and Commerce Policy</li>
</ul>

<h2>4. Account Registration and Security</h2>
<ul>
<li>You are responsible for maintaining the confidentiality of your account credentials</li>
<li>You must provide accurate and complete information during registration</li>
<li>You are responsible for all activities that occur under your account</li>
<li>You must notify us immediately of any unauthorized use of your account</li>
<li>We reserve the right to suspend or terminate accounts that violate these terms</li>
</ul>

<h2>5. Multi-Tenant Data Isolation</h2>
<p>The Service operates as a multi-tenant platform. Each organization ("tenant") has logically isolated data. You agree that:</p>
<ul>
<li>You will only access data belonging to your own organization</li>
<li>You will not attempt to access, modify, or interfere with another tenant's data</li>
<li>Administrators are responsible for managing their organization's agents and permissions</li>
</ul>

<h2>6. Acceptable Use</h2>
<p>You agree NOT to use the Service to:</p>
<ul>
<li>Send spam, unsolicited messages, or bulk messaging outside of Meta's approved templates</li>
<li>Violate WhatsApp's Business Messaging Policy or 24-hour customer service window rules</li>
<li>Transmit malicious content, malware, or phishing attempts</li>
<li>Harass, threaten, or abuse end-users or other agents</li>
<li>Collect or store personal data beyond what is necessary for customer support</li>
<li>Attempt to reverse-engineer, decompile, or hack the Service</li>
<li>Use the Service for any illegal or unauthorized purpose</li>
</ul>

<h2>7. WhatsApp Business API Compliance</h2>
<p>By using the Service, you acknowledge and agree that:</p>
<ul>
<li>All messaging through the Service is subject to Meta's WhatsApp Business API policies</li>
<li>You must comply with the 24-hour customer service messaging window</li>
<li>Messages sent outside the 24-hour window must use Meta-approved templates</li>
<li>You are responsible for obtaining and maintaining your own WhatsApp Business API access tokens</li>
<li>We are not responsible for changes to Meta's API policies, pricing, or availability</li>
</ul>

<h2>8. Data Processing</h2>
<p>We process data on your behalf to provide the Service. Our handling of personal data is governed by our <a href="privacy-policy">Privacy Policy</a>. You are responsible for:</p>
<ul>
<li>Ensuring you have a lawful basis to process your customers' personal data</li>
<li>Informing your customers about how their data is processed</li>
<li>Responding to data subject requests from your customers</li>
<li>Complying with applicable data protection regulations (including GDPR)</li>
</ul>

<h2>9. API Credentials and Security</h2>
<ul>
<li>WhatsApp API access tokens provided by you are encrypted at rest using AES-256 encryption</li>
<li>You are responsible for the security and rotation of your API credentials</li>
<li>We are not liable for any unauthorized access resulting from compromised credentials on your end</li>
<li>You must not share your API tokens with unauthorized third parties</li>
</ul>

<h2>10. Service Availability</h2>
<ul>
<li>We strive to maintain high availability but do not guarantee uninterrupted access</li>
<li>The Service may be temporarily unavailable due to maintenance, updates, or circumstances beyond our control</li>
<li>We are not responsible for interruptions caused by Meta's WhatsApp Business API</li>
<li>We will make reasonable efforts to notify users of planned maintenance</li>
</ul>

<h2>11. Intellectual Property</h2>
<ul>
<li>The Service, including its design, code, and functionality, is owned by BlockchainTools SL</li>
<li>You retain ownership of your data and content transmitted through the Service</li>
<li>You grant us a limited license to process your data solely to provide the Service</li>
<li>WhatsApp and Meta are trademarks of Meta Platforms, Inc.</li>
</ul>

<h2>12. Limitation of Liability</h2>
<p>To the maximum extent permitted by law:</p>
<ul>
<li>The Service is provided "as is" without warranties of any kind</li>
<li>We are not liable for any indirect, incidental, or consequential damages</li>
<li>We are not liable for any loss of data, revenue, or business opportunities</li>
<li>We are not responsible for the content of messages sent or received through the Service</li>
<li>Our total liability shall not exceed the fees paid by you in the 12 months preceding the claim</li>
</ul>

<h2>13. Termination</h2>
<ul>
<li>You may terminate your account at any time by contacting us</li>
<li>We may suspend or terminate your account for violation of these terms</li>
<li>Upon termination, your data will be retained for 30 days and then permanently deleted</li>
<li>Provisions relating to data protection, limitation of liability, and intellectual property survive termination</li>
</ul>

<h2>14. Changes to These Terms</h2>
<p>We may update these Terms of Service from time to time. Changes will be posted on this page with an updated date. Continued use of the Service after changes constitutes acceptance of the revised terms. For material changes, we will provide notice via the Service or email.</p>

<h2>15. Governing Law</h2>
<p>These terms are governed by the laws of Spain. Any disputes shall be resolved in the courts of Barcelona, Spain.</p>

<h2>16. Contact</h2>
<p>For questions about these Terms of Service:</p>
<div class="contact">
<strong>BlockchainTools SL</strong><br>
Email: info@blockchaintools.es
</div>
</body>
</html>"""

api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(webhook.router)
api_router.include_router(dashboard.router)
api_router.include_router(agents.router)
api_router.include_router(cases.router)
api_router.include_router(media.router)
api_router.include_router(contacts.router)
api_router.include_router(window.router)
api_router.include_router(admin_platform.router)
api_router.include_router(templates.router)
api_router.include_router(setup.router)
api_router.include_router(contacts_import.router)
api_router.include_router(media_proxy.router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media files directory for serving uploaded files
MEDIA_FILES_DIR = ROOT_DIR / "media_files" / "media"
MEDIA_FILES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/media/files", StaticFiles(directory=str(MEDIA_FILES_DIR)), name="media_files")

import asyncio
from routers.window import run_auto_reminder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def auto_reminder_loop():
    """Periodic background task: check every 5 minutes for conversations needing auto-reminder"""
    while True:
        try:
            await run_auto_reminder()
        except Exception as e:
            logger.error(f"Auto-reminder loop error: {e}")
        await asyncio.sleep(300)  # 5 minutes

@app.on_event("startup")
async def startup_event():
    logger.info("WhatsApp Business Desk API starting...")
    asyncio.create_task(auto_reminder_loop())
    logger.info("Auto-reminder background task started (every 5 min)")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("WhatsApp Business Desk API shutting down...")
