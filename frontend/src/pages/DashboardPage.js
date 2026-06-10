import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../lib/api';
import { useTranslation } from '../contexts/LanguageContext';
import AppHeader from '../components/AppHeader';
import { ChatCircle, Clock, UserCircle, Check, Warning, HourglassHigh, UserMinus, WarningCircle, Stack } from '@phosphor-icons/react';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try { const res = await dashboardApi.getMetrics(); setMetrics(res.data); } catch {} finally { setLoading(false); }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const kpiCards = metrics ? [
    { label: t('dash.new_today'), value: metrics.new_today, icon: ChatCircle, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: t('dash.pending'), value: metrics.per_atendre, icon: Warning, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: t('dash.in_progress'), value: metrics.en_atencio, icon: UserCircle, color: 'text-green-600', bg: 'bg-green-50' },
    { label: t('dash.waiting'), value: metrics.esperant_client, icon: HourglassHigh, color: 'text-orange-600', bg: 'bg-orange-50' },
    { label: t('dash.closed_today'), value: metrics.closed_today, icon: Check, color: 'text-slate-600', bg: 'bg-slate-50' },
    { label: t('dash.unassigned'), value: metrics.unassigned, icon: UserMinus, color: 'text-red-600', bg: 'bg-red-50' },
    { label: t('dash.unclassified_msgs'), value: metrics.unclassified_msgs, icon: WarningCircle, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: t('dash.multi_case_convs'), value: metrics.multi_case_convs, icon: Stack, color: 'text-purple-600', bg: 'bg-purple-50' },
  ] : [];

  return (
    <div className="h-screen flex flex-col bg-[#F8FAFC]">
      <AppHeader currentPage="dashboard" onNavigate={(p) => navigate(p === 'dashboard' ? '/dashboard' : p === 'contacts' ? '/contacts' : p === 'calendar' ? '/calendar' : p === 'agents' ? '/agents' : p === 'admin' ? '/admin' : '/')} />
      <div className="flex-1 overflow-y-auto p-6">
        <h1 data-testid="dashboard-title" className="text-2xl font-bold tracking-tight mb-6" style={{ fontFamily: 'Manrope' }}>{t('dash.title')}</h1>
        {loading ? <p className="text-sm text-[#64748B]">{t('dash.loading')}</p> : metrics ? (
          <div className="space-y-6">
            <div className="grid grid-cols-4 gap-4">
              {kpiCards.map(k => (
                <div key={k.label} className="bg-white border border-[#E2E8F0] rounded-md p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-8 h-8 rounded-md ${k.bg} flex items-center justify-center`}><k.icon size={18} className={k.color} weight="bold" /></div>
                    <span className="text-xs font-medium text-[#64748B] uppercase tracking-wide">{k.label}</span>
                  </div>
                  <p className="text-2xl font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{k.value}</p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white border border-[#E2E8F0] rounded-md p-4">
                <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: 'Manrope' }}>{t('dash.cases_by_agent')}</h3>
                {metrics.cases_by_agent.length === 0 ? <p className="text-sm text-[#64748B]">{t('dash.no_data')}</p> : metrics.cases_by_agent.map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-sm py-1"><span className="text-[#475569]">{a.agent_name}</span><span className="font-semibold">{a.count}</span></div>
                ))}
              </div>
              <div className="bg-white border border-[#E2E8F0] rounded-md p-4">
                <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: 'Manrope' }}>{t('dash.resolved_by_agent')}</h3>
                {metrics.resolved_by_agent.length === 0 ? <p className="text-sm text-[#64748B]">{t('dash.no_data')}</p> : metrics.resolved_by_agent.map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-sm py-1"><span className="text-[#475569]">{a.agent_name}</span><span className="font-semibold">{a.count}</span></div>
                ))}
              </div>
            </div>
            <div className="bg-white border border-[#E2E8F0] rounded-md p-4">
              <h3 className="text-sm font-semibold mb-2" style={{ fontFamily: 'Manrope' }}>{t('dash.summary')}</h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div><span className="text-[#64748B]">{t('dash.total_active')}</span><p className="text-lg font-bold">{metrics.total_active}</p></div>
                <div><span className="text-[#64748B]">{t('dash.total_cases')}</span><p className="text-lg font-bold">{metrics.total_cases}</p></div>
              </div>
            </div>
          </div>
        ) : <p className="text-sm text-red-500">{t('dash.error')}</p>}
      </div>
    </div>
  );
}
