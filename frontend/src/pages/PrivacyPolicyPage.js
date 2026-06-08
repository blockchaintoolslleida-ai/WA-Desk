import { ArrowLeft } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

export default function PrivacyPolicyPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#F8FAFC]" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm text-[#475569] hover:text-[#0F172A] mb-8 transition-colors">
          <ArrowLeft size={16} /> Tornar
        </button>

        <h1 className="text-2xl font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>Privacy Policy</h1>
        <p className="text-sm text-[#94A3B8] mb-8">Last updated: April 8, 2026</p>

        <div className="prose prose-sm max-w-none space-y-6 text-[#334155] leading-relaxed">

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>1. Introduction</h2>
            <p>
              WADesk ("we", "our", "us") is a multi-tenant WhatsApp Business helpdesk platform that enables businesses to manage customer communications through the WhatsApp Business API. This Privacy Policy describes how we collect, use, store, and protect information when you use our application.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>2. Information We Collect</h2>
            <h3 className="text-sm font-semibold text-[#0F172A] mt-4 mb-1">2.1 Account Information</h3>
            <p>When you register and use WADesk, we collect:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li>Full name, email address, and phone number</li>
              <li>Organization/company name and identifier</li>
              <li>User role and permissions within the platform</li>
            </ul>

            <h3 className="text-sm font-semibold text-[#0F172A] mt-4 mb-1">2.2 WhatsApp Business Data</h3>
            <p>To provide our helpdesk services, we process:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li>WhatsApp Business Account configuration (Phone Number ID, account name)</li>
              <li>API Access Tokens (stored encrypted using AES-256/Fernet encryption)</li>
              <li>Incoming and outgoing WhatsApp messages (text, images, documents, audio, video)</li>
              <li>Contact information of end-users who communicate via WhatsApp (phone number, profile name)</li>
              <li>Message metadata (timestamps, delivery status, read receipts)</li>
              <li>WhatsApp message templates</li>
            </ul>

            <h3 className="text-sm font-semibold text-[#0F172A] mt-4 mb-1">2.3 Usage Data</h3>
            <p>We automatically collect:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li>Admin action audit logs (configuration changes, login events)</li>
              <li>Agent activity within the helpdesk (case assignments, response times)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>3. How We Use Information</h2>
            <p>We use the collected information exclusively to:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Provide the helpdesk service:</strong> Receive, display, and send WhatsApp messages between businesses and their customers</li>
              <li><strong>Manage conversations:</strong> Organize messages into conversations and support cases for efficient customer service</li>
              <li><strong>Enforce messaging policies:</strong> Implement WhatsApp's 24-hour messaging window and template message requirements</li>
              <li><strong>Multi-tenant isolation:</strong> Ensure each business can only access their own data, contacts, and conversations</li>
              <li><strong>Administration:</strong> Allow business administrators to configure their WhatsApp Business Account, manage agents, and review audit logs</li>
              <li><strong>Service improvement:</strong> Monitor platform reliability and performance</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>4. Data Storage and Security</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Database:</strong> All data is stored in Supabase (PostgreSQL) with encrypted connections</li>
              <li><strong>Credentials encryption:</strong> WhatsApp API tokens and secrets are encrypted at rest using AES-256 (Fernet) encryption before storage. Plain-text tokens are never stored or logged</li>
              <li><strong>Tenant isolation:</strong> Each business tenant's data is logically isolated. Agents and administrators can only access data belonging to their own organization</li>
              <li><strong>Media files:</strong> WhatsApp media (images, documents) are stored in Supabase Storage with access controls</li>
              <li><strong>Audit trail:</strong> All administrative actions are logged for security and compliance purposes</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>5. Data Sharing</h2>
            <p>We do not sell, rent, or share personal data with third parties except:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Meta (WhatsApp Business API):</strong> Messages are transmitted through Meta's WhatsApp Business API as required to deliver the messaging service</li>
              <li><strong>Supabase:</strong> Data is stored in Supabase's cloud infrastructure (hosted in the EU)</li>
              <li><strong>Legal requirements:</strong> We may disclose information if required by law or legal process</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>6. Data Retention</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li>Messages and conversation data are retained for as long as the business account is active</li>
              <li>Audit logs are retained for 12 months</li>
              <li>Upon account deletion, all associated data (messages, contacts, configurations) is permanently removed within 30 days</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>7. User Rights</h2>
            <p>In accordance with applicable data protection regulations (including GDPR), you have the right to:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li><strong>Access:</strong> Request a copy of your personal data</li>
              <li><strong>Rectification:</strong> Correct inaccurate personal data</li>
              <li><strong>Erasure:</strong> Request deletion of your personal data</li>
              <li><strong>Portability:</strong> Receive your data in a structured, machine-readable format</li>
              <li><strong>Restriction:</strong> Request restriction of processing</li>
              <li><strong>Objection:</strong> Object to processing of your personal data</li>
            </ul>
            <p className="mt-2">To exercise these rights, contact us at the email address provided below.</p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>8. WhatsApp Business API Compliance</h2>
            <p>Our use of the WhatsApp Business API complies with:</p>
            <ul className="list-disc pl-6 space-y-1">
              <li>Meta's WhatsApp Business API Terms of Service</li>
              <li>WhatsApp Business Messaging Policy (including the 24-hour messaging window)</li>
              <li>Meta Platform Terms and Developer Policies</li>
            </ul>
            <p className="mt-2">
              We only send messages to users who have initiated a conversation or have explicitly opted in to receive communications from the business. We enforce the 24-hour customer service window and require approved message templates for any communication outside this window.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>9. Cookies and Tracking</h2>
            <p>
              WADesk uses only essential cookies required for authentication (session tokens stored in localStorage). We do not use tracking cookies, analytics, or advertising technologies.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>10. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. Any changes will be reflected on this page with an updated "Last updated" date. Continued use of the service after changes constitutes acceptance of the revised policy.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>11. Contact</h2>
            <p>
              For questions about this Privacy Policy or to exercise your data rights, please contact:
            </p>
            <div className="mt-2 p-4 bg-white border border-[#E2E8F0] rounded-lg text-sm">
              <p className="font-semibold text-[#0F172A]">WADesk - Data Protection</p>
              <p className="text-[#64748B]">Email: privacy@wadesk.app</p>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
