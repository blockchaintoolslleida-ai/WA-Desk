import { useState, useEffect } from 'react';
import { adminApi } from '../../lib/api';

export default function AuditSection({ t, locale }) {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    adminApi.getAuditLogs().then(res => setLogs(res.data || [])).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('admin.logs.title')}</h2>
      {logs.length > 0 ? (
        <div className="border border-[#E2E8F0] rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-[#475569]">{t('admin.logs.action')}</th>
                <th className="px-3 py-2 text-left font-medium text-[#475569]">{t('admin.logs.entity')}</th>
                <th className="px-3 py-2 text-left font-medium text-[#475569]">{t('admin.logs.description')}</th>
                <th className="px-3 py-2 text-left font-medium text-[#475569]">{t('admin.logs.date')}</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} className="border-b border-[#F1F5F9] last:border-0">
                  <td className="px-3 py-2 font-mono font-medium">{log.action_type}</td>
                  <td className="px-3 py-2">{log.entity_type}</td>
                  <td className="px-3 py-2 text-[#475569] truncate max-w-[300px]">{log.description}</td>
                  <td className="px-3 py-2 text-[#94A3B8] whitespace-nowrap">{new Date(log.created_at).toLocaleString(locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-[#94A3B8] py-8 text-center">{t('admin.logs.no_logs')}</p>
      )}
    </div>
  );
}
