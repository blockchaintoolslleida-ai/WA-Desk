import { useState } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { Gear } from '@phosphor-icons/react';

export default function TenantSetupForm({ t, onCreated }) {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [saving, setSaving] = useState(false);

  const handleNameChange = (val) => {
    setName(val);
    setSlug(val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
  };

  const handleCreate = async () => {
    if (!name.trim() || !slug.trim()) return;
    setSaving(true);
    try {
      await adminApi.createMyTenant({ name: name.trim(), slug: slug.trim() });
      toast.success(t('admin.tenant.created_ok'));
      onCreated();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error';
      if (msg.includes('slug')) toast.error(t('admin.tenant.slug_exists'));
      else toast.error(msg);
    }
    setSaving(false);
  };

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-white border border-[#E2E8F0] rounded-lg">
      <div className="w-12 h-12 rounded-full bg-[#0F172A] flex items-center justify-center mb-4">
        <Gear size={24} weight="bold" className="text-white" />
      </div>
      <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('admin.tenant.create_title')}</h2>
      <p className="text-sm text-[#64748B] mb-5">{t('admin.tenant.create_desc')}</p>

      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">{t('admin.tenant.name')}</label>
          <input data-testid="tenant-name" type="text" value={name} onChange={e => handleNameChange(e.target.value)}
            placeholder={t('admin.tenant.name_placeholder')}
            className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
        </div>
        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">{t('admin.tenant.slug')}</label>
          <input data-testid="tenant-slug" type="text" value={slug} onChange={e => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
            placeholder={t('admin.tenant.slug_placeholder')}
            className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
        </div>
        <button data-testid="create-tenant-btn" onClick={handleCreate} disabled={saving || !name.trim() || !slug.trim()}
          className="w-full px-4 py-2.5 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-40">
          {saving ? '...' : t('admin.tenant.create_btn')}
        </button>
      </div>
    </div>
  );
}
