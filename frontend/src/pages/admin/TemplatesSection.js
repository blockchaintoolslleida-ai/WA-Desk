import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { ArrowClockwise, ChatText, CircleNotch, PaperPlaneRight, Plus, Trash } from '@phosphor-icons/react';

export default function TemplatesSection({ t }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sendModal, setSendModal] = useState(null);
  const [sendPhone, setSendPhone] = useState('');
  const [sending, setSending] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingName, setDeletingName] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [form, setForm] = useState({
    name: '',
    category: 'UTILITY',
    language: 'ca',
    header_text: '',
    body_text: '',
    footer_text: '',
  });

  const API = process.env.REACT_APP_BACKEND_URL;
  const token = localStorage.getItem('access_token');

  const loadTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/templates`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error');
      }
      const data = await res.json();
      setTemplates(data.templates || []);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  useEffect(() => { loadTemplates(); }, []);

  const handleSend = async () => {
    if (!sendModal || !sendPhone.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/api/admin/templates/send`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_name: sendModal.name,
          language_code: sendModal.language,
          to_phone: sendPhone.trim()
        })
      });
      const data = await res.json();
      if (data.ok) {
        toast.success(t('templates.sent_ok'));
        setSendModal(null);
        setSendPhone('');
      } else {
        toast.error(data.error || t('templates.sent_error'));
      }
    } catch {
      toast.error(t('templates.sent_error'));
    }
    setSending(false);
  };

  const resetForm = () => setForm({
    name: '', category: 'UTILITY', language: 'ca',
    header_text: '', body_text: '', footer_text: '',
  });

  const handleCreate = async () => {
    if (!form.name.trim() || !form.body_text.trim()) {
      toast.error(t('templates.create_required'));
      return;
    }
    setCreating(true);
    try {
      const res = await fetch(`${API}/api/admin/templates`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        toast.success(t('templates.created_ok'));
        setCreateOpen(false);
        resetForm();
        await loadTemplates();
      } else {
        toast.error(data.detail || data.error || t('templates.created_error'));
      }
    } catch {
      toast.error(t('templates.created_error'));
    }
    setCreating(false);
  };

  const handleDelete = async (name) => {
    setDeletingName(name);
    try {
      const res = await fetch(`${API}/api/admin/templates/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        toast.success(t('templates.deleted_ok'));
        setConfirmDelete(null);
        await loadTemplates();
      } else {
        toast.error(data.detail || t('templates.deleted_error'));
      }
    } catch {
      toast.error(t('templates.deleted_error'));
    }
    setDeletingName(null);
  };

  const statusBadge = (status) => {
    const colors = {
      APPROVED: 'bg-emerald-100 text-emerald-700',
      PENDING: 'bg-amber-100 text-amber-700',
      REJECTED: 'bg-red-100 text-red-700',
    };
    const labels = {
      APPROVED: t('templates.approved'),
      PENDING: t('templates.pending'),
      REJECTED: t('templates.rejected'),
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-700'}`}>
        {labels[status] || status}
      </span>
    );
  };

  if (loading) return <div className="p-6 text-sm text-[#94A3B8]">{t('templates.loading')}</div>;

  if (error) return (
    <div className="p-6">
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      <button onClick={loadTemplates} className="mt-3 px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md">
        <ArrowClockwise size={14} className="inline mr-1" /> Retry
      </button>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('templates.title')}</h2>
          <p className="text-xs text-[#94A3B8] mt-0.5">{t('templates.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#64748B] font-medium">{templates.length} {t('templates.total')}</span>
          <button onClick={loadTemplates} data-testid="refresh-templates"
            className="p-2 text-[#475569] border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9]">
            <ArrowClockwise size={14} />
          </button>
          <button onClick={() => setCreateOpen(true)} data-testid="create-template-btn"
            className="px-4 py-2 text-xs font-bold bg-emerald-600 text-white rounded-md hover:bg-emerald-700 flex items-center gap-1.5 shadow-sm ring-2 ring-emerald-100 hover:ring-emerald-200 transition-all">
            <Plus size={14} weight="bold" />
            {t('templates.create_new')}
          </button>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="text-center py-12">
          <ChatText size={40} className="mx-auto text-[#CBD5E1] mb-3" weight="duotone" />
          <p className="text-sm text-[#94A3B8]">{t('templates.empty')}</p>
        </div>
      ) : (
        <div className="border border-[#E2E8F0] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-[#475569]">{t('templates.name')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-[#475569]">{t('templates.status')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-[#475569]">{t('templates.category')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-[#475569]">{t('templates.language')}</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold text-[#475569]">{t('templates.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((tpl, i) => (
                <tr key={tpl.id || i} data-testid={`template-row-${tpl.name}`} className="border-b border-[#F1F5F9] last:border-0 hover:bg-[#F8FAFC]">
                  <td className="px-4 py-3">
                    <span className="font-medium text-[#0F172A]">{tpl.name}</span>
                    {tpl.components?.find(c => c.type === 'BODY') && (
                      <p className="text-xs text-[#94A3B8] mt-0.5 truncate max-w-[280px]">
                        {tpl.components.find(c => c.type === 'BODY')?.text}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3">{statusBadge(tpl.status)}</td>
                  <td className="px-4 py-3 text-[#64748B]">{tpl.category}</td>
                  <td className="px-4 py-3 text-[#64748B]">{tpl.language}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center gap-1.5 justify-end">
                      {tpl.status === 'APPROVED' && (
                        <button data-testid={`send-template-${tpl.name}`}
                          onClick={() => setSendModal(tpl)}
                          className="px-3 py-1.5 text-xs font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] flex items-center gap-1">
                          <PaperPlaneRight size={12} weight="bold" />
                          {t('templates.send_test')}
                        </button>
                      )}
                      <button data-testid={`delete-template-${tpl.name}`}
                        onClick={() => setConfirmDelete(tpl)}
                        title={t('templates.delete')}
                        className="p-1.5 text-red-600 border border-red-200 rounded-md hover:bg-red-50">
                        <Trash size={12} weight="bold" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Send modal */}
      {sendModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setSendModal(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
              {t('templates.send_test')}: {sendModal.name}
            </h3>
            <p className="text-xs text-[#94A3B8] mb-4">{sendModal.language} · {sendModal.category}</p>

            {sendModal.components?.find(c => c.type === 'BODY') && (
              <div className="p-3 bg-[#F1F5F9] rounded-lg mb-4 text-xs text-[#334155] leading-relaxed">
                {sendModal.components.find(c => c.type === 'BODY')?.text}
              </div>
            )}

            <label className="text-xs font-medium text-[#475569] mb-1.5 block">{t('templates.send_to')}</label>
            <input data-testid="template-send-phone" type="text" value={sendPhone}
              onChange={e => setSendPhone(e.target.value)}
              placeholder="34690829362"
              className="w-full px-4 py-2.5 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono mb-4" />

            <div className="flex gap-2">
              <button onClick={() => setSendModal(null)}
                className="flex-1 px-4 py-2.5 text-sm font-medium border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC]">
                {t('templates.cancel')}
              </button>
              <button data-testid="confirm-send-template" onClick={handleSend}
                disabled={sending || !sendPhone.trim()}
                className="flex-1 px-4 py-2.5 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {sending ? <CircleNotch size={14} className="animate-spin" /> : <PaperPlaneRight size={14} weight="bold" />}
                {sending ? '...' : t('templates.send_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create modal */}
      {createOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => !creating && setCreateOpen(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
              {t('templates.create_title')}
            </h3>
            <p className="text-xs text-[#94A3B8] mb-4">{t('templates.create_subtitle')}</p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_name')} *</label>
                <input data-testid="tpl-name" type="text" value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                  placeholder="benvinguda_taller"
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
                <p className="text-[10px] text-[#94A3B8] mt-1">{t('templates.field_name_hint')}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_category')} *</label>
                  <select data-testid="tpl-category" value={form.category}
                    onChange={e => setForm({ ...form, category: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                    <option value="UTILITY">UTILITY</option>
                    <option value="MARKETING">MARKETING</option>
                    <option value="AUTHENTICATION">AUTHENTICATION</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_language')} *</label>
                  <select data-testid="tpl-language" value={form.language}
                    onChange={e => setForm({ ...form, language: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                    <option value="ca">Català (ca)</option>
                    <option value="es">Español (es)</option>
                    <option value="en">English (en)</option>
                    <option value="en_US">English US (en_US)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_header')}</label>
                <input data-testid="tpl-header" type="text" maxLength={60} value={form.header_text}
                  onChange={e => setForm({ ...form, header_text: e.target.value })}
                  placeholder={t('templates.field_header_placeholder')}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>

              <div>
                <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_body')} *</label>
                <textarea data-testid="tpl-body" rows={4} maxLength={1024} value={form.body_text}
                  onChange={e => setForm({ ...form, body_text: e.target.value })}
                  placeholder={t('templates.field_body_placeholder')}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] resize-none" />
                <p className="text-[10px] text-[#94A3B8] mt-1">{form.body_text.length} / 1024</p>
              </div>

              <div>
                <label className="text-xs font-medium text-[#475569] mb-1 block">{t('templates.field_footer')}</label>
                <input data-testid="tpl-footer" type="text" maxLength={60} value={form.footer_text}
                  onChange={e => setForm({ ...form, footer_text: e.target.value })}
                  placeholder={t('templates.field_footer_placeholder')}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button onClick={() => { setCreateOpen(false); resetForm(); }}
                disabled={creating}
                className="flex-1 px-4 py-2.5 text-sm font-medium border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC]">
                {t('templates.cancel')}
              </button>
              <button data-testid="confirm-create-template" onClick={handleCreate}
                disabled={creating || !form.name.trim() || !form.body_text.trim()}
                className="flex-1 px-4 py-2.5 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {creating ? <CircleNotch size={14} className="animate-spin" /> : <Plus size={14} weight="bold" />}
                {creating ? '...' : t('templates.create_btn')}
              </button>
            </div>
            <p className="text-[10px] text-[#94A3B8] mt-3 text-center">{t('templates.create_note')}</p>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => !deletingName && setConfirmDelete(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
              {t('templates.delete_title')}
            </h3>
            <p className="text-sm text-[#475569] mb-4">
              {t('templates.delete_confirm')} <span className="font-mono font-semibold text-[#0F172A]">{confirmDelete.name}</span>?
            </p>
            <div className="flex gap-2">
              <button onClick={() => setConfirmDelete(null)} disabled={!!deletingName}
                className="flex-1 px-4 py-2.5 text-sm font-medium border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC]">
                {t('templates.cancel')}
              </button>
              <button data-testid="confirm-delete-template" onClick={() => handleDelete(confirmDelete.name)}
                disabled={!!deletingName}
                className="flex-1 px-4 py-2.5 text-sm font-semibold bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-40 flex items-center justify-center gap-2">
                {deletingName ? <CircleNotch size={14} className="animate-spin" /> : <Trash size={14} weight="bold" />}
                {deletingName ? '...' : t('templates.delete_btn')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
