import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';
import { toast } from 'sonner';
import { CheckCircle, XCircle, Copy } from '@phosphor-icons/react';
import StatusBadge from './StatusBadge';

export default function WebhookSection({ t }) {
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState('');

  const load = async () => {
    try {
      const res = await adminApi.getWebhookInfo();
      setInfo(res.data);
    } catch { /* tables may not exist */ }
  };
  useEffect(() => { load(); }, []);

  const copy = (val, key) => {
    navigator.clipboard.writeText(val);
    setCopied(key);
    toast.success(t('admin.webhook.copied'));
    setTimeout(() => setCopied(''), 2000);
  };

  const handleVerify = async () => {
    try {
      await adminApi.verifyWebhook();
      toast.success(t('admin.status.verified'));
      load();
    } catch { toast.error('Error'); }
  };

  if (!info) return <div className="p-6 text-sm text-[#94A3B8]">{t('general.loading')}</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('admin.webhook.title')}</h2>

      <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg space-y-3">
        <p className="text-xs text-[#64748B]">{t('admin.webhook.instructions')}</p>

        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">{t('admin.webhook.url')}</label>
          <div className="flex items-center gap-2">
            <code data-testid="webhook-url" className="flex-1 px-3 py-2 bg-white border border-[#E2E8F0] rounded-md text-xs font-mono text-[#0F172A] truncate">
              {info.webhook_url}
            </code>
            <button data-testid="copy-webhook-url" onClick={() => copy(info.webhook_url, 'url')}
              className={`px-3 py-2 text-xs border rounded-md flex items-center gap-1 ${copied === 'url' ? 'border-green-300 text-green-600 bg-green-50' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9]'}`}>
              <Copy size={14} /> {t('admin.webhook.copy_url')}
            </button>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-[#475569] mb-1 block">{t('admin.webhook.verify_token')}</label>
          <div className="flex items-center gap-2">
            <code data-testid="webhook-verify-token" className="flex-1 px-3 py-2 bg-white border border-[#E2E8F0] rounded-md text-xs font-mono text-[#0F172A]">
              {info.verify_token}
            </code>
            <button data-testid="copy-verify-token" onClick={() => copy(info.verify_token, 'token')}
              className={`px-3 py-2 text-xs border rounded-md flex items-center gap-1 ${copied === 'token' ? 'border-green-300 text-green-600 bg-green-50' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9]'}`}>
              <Copy size={14} /> {t('admin.webhook.copy_token')}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-[#475569]">{t('admin.webhook.status')}:</span>
          <StatusBadge status={info.webhook_status} t={t} />
          <button data-testid="verify-webhook" onClick={handleVerify}
            className="px-3 py-1.5 text-xs border border-green-600 text-green-700 rounded-md hover:bg-green-50 flex items-center gap-1">
            <CheckCircle size={14} weight="bold" /> {t('admin.webhook.verify_now')}
          </button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-[#0F172A] mb-2">{t('admin.webhook.last_events')}</h3>
        {info.last_events?.length > 0 ? (
          <div className="border border-[#E2E8F0] rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-[#475569]">Event</th>
                  <th className="px-3 py-2 text-left font-medium text-[#475569]">Status</th>
                  <th className="px-3 py-2 text-left font-medium text-[#475569]">Error</th>
                  <th className="px-3 py-2 text-left font-medium text-[#475569]">{t('admin.logs.date')}</th>
                </tr>
              </thead>
              <tbody>
                {info.last_events.map(ev => (
                  <tr key={ev.id} className="border-b border-[#F1F5F9] last:border-0">
                    <td className="px-3 py-2 font-mono">{ev.event_type}</td>
                    <td className="px-3 py-2">
                      {ev.delivery_status === 'received' ? <CheckCircle size={14} className="text-green-500" /> : <XCircle size={14} className="text-red-500" />}
                    </td>
                    <td className="px-3 py-2 text-red-500 truncate max-w-[200px]">{ev.error_message || '—'}</td>
                    <td className="px-3 py-2 text-[#94A3B8]">{new Date(ev.received_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[#94A3B8] py-4 text-center">{t('admin.webhook.no_events')}</p>
        )}
      </div>
    </div>
  );
}
