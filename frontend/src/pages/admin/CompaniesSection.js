import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { Buildings, Trash, Users, CheckCircle, Pencil, UserPlus, X } from '@phosphor-icons/react';

export default function CompaniesSection({ t }) {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);

  // Edit modal
  const [editModal, setEditModal] = useState(null);
  const [editName, setEditName] = useState('');
  const [editSlug, setEditSlug] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  // Add user modal
  const [addUserModal, setAddUserModal] = useState(null);
  const [newUser, setNewUser] = useState({ full_name: '', email: '', password: '', role: 'agent' });
  const [addingUser, setAddingUser] = useState(false);

  const load = async () => {
    try {
      const res = await adminApi.getTenants();
      setTenants(res.data || []);
    } catch { toast.error('Error'); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const loadUsers = async (tenantId) => {
    setUsersLoading(true);
    try {
      const res = await adminApi.getTenantUsers(tenantId);
      setUsers(res.data || []);
    } catch { setUsers([]); }
    setUsersLoading(false);
  };

  const toggleExpand = (id) => {
    if (expanded === id) { setExpanded(null); setUsers([]); }
    else { setExpanded(id); loadUsers(id); }
  };

  const handleDeleteTenant = async (id, name) => {
    if (!window.confirm(`${t('admin.companies.delete_confirm')} "${name}"?\n\n${t('admin.companies.delete_warn')}`)) return;
    try {
      await adminApi.deleteTenant(id);
      toast.success(`${t('admin.companies.deleted')}: ${name}`);
      load();
    } catch { toast.error('Error'); }
  };

  const openEdit = (t) => { setEditModal(t.id); setEditName(t.name); setEditSlug(t.slug); };
  const saveEdit = async () => {
    if (!editName.trim()) return;
    setEditSaving(true);
    try {
      await adminApi.updateTenant(editModal, { name: editName.trim(), slug: editSlug.trim() });
      toast.success(t('admin.companies.saved') || 'Saved');
      setEditModal(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
    setEditSaving(false);
  };

  const handleAddUser = async () => {
    if (!newUser.full_name.trim() || !newUser.email.trim() || !newUser.password.trim()) return;
    setAddingUser(true);
    try {
      await adminApi.assignTenantUser(addUserModal, newUser);
      toast.success(t('admin.companies.user_added') || 'User added');
      setAddUserModal(null);
      setNewUser({ full_name: '', email: '', password: '', role: 'agent' });
      if (expanded === addUserModal) loadUsers(addUserModal);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
    setAddingUser(false);
  };

  const handleRemoveUser = async (tenantId, userId, name) => {
    if (!window.confirm(`${t('admin.companies.remove_user_confirm') || 'Remove'} "${name}"?`)) return;
    try {
      await adminApi.removeTenantUser(tenantId, userId);
      toast.success(`${t('admin.companies.user_removed') || 'Removed'}: ${name}`);
      loadUsers(tenantId);
      load();
    } catch { toast.error('Error'); }
  };

  if (loading) return <div className="p-6 text-sm text-[#94A3B8]">{t('general.loading')}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
          {t('admin.companies.title') || 'Companies'}
        </h2>
        <span className="text-xs text-[#94A3B8]">{tenants.length} {t('admin.companies.count') || 'companies'}</span>
      </div>

      {tenants.map(tenant => (
        <div key={tenant.id} className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
          <div className="p-4">
            <div className="flex items-center justify-between">
              <button onClick={() => toggleExpand(tenant.id)} className="flex items-center gap-2 text-left flex-1 min-w-0">
                <Buildings size={18} weight="bold" className="text-[#0F172A] flex-shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-[#0F172A] truncate">{tenant.name}</h3>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-[#64748B]">
                    <span className="font-mono text-[10px]">{tenant.slug}</span>
                    <span className="flex items-center gap-1"><Users size={11} /> {tenant.user_count || 0}</span>
                    {tenant.has_whatsapp && <span className="flex items-center gap-1 text-emerald-600"><CheckCircle size={11} weight="bold" /> WhatsApp</span>}
                  </div>
                </div>
              </button>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button onClick={() => openEdit(tenant)} className="p-1.5 text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-md" title={t('admin.companies.edit') || 'Edit'}>
                  <Pencil size={14} />
                </button>
                <button onClick={() => handleDeleteTenant(tenant.id, tenant.name)} className="p-1.5 text-[#94A3B8] hover:text-red-500 hover:bg-red-50 rounded-md" title={t('admin.companies.delete')}>
                  <Trash size={14} weight="bold" />
                </button>
              </div>
            </div>
          </div>

          {/* Expanded: user list */}
          {expanded === tenant.id && (
            <div className="border-t border-[#E2E8F0] bg-[#F8FAFC] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-[#475569] uppercase tracking-wide">{t('admin.companies.users') || 'Users'}</h4>
                <button onClick={() => setAddUserModal(tenant.id)}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-[#0F172A] text-white rounded hover:bg-[#1E293B]">
                  <UserPlus size={12} weight="bold" /> {t('admin.companies.add_user') || 'Add'}
                </button>
              </div>

              {usersLoading ? (
                <p className="text-xs text-[#94A3B8]">{t('general.loading')}</p>
              ) : users.length === 0 ? (
                <p className="text-xs text-[#94A3B8]">{t('admin.companies.no_users') || 'No users'}</p>
              ) : (
                <div className="space-y-1">
                  {users.map(u => (
                    <div key={u.id} className="flex items-center justify-between px-3 py-1.5 bg-white border border-[#E2E8F0] rounded">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${u.role === 'admin' ? 'bg-[#0F172A]' : 'bg-[#94A3B8]'}`} />
                        <span className="text-xs font-medium text-[#0F172A] truncate">{u.full_name}</span>
                        <span className="text-[10px] text-[#94A3B8] truncate hidden sm:inline">{u.email}</span>
                        <span className="text-[10px] px-1 py-0.5 rounded bg-[#F1F5F9] text-[#64748B]">{u.role}</span>
                      </div>
                      <button onClick={() => handleRemoveUser(tenant.id, u.id, u.full_name)}
                        className="p-1 text-[#94A3B8] hover:text-red-500 flex-shrink-0" title={t('admin.companies.remove_user') || 'Remove'}>
                        <X size={12} weight="bold" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {tenants.length === 0 && (
        <p className="text-sm text-[#94A3B8] text-center py-8">{t('admin.companies.empty') || 'No companies'}</p>
      )}

      {/* Edit Modal */}
      {editModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditModal(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[#0F172A] mb-4">{t('admin.companies.edit_company') || 'Edit Company'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#475569]">{t('admin.companies.name') || 'Name'}</label>
                <input type="text" value={editName} onChange={e => setEditName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
              </div>
              <div>
                <label className="text-xs font-medium text-[#475569]">Slug</label>
                <input type="text" value={editSlug} onChange={e => setEditSlug(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setEditModal(null)} className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md">{t('conv.cancel') || 'Cancel'}</button>
                <button onClick={saveEdit} disabled={editSaving} className="flex-1 px-3 py-2 text-sm bg-[#0F172A] text-white rounded-md disabled:opacity-50">
                  {editSaving ? '...' : t('admin.account.save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {addUserModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setAddUserModal(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[#0F172A] mb-4">{t('admin.companies.add_user_title') || 'Add User to Company'}</h3>
            <div className="space-y-2">
              <input type="text" placeholder={t('admin.companies.user_name') || 'Full name'} value={newUser.full_name}
                onChange={e => setNewUser(p => ({...p, full_name: e.target.value}))}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md" />
              <input type="email" placeholder="Email" value={newUser.email}
                onChange={e => setNewUser(p => ({...p, email: e.target.value}))}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md" />
              <input type="password" placeholder={t('admin.companies.password') || 'Password'} value={newUser.password}
                onChange={e => setNewUser(p => ({...p, password: e.target.value}))}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md" />
              <select value={newUser.role} onChange={e => setNewUser(p => ({...p, role: e.target.value}))}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md">
                <option value="agent">{t('admin.companies.role_agent') || 'Agent'}</option>
                <option value="admin">{t('admin.companies.role_admin') || 'Admin'}</option>
              </select>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setAddUserModal(null)} className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md">{t('conv.cancel') || 'Cancel'}</button>
                <button onClick={handleAddUser} disabled={addingUser} className="flex-1 px-3 py-2 text-sm bg-[#0F172A] text-white rounded-md disabled:opacity-50">
                  {addingUser ? '...' : t('admin.companies.add_user_btn') || 'Add User'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
