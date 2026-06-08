import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { CheckCircle, XCircle, PlugsConnected, Shield, Rocket, Phone, CircleNotch, ArrowRight, Check, Buildings, ArrowSquareOut } from '@phosphor-icons/react';

export default function SetupWizard({ t, account, secrets, onComplete }) {
  const [step, setStep] = useState(0);
  const [phoneId, setPhoneId] = useState(account?.phone_number_id || '');
  const [wabaId, setWabaId] = useState(account?.whatsapp_business_account_id || '');
  const [cert, setCert] = useState('');
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  const hasCert = secrets?.has_access_token;
  const hasPhone = !!account?.phone_number_id;
  const hasWaba = !!account?.whatsapp_business_account_id;

  useEffect(() => {
    if (hasPhone && hasWaba && hasCert) setStep(2);
    else if (hasPhone && hasWaba) setStep(1);
    else setStep(0);
  }, [hasPhone, hasWaba, hasCert]);

  const steps = [
    { key: 'phone', icon: Phone, label: t('wizard.step_phone') },
    { key: 'cert', icon: Shield, label: t('wizard.step_cert') },
    { key: 'validate', icon: PlugsConnected, label: t('wizard.step_validate') },
  ];

  const savePhoneAndWaba = async () => {
    if (!phoneId.trim() || !wabaId.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateAccount({
        account_name: account?.account_name || 'WhatsApp Business',
        phone_number_id: phoneId.trim(),
        whatsapp_business_account_id: wabaId.trim(),
      });
      toast.success(t('wizard.phone_saved'));
      setStep(1);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

  const saveCertificate = async () => {
    if (!cert.trim()) return;
    setSaving(true);
    try {
      await adminApi.updateSecrets({ access_token: cert.trim() });
      toast.success(t('wizard.cert_saved'));
      setCert('');
      setStep(2);
    } catch { toast.error('Error'); }
    setSaving(false);
  };

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

  return (
    <div className="max-w-xl mx-auto py-10 px-4">
      <div className="text-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#0F172A] to-[#334155] flex items-center justify-center mx-auto mb-4 shadow-lg">
          <Rocket size={28} weight="duotone" className="text-white" />
        </div>
        <h1 className="text-xl font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('wizard.title')}</h1>
        <p className="text-sm text-[#64748B]">{t('wizard.subtitle')}</p>
      </div>

      <div className="flex items-center justify-center gap-0 mb-10">
        {steps.map((s, i) => {
          const done = i < step || (i === 2 && validationResult?.ok);
          const active = i === step;
          return (
            <div key={s.key} className="flex items-center">
              <button onClick={() => { if (i <= step) setStep(i); }}
                data-testid={`wizard-step-${s.key}`}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold transition-all ${
                  done ? 'bg-emerald-100 text-emerald-700' :
                  active ? 'bg-[#0F172A] text-white shadow-md' :
                  'bg-[#F1F5F9] text-[#94A3B8]'
                }`}>
                {done ? <Check size={14} weight="bold" /> : <s.icon size={14} weight={active ? 'bold' : 'regular'} />}
                <span className="hidden sm:inline">{s.label}</span>
                <span className="sm:hidden">{i + 1}</span>
              </button>
              {i < steps.length - 1 && (
                <div className={`w-8 h-0.5 mx-1 rounded ${i < step ? 'bg-emerald-300' : 'bg-[#E2E8F0]'}`} />
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm">
        {step === 0 && (
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
              <label className="text-xs font-medium text-[#475569] mb-1.5 block flex items-center gap-1">
                <Phone size={12} weight="bold" /> {t('wizard.phone_label')}
              </label>
              <input data-testid="wizard-phone-id" type="text" value={phoneId}
                onChange={e => setPhoneId(e.target.value)}
                placeholder="123456789012345"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono tracking-wide" />
            </div>
            <div>
              <label className="text-xs font-medium text-[#475569] mb-1.5 block flex items-center gap-1">
                <Buildings size={12} weight="bold" /> {t('wizard.waba_label')}
              </label>
              <input data-testid="wizard-waba-id" type="text" value={wabaId}
                onChange={e => setWabaId(e.target.value)}
                placeholder="123456789012345"
                className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono tracking-wide" />
              <p className="text-[10px] text-[#94A3B8] mt-1">{t('wizard.waba_hint')}</p>
            </div>
            <button data-testid="wizard-save-phone" onClick={savePhoneAndWaba}
              disabled={saving || !phoneId.trim() || !wabaId.trim()}
              className="w-full px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2 transition-all">
              {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
              {saving ? t('general.loading') : t('wizard.next')}
            </button>
          </div>
        )}

        {step === 1 && (
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
              <textarea data-testid="wizard-cert" rows={4} value={cert}
                onChange={e => setCert(e.target.value)}
                placeholder={t('wizard.cert_placeholder')}
                className="w-full px-4 py-3 text-xs border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F172A] font-mono resize-none" />
            </div>
            <div className="flex gap-2">
              {hasCert && (
                <button data-testid="wizard-skip-cert" onClick={() => setStep(2)}
                  className="flex-1 px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC] transition-all">
                  {t('wizard.skip')}
                </button>
              )}
              <button data-testid="wizard-save-cert" onClick={saveCertificate}
                disabled={saving || !cert.trim()}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2 transition-all">
                {saving ? <CircleNotch size={16} className="animate-spin" /> : <ArrowRight size={16} weight="bold" />}
                {saving ? t('general.loading') : t('wizard.next')}
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-bold text-[#0F172A] mb-1" style={{ fontFamily: 'Manrope' }}>{t('wizard.validate_title')}</h2>
              <p className="text-sm text-[#64748B]">{t('wizard.validate_desc')}</p>
            </div>

            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">Phone Number ID</span>
                <span className="font-mono font-medium text-[#0F172A]">{account?.phone_number_id || phoneId || '—'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">WABA ID</span>
                <span className="font-mono font-medium text-[#0F172A]">{account?.whatsapp_business_account_id || wabaId || '—'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#64748B]">{t('wizard.step_cert')}</span>
                {hasCert || cert ? (
                  <span className="flex items-center gap-1 text-emerald-600 font-medium">
                    <CheckCircle size={12} weight="bold" /> {t('wizard.configured')}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-red-500 font-medium">
                    <XCircle size={12} weight="bold" /> {t('wizard.not_configured')}
                  </span>
                )}
              </div>
            </div>

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
                    {validationResult.data && (
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {validationResult.data.verified_name && (
                          <div className="text-xs">
                            <span className="text-emerald-600">{t('wizard.verified_name')}</span>
                            <p className="font-semibold text-emerald-800">{validationResult.data.verified_name}</p>
                          </div>
                        )}
                        {validationResult.data.display_phone_number && (
                          <div className="text-xs">
                            <span className="text-emerald-600">{t('wizard.phone_number')}</span>
                            <p className="font-semibold text-emerald-800">{validationResult.data.display_phone_number}</p>
                          </div>
                        )}
                        {validationResult.data.quality_rating && (
                          <div className="text-xs">
                            <span className="text-emerald-600">{t('wizard.quality')}</span>
                            <p className="font-semibold text-emerald-800">{validationResult.data.quality_rating}</p>
                          </div>
                        )}
                      </div>
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
              <button onClick={() => setStep(0)}
                className="px-4 py-3 text-sm font-medium border border-[#E2E8F0] text-[#475569] rounded-lg hover:bg-[#F8FAFC] transition-all">
                {t('wizard.edit_config')}
              </button>
              <button data-testid="wizard-validate" onClick={validateConnection}
                disabled={validating}
                className="flex-1 px-4 py-3 text-sm font-semibold bg-[#0F172A] text-white rounded-lg hover:bg-[#1E293B] disabled:opacity-40 flex items-center justify-center gap-2 transition-all">
                {validating ? <CircleNotch size={16} className="animate-spin" /> : <PlugsConnected size={16} weight="bold" />}
                {validating ? t('general.loading') : t('wizard.validate_btn')}
              </button>
            </div>

            {validationResult?.ok && (
              <button data-testid="wizard-finish" onClick={onComplete}
                className="w-full px-4 py-3 text-sm font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center justify-center gap-2 transition-all shadow-md">
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
