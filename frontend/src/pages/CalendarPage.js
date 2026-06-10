import { useState, useEffect } from 'react';
import { Calendar, Plugs, PlugsConnected, Trash, PaperPlaneRight, Clock, Bell, CheckCircle, XCircle, ArrowCounterClockwise } from '@phosphor-icons/react';
import AppHeader from '../components/AppHeader';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { calendarApi } from '../services/calendarApi';
import { toast } from 'sonner';

const LEAD_TIME_OPTIONS = [
  { value: 1, label: '1 hora' },
  { value: 2, label: '2 hores' },
  { value: 6, label: '6 hores' },
  { value: 12, label: '12 hores' },
  { value: 24, label: '24 hores' },
  { value: 48, label: '48 hores' },
  { value: 72, label: '72 hores' },
];

export default function CalendarPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [email, setEmail] = useState('');

  // Settings
  const [isActive, setIsActive] = useState(true);
  const [leadTime, setLeadTime] = useState(24);
  const [template, setTemplate] = useState('');
  const [saving, setSaving] = useState(false);

  // Test
  const [testPhone, setTestPhone] = useState('');
  const [testTitle, setTestTitle] = useState('Cita de prova');
  const [testDate, setTestDate] = useState('');
  const [testTime, setTestTime] = useState('10:00');
  const [sending, setSending] = useState(false);

  // Logs
  const [logs, setLogs] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [logsLoading, setLogsLoading] = useState(false);

  // ── Load status and settings ─────────────────────────────────
  const loadData = async () => {
    try {
      setLoading(true);
      const [statusRes, settingsRes] = await Promise.allSettled([
        calendarApi.getStatus(),
        calendarApi.getSettings(),
      ]);

      if (statusRes.status === 'fulfilled') {
        setConnected(statusRes.value.data.connected);
        setEmail(statusRes.value.data.email || '');
      }
      if (settingsRes.status === 'fulfilled') {
        const s = settingsRes.value.data;
        setIsActive(!!s.is_active);
        setLeadTime(s.lead_time_hours || 24);
        setTemplate(s.template_text || '');
      }
    } catch (e) {
      console.error('Error loading calendar data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // ── Handle OAuth callback (code + state in URL) ─────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const error = params.get('error');
    const connected = params.get('connected');

    if (error) {
      toast.error('Error OAuth: ' + error);
      window.history.replaceState({}, '', '/calendar');
      return;
    }

    if (connected) {
      toast.success('Google Calendar connectat!');
      window.history.replaceState({}, '', '/calendar');
      loadData();
      return;
    }

    if (code && state) {
      // Exchange code for tokens
      const exchange = async () => {
        try {
          await calendarApi.exchangeCode({ code, state });
          toast.success('Google Calendar connectat correctament!');
          window.history.replaceState({}, '', '/calendar');
          loadData();
        } catch (e) {
          toast.error(e.response?.data?.detail || 'Error intercanviant el codi');
          window.history.replaceState({}, '', '/calendar');
        }
      };
      exchange();
    }
  }, []);

  // ── Load logs ────────────────────────────────────────────────
  const loadLogs = async () => {
    setLogsLoading(true);
    try {
      const params = filterStatus ? { status: filterStatus } : {};
      const res = await calendarApi.getLogs(params);
      setLogs(res.data || []);
    } catch (e) {
      console.error('Error loading logs:', e);
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => { if (connected) loadLogs(); }, [connected, filterStatus]);

  // ── Connect ──────────────────────────────────────────────────
  const handleConnect = async () => {
    try {
      const res = await calendarApi.getAuthUrl();
      const url = res.data?.url;
      if (url) {
        window.open(url, 'google-oauth', 'width=600,height=700');
        toast.success('Finestra OAuth oberta. Torna aqui despres de connectar.');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error obtenint URL de connexió');
    }
  };

  // ── Disconnect ───────────────────────────────────────────────
  const handleDisconnect = async () => {
    if (!window.confirm('Segur que vols desconnectar Google Calendar?')) return;
    try {
      await calendarApi.disconnect();
      setConnected(false);
      setEmail('');
      toast.success('Google Calendar desconnectat');
    } catch (e) {
      toast.error('Error desconnectant');
    }
  };

  // ── Save settings ────────────────────────────────────────────
  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await calendarApi.updateSettings({
        is_active: isActive,
        lead_time_hours: leadTime,
        template_text: template,
      });
      toast.success('Configuració guardada');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error guardant');
    } finally {
      setSaving(false);
    }
  };

  // ── Test reminder ────────────────────────────────────────────
  const handleTest = async () => {
    if (!testPhone.trim()) {
      toast.error('Introdueix un numero de telefon');
      return;
    }
    setSending(true);
    try {
      const res = await calendarApi.testReminder({
        phone: testPhone.trim(),
        event_title: testTitle || 'Cita de prova',
        event_date: testDate || new Date().toLocaleDateString('ca-ES'),
        event_time: testTime || '10:00',
      });
      if (res.data?.sent) {
        toast.success('Missatge de prova enviat!');
      } else {
        toast.error(res.data?.error || 'Error enviant');
      }
    } catch (e) {
      toast.error('Error enviant missatge de prova');
    } finally {
      setSending(false);
    }
  };

  // ── Template preview ─────────────────────────────────────────
  const previewText = template
    .replace('{{client_name}}', 'Client Exemple')
    .replace('{{event_title}}', 'Cita de prova')
    .replace('{{event_date}}', '15/06/2026')
    .replace('{{event_time}}', '10:00');

  // ── Status badge ─────────────────────────────────────────────
  const statusBadge = (s) => {
    const map = {
      sent: 'bg-emerald-100 text-emerald-700 border-emerald-200',
      pending: 'bg-amber-100 text-amber-700 border-amber-200',
      failed: 'bg-red-100 text-red-700 border-red-200',
    };
    const labels = { sent: 'Enviat', pending: 'Pendent', failed: 'Error' };
    return (
      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${map[s] || 'bg-slate-100 text-slate-600'}`}>
        {labels[s] || s}
      </span>
    );
  };

  // ── Format date ──────────────────────────────────────────────
  const fmt = (iso) => {
    if (!iso) return '-';
    try {
      return new Date(iso).toLocaleString('ca-ES', { dateStyle: 'short', timeStyle: 'short' });
    } catch { return iso; }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F8FAFC]">
        <AppHeader currentPage="calendar" onNavigate={(p) => navigate(p === 'inbox' ? '/' : p === 'dashboard' ? '/dashboard' : p === 'contacts' ? '/contacts' : p === 'calendar' ? '/calendar' : p === 'agents' ? '/agents' : p === 'admin' ? '/admin' : '/')} />
        <div className="flex items-center justify-center h-64 text-slate-500">Carregant...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <AppHeader currentPage="calendar" onNavigate={(p) => navigate(
        p === 'inbox' ? '/' :
        p === 'dashboard' ? '/dashboard' :
        p === 'contacts' ? '/contacts' :
        p === 'agents' ? '/agents' :
        p === 'admin' ? '/admin' :
        '/calendar'
      )} />

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        <h1 className="text-2xl font-bold text-[#0F172A] flex items-center gap-2">
          <Calendar size={28} className="text-[#2563EB]" />
          Recordatoris Google Calendar
        </h1>

        {/* ── SECTION 1: Connection ─────────────────────────── */}
        <section className="bg-white rounded-xl border border-[#E2E8F0] p-6">
          <h2 className="text-sm font-semibold text-[#475569] uppercase tracking-wide mb-4">
            Connexio Google Calendar
          </h2>

          {connected ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                  <PlugsConnected size={20} className="text-emerald-600" weight="bold" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#0F172A]">Connectat</p>
                  <p className="text-xs text-slate-500">{email}</p>
                </div>
              </div>
              <button
                onClick={handleDisconnect}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash size={14} /> Desconnectar
              </button>
            </div>
          ) : (
            <button
              onClick={handleConnect}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] transition-colors"
            >
              <Plugs size={18} /> Connectar amb Google
            </button>
          )}
        </section>

        {/* ── SECTION 2: Settings ────────────────────────────── */}
        <section className="bg-white rounded-xl border border-[#E2E8F0] p-6">
          <h2 className="text-sm font-semibold text-[#475569] uppercase tracking-wide mb-4">
            Configuracio de recordatoris
          </h2>

          <div className="space-y-5">
            {/* Active toggle */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell size={18} className="text-[#64748B]" />
                <span className="text-sm text-[#0F172A] font-medium">Activar recordatoris</span>
              </div>
              <button
                onClick={() => setIsActive(!isActive)}
                className={`relative w-11 h-6 rounded-full transition-colors ${isActive ? 'bg-emerald-500' : 'bg-slate-300'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${isActive ? 'left-[22px]' : 'left-0.5'}`} />
              </button>
            </div>

            {/* Lead time */}
            <div>
              <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600 mb-1.5">
                <Clock size={14} /> Antelacio del recordatori
              </label>
              <select
                value={leadTime}
                onChange={(e) => setLeadTime(Number(e.target.value))}
                className="w-full sm:w-48 px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:ring-2 focus:ring-[#2563EB] focus:border-transparent outline-none"
              >
                {LEAD_TIME_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Template */}
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1.5 block">
                Plantilla del missatge
              </label>
              <textarea
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB] focus:border-transparent outline-none resize-y"
                placeholder="Hola {{client_name}}, recordatori: {{event_title}}..."
              />
              <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-[#E2E8F0]">
                <p className="text-[10px] font-medium text-slate-400 uppercase mb-1">Previsualitzacio</p>
                <p className="text-sm text-slate-700">{previewText}</p>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                Variables: {'{{'}client_name{'}}'}, {'{{'}event_title{'}}'}, {'{{'}event_date{'}}'}, {'{{'}event_time{'}}'}
              </p>
            </div>

            {/* Save */}
            <button
              onClick={handleSaveSettings}
              disabled={saving}
              className="px-4 py-2 bg-[#0F172A] text-white text-sm font-medium rounded-lg hover:bg-[#1E293B] transition-colors disabled:opacity-50"
            >
              {saving ? 'Guardant...' : 'Guardar configuracio'}
            </button>
          </div>
        </section>

        {/* ── SECTION 3: Test ────────────────────────────────── */}
        <section className="bg-white rounded-xl border border-[#E2E8F0] p-6">
          <h2 className="text-sm font-semibold text-[#475569] uppercase tracking-wide mb-4">
            Enviar missatge de prova
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Telefon</label>
              <input
                type="text"
                value={testPhone}
                onChange={(e) => setTestPhone(e.target.value)}
                placeholder="+34600000000"
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB] outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Titol</label>
              <input
                type="text"
                value={testTitle}
                onChange={(e) => setTestTitle(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB] outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Data</label>
              <input
                type="text"
                value={testDate}
                onChange={(e) => setTestDate(e.target.value)}
                placeholder="15/06/2026"
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB] outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Hora</label>
              <input
                type="text"
                value={testTime}
                onChange={(e) => setTestTime(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB] outline-none"
              />
            </div>
          </div>

          <button
            onClick={handleTest}
            disabled={sending || !testPhone.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            <PaperPlaneRight size={16} /> {sending ? 'Enviant...' : 'Enviar prova'}
          </button>
        </section>

        {/* ── SECTION 4: Logs ────────────────────────────────── */}
        {connected && (
          <section className="bg-white rounded-xl border border-[#E2E8F0] p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-[#475569] uppercase tracking-wide">
                Registre de recordatoris
              </h2>
              <div className="flex items-center gap-2">
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-2 py-1.5 text-xs border border-[#E2E8F0] rounded-lg bg-white"
                >
                  <option value="">Tots</option>
                  <option value="pending">Pendents</option>
                  <option value="sent">Enviats</option>
                  <option value="failed">Errors</option>
                </select>
                <button
                  onClick={loadLogs}
                  className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
                  title="Refrescar"
                >
                  <ArrowCounterClockwise size={16} />
                </button>
              </div>
            </div>

            {logsLoading ? (
              <p className="text-xs text-slate-400">Carregant...</p>
            ) : logs.length === 0 ? (
              <p className="text-xs text-slate-400">Cap recordatori encara</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#E2E8F0]">
                      <th className="text-left py-2 font-medium text-slate-500">Event</th>
                      <th className="text-left py-2 font-medium text-slate-500">Telefon</th>
                      <th className="text-left py-2 font-medium text-slate-500">Programat</th>
                      <th className="text-left py-2 font-medium text-slate-500">Enviat</th>
                      <th className="text-left py-2 font-medium text-slate-500">Estat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id} className="border-b border-[#F1F5F9]">
                        <td className="py-2 pr-2 text-slate-700 max-w-[180px] truncate">{log.event_title || '-'}</td>
                        <td className="py-2 pr-2 text-slate-500">{log.contact_phone || '-'}</td>
                        <td className="py-2 pr-2 text-slate-500">{fmt(log.scheduled_for)}</td>
                        <td className="py-2 pr-2 text-slate-500">{fmt(log.sent_at)}</td>
                        <td className="py-2">{statusBadge(log.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
