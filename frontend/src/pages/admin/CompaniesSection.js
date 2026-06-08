import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { Buildings, Trash, Users, CheckCircle } from '@phosphor-icons/react';

export default function CompaniesSection({ t }) {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await adminApi.getTenants();
      setTenants(res.data || []);
    } catch { toast.error('Error loading companies'); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDeleteTenant = async (id, name) => {
    if (!window.confirm(`${t('admin.companies.delete_confirm') || 'Delete company'} "${name}"? ${t('admin.companies.delete_warn') || 'This will delete ALL data (conversations, contacts, messages). This cannot be undone.'}`)) return;
    try {
      await adminApi.deleteTenant(id);
      toast.success(`${t('admin.companies.deleted') || 'Company deleted'}: ${name}`);
      load();
    } catch { toast.error('Error'); }
  };

  const handleDeleteUser = async (id, name) => {
    if (!window.confirm(`${t('admin.companies.delete_user_confirm') || 'Delete user'} "${name}"?`)) return;
    try {
      await adminApi.deleteUser(id);
      toast.success(`${t('admin.companies.user_deleted') || 'User deleted'}: ${name}`);
      load();
    } catch { toast.error('Error'); }
  };

  if (loading) return <div className="p-6 text-sm text-[#94A3B8]">{t('general.loading')}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
          {t('admin.companies.title') || 'Company Management'}
        </h2>
        <span className="text-xs text-[#94A3B8]">{tenants.length} {t('admin.companies.count') || 'companies'}</span>
      </div>

      {tenants.map(tenant => (
        <div key={tenant.id} className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
          <div className="p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Buildings size={18} weight="bold" className="text-[#0F172A]" />
                <h3 className="text-sm font-bold text-[#0F172A]">{tenant.name}</h3>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F1F5F9] text-[#64748B] font-mono">{tenant.slug}</span>
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-[#64748B]">
                <span className="flex items-center gap-1"><Users size={12} /> {tenant.user_count || 0} users</span>
                {tenant.has_whatsapp && (
                  <span className="flex items-center gap-1 text-emerald-600"><CheckCircle size={12} weight="bold" /> WhatsApp</span>
                )}
              </div>
            </div>
            <button onClick={() => handleDeleteTenant(tenant.id, tenant.name)}
              className="p-2 text-[#94A3B8] hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
              title={t('admin.companies.delete') || 'Delete company'}>
              <Trash size={16} weight="bold" />
            </button>
          </div>
        </div>
      ))}

      {tenants.length === 0 && (
        <p className="text-sm text-[#94A3B8] text-center py-8">{t('admin.companies.empty') || 'No companies yet'}</p>
      )}
    </div>
  );
}
