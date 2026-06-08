import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { agentsApi } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from '../contexts/LanguageContext';
import AppHeader from '../components/AppHeader';
import { toast } from 'sonner';
import { UserPlus, PencilSimple, Trash, Check, X, ShieldCheck, UserCircle, Crown } from '@phosphor-icons/react';

const ROLE_ICONS = { super_admin: Crown, admin: ShieldCheck, agent: UserCircle };

export default function AgentsPage() {
  const navigate = useNavigate();
  const { isAdmin, isSuperAdmin, user } = useAuth();
  const { t } = useTranslation();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'agent', phone: '' });
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { loadAgents(); }, []);

  const loadAgents = async () => {
    try {
      const res = await agentsApi.list();
      setAgents(res.data || []);
    } catch {} finally { setLoading(false); }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await agentsApi.create(form);
      toast.success(t('agents.created_ok'));
      setShowCreate(false);
      setForm({ full_name: '', email: '', password: '', role: 'agent', phone: '' });
      loadAgents();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('agents.create_error'));
    } finally { setSaving(false); }
  };

  const startEdit = (agent) => {
    setEditingId(agent.id);
    setEditForm({ full_name: agent.full_name, role: agent.role, phone: agent.phone || '', is_active: agent.is_active });
  };

  const handleUpdate = async () => {
    setSaving(true);
    try {
      await agentsApi.update(editingId, editForm);
      toast.success(t('agents.updated_ok'));
      setEditingId(null);
      loadAgents();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('agents.update_error'));
    } finally { setSaving(false); }
  };

  const handleDelete = async (agent) => {
    if (!window.confirm(t('agents.confirm_delete', { name: agent.full_name }))) return;
    try {
      await agentsApi.remove(agent.id);
      toast.success(t('agents.deleted_ok'));
      loadAgents();
    } catch (err) {
      toast.error(err.response?.data?.detail || t('agents.delete_error'));
    }
  };

  const canManage = (agent) => {
    if (agent.id === user?.id) return false;
    if (isSuperAdmin) return agent.role !== 'super_admin';
    if (isAdmin) return agent.role === 'agent';
    return false;
  };

  const roleOptions = isSuperAdmin ? ['agent', 'admin'] : ['agent'];

  return (
    <div className="h-screen flex flex-col bg-[#F8FAFC]">
      <AppHeader currentPage="agents" onNavigate={(page) => navigate(page === 'dashboard' ? '/dashboard' : page === 'contacts' ? '/contacts' : page === 'agents' ? '/agents' : page === 'admin' ? '/admin' : '/')} />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 data-testid="agents-title" className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>
            {t('agents.title')}
          </h1>
          {isAdmin && (
            <button data-testid="create-agent-button" onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] transition-colors">
              <UserPlus size={16} /> {t('agents.create')}
            </button>
          )}
        </div>

        {/* Create form */}
        {showCreate && (
          <form onSubmit={handleCreate} data-testid="create-agent-form" className="bg-white border border-[#E2E8F0] rounded-md p-4 mb-4">
            <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: 'Manrope' }}>{t('agents.new_agent')}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('agents.field_name')}</label>
                <input data-testid="agent-name-input" type="text" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  className="w-full mt-0.5 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('agents.field_email')}</label>
                <input data-testid="agent-email-input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full mt-0.5 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('agents.field_password')}</label>
                <input data-testid="agent-password-input" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full mt-0.5 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('agents.field_phone')}</label>
                <input data-testid="agent-phone-input" type="text" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full mt-0.5 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-[#64748B] uppercase">{t('agents.field_role')}</label>
                <select data-testid="agent-role-select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="w-full mt-0.5 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                  {roleOptions.map(r => <option key={r} value={r}>{t(`agents.role_${r}`)}</option>)}
                </select>
              </div>
              <div className="flex items-end">
                <button data-testid="submit-agent" type="submit" disabled={saving}
                  className="w-full py-2 bg-[#0F172A] text-white text-sm font-medium rounded-md hover:bg-[#1E293B] disabled:opacity-50">
                  {saving ? t('agents.creating') : t('agents.create')}
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Agents table */}
        {loading ? (
          <p className="text-sm text-[#64748B]">{t('general.loading')}</p>
        ) : (
          <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <th className="text-left px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_name')}</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_email')}</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_phone')}</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_role')}</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_status')}</th>
                  {isAdmin && <th className="text-right px-4 py-2 text-xs font-semibold text-[#64748B] uppercase tracking-wide">{t('agents.col_actions')}</th>}
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => {
                  const RoleIcon = ROLE_ICONS[agent.role] || UserCircle;
                  const isEditing = editingId === agent.id;
                  const manageable = canManage(agent);

                  return (
                    <tr key={agent.id} data-testid={`agent-row-${agent.id}`} className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#FAFBFC] transition-colors">
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <input data-testid="edit-name-input" value={editForm.full_name} onChange={e => setEditForm({ ...editForm, full_name: e.target.value })}
                            className="px-2 py-1 text-sm border border-[#E2E8F0] rounded-md w-full focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
                        ) : (
                          <span className="font-medium">{agent.full_name} {agent.id === user?.id && <span className="text-[10px] text-[#64748B]">({t('agents.you')})</span>}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[#475569]">{agent.email}</td>
                      <td className="px-4 py-3 text-[#475569]">
                        {isEditing ? (
                          <input data-testid="edit-phone-input" value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })}
                            className="px-2 py-1 text-sm border border-[#E2E8F0] rounded-md w-full focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
                        ) : (
                          <span className="font-mono text-xs">{agent.phone || '-'}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isEditing && manageable ? (
                          <select data-testid="edit-role-select" value={editForm.role} onChange={e => setEditForm({ ...editForm, role: e.target.value })}
                            className="px-2 py-1 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                            {roleOptions.map(r => <option key={r} value={r}>{t(`agents.role_${r}`)}</option>)}
                          </select>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md bg-[#F1F5F9] text-[#475569]">
                            <RoleIcon size={12} /> {t(`agents.role_${agent.role}`)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <select data-testid="edit-status-select" value={editForm.is_active ? 'true' : 'false'} onChange={e => setEditForm({ ...editForm, is_active: e.target.value === 'true' })}
                            className="px-2 py-1 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
                            <option value="true">{t('agents.status_active')}</option>
                            <option value="false">{t('agents.status_inactive')}</option>
                          </select>
                        ) : (
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${agent.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                            {agent.is_active ? t('agents.status_active') : t('agents.status_inactive')}
                          </span>
                        )}
                      </td>
                      {isAdmin && (
                        <td className="px-4 py-3 text-right">
                          {isEditing ? (
                            <div className="flex items-center justify-end gap-1">
                              <button data-testid="save-edit-btn" onClick={handleUpdate} disabled={saving} className="p-1 rounded hover:bg-green-50 text-green-600"><Check size={16} weight="bold" /></button>
                              <button data-testid="cancel-edit-btn" onClick={() => setEditingId(null)} className="p-1 rounded hover:bg-red-50 text-red-500"><X size={16} /></button>
                            </div>
                          ) : manageable ? (
                            <div className="flex items-center justify-end gap-1">
                              <button data-testid={`edit-agent-${agent.id}`} onClick={() => startEdit(agent)} className="p-1.5 rounded hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#0F172A] transition-colors" title={t('agents.edit')}>
                                <PencilSimple size={15} />
                              </button>
                              <button data-testid={`delete-agent-${agent.id}`} onClick={() => handleDelete(agent)} className="p-1.5 rounded hover:bg-red-50 text-[#64748B] hover:text-red-600 transition-colors" title={t('agents.delete')}>
                                <Trash size={15} />
                              </button>
                            </div>
                          ) : null}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
