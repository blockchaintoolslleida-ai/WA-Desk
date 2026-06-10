import { useState, useEffect } from 'react';
import { automationApi, agentsApi } from '../../lib/api';
import { toast } from 'sonner';
import {
  Lightning, Chat, Clock, MagnifyingGlass, UserPlus,
  Warning, Plus, Pencil, Trash, X,
} from '@phosphor-icons/react';

const CATEGORIES = [
  { id: 'greeting', color: '#22C55E', bg: '#F0FDF4', border: '#BBF7D0',
    icon: Chat, key: 'cat_greeting', descKey: 'cat_greeting_desc', num: 1 },
  { id: 'schedule', color: '#F97316', bg: '#FFF7ED', border: '#FED7AA',
    icon: Clock, key: 'cat_schedule', descKey: 'cat_schedule_desc', num: 2 },
  { id: 'keywords', color: '#3B82F6', bg: '#EFF6FF', border: '#BFDBFE',
    icon: MagnifyingGlass, key: 'cat_keywords', descKey: 'cat_keywords_desc', num: 3 },
  { id: 'assignment', color: '#8B5CF6', bg: '#F5F3FF', border: '#DDD6FE',
    icon: UserPlus, key: 'cat_assignment', descKey: 'cat_assignment_desc', num: 4 },
  { id: 'fallback', color: '#EF4444', bg: '#FEF2F2', border: '#FECACA',
    icon: Warning, key: 'cat_fallback', descKey: 'cat_fallback_desc', num: 5 },
];

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_KEY_MAP = { mon: 'day_mon', tue: 'day_tue', wed: 'day_wed', thu: 'day_thu', fri: 'day_fri', sat: 'day_sat', sun: 'day_sun' };

