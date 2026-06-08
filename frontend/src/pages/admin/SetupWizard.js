import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { CheckCircle, XCircle, PlugsConnected, Shield, Rocket, Phone, CircleNotch, ArrowRight, Check, Buildings, ArrowSquareOut, Globe, Key, DeviceMobile } from '@phosphor-icons/react';

export default function SetupWizard({ t, account, secrets, onComplete }) {
  // Connection type: 'meta' or 'openwa'
  const [connType, setConnType] = useState(account?.connection_type || 'meta');
  // Current step (0=type, 1=fields, 2=secrets, 3=validate)
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  // Meta state
  const [phoneId, setPhoneId] = useState(account?.phone_number_id || '');
  const [wabaId, setWabaId] = useState(account?.whatsapp_business_account_id || '');
  const [metaCert, setMetaCert] = useState('');

  // OpenWA state
  const [openwaUrl, setOpenwaUrl] = useState(account?.openwa_server_url || '');
  const [openwaKey, setOpenwaKey] = useState('');
  const [openwaSessionId, setOpenwaSessionId] = useState(account?.openwa_session_id || '');

  const hasCert = secrets?.has_access_token;
  const hasPhone = !!account?.phone_number_id;
  const hasWaba = !!account?.whatsapp_business_account_id;
  const hasOpenWAUrl = !!account?.openwa_server_url;
  const hasOpenWAKey = secrets?.has_openwa_api_key;
  const hasOpenWASession = !!account?.openwa_session_id;

  const isOpenWA = connType === 'openwa';

  // Auto-advance based on existing config. Stay at step 0 if nothing configured yet.
  useEffect(() => {
    if (isOpenWA) {
      if (hasOpenWAUrl && hasOpenWAKey && hasOpenWASession) setStep(3);
      else if (hasOpenWAUrl && hasOpenWAKey) setStep(2);
      else if (hasOpenWAUrl || hasOpenWAKey) setStep(1);
      else setStep(0); // nothing configured — stay at type selection
    } else {
      if (hasPhone && hasWaba && hasCert) setStep(3);
      else if (hasPhone && hasWaba) setStep(2);
      else if (hasPhone || hasWaba || hasCert) setStep(1);
      else setStep(0); // nothing configured — stay at type selection
    }
  }, []); // Only on mount

  // ── Meta handlers ──────────────────────────────────────────

  const saveMetaFields = async () => {
    if (!phoneId.trim() || !wabaId.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateAccount({
        account_name: account?.account_name || 'WhatsApp Business',
        connection_type: 'meta',
        phone_number_id: phoneId.trim(),
        whatsapp_business_account_id: wabaId.trim(),
      });
      toast.success(t('wizard.phone_saved'));
      setStep(2);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  const saveMetaCert = async () => {
    if (!metaCert.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateSecrets({ access_token: metaCert.trim() });
      toast.success(t('wizard.cert_saved'));
      setMetaCert('');
      setStep(3);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  // ── OpenWA handlers ────────────────────────────────────────

  const saveOpenWAFields = async () => {
    if (!openwaUrl.trim() || !openwaKey.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateAccount({
        connection_type: 'openwa',
        openwa_server_url: openwaUrl.trim(),
      });
      await adminApi.updateSecrets({ openwa_api_key: openwaKey.trim() });
      toast.success(t('wizard.openwa_url_saved') || 'OpenWA configuration saved');
      setOpenwaKey('');
      setStep(2);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  const saveOpenWASession = async () => {
    if (!openwaSessionId.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateAccount({ openwa_session_id: openwaSessionId.trim() });
      toast.success(t('wizard.openwa_session_saved') || 'Session ID saved');
      setStep(3);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  // ── Shared validation ──────────────────────────────────────

  const validateConnection = async () => {
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await adminApi.validateConnection();
      if (res.data.valid) {
        setValidationResult({ ok: true, data: res.data.data });
        toast.success(t('wizard.connected_ok'));
      } else {
        setValidationResult({ ok: false, error: res.data.error });
      }
    } catch { setValidationResult({ ok: false, error: 'Connection failed' }); }
    setValidating(false);
  };

  // ── Render ─────────────────────────────────────────────────

  const metaSteps = [
    { key: 'type', label: t('wizard.step_type') || 'Type' },
    { key: 'phone', label: t('wizard.step_phone') },
    { key: 'cert', label: t('wizard.step_cert') },
    { key: 'validate', label: t('wizard.step_validate') },
  ];

  const openwaSteps = [
    { key: 'type', label: t('wizard.step_type') || 'Type' },
    { key: 'server', label: t('wizard.step_server') || 'Server' },
    { key: 'session', label: t('wizard.step_session') || 'Session' },
    { key: 'validate', label: t('wizard.step_validate') },
  ];

  const steps = isOpenWA ? openwaSteps : metaSteps;

  return (
    <div className="max-w-xl mx-auto py-10 px-4">
      <div className="text-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#0F172A] to-[#334155] flex items-center justify-center mx-auto mb-4 shadow-lg">
          <Rocket size={28} weight="duotone" className="text-white" />
        </div>
        <h1 className="text-xl font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('wizard.title')}</h1>
        <p className="text-sm text-[#64748B]">{t('wizard.subtitle')}</p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center justify-center gap-0 mb-10">
        {steps.map((s, i) => {
          const done = i < step || (i === 3 && validationResult?.ok);
          const active = i === step;
          return (
            <div key={s.key} className="flex items-center">
              <button onClick={() => { if (i <= step) setStep(i); }}
                data-testid={`wizard-step-${s.key}`}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  done ? 'bg-emerald-100 text-emerald-700' :
                  active ? 'bg-[#0F172A] text-white shadow-md' :
                  'bg-[#F1F5F9] text-[#94A3B8]'
                }`}>
                {done ? <Check size={14} weight="bold" /> : <span className="w-4 text-center">{i + 1}</span>}
                <span className="hidden sm:inline">{s.label}</span>
              </button>
              {i < steps.length - 1 && (
                <div className={`w-6 h-0.5 mx-1 rounded ${i < step ? 'bg-emerald-300' : 'bg-[#E2E8F0]'}`} />
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm">
        {/* ═══════════ STEP 0: Connection Type Selection ═══════════ */}
        {step === 0 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
                {t('wizard.select_type_title') || 'Select connection type'}
              </h2>
              <p className="text-sm text-[#64748B]">
                {t('wizard.select_type_desc') || 'Choose how you want to connect WhatsApp'}
              </p>
            </div>
            <div className="space-y-3">
              <button type="button" onClick={() => setConnType('meta')}
                className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                  !isOpenWA ? 'border-[#0F172A] bg-[#F8FAFC]' : 'border-[#E2E8F0] bg-white hover:bg-[#F8FAFC]'
                }`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${!isOpenWA ? 'bg-[#0F172A] text-white' : 'bg-[#F1F5F9] text-[#64748B]'}`}>
                    <Buildings size={20} weight="bold" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-sm font-bold text-[#0F172A]">{t('admin.account.type_meta') || 'WhatsApp Business API (Meta)'}</h3>
                    <p className="text-xs text-[#64748B]">{t('admin.account.type_meta_desc') || 'Official Meta connection'}</p>
                  </div>
                  {!isOpenWA && <CheckCircle size={18} weight="fill" className="text-[#0F172A]" />}
                </div>
              </button>
              <button type="button" onClick={() => setConnType('openwa')}
                className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                  isOpenWA ? 'border-[#0F172A] bg-[#F8FAFC]' : 'border-[#E2E8F0] bg-white hover:bg-[#F8FAFC]'
                }`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isOpenWA ? 'bg-[#0F172A] text-white' : 'bg-[#F1F5F9] text-[#64748B]'}`}>
                    <Globe size={20} weight="bold" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-sm font-bold text-[#0F172A]">{t('admin.account.type_openwa') || 'OpenWA Gateway'}</h3>
                    <p className="text-xs text-[#64748B]">{t('admin.account.type_openwa_desc') || 'Self-hosted gateway'}</p>
                  </div>
                  {isOpenWA && <CheckCircle size={18} weight="fill" className="text-[#0F172A]" />}
                </div>
              </button>
            </div>
            <button data-testid="wizard-select-type" onClick={() => setStep(1)}
              className="w-full px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] flex items-center justify-center gap-2 transition-all">
              {t('wizard.next')} <ArrowRight size={16} weight="bold" />
            </button>
          </div>
        )}

        {/* ═══════════ META Step 1: Phone ID + WABA ID ═══════════ */}
        {step === 1 && !isOpenWA && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('wizard.phone_title')}</h2>
              <p className="text-sm text-[#64748B]">{t('wizard.phone_desc')}</p>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-blue-800">{t('wizard.where_to_find')}</p>
                <a href="https://business.facebook.com/wa/manage/phone-numbers/" target="_blank" rel="noreferrer"
                  className="text-[10px] font-medium text-blue-700 hover:text-blue-900 flex items-center gap-0.5 hover:underline">
                  Meta Business <ArrowSquareOut size={10} weight="bold" />
                </a>
              </div>
              <ol className="text-xs text-blue-700 space-y-1.5 list-decimal list-inside">
                <li>{t('wizard.phone_step1')}</li>
                <li>{t('wizard.phone_step2')}</li>
                <li>{t('wizard.phone_step3')}</li>
              </ol>
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                <Phone size={12} weight="bold" className="inline mr-1" /> {t('wizard.phone_label')}
              </label>
              <input data-testid="wizard-phone-id" type="text" value={phoneId}
                onChange={e => setPhoneId(e.target.value)}
                placeholder="123456789012345"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                <Buildings size={12} weight="bold" className="inline mr-1" /> {t('wizard.waba_label')}
              </label>
              <input data-testid="wizard-waba-id" type="text" value={wabaId}
                onChange={e => setWabaId(e.target.value)}
                placeholder="123456789012345"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
              <p className="text-[10px] text-[#94A3B8] mt-1">{t('wizard.waba_hint')}</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(0)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                {t('wizard.back') || 'Back'}
              </button>
              <button data-testid="wizard-save-phone" onClick={saveMetaFields}
                disabled={saving || !phoneId.trim() || !wabaId.trim()}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
                {saving ? t('general.loading') : t('wizard.next')}
              </button>
            </div>
          </div>
        )}

        {/* ═══════════ OPENWA Step 1: Server URL + API Key ═══════════ */}
        {step === 1 && isOpenWA && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
                {t('wizard.openwa_url_title') || 'Step 1: OpenWA Server'}
              </h2>
              <p className="text-sm text-[#64748B]">
                {t('wizard.openwa_url_desc') || 'Enter your OpenWA server URL and API key'}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                <Globe size={12} weight="bold" className="inline mr-1" /> {t('admin.account.openwa_url') || 'OpenWA Server URL'}
              </label>
              <input data-testid="wizard-openwa-url" type="text" value={openwaUrl}
                onChange={e => setOpenwaUrl(e.target.value)}
                placeholder="http://192.168.1.100:2785"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                <Key size={12} weight="bold" className="inline mr-1" /> {t('admin.account.openwa_api_key') || 'OpenWA API Key'}
              </label>
              <textarea data-testid="wizard-openwa-key" rows={3} value={openwaKey}
                onChange={e => setOpenwaKey(e.target.value)}
                placeholder="owa_..."
                className="w-full px-4 py-3 text-xs border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono resize-none" />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(0)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                {t('wizard.back') || 'Back'}
              </button>
              <button data-testid="wizard-save-openwa-fields" onClick={saveOpenWAFields}
                disabled={saving || !openwaUrl.trim() || !openwaKey.trim()}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
                {saving ? t('general.loading') : t('wizard.next')}
              </button>
            </div>
          </div>
        )}

        {/* ═══════════ META Step 2: Certificate ═══════════ */}
        {step === 2 && !isOpenWA && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('wizard.cert_title')}</h2>
              <p className="text-sm text-[#64748B]">{t('wizard.cert_desc')}</p>
            </div>
            <div className="rounded-lg border border-amber-100 bg-amber-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-amber-800">{t('wizard.where_to_find')}</p>
                <a href="https://business.facebook.com/settings/system-users" target="_blank" rel="noreferrer"
                  className="text-[10px] font-medium text-amber-800 hover:text-amber-900 flex items-center gap-0.5 hover:underline">
                  System Users <ArrowSquareOut size={10} weight="bold" />
                </a>
              </div>
              <ol className="text-xs text-amber-700 space-y-1.5 list-decimal list-inside">
                <li>{t('wizard.cert_step1')}</li>
                <li>{t('wizard.cert_step2')}</li>
                <li>{t('wizard.cert_step3')}</li>
              </ol>
              <p className="text-[11px] text-amber-700 font-semibold pt-1 border-t border-amber-200/60">
                ⚡ {t('wizard.cert_tip_permanent')}
              </p>
            </div>
            {hasCert && (
              <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                <CheckCircle size={16} className="text-emerald-600" weight="bold" />
                <span className="text-xs text-emerald-700 font-medium">{t('wizard.cert_already')}</span>
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                {hasCert ? t('wizard.cert_replace') : t('wizard.cert_label')}
              </label>
              <textarea data-testid="wizard-cert" rows={4} value={metaCert}
                onChange={e => setMetaCert(e.target.value)}
                placeholder={t('wizard.cert_placeholder')}
                className="w-full px-4 py-3 text-xs border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono resize-none" />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(1)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                {t('wizard.back') || 'Back'}
              </button>
              {hasCert && (
                <button data-testid="wizard-skip-cert" onClick={() => setStep(3)}
                  className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                  {t('wizard.skip')}
                </button>
              )}
              <button data-testid="wizard-save-cert" onClick={saveMetaCert}
                disabled={saving || !metaCert.trim()}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
                {saving ? t('general.loading') : t('wizard.next')}
              </button>
            </div>
          </div>
        )}

        {/* ═══════════ OPENWA Step 2: Session ID ═══════════ */}
        {step === 2 && isOpenWA && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
                {t('wizard.openwa_session_title') || 'Step 2: OpenWA Session'}
              </h2>
              <p className="text-sm text-[#64748B]">
                {t('wizard.openwa_session_desc') || 'Enter the Session ID from your OpenWA server'}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block">
                <DeviceMobile size={12} weight="bold" className="inline mr-1" /> {t('admin.account.openwa_session') || 'Session ID'}
              </label>
              <input data-testid="wizard-openwa-session" type="text" value={openwaSessionId}
                onChange={e => setOpenwaSessionId(e.target.value)}
                placeholder="sess_abc123"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono" />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(1)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                {t('wizard.back') || 'Back'}
              </button>
              {hasOpenWASession && (
                <button data-testid="wizard-skip-openwa-session" onClick={() => setStep(3)}
                  className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                  {t('wizard.skip')}
                </button>
              )}
              <button data-testid="wizard-save-openwa-session" onClick={saveOpenWASession}
                disabled={saving || !openwaSessionId.trim()}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
                {saving ? t('general.loading') : t('wizard.next')}
              </button>
            </div>
          </div>
        )}

        {/* ═══════════ Step 3: Validate (both types) ═══════════ */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>
                {isOpenWA ? (t('wizard.openwa_validate_title') || 'Verify OpenWA connection') : t('wizard.validate_title')}
              </h2>
              <p className="text-sm text-[#64748B]">
                {isOpenWA ? (t('wizard.openwa_session_desc') || '') : t('wizard.validate_desc')}
              </p>
            </div>

            {/* Config summary */}
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-4 space-y-2">
              {!isOpenWA ? (
                <>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">Phone Number ID</span>
                    <span className="font-mono font-medium text-[#0F172A]">{phoneId || account?.phone_number_id || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">WABA ID</span>
                    <span className="font-mono font-medium text-[#0F172A]">{wabaId || account?.whatsapp_business_account_id || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">{t('wizard.step_cert')}</span>
                    {hasCert || metaCert ? (
                      <span className="flex items-center gap-1 text-emerald-600 font-medium">
                        <CheckCircle size={12} weight="bold" /> {t('wizard.configured')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-500 font-medium">
                        <XCircle size={12} weight="bold" /> {t('wizard.not_configured')}
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">{t('admin.account.openwa_server') || 'Server'}</span>
                    <span className="font-mono font-medium text-[#0F172A]">{openwaUrl || account?.openwa_server_url || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">{t('admin.account.openwa_session_label') || 'Session'}</span>
                    <span className="font-mono font-medium text-[#0F172A]">{openwaSessionId || account?.openwa_session_id || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B]">{t('admin.account.openwa_api_key') || 'API Key'}</span>
                    {hasOpenWAKey || openwaKey ? (
                      <span className="flex items-center gap-1 text-emerald-600 font-medium">
                        <CheckCircle size={12} weight="bold" /> {t('wizard.configured')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-500 font-medium">
                        <XCircle size={12} weight="bold" /> {t('wizard.not_configured')}
                      </span>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Validation result */}
            {validationResult && (
              <div className={`rounded-lg border p-4 ${
                validationResult.ok
                  ? 'border-emerald-200 bg-emerald-50'
                  : 'border-red-200 bg-red-50'
              }`}>
                {validationResult.ok ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle size={20} className="text-emerald-600" weight="bold" />
                      <span className="text-sm font-bold text-emerald-800">{t('wizard.success')}</span>
                    </div>
                    {validationResult.data && !isOpenWA && (
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {validationResult.data.verified_name && (
                          <div className="text-xs"><span className="text-emerald-600">{t('wizard.verified_name')}</span><p className="font-semibold text-emerald-800">{validationResult.data.verified_name}</p></div>
                        )}
                        {validationResult.data.display_phone_number && (
                          <div className="text-xs"><span className="text-emerald-600">{t('wizard.phone_number')}</span><p className="font-semibold text-emerald-800">{validationResult.data.display_phone_number}</p></div>
                        )}
                      </div>
                    )}
                    {validationResult.data?.status && isOpenWA && (
                      <div className="text-xs"><span className="text-emerald-600">Session Status</span><p className="font-semibold text-emerald-800">{validationResult.data.status}</p></div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <XCircle size={20} className="text-red-600" weight="bold" />
                      <span className="text-sm font-bold text-red-800">{t('wizard.error')}</span>
                    </div>
                    <p className="text-xs text-red-700">{validationResult.error}</p>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <button onClick={() => setStep(isOpenWA ? 2 : 1)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC]">
                {t('wizard.edit_config')}
              </button>
              <button data-testid="wizard-validate" onClick={validateConnection}
                disabled={validating}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2">
                {validating ? <CircleNotch size={16} className="animate-spin" /> : <PlugsConnected size={16} weight="bold" />}
                {validating ? t('general.loading') : t('wizard.validate_btn')}
              </button>
            </div>

            {validationResult?.ok && (
              <button data-testid="wizard-finish" onClick={onComplete}
                className="w-full px-4 py-3 text-sm font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center justify-center gap-2 shadow-md">
                <Rocket size={16} weight="bold" />
                {t('wizard.finish')}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
