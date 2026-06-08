import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import AppHeader from '../components/AppHeader';
import { contactsApi } from '../lib/api';
import { toast } from 'sonner';
import { MagnifyingGlass, UserPlus, PencilSimple, Trash, ChatCircleDots, Phone, Envelope, X, Check, CaretLeft, CaretRight, GoogleLogo } from '@phosphor-icons/react';

export default function ContactsPage() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);

  // Create/edit modal
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ name: '', phone: '', email: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const loadContacts = async (p = 1, s = search) => {
    setLoading(true);
    try {
      const res = await contactsApi.list({ page: p, limit: 50, search: s || undefined });
      setContacts(res.data?.contacts || []);
      setTotal(res.data?.total || 0);
      setPages(res.data?.pages || 1);
      setPage(res.data?.page || 1);
    } catch { toast.error('Error loading contacts'); }
    setLoading(false);
  };

  useEffect(() => { loadContacts(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadContacts(1, search);
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: '', phone: '', email: '', notes: '' });
    setShowModal(true);
  };

  const openEdit = (c) => {
    setEditingId(c.id);
    setForm({ name: c.name || '', phone: c.phone || '', email: c.email || '', notes: c.notes || '' });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      if (editingId) {
        await contactsApi.update(editingId, form);
        toast.success(t('contacts.updated') || 'Contact updated');
      } else {
        await contactsApi.create(form);
        toast.success(t('contacts.created') || 'Contact created');
      }
      setShowModal(false);
      loadContacts(page, search);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
    setSaving(false);
  };

  const handleDelete = async (c) => {
    if (!window.confirm(`${t('contacts.delete_confirm') || 'Delete'} "${c.name}"?`)) return;
    try {
      await contactsApi.delete(c.id);
      toast.success(t('contacts.deleted') || 'Contact deleted');
      loadContacts(page, search);
    } catch { toast.error('Error'); }
  };

  const handleStartConversation = async (c) => {
    try {
      const res = await contactsApi.startConversation(c.id);
      navigate(`/?conv=${res.data.conversation_id}`);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };

  return (
    <div className="h-screen flex flex-col bg-[#F8FAFC]">
      <AppHeader currentPage="contacts" onNavigate={(p) => navigate(p === 'dashboard' ? '/dashboard' : p === 'agents' ? '/agents' : p === 'admin' ? '/admin' : '/')} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
                {t('contacts.title') || 'Contacts'}
              </h1>
              <p className="text-sm text-[#64748B] mt-1">{total} {t('contacts.total') || 'total'}</p>
            </div>
            {isAdmin && (
              <button data-testid="create-contact-button" onClick={openCreate}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
                <UserPlus size={16} /> {t('contacts.create') || 'New Contact'}
              </button>
            )}
          </div>

          {/* Search */}
          <form onSubmit={handleSearch} className="mb-4">
            <div className="relative">
              <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder={t('contacts.search_placeholder') || 'Search by name, phone or email...'}
                className="w-full pl-9 pr-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] bg-white" />
            </div>
          </form>

          {/* Contacts list */}
          <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-sm text-[#94A3B8]">{t('general.loading')}</div>
            ) : contacts.length === 0 ? (
              <div className="p-8 text-center text-sm text-[#94A3B8]">
                {search ? (t('contacts.no_results') || 'No contacts found') : (t('contacts.empty') || 'No contacts yet')}
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-semibold text-[#64748B] uppercase tracking-wide">{t('contacts.col_name') || 'Name'}</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-[#64748B] uppercase tracking-wide">{t('contacts.col_phone') || 'Phone'}</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-[#64748B] uppercase tracking-wide hidden md:table-cell">Email</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-[#64748B] uppercase tracking-wide hidden md:table-cell">{t('contacts.col_source') || 'Source'}</th>
                    <th className="text-right px-4 py-2.5 font-semibold text-[#64748B] uppercase tracking-wide">{t('contacts.col_actions') || 'Actions'}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {contacts.map(c => (
                    <tr key={c.id} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="font-medium text-[#0F172A]">{c.name || '—'}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="font-mono text-[11px] text-[#64748B]">{c.phone || '—'}</span>
                      </td>
                      <td className="px-4 py-2.5 hidden md:table-cell">
                        <span className="text-[#64748B]">{c.email || '—'}</span>
                      </td>
                      <td className="px-4 py-2.5 hidden md:table-cell">
                        {c.source === 'google' ? (
                          <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700">
                            <GoogleLogo size={10} weight="bold" /> Google
                          </span>
                        ) : (
                          <span className="text-[10px] text-[#94A3B8]">{t('contacts.source_manual') || 'Manual'}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => handleStartConversation(c)}
                            className="p-1.5 text-[#0F172A] hover:bg-[#F1F5F9] rounded-md" title={t('contacts.start_chat') || 'Start conversation'}>
                            <ChatCircleDots size={15} weight="bold" />
                          </button>
                          {isAdmin && (
                            <>
                              <button onClick={() => openEdit(c)}
                                className="p-1.5 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-md" title={t('contacts.edit') || 'Edit'}>
                                <PencilSimple size={14} />
                              </button>
                              <button onClick={() => handleDelete(c)}
                                className="p-1.5 text-[#94A3B8] hover:text-red-500 hover:bg-red-50 rounded-md" title={t('contacts.delete') || 'Delete'}>
                                <Trash size={14} />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button onClick={() => loadContacts(page - 1, search)} disabled={page <= 1}
                className="p-1.5 text-[#64748B] hover:text-[#0F172A] disabled:opacity-30"><CaretLeft size={16} /></button>
              <span className="text-xs text-[#64748B]">{page} / {pages}</span>
              <button onClick={() => loadContacts(page + 1, search)} disabled={page >= pages}
                className="p-1.5 text-[#64748B] hover:text-[#0F172A] disabled:opacity-30"><CaretRight size={16} /></button>
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-[#0F172A]">
                {editingId ? (t('contacts.edit_contact') || 'Edit Contact') : (t('contacts.new_contact') || 'New Contact')}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-[#94A3B8] hover:text-[#0F172A]"><X size={18} /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#475569]">{t('contacts.field_name') || 'Name'} *</label>
                <input type="text" value={form.name} onChange={e => setForm(p => ({...p, name: e.target.value}))}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-xs font-medium text-[#475569]">{t('contacts.field_phone') || 'Phone'}</label>
                <input type="text" value={form.phone} onChange={e => setForm(p => ({...p, phone: e.target.value}))}
                  placeholder="+34612345678"
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
              </div>
              <div>
                <label className="text-xs font-medium text-[#475569]">Email</label>
                <input type="email" value={form.email} onChange={e => setForm(p => ({...p, email: e.target.value}))}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-xs font-medium text-[#475569]">{t('contacts.field_notes') || 'Notes'}</label>
                <textarea value={form.notes} onChange={e => setForm(p => ({...p, notes: e.target.value}))} rows={2}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] resize-none" />
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setShowModal(false)} className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md">
                  {t('contacts.cancel') || 'Cancel'}
                </button>
                <button onClick={handleSave} disabled={saving || !form.name.trim()}
                  className="flex-1 px-3 py-2 text-sm bg-[#0F172A] text-white rounded-md disabled:opacity-50">
                  {saving ? '...' : (t('contacts.save') || 'Save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
