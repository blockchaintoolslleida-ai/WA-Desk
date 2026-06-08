import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { Eye, EyeSlash, ArrowClockwise, Plugs, PlugsConnected, Shield, WarningCircle, CheckCircle, Phone, Buildings, IdentificationBadge, Globe, Key, DeviceMobile, Trash } from '@phosphor-icons/react';
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
      const payload = {
        account_name: form.account_name || '',
        phone_number_id: form.phone_number_id || '',
        whatsapp_business_account_id: form.whatsapp_business_account_id || '',
        connection_type: form.connection_type || 'meta',
        openwa_server_url: form.openwa_server_url || '',
        openwa_session_id: form.openwa_session_id || '',
      };
      const res = await adminApi.updateAccount(payload);
      const updated = res.data.account;
      setAccount(updated);
      setForm(updated);  // Sync form with saved data
      toast.success(t('admin.account.saved_ok'));
    } catch (e) { toast.error('Error saving: ' + (e?.message || '')); }
    setSaving(false);
  };

  const handleSaveCertificate = async () => {
    if (!certificate.trim()) return;
    setSavingCert(true);
    try {
      const connType = form.connection_type || 'meta';
      if (connType === 'openwa') {
        await adminApi.updateSecrets({ openwa_api_key: certificate.trim() });
      } else {
        await adminApi.updateSecrets({ access_token: certificate.trim() });
      }
      toast.success(t('admin.secrets.saved_ok'));
      setCertificate('');
      load();  // Reload to get updated masked value
    } catch (e) { toast.error('Error saving: ' + (e?.message || '')); }
    setSavingCert(false);
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await adminApi.validateConnection();
      if (res.data.valid) { toast.success(t('admin.account.validated_ok')); load(); }
      else toast.error(res.data.error || 'Validation failed');
    } catch (e) { toast.error('Error: ' + (e?.message || '')); }
    setValidating(false);
  };

  const handleDisconnect = async () => {
    try {
      await adminApi.disconnectAccount();
      toast.success(t('admin.account.disconnected'));
      load();
    } catch (e) { toast.error('Error: ' + (e?.message || '')); }
  };

  const handleClearConfig = async () => {
    // Reset all WhatsApp config fields to empty, preserving only tenant link
    setSaving(true);
    try {
      const payload = {
        account_name: '',
        phone_number_id: '',
        whatsapp_business_account_id: '',
        connection_type: 'meta',
        openwa_server_url: '',
        openwa_session_id: '',
      };
      // Also clear secrets
      if (secrets?.has_access_token) {
        await adminApi.updateSecrets({ access_token: '' });
      }
      if (secrets?.has_openwa_api_key) {
        await adminApi.updateSecrets({ openwa_api_key: '' });
      }
      const res = await adminApi.updateAccount(payload);
      // Mark as disconnected so wizard appears
      await adminApi.disconnectAccount();
      toast.success(t('admin.account.cleared') || 'Configuration cleared');
      // Reload to show wizard
      load();
    } catch (e) { toast.error('Error: ' + (e?.message || '')); }
    setSaving(false);
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

  const connType = form.connection_type || 'meta';
  const isOpenWA = connType === 'openwa';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('admin.account.title')}</h2>
        <div className="flex items-center gap-2">
          <StatusBadge status={account.connection_status} t={t} />
          <StatusBadge status={account.token_status} t={t} />
        </div>
      </div>

      {/* Connection Type Selector */}
      <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-3">
        <h3 className="text-sm font-semibold text-[#0F172A]">{t('admin.account.connection_type') || 'Connection Type'}</h3>
        <div className="flex gap-2">
          <button type="button" onClick={() => setForm(p => ({ ...p, connection_type: 'meta' }))}
            className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${
              !isOpenWA
                ? 'bg-[#0F172A] text-white border-[#0F172A]'
                : 'bg-white text-[#475569] border-[#E2E8F0] hover:bg-[#F1F5F9]'
            }`}>
            <div className="flex items-center justify-center gap-2">
              <Buildings size={18} weight="bold" />
              <span>{t('admin.account.type_meta') || 'WhatsApp Business API (Meta)'}</span>
            </div>
          </button>
          <button type="button" onClick={() => setForm(p => ({ ...p, connection_type: 'openwa' }))}
            className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${
              isOpenWA
                ? 'bg-[#0F172A] text-white border-[#0F172A]'
                : 'bg-white text-[#475569] border-[#E2E8F0] hover:bg-[#F1F5F9]'
            }`}>
            <div className="flex items-center justify-center gap-2">
              <Globe size={18} weight="bold" />
              <span>{t('admin.account.type_openwa') || 'OpenWA Gateway'}</span>
            </div>
          </button>
        </div>
      </div>

      {/* Connected Summary - shown when connected */}
      {account.connection_status === 'connected' && (
        <div data-testid="connection-summary" className="rounded-xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={18} weight="fill" className="text-emerald-600" />
            <h3 className="text-sm font-bold text-emerald-900" style={{ fontFamily: 'Manrope' }}>
              {isOpenWA ? (t('admin.account.openwa_connected') || 'OpenWA Gateway Connected') : t('admin.account.connected_summary')}
            </h3>
          </div>
          {isOpenWA ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
                  <Globe size={11} weight="bold" /> {t('admin.account.openwa_server') || 'Server'}
                </div>
                <p className="font-mono text-xs font-medium text-[#0F172A] break-all">
                  {account.openwa_server_url || '—'}
                </p>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
                  <Key size={11} weight="bold" /> {t('admin.account.openwa_session_label') || 'Session'}
                </div>
                <p className="font-mono text-xs font-medium text-[#0F172A] break-all">
                  {account.openwa_session_id || '—'}
                </p>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
                  <DeviceMobile size={11} weight="bold" /> {t('admin.account.business_phone') || 'Phone'}
                </div>
                <p className="font-mono text-base font-bold text-[#0F172A]">
                  {account.display_phone_number || '—'}
                </p>
              </div>
            </div>
          ) : (
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
          )}
        </div>
      )}

      {/* Meta fields */}
      {!isOpenWA && (
        <>
          <div className="grid grid-cols-2 gap-4">
            {field(t('admin.account.name'), 'account_name')}
            {field(t('admin.account.phone_id'), 'phone_number_id', 'Meta WhatsApp Manager > Certificat')}
          </div>
          <div>
            {field(t('admin.account.waba_id') || 'WhatsApp Business Account ID', 'whatsapp_business_account_id', 'Meta Business Manager > WhatsApp Manager')}
          </div>
        </>
      )}

      {/* OpenWA fields */}
      {isOpenWA && (
        <div className="space-y-3">
          {field(t('admin.account.openwa_url') || 'OpenWA Server URL', 'openwa_server_url', 'Ex: http://192.168.1.100:2785')}
          {field(t('admin.account.openwa_session') || 'OpenWA Session ID', 'openwa_session_id', 'Ex: sess_abc123')}
        </div>
      )}

      {/* Certificate / API Key section */}
      <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[#0F172A]">
            {isOpenWA ? (t('admin.account.openwa_api_key') || 'OpenWA API Key') : t('admin.account.certificate')}
          </h3>
          <Shield size={18} weight="duotone" className="text-[#94A3B8]" />
        </div>
        {!isOpenWA && (
          <div className="px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
            <WarningCircle size={14} className="inline mr-1" weight="bold" />
            {t('admin.account.cert_hint')}
          </div>
        )}
        {isOpenWA && (
          <div className="px-3 py-2 rounded-md bg-blue-50 border border-blue-200 text-xs text-blue-800">
            <Globe size={14} className="inline mr-1" weight="bold" />
            {t('admin.account.openwa_api_key_hint') || 'API key from your OpenWA server (starts with owa_)'}
          </div>
        )}

        {/* Show existing credential (masked) */}
        {(isOpenWA ? secrets?.has_openwa_api_key : secrets?.has_access_token) && (
          <div className="space-y-1">
            <label className="text-xs font-medium text-[#475569] flex items-center justify-between">
              {isOpenWA ? (t('admin.account.current_api_key') || 'Current API Key') : t('admin.account.current_cert')}
              <button type="button" onClick={() => setShowCert(!showCert)}
                className="text-[10px] text-blue-600 flex items-center gap-0.5 hover:underline">
                {showCert ? <><EyeSlash size={10} /> {t('admin.secrets.hide')}</> : <><Eye size={10} /> {t('admin.secrets.show')}</>}
              </button>
            </label>
            <div className="px-3 py-1.5 bg-white border border-[#E2E8F0] rounded-md text-xs text-[#64748B] font-mono truncate">
              {showCert
                ? (isOpenWA ? (secrets?.masked_openwa_api_key || '') : (secrets?.masked_access_token || ''))
                : '••••••••••••'}
            </div>
          </div>
        )}

        {/* New credential input */}
        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">
            {isOpenWA
              ? ((secrets?.has_openwa_api_key)
                  ? (t('admin.account.replace_api_key') || 'Replace API Key')
                  : (t('admin.account.new_api_key') || 'New API Key'))
              : ((secrets?.has_access_token)
                  ? t('admin.account.replace_cert') || t('admin.account.new_cert')
                  : t('admin.account.new_cert'))
            }
          </label>
          <textarea data-testid="certificate-input" rows={3} value={certificate}
            onChange={e => setCertificate(e.target.value)}
            placeholder={isOpenWA
              ? (t('admin.account.openwa_key_placeholder') || 'owa_...')
              : t('admin.account.cert_placeholder')}
            className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A] bg-white font-mono resize-none" />
        </div>
        <button data-testid="save-certificate" onClick={handleSaveCertificate}
          disabled={savingCert || !certificate.trim()}
          className="px-4 py-2 text-sm font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-40">
          {savingCert ? '...' : t('admin.account.save_cert')}
        </button>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-2 flex-wrap">
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
        <button data-testid="clear-config" onClick={handleClearConfig}
          className="px-4 py-2 text-sm font-medium border border-amber-300 text-amber-600 rounded-md hover:bg-amber-50 flex items-center gap-1.5">
          <Trash size={16} weight="bold" />
          {t('admin.account.clear') || 'Clear config'}
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
