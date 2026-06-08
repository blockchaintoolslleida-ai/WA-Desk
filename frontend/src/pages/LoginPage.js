import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from '../contexts/LanguageContext';
import { ChatCircleDots } from '@phosphor-icons/react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) navigate('/');
    else setError(result.error);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-[#0F172A] rounded-md mb-4">
            <ChatCircleDots size={24} weight="bold" className="text-white" />
          </div>
          <h1 data-testid="login-title" className="text-2xl font-bold tracking-tight text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('login.title')}</h1>
          <p className="text-sm text-[#64748B] mt-1">{t('login.subtitle')}</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white border border-[#E2E8F0] rounded-md p-6 space-y-4">
          {error && <div data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}
          <div>
            <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1.5">{t('login.email_label')}</label>
            <input data-testid="login-email-input" type="text" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" placeholder="admin@example.com" required />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#475569] uppercase tracking-wide mb-1.5">{t('login.password_label')}</label>
            <input data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" placeholder="••••••••" required />
          </div>
          <button data-testid="login-submit-button" type="submit" disabled={loading} className="w-full py-2.5 bg-[#0F172A] text-white text-sm font-semibold rounded-md hover:bg-[#1E293B] disabled:opacity-50">
            {loading ? t('login.loading') : t('login.submit')}
          </button>
        </form>
        <p className="text-center text-xs text-[#64748B] mt-4">WhatsApp Business Desk v2.0</p>
      </div>
    </div>
  );
}
