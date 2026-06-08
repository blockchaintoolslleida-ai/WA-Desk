import { useState, useEffect } from 'react';
import { setupApi } from '../lib/api';
import { useTranslation } from '../contexts/LanguageContext';
import { CheckCircle, XCircle, ArrowRight } from '@phosphor-icons/react';

export default function SetupPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState(null);

  useEffect(() => { checkTables(); }, []);

  const checkTables = async () => {
    try {
      const res = await setupApi.check();
      setStatus(res.data);
    } catch (err) {
      setStatus({ all_tables_ready: false, tables: {}, instruction: t('setup.backend_error') });
    }
  };

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await setupApi.seed();
      setSeedResult(res.data);
    } catch (err) {
      setSeedResult({ message: `Error: ${err.response?.data?.detail || err.message}`, seeded: false });
    }
    setSeeding(false);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white border border-[#E2E8F0] rounded-md p-6">
        <h1 className="text-xl font-bold mb-4" style={{ fontFamily: 'Manrope' }}>{t('setup.title')}</h1>

        {status && (
          <div className="space-y-3">
            <div className={`px-3 py-2 rounded-md text-sm font-medium ${status.all_tables_ready ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
              {status.all_tables_ready ? t('setup.all_ready') : t('setup.missing_tables')}
            </div>

            <div className="space-y-1">
              {Object.entries(status.tables || {}).map(([table, st]) => (
                <div key={table} className="flex items-center gap-2 text-sm">
                  {st === 'ok' ? <CheckCircle size={16} className="text-green-500" /> : <XCircle size={16} className="text-red-500" />}
                  <span className="font-mono text-xs">{table}</span>
                  <span className="text-[#64748B] text-xs">{st}</span>
                </div>
              ))}
            </div>

            {!status.all_tables_ready && (
              <div className="mt-4 p-3 bg-slate-50 rounded-md text-sm">
                <p className="font-semibold mb-1">{t('setup.instructions')}</p>
                <ol className="list-decimal list-inside space-y-1 text-[#475569]">
                  <li>{t('setup.step1')}</li>
                  <li>{t('setup.step2')}</li>
                  <li>{t('setup.step3')} <code className="bg-slate-200 px-1 rounded text-xs">supabase_wa_migration.sql</code></li>
                  <li>{t('setup.step4')}</li>
                </ol>
                <button onClick={checkTables} className="mt-3 px-4 py-1.5 bg-[#0F172A] text-white text-sm rounded-md hover:bg-[#1E293B] transition-colors">
                  {t('setup.check_again')}
                </button>
              </div>
            )}

            {status.all_tables_ready && (
              <div className="mt-4 space-y-3">
                <button
                  data-testid="seed-button"
                  onClick={handleSeed}
                  disabled={seeding}
                  className="px-4 py-2 bg-[#0F172A] text-white text-sm rounded-md hover:bg-[#1E293B] transition-colors disabled:opacity-50"
                >
                  {seeding ? t('setup.seeding') : t('setup.seed')}
                </button>

                {seedResult && (
                  <div className={`px-3 py-2 rounded-md text-sm ${seedResult.seeded ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}`}>
                    {seedResult.message}
                  </div>
                )}

                <a href="/" className="inline-flex items-center gap-1 text-sm font-medium text-[#2563EB] hover:underline">
                  {t('setup.go_panel')} <ArrowRight size={14} />
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
