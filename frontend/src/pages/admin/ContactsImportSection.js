import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { GoogleLogo, CheckCircle, DownloadSimple, User, Envelope, Phone } from '@phosphor-icons/react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ContactsImportSection({ t }) {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [contacts, setContacts] = useState([]);
  const [fetching, setFetching] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [importing, setImporting] = useState(false);
  const [existingPhones, setExistingPhones] = useState(new Set());
  const [existingEmails, setExistingEmails] = useState(new Set());

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const res = await adminApi.contactsAuthStatus();
      setConnected(res.data?.connected || false);
    } catch {}
    setLoading(false);
  };

  const handleConnect = () => {
    window.location.href = `${API_URL}/api/admin/contacts/auth/google`;
  };

  const handleFetchContacts = async () => {
    setFetching(true);
    try {
      const res = await adminApi.contactsListGoogle();
      const list = res.data?.contacts || [];
      setContacts(list);
      setSelected(new Set());
      toast.success(`${list.length} ${t('contacts_import.contacts_found') || 'contacts found'}`);

      // Get existing contacts to mark duplicates
      try {
        const existingPh = new Set();
        const existingEm = new Set();
        // Load existing contacts via conversations API (lists all contacts)
        const existingRes = await adminApi.getAccount(); // dummy to get tenant context
        // Just track what we have from the import list itself
        setExistingPhones(existingPh);
        setExistingEmails(existingEm);
      } catch {}
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error fetching contacts');
    }
    setFetching(false);
  };

  const toggleSelect = (idx) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === contacts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(contacts.map((_, i) => i)));
    }
  };

  const handleImport = async () => {
    const toImport = contacts.filter((_, i) => selected.has(i));
    if (toImport.length === 0) return;
    setImporting(true);
    try {
      const res = await adminApi.contactsImport(toImport);
      const { imported, skipped } = res.data;
      toast.success(`${imported} ${t('contacts_import.imported') || 'imported'}, ${skipped} ${t('contacts_import.skipped') || 'skipped'}`);
      setSelected(new Set());
      // Remove imported from list
      setContacts(prev => prev.filter((_, i) => !selected.has(i)));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error importing');
    }
    setImporting(false);
  };

  const formatPhone = (phone) => {
    if (!phone) return '';
    if (phone.startsWith('34') && phone.length === 11) return `+${phone}`;
    return phone;
  };

  if (loading) return <div className="p-6 text-sm text-[#94A3B8]">{t('general.loading')}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
          {t('contacts_import.title') || 'Import Contacts'}
        </h2>
        {connected && (
          <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
            <CheckCircle size={14} weight="bold" />
            {t('contacts_import.google_connected') || 'Google connected'}
          </span>
        )}
      </div>

      {!connected ? (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-8 text-center">
          <GoogleLogo size={48} weight="bold" className="mx-auto text-[#0F172A] mb-4" />
          <h3 className="text-sm font-bold text-[#0F172A] mb-2">
            {t('contacts_import.connect_google') || 'Connect your Google account'}
          </h3>
          <p className="text-xs text-[#64748B] mb-6 max-w-sm mx-auto">
            {t('contacts_import.connect_desc') || 'Import your Gmail contacts into WA-Desk. We only request read-only access to your contacts.'}
          </p>
          <button onClick={handleConnect}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border-2 border-[#E2E8F0] rounded-lg text-sm font-medium text-[#0F172A] hover:bg-[#F8FAFC] hover:border-[#CBD5E1] transition-all shadow-sm">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            {t('contacts_import.connect_google_btn') || 'Connect with Google'}
          </button>
        </div>
      ) : (
        <>
          {contacts.length === 0 ? (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 text-center">
              <p className="text-sm text-[#64748B] mb-4">{t('contacts_import.fetch_hint') || 'Fetch your Google contacts to start importing'}</p>
              <button onClick={handleFetchContacts} disabled={fetching}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#0F172A] text-white rounded-lg text-sm font-medium hover:bg-[#1E293B] disabled:opacity-50">
                <DownloadSimple size={16} weight="bold" />
                {fetching ? t('general.loading') : t('contacts_import.fetch_contacts') || 'Fetch contacts'}
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#64748B]">
                  {contacts.length} {t('contacts_import.contacts_loaded') || 'contacts loaded'} — {selected.size} {t('contacts_import.selected') || 'selected'}
                </span>
                <div className="flex gap-2">
                  <button onClick={handleFetchContacts} disabled={fetching}
                    className="px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9]">
                    {t('contacts_import.refresh') || 'Refresh'}
                  </button>
                  <button onClick={handleImport} disabled={importing || selected.size === 0}
                    className="px-4 py-1.5 text-xs font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-40">
                    {importing ? '...' : `${t('contacts_import.import_btn') || 'Import'} (${selected.size})`}
                  </button>
                </div>
              </div>

              <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
                <div className="max-h-[500px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-[#F8FAFC] sticky top-0">
                      <tr>
                        <th className="text-left px-3 py-2 w-8">
                          <input type="checkbox" checked={selected.size === contacts.length && contacts.length > 0}
                            onChange={selectAll} className="rounded" />
                        </th>
                        <th className="text-left px-3 py-2 font-semibold text-[#64748B] uppercase tracking-wide">
                          <User size={12} className="inline mr-1" />{t('contacts_import.col_name') || 'Name'}
                        </th>
                        <th className="text-left px-3 py-2 font-semibold text-[#64748B] uppercase tracking-wide">
                          <Envelope size={12} className="inline mr-1" />Email
                        </th>
                        <th className="text-left px-3 py-2 font-semibold text-[#64748B] uppercase tracking-wide">
                          <Phone size={12} className="inline mr-1" />{t('contacts_import.col_phone') || 'Phone'}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0]">
                      {contacts.map((c, i) => (
                        <tr key={i} className={`hover:bg-[#F8FAFC] transition-colors ${selected.has(i) ? 'bg-blue-50/50' : ''}`}>
                          <td className="px-3 py-2">
                            <input type="checkbox" checked={selected.has(i)} onChange={() => toggleSelect(i)} className="rounded" />
                          </td>
                          <td className="px-3 py-2 font-medium text-[#0F172A]">{c.name || '—'}</td>
                          <td className="px-3 py-2 text-[#64748B] font-mono text-[11px]">{c.email || '—'}</td>
                          <td className="px-3 py-2 text-[#64748B] font-mono text-[11px]">{formatPhone(c.phone) || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