export default function AutomationSection({ t, locale }) {
  const [tab, setTab] = useState('rules');

  return (
    <div className="space-y-6" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
            <Lightning size={18} weight="fill" className="inline mr-2 text-amber-500" />
            {t('admin.nav.automation') || 'Automatitzacions'}
          </h2>
        </div>
      </div>

      {/* Internal Tabs */}
      <div className="flex gap-0 border-b-2 border-[#E2E8F0]">
        {['rules', 'hours', 'assignment'].map(tabId => (
          <button key={tabId} onClick={() => setTab(tabId)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === tabId
                ? 'text-[#0F172A] border-b-2 border-[#0F172A] -mb-0.5'
                : 'text-[#94A3B8] hover:text-[#475569]'
            }`}>
            {t(`admin.automation.tab_${tabId}`)}
          </button>
        ))}
      </div>

      {tab === 'rules' && <RulesTab t={t} />}
      {tab === 'hours' && <BusinessHoursTab t={t} />}
      {tab === 'assignment' && <AssignmentTab t={t} />}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// RULES TAB
// ═══════════════════════════════════════════════════════════════

function RulesTab({ t }) {
  const [rules, setRules] = useState([]);
  const [editingRule, setEditingRule] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await automationApi.getRules();
      setRules(res.data.rules || []);
    } catch { /* tables may not exist yet */ }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleToggle = async (ruleId) => {
    try {
      const res = await automationApi.toggleRule(ruleId);
      setRules(prev => prev.map(r => r.id === ruleId ? { ...r, is_active: res.data.is_active } : r));
    } catch (e) { toast.error('Error toggling rule'); }
  };

  const handleDelete = async (ruleId) => {
    try {
      await automationApi.deleteRule(ruleId);
      setRules(prev => prev.filter(r => r.id !== ruleId));
      toast.success('Rule deleted');
    } catch (e) { toast.error('Error deleting rule'); }
  };

  const handleSave = async (data) => {
    try {
      if (data.id) {
        const res = await automationApi.updateRule(data.id, data);
        setRules(prev => prev.map(r => r.id === data.id ? res.data.rule : r));
      } else {
        const res = await automationApi.createRule(data);
        setRules(prev => [...prev, res.data.rule]);
      }
      setEditingRule(null);
      toast.success(data.id ? 'Rule updated' : 'Rule created');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error saving rule');
    }
  };

  if (loading) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  return (
    <div className="space-y-3">
      {CATEGORIES.map(cat => {
        const catRules = (rules || []).filter(r => r.category === cat.id).sort((a, b) => a.priority - b.priority);
        const isAssignment = cat.id === 'assignment';
        return (
          <div key={cat.id} className="border border-[#E2E8F0] rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5" style={{ background: cat.bg, borderBottom: `1px solid ${cat.border}` }}>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 flex items-center justify-center rounded-full text-white text-[10px] font-bold" style={{ background: cat.color }}>{cat.num}</span>
                <span className="text-xs font-bold" style={{ color: cat.color }}>{t(`admin.automation.${cat.key}`)}</span>
                <span className="text-[10px] text-[#64748B]">{t(`admin.automation.${cat.descKey}`)}</span>
              </div>
              {!isAssignment && !(cat.id === 'fallback' && catRules.length > 0) && (
                <button onClick={() => setEditingRule({ category: cat.id, is_active: true, priority: catRules.length + 1, trigger_config: {}, response_text: '', delay_seconds: 0, daily_limit: null })}
                  className="text-[11px] px-2.5 py-1 bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] flex items-center gap-1">
                  <Plus size={11} /> {t('admin.automation.add_rule')}
                </button>
              )}
              {isAssignment && (
                <span className="text-[10px] text-[#64748B]">⏻ {t('admin.automation.tab_assignment')}</span>
              )}
            </div>
            <div className="divide-y divide-[#F1F5F9]">
              {catRules.length === 0 && !isAssignment ? (
                <p className="px-4 py-3 text-[11px] text-[#94A3B8] italic">{t('admin.automation.no_rules')}</p>
              ) : (
                catRules.map(rule => (
                  <div key={rule.id} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                    <span className="w-5 text-center font-bold text-[#94A3B8]">{rule.priority}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-[#0F172A] truncate">{rule.name}</div>
                      <div className="text-[10px] text-[#64748B]">
                        {_describeTrigger(rule.category, rule.trigger_config, t)}
                        {rule.delay_seconds > 0 ? ` · Delay: ${rule.delay_seconds}s` : ''}
                        {rule.daily_limit ? ` · Limit: ${rule.daily_limit}/day` : ''}
                      </div>
                    </div>
                    {/* Toggle */}
                    <button onClick={() => handleToggle(rule.id)}
                      className={`relative w-7 h-4 rounded-full flex-shrink-0 transition-colors ${rule.is_active ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
                      <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-all ${rule.is_active ? 'right-0.5' : 'left-0.5'}`} />
                    </button>
                    <button onClick={() => setEditingRule({ ...rule })} className="text-[#94A3B8] hover:text-[#0F172A]"><Pencil size={12} /></button>
                    <button onClick={() => handleDelete(rule.id)} className="text-[#94A3B8] hover:text-red-500"><Trash size={12} /></button>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}

      {editingRule && (
        <RuleEditorModal rule={editingRule} t={t}
          onClose={() => setEditingRule(null)}
          onSave={handleSave} />
      )}
    </div>
  );
}


function _describeTrigger(category, triggerConfig, t) {
  if (category === 'greeting') return t('admin.automation.cat_greeting_desc');
  if (category === 'schedule') {
    const type = (triggerConfig && triggerConfig.type) || 'outside_hours';
    return type === 'outside_hours' ? t('admin.automation.trigger_outside_hours') : t('admin.automation.trigger_inside_hours');
  }
  if (category === 'keywords') {
    const kws = (triggerConfig && triggerConfig.keywords) || [];
    return kws.length ? kws.slice(0, 3).join(', ') + (kws.length > 3 ? '...' : '') : 'Sense paraules';
  }
  if (category === 'fallback') return t('admin.automation.cat_fallback_desc');
  return '';
}


// ═══════════════════════════════════════════════════════════════
// RULE EDITOR MODAL
// ═══════════════════════════════════════════════════════════════

function RuleEditorModal({ rule, t, onClose, onSave }) {
  const [form, setForm] = useState({
    id: rule.id || null,
    name: rule.name || '',
    is_active: rule.is_active !== undefined ? rule.is_active : true,
    priority: rule.priority || 1,
    category: rule.category,
    trigger_config: rule.trigger_config || {},
    response_text: rule.response_text || '',
    delay_seconds: rule.delay_seconds || 0,
    daily_limit: rule.daily_limit || null,
  });

  const handleKeywordAdd = () => {
    const input = document.getElementById('kw-input');
    const word = (input?.value || '').trim().toLowerCase();
    if (!word) return;
    const current = form.trigger_config?.keywords || [];
    if (current.includes(word)) return;
    setForm(f => ({ ...f, trigger_config: { ...f.trigger_config, keywords: [...current, word], match_mode: 'any' } }));
    if (input) input.value = '';
  };

  const handleKeywordRemove = (kw) => {
    const current = form.trigger_config?.keywords || [];
    setForm(f => ({ ...f, trigger_config: { ...f.trigger_config, keywords: current.filter(k => k !== kw), match_mode: 'any' } }));
  };

  const handleSave = () => {
    if (!form.name.trim()) return;
    onSave({
      id: form.id,
      category: form.category,
      name: form.name.trim(),
      is_active: form.is_active,
      priority: form.priority,
      trigger_config: form.trigger_config,
      response_text: form.response_text,
      delay_seconds: form.delay_seconds,
      daily_limit: form.daily_limit || null,
    });
  };

  const isSchedule = form.category === 'schedule';
  const isKeywords = form.category === 'keywords';
  const isSimple = form.category === 'greeting' || form.category === 'fallback';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E2E8F0]">
          <h3 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>
            {form.id ? t('admin.automation.edit_rule') : t('admin.automation.add_rule')}
          </h3>
          <button onClick={onClose} className="text-[#94A3B8] hover:text-[#0F172A]"><X size={16} /></button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.rule_name')}</label>
            <input type="text" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]"
              placeholder="Ex: Fora d'horari" />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between px-3 py-2 bg-[#F8FAFC] rounded-md">
            <span className="text-xs font-semibold text-[#475569]">{t('admin.automation.rule_active')}</span>
            <button onClick={() => setForm(f => ({ ...f, is_active: !f.is_active }))}
              className={`relative w-8 h-5 rounded-full transition-colors ${form.is_active ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${form.is_active ? 'right-0.5' : 'left-0.5'}`} />
            </button>
          </div>

          {/* Priority */}
          <div>
            <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.rule_priority')}</label>
            <input type="number" value={form.priority} min={1}
              onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) || 1 }))}
              className="w-24 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
          </div>

          {/* Trigger (varies by category) */}
          {!isSimple && (
            <>
              <div className="border-t border-[#E2E8F0] pt-3">
                <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide mb-2">🎯 {t('admin.automation.rule_trigger')}</div>

                {isSchedule && (
                  <select value={form.trigger_config?.type || 'outside_hours'}
                    onChange={e => setForm(f => ({ ...f, trigger_config: { type: e.target.value } }))}
                    className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
                    <option value="outside_hours">{t('admin.automation.trigger_outside_hours')}</option>
                    <option value="inside_hours">{t('admin.automation.trigger_inside_hours')}</option>
                  </select>
                )}

                {isKeywords && (
                  <div>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {(form.trigger_config?.keywords || []).map(kw => (
                        <span key={kw} className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#EFF6FF] border border-[#BFDBFE] rounded-full text-[11px] text-[#1E40AF]">
                          {kw}
                          <button onClick={() => handleKeywordRemove(kw)} className="font-bold hover:text-red-500">×</button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <input id="kw-input" type="text"
                        className="flex-1 px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md"
                        placeholder={t('admin.automation.keyword_placeholder')}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleKeywordAdd(); } }} />
                      <button onClick={handleKeywordAdd}
                        className="px-3 py-1.5 text-xs bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
                        {t('admin.automation.add_keyword')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Response text */}
          <div className="border-t border-[#E2E8F0] pt-3">
            <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide mb-2">⚡ {t('admin.automation.rule_response')}</div>
            <textarea rows={3} value={form.response_text}
              onChange={e => setForm(f => ({ ...f, response_text: e.target.value }))}
              className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md resize-none font-mono"
              placeholder="Escriu el missatge de resposta..." />
            <p className="text-[10px] text-[#94A3B8] mt-1">
              {t('admin.automation.markers_hint')} <code className="bg-[#F1F5F9] px-1 rounded">{'{{agent_name}}'} {'{{business_name}}'} {'{{contact_name}}'}</code>
            </p>
          </div>

          {/* Delay + Daily limit */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-[#475569] block mb-1">⏱️ {t('admin.automation.rule_delay')}</label>
              <input type="number" value={form.delay_seconds} min={0}
                onChange={e => setForm(f => ({ ...f, delay_seconds: parseInt(e.target.value) || 0 }))}
                className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-[#475569] block mb-1">📊 {t('admin.automation.rule_daily_limit')}</label>
              <input type="number" value={form.daily_limit || ''} min={1}
                placeholder={t('admin.automation.rule_unlimited')}
                onChange={e => setForm(f => ({ ...f, daily_limit: e.target.value ? parseInt(e.target.value) : null }))}
                className="w-full px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md text-[#475569] hover:bg-white">
            {t('admin.automation.cancel')}
          </button>
          <button onClick={handleSave}
            className="px-4 py-1.5 text-xs bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
            {t('admin.automation.save_rule')}
          </button>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// BUSINESS HOURS TAB
// ═══════════════════════════════════════════════════════════════

function BusinessHoursTab({ t }) {
  const [timezone, setTimezone] = useState('Europe/Madrid');
  const [schedule, setSchedule] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await automationApi.getBusinessHours();
      const bh = res.data.business_hours;
      if (bh) {
        setTimezone(bh.timezone || 'Europe/Madrid');
        setSchedule(bh.schedule || {});
      }
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleDayToggle = (dayKey) => {
    setSchedule(prev => {
      const current = prev[dayKey] || [];
      if (current.length > 0) return { ...prev, [dayKey]: [] };
      return { ...prev, [dayKey]: [['09:00', '13:00']] };
    });
  };

  const handleSlotChange = (dayKey, slotIdx, field, value) => {
    setSchedule(prev => {
      const slots = [...(prev[dayKey] || [])];
      if (!slots[slotIdx]) return prev;
      slots[slotIdx] = [...slots[slotIdx]];
      slots[slotIdx][field] = value;
      return { ...prev, [dayKey]: slots };
    });
  };

  const handleAddSlot = (dayKey) => {
    setSchedule(prev => ({
      ...prev,
      [dayKey]: [...(prev[dayKey] || []), ['09:00', '13:00']],
    }));
  };

  const handleRemoveSlot = (dayKey, slotIdx) => {
    setSchedule(prev => {
      const slots = (prev[dayKey] || []).filter((_, i) => i !== slotIdx);
      return { ...prev, [dayKey]: slots };
    });
  };

  const handleSave = async () => {
    try {
      await automationApi.updateBusinessHours({ timezone, schedule });
      toast.success(t('admin.automation.save_hours'));
    } catch (e) { toast.error('Error saving'); }
  };

  if (loading) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  return (
    <div className="space-y-4">
      {/* Timezone */}
      <div>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.timezone')}</label>
        <select value={timezone} onChange={e => setTimezone(e.target.value)}
          className="w-72 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
          <option>Europe/Madrid</option>
          <option>Europe/London</option>
          <option>Europe/Paris</option>
          <option>Europe/Berlin</option>
          <option>America/New_York</option>
          <option>America/Chicago</option>
          <option>America/Los_Angeles</option>
          <option>Asia/Tokyo</option>
        </select>
      </div>

      {/* Days grid */}
      <div className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wide">Dies i franges</div>
      <div className="space-y-2">
        {DAY_KEYS.map(dayKey => {
          const slots = schedule[dayKey] || [];
          const isOpen = slots.length > 0;
          return (
            <div key={dayKey} className={`flex items-start gap-3 p-3 rounded-lg border ${isOpen ? 'bg-[#F8FAFC] border-[#E2E8F0]' : 'bg-[#F1F5F9] border-[#E2E8F0]'}`}>
              <div className="flex items-center gap-2 min-w-[110px] pt-1">
                <button onClick={() => handleDayToggle(dayKey)}
                  className={`relative w-8 h-5 rounded-full transition-colors ${isOpen ? 'bg-green-500' : 'bg-[#CBD5E1]'}`}>
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${isOpen ? 'right-0.5' : 'left-0.5'}`} />
                </button>
                <span className={`text-xs font-semibold ${isOpen ? 'text-[#0F172A]' : 'text-[#94A3B8]'}`}>
                  {t(`admin.automation.${DAY_KEY_MAP[dayKey]}`)}
                </span>
              </div>
              <div className="flex-1 space-y-1.5">
                {isOpen ? (
                  <>
                    {slots.map((slot, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <input type="time" value={slot[0] || ''}
                          onChange={e => handleSlotChange(dayKey, i, 0, e.target.value)}
                          className="w-24 px-2 py-1 text-[11px] border border-[#E2E8F0] rounded-md" />
                        <span className="text-[11px] text-[#94A3B8]">a</span>
                        <input type="time" value={slot[1] || ''}
                          onChange={e => handleSlotChange(dayKey, i, 1, e.target.value)}
                          className="w-24 px-2 py-1 text-[11px] border border-[#E2E8F0] rounded-md" />
                        <button onClick={() => handleRemoveSlot(dayKey, i)}
                          className="text-[#94A3B8] hover:text-red-500 ml-1">
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                    <button onClick={() => handleAddSlot(dayKey)}
                      className="text-[10px] px-2 py-0.5 border border-dashed border-[#CBD5E1] rounded text-[#64748B] hover:bg-white">
                      + {t('admin.automation.add_slot')}
                    </button>
                  </>
                ) : (
                  <span className="text-[11px] text-[#94A3B8]">{t('admin.automation.closed')}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave}
          className="px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
          {t('admin.automation.save_hours')}
        </button>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// ASSIGNMENT TAB
// ═══════════════════════════════════════════════════════════════

function AssignmentTab({ t }) {
  const [config, setConfig] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [aRes, agRes] = await Promise.all([
        automationApi.getAssignment(),
        agentsApi.list(),
      ]);
      setConfig(aRes.data.assignment || {});
      setAgents(agRes.data.agents || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    try {
      await automationApi.updateAssignment({
        is_enabled: config.is_enabled,
        timeout_minutes: config.timeout_minutes,
        strategy: config.strategy,
        agent_pool: config.agent_pool,
      });
      toast.success(t('admin.automation.save_assignment'));
    } catch (e) { toast.error('Error saving'); }
  };

  const toggleAgent = (agentId) => {
    setConfig(prev => {
      const pool = prev.agent_pool || [];
      if (pool.includes(agentId)) {
        return { ...prev, agent_pool: pool.filter(id => id !== agentId) };
      }
      return { ...prev, agent_pool: [...pool, agentId] };
    });
  };

  if (loading || !config) return <p className="text-sm text-[#94A3B8] py-4">{t('general.loading')}</p>;

  const enabled = config.is_enabled;

  return (
    <div className="space-y-5">
      {/* Master toggle */}
      <div className="flex items-center justify-between p-4 bg-[#F5F3FF] border border-[#DDD6FE] rounded-lg">
        <div>
          <div className="text-sm font-bold text-[#4C1D95]">{t('admin.automation.assignment_enabled')}</div>
          <div className="text-[11px] text-[#7C3AED] mt-0.5">{t('admin.automation.assignment_desc')}</div>
        </div>
        <button onClick={() => setConfig(p => ({ ...p, is_enabled: !p.is_enabled }))}
          className={`relative w-10 h-6 rounded-full transition-colors ${enabled ? 'bg-[#8B5CF6]' : 'bg-[#CBD5E1]'}`}>
          <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${enabled ? 'right-0.5' : 'left-0.5'}`} />
        </button>
      </div>

      {/* Timeout */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.assignment_timeout')}</label>
        <input type="number" value={config.timeout_minutes || 5} min={1}
          onChange={e => setConfig(p => ({ ...p, timeout_minutes: parseInt(e.target.value) || 5 }))}
          disabled={!enabled}
          className="w-32 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md" />
        <p className="text-[10px] text-[#94A3B8] mt-1.5">{t('admin.automation.assignment_timeout_hint')}</p>
      </div>

      {/* Strategy */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-1">{t('admin.automation.assignment_strategy')}</label>
        <select value={config.strategy || 'round_robin'}
          onChange={e => setConfig(p => ({ ...p, strategy: e.target.value }))}
          disabled={!enabled}
          className="w-64 px-3 py-2 text-xs border border-[#E2E8F0] rounded-md bg-white">
          <option value="round_robin">{t('admin.automation.strategy_round_robin')}</option>
          <option value="least_conversations">{t('admin.automation.strategy_least')}</option>
        </select>
      </div>

      {/* Agent pool */}
      <div className={`p-4 border rounded-lg ${!enabled ? 'opacity-40 pointer-events-none' : 'border-[#E2E8F0] bg-[#F8FAFC]'}`}>
        <label className="text-[11px] font-semibold text-[#475569] block mb-2">{t('admin.automation.assignment_agents')}</label>
        <div className="space-y-1.5">
          {agents.map(agent => (
            <label key={agent.id} className="flex items-center gap-2 text-xs cursor-pointer">
              <input type="checkbox" checked={(config.agent_pool || []).includes(agent.id)}
                onChange={() => toggleAgent(agent.id)}
                disabled={!enabled}
                className="accent-[#8B5CF6]" />
              {agent.full_name || agent.email || agent.id}
            </label>
          ))}
          {agents.length === 0 && (
            <p className="text-[11px] text-[#94A3B8] italic">{t('admin.automation.no_rules')}</p>
          )}
        </div>
      </div>

      {/* Warning when disabled */}
      {!enabled && (
        <div className="p-3 bg-[#FEF2F2] border border-[#FECACA] rounded-md text-[11px] text-[#991B1B]">
          ⚠️ {t('admin.automation.assignment_disabled_warn')}
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={handleSave}
          className="px-4 py-2 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B]">
          {t('admin.automation.save_assignment')}
        </button>
      </div>
    </div>
  );
}
