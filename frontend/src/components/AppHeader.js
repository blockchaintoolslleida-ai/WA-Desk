import { useTranslation } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { ChatCircleDots, ChartBar, Users, SignOut, Globe, GearSix } from '@phosphor-icons/react';

const LANGS = [
  { code: 'ca', label: 'CA' },
  { code: 'es', label: 'ES' },
  { code: 'en', label: 'EN' },
];

export default function AppHeader({ currentPage, onNavigate }) {
  const { user, logout, isAdmin } = useAuth();
  const { t, language, setLanguage } = useTranslation();

  return (
    <header className="h-12 min-h-[48px] bg-[#0F172A] flex items-center justify-between px-4" data-testid="app-header">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => onNavigate('inbox')}>
          <ChatCircleDots size={20} weight="bold" className="text-white" />
          <span className="text-white text-sm font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>WA Desk</span>
        </div>
        <nav className="flex items-center gap-1">
          <button data-testid="nav-inbox" onClick={() => onNavigate('inbox')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${currentPage === 'inbox' ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}>
            {t('nav.inbox')}
          </button>
          <button data-testid="nav-dashboard" onClick={() => onNavigate('dashboard')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1 ${currentPage === 'dashboard' ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}>
            <ChartBar size={14} /> {t('nav.dashboard')}
          </button>
          {isAdmin && (
            <button data-testid="nav-agents" onClick={() => onNavigate('agents')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1 ${currentPage === 'agents' ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}>
              <Users size={14} /> {t('nav.agents')}
            </button>
          )}
          {isAdmin && (
            <button data-testid="nav-admin" onClick={() => onNavigate('admin')} className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1 ${currentPage === 'admin' ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}>
              <GearSix size={14} /> {t('nav.admin')}
            </button>
          )}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-0.5 bg-white/10 rounded-md p-0.5">
          {LANGS.map(l => (
            <button key={l.code} data-testid={`lang-${l.code}`} onClick={() => setLanguage(l.code)} className={`px-1.5 py-0.5 text-[10px] font-bold rounded transition-colors ${language === l.code ? 'bg-white text-[#0F172A]' : 'text-slate-400 hover:text-white'}`}>
              {l.label}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-400">{user?.full_name}</span>
        <button data-testid="logout-button" onClick={logout} className="text-slate-400 hover:text-white transition-colors" title={t('nav.logout')}>
          <SignOut size={18} />
        </button>
      </div>
    </header>
  );
}
