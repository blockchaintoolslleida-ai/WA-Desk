import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { Eye, EyeSlash, ArrowClockwise, Plugs, PlugsConnected, Shield, WarningCircle, CheckCircle, Phone, Buildings, IdentificationBadge } from '@phosphor-icons/react';
import StatusBadge from './StatusBadge';
import SetupWizard from './SetupWizard';

export default function AccountSection({ t, locale }) {
  const [account, setAccount] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [certificate, setCertificate] = useState('');
  const [savingCert, setSavingCert] = useState(false);
  const [showCert, setShowCert] = useState(false);
  const [secrets, setSecrets] = useState(null);
  const [showWizard, setShowWizard] = useState(null);

  const load = async () => {
    let acc = null;
    let sec = null;
    try {
      const res = await adminApi.getAccount();
      acc = res.data?.account;
      if (acc) { setAccount(acc); setForm(acc); }
    } catch { /* tables may not exist yet */ }
    try {
      const sRes = await adminApi.getSecrets();
      sec = sRes.data?.secrets;
      setSecrets(sec);
    } catch {}

    if (acc) {
      const isConnected = acc.connection_status === 'connected';
      setShowWizard(!isConnected);
    } else {
      setShowWizard(true);
    }
  };
  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await adminApi.updateAccount({
        account_name: form.account_name,
        phone_number_id: form.phone_number_id,
        whatsapp_business_account_id: form.whatsapp_business_account_id,
      });
      setAccount(res.data.account);
      toast.success(t('admin.account.saved_ok'));
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  const handleSaveCertificate = async () => {
    if (!certificate.trim()) return;
    setSavingCert(true);
    try {
      await adminApi.updateSecrets({ access_token: certificate.trim() });
      toast.success(t('admin.secrets.saved_ok'));
      setCertificate('');
      load();
    } catch { toast.error('Error'); }
    setSavingCert(false);
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await adminApi.validateConnection();
      if (res.data.valid) { toast.success(t('admin.account.validated_ok')); load(); }
      else toast.error(res.data.error);
    } catch { toast.error('Error'); }
    setValidating(false);
  };

  const handleDisconnect = async () => {
    try {
      await adminApi.disconnectAccount();
      toast.success(t('admin.account.disconnected'));
      load();
    } catch { toast.error('Error'); }
  };

  const field = (label, key, tooltip) => (
    <div key={key}>
      <label className="text-xs font-medium text-[#475569] mb-1 block">{label}
        {tooltip && <span className="ml-1 text-[10px] text-[#94A3B8]" title={tooltip}>?</span>}
      </label>
      <input data-testid={`field-${key}`} type="text" value={form[key] || ''}
        onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
        className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] bg-white" />
    </div>
  );

  if (!account) return <div className="p-6 text-sm text-[#94A3B8]">{t('general.loading')}</div>;

  if (showWizard) {
    return <SetupWizard t={t} account={account} secrets={secrets}
      onComplete={() => { setShowWizard(false); load(); }} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('admin.account.title')}</h2>
        <div className="flex items-center gap-2">
          <StatusBadge status={account.connection_status} t={t} />
          <StatusBadge status={account.token_status} t={t} />
        </div>
      </div>

      {/* Connection Summary card — prominently shows the actual business phone for Meta reviewer */}
      <div data-testid="connection-summary" className="rounded-xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5">
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle size={18} weight="fill" className="text-emerald-600" />
          <h3 className="text-sm font-bold text-emerald-900" style={{ fontFamily: 'Manrope' }}>{t('admin.account.connected_summary')}</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
              <Phone size={11} weight="bold" /> {t('admin.account.business_phone')}
            </div>
            <p data-testid="business-phone-number" className="font-mono text-base font-bold text-[#0F172A]">
              {account.display_phone_number || '—'}
            </p>
            {account.sender_display_name && (
              <p className="text-[11px] text-[#64748B] mt-0.5">{account.sender_display_name}</p>
            )}
          </div>
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
              <IdentificationBadge size={11} weight="bold" /> Phone Number ID
            </div>
            <p data-testid="phone-number-id-display" className="font-mono text-xs font-medium text-[#0F172A] break-all">
              {account.phone_number_id || '—'}
            </p>
          </div>
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
              <Buildings size={11} weight="bold" /> WABA ID
            </div>
            <p data-testid="waba-id-display" className="font-mono text-xs font-medium text-[#0F172A] break-all">
              {account.whatsapp_business_account_id || '—'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {field(t('admin.account.name'), 'account_name')}
        {field(t('admin.account.phone_id'), 'phone_number_id', 'Meta WhatsApp Manager > Certificat')}
      </div>
      <div>
        {field(t('admin.account.waba_id') || 'WhatsApp Business Account ID', 'whatsapp_business_account_id', 'Meta Business Manager > WhatsApp Manager')}
      </div>

      <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[#0F172A]">{t('admin.account.certificate')}</h3>
          <Shield size={18} weight="duotone" className="text-[#94A3B8]" />
        </div>
        <div className="px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
          <WarningCircle size={14} className="inline mr-1" weight="bold" />
          {t('admin.account.cert_hint')}
        </div>
        {secrets?.has_access_token && (
          <div className="space-y-1">
            <label className="text-xs font-medium text-[#475569] flex items-center justify-between">
              {t('admin.account.current_cert')}
              <button type="button" onClick={() => setShowCert(!showCert)}
                className="text-[10px] text-blue-600 flex items-center gap-0.5 hover:underline">
                {showCert ? <><EyeSlash size={10} /> {t('admin.secrets.hide')}</> : <><Eye size={10} /> {t('admin.secrets.show')}</>}
              </button>
            </label>
            <div className="px-3 py-1.5 bg-white border border-[#E2E8F0] rounded-md text-xs text-[#64748B] font-mono truncate">
              {showCert ? secrets.masked_access_token : '••••••••••••'}
            </div>
          </div>
        )}
        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">{t('admin.account.new_cert')}</label>
          <textarea data-testid="certificate-input" rows={3} value={certificate}
            onChange={e => setCertificate(e.target.value)}
            placeholder={t('admin.account.cert_placeholder')}
            className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] bg-white font-mono resize-none" />
        </div>
        <button data-testid="save-certificate" onClick={handleSaveCertificate}
          disabled={savingCert || !certificate.trim()}
          className="px-4 py-2 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-40">
          {savingCert ? '...' : t('admin.account.save_cert')}
        </button>
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button data-testid="save-account" onClick={handleSave} disabled={saving}
          className="px-4 py-2 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-50">
          {saving ? '...' : t('admin.account.save')}
        </button>
        <button data-testid="validate-connection" onClick={handleValidate} disabled={validating}
          className="px-4 py-2 text-sm font-medium border border-green-600 text-green-700 rounded-md hover:bg-green-50 disabled:opacity-50 flex items-center gap-1.5">
          <PlugsConnected size={16} weight="bold" />
          {validating ? '...' : t('admin.account.validate')}
        </button>
        <button data-testid="disconnect-account" onClick={handleDisconnect}
          className="px-4 py-2 text-sm font-medium border border-red-300 text-red-600 rounded-md hover:bg-red-50 flex items-center gap-1.5">
          <Plugs size={16} weight="bold" />
          {t('admin.account.disconnect')}
        </button>
        <button data-testid="refresh-status" onClick={load}
          className="px-3 py-2 text-sm text-[#475569] border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9] flex items-center gap-1">
          <ArrowClockwise size={14} />
          {t('admin.account.refresh')}
        </button>
      </div>

      {account.last_validation_at && (
        <p className="text-[11px] text-[#94A3B8]">
          {t('admin.account.validate')}: {new Date(account.last_validation_at).toLocaleString(locale)}
        </p>
      )}
    </div>
  );
}
