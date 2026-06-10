import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import AppHeader from '../components/AppHeader';
import { adminApi } from '../lib/api';
import { Gear, LinkSimple, ClockCounterClockwise, CheckCircle, XCircle, CaretRight, ArrowLeft, ChatText, Buildings, DownloadSimple, Lightning } from '@phosphor-icons/react';

import AccountSection from './admin/AccountSection';
import TemplatesSection from './admin/TemplatesSection';
import WebhookSection from './admin/WebhookSection';
import AuditSection from './admin/AuditSection';
import TenantSetupForm from './admin/TenantSetupForm';
import CompaniesSection from './admin/CompaniesSection';
import ContactsImportSection from './admin/ContactsImportSection';
import AutomationSection from './admin/AutomationSection';

const NAV_ITEMS = [
  { id: 'account', icon: Gear, key: 'admin.nav.account' },
  { id: 'templates', icon: ChatText, key: 'admin.nav.templates' },
  { id: 'automation', icon: Lightning, key: 'admin.nav.automation' },
  { id: 'webhook', icon: LinkSimple, key: 'admin.nav.webhook' },
  { id: 'logs', icon: ClockCounterClockwise, key: 'admin.nav.logs' },
];

export default function AdminPage() {
  const { t, locale } = useTranslation();
  const { profile, isSuperAdmin } = useAuth();
  const navigate = useNavigate();
  const [section, setSection] = useState('account');
  const [setupReady, setSetupReady] = useState(null);
  const [setupStatus, setSetupStatus] = useState({});
  const [hasTenant, setHasTenant] = useState(null);

  useEffect(() => {
    checkSetup();
  }, []);

  const checkSetup = async () => {
    try {
      const res = await adminApi.checkSetup();
      setSetupReady(res.data.all_ready);
      setSetupStatus(res.data.tables || {});
      if (res.data.all_ready) checkTenant();
    } catch {
      setSetupReady(false);
    }
  };

  const checkTenant = async () => {
    try {
      const res = await adminApi.getMyTenant();
      setHasTenant(!!res.data.tenant);
    } catch {
      setHasTenant(false);
    }
  };

  if (profile && !['super_admin', 'admin'].includes(profile.role)) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center">
        <p className="text-red-500 font-medium">403 - Accés denegat</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
      <AppHeader currentPage="admin" onNavigate={(p) => navigate(p === 'dashboard' ? '/dashboard' : p === 'contacts' ? '/contacts' : p === 'calendar' ? '/calendar' : p === 'agents' ? '/agents' : p === 'admin' ? '/admin' : '/')} />

      <div className="flex h-[calc(100vh-48px)]">
        <aside data-testid="admin-sidebar" className="w-56 bg-white border-r border-[#E2E8F0] flex-shrink-0 flex flex-col">
          <div className="p-4 border-b border-[#E2E8F0]">
            <h1 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('admin.config_title')}</h1>
          </div>
          <nav className="p-2 space-y-0.5 flex-1">
            {NAV_ITEMS.map(item => (
              <button key={item.id} data-testid={`admin-nav-${item.id}`}
                onClick={() => setSection(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  section === item.id
                    ? 'bg-[#0F172A] text-white font-medium'
                    : 'text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]'
                }`}>
                <item.icon size={16} weight={section === item.id ? 'bold' : 'regular'} />
                {t(item.key)}
                {section === item.id && <CaretRight size={12} className="ml-auto" weight="bold" />}
              </button>
            ))}
            {isSuperAdmin && (
              <button data-testid="admin-nav-companies"
                onClick={() => setSection('companies')}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  section === 'companies'
                    ? 'bg-[#0F172A] text-white font-medium'
                    : 'text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]'
                }`}>
                <Buildings size={16} weight={section === 'companies' ? 'bold' : 'regular'} />
                {t('admin.nav.companies') || 'Empreses'}
                {section === 'companies' && <CaretRight size={12} className="ml-auto" weight="bold" />}
              </button>
            )}
            <button data-testid="admin-nav-contacts-import"
              onClick={() => setSection('contacts-import')}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                section === 'contacts-import'
                  ? 'bg-[#0F172A] text-white font-medium'
                  : 'text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]'
              }`}>
              <DownloadSimple size={16} weight={section === 'contacts-import' ? 'bold' : 'regular'} />
              {t('admin.nav.contacts_import') || 'Importar contactes'}
              {section === 'contacts-import' && <CaretRight size={12} className="ml-auto" weight="bold" />}
            </button>
          </nav>
          <div className="p-2 border-t border-[#E2E8F0]">
            <button data-testid="back-to-inbox" onClick={() => navigate('/')}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A] transition-colors">
              <ArrowLeft size={16} />
              {t('admin.back_to_inbox')}
            </button>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          {setupReady === false ? (
            <div className="max-w-lg mx-auto mt-16 p-6 bg-white border border-[#E2E8F0] rounded-lg">
              <h2 className="text-base font-bold text-[#0F172A] mb-3" style={{ fontFamily: 'Manrope' }}>{t('admin.setup_required')}</h2>
              <p className="text-sm text-[#475569] mb-3">{t('admin.setup_instructions')}</p>
              <code className="block px-3 py-2 bg-[#F1F5F9] border border-[#E2E8F0] rounded-md text-xs font-mono mb-4">
                {t('admin.setup_file')}
              </code>
              <div className="space-y-1 mb-4">
                {Object.entries(setupStatus).map(([table, st]) => (
                  <div key={table} className="flex items-center gap-2 text-xs">
                    {st === 'ok' ? <CheckCircle size={14} className="text-green-500" /> : <XCircle size={14} className="text-red-500" />}
                    <span className="font-mono">{table}</span>
                  </div>
                ))}
              </div>
              <button data-testid="admin-setup-check" onClick={checkSetup}
                className="px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
                {t('admin.setup_check')}
              </button>
            </div>
          ) : hasTenant === false ? (
            <TenantSetupForm t={t} onCreated={checkTenant} />
          ) : hasTenant === null ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-sm text-[#94A3B8]">{t('general.loading')}</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto p-6">
              {section === 'account' && <AccountSection t={t} locale={locale} />}
              {section === 'templates' && <TemplatesSection t={t} />}
              {section === 'automation' && <AutomationSection t={t} locale={locale} />}
              {section === 'webhook' && <WebhookSection t={t} />}
              {section === 'logs' && <AuditSection t={t} locale={locale} />}
              {section === 'companies' && <CompaniesSection t={t} />}
              {section === 'contacts-import' && <ContactsImportSection t={t} />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
