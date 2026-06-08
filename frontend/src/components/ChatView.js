import { useState, useRef, useEffect, useMemo } from 'react';
import { useTranslation } from '../contexts/LanguageContext';
import { PaperPlaneRight, CheckSquare, Square, PlusCircle, ArrowsLeftRight, WarningCircle, Tag, ArrowBendUpLeft, X, Paperclip, Image, FileDoc, MicrophoneStage, VideoCamera, DownloadSimple, Play, Timer, Lock, PaperPlaneTilt } from '@phosphor-icons/react';
import { windowApi } from '../lib/api';
import { toast } from 'sonner';

const CASE_COLORS = [
  { bg: '#DBEAFE', text: '#1E40AF', dot: '#3B82F6', border: '#BFDBFE' },
  { bg: '#D1FAE5', text: '#065F46', dot: '#10B981', border: '#A7F3D0' },
  { bg: '#EDE9FE', text: '#5B21B6', dot: '#8B5CF6', border: '#DDD6FE' },
  { bg: '#FFE4E6', text: '#9F1239', dot: '#F43F5E', border: '#FECDD3' },
  { bg: '#FEF3C7', text: '#92400E', dot: '#F59E0B', border: '#FDE68A' },
  { bg: '#CCFBF1', text: '#134E4A', dot: '#14B8A6', border: '#99F6E4' },
  { bg: '#E0E7FF', text: '#3730A3', dot: '#6366F1', border: '#C7D2FE' },
  { bg: '#FFEDD5', text: '#9A3412', dot: '#F97316', border: '#FED7AA' },
];
const UNCLASSIFIED_COLOR = { bg: '#FEF3C7', text: '#92400E', dot: '#D97706', border: '#FDE68A' };

function formatTime(d, locale) { return d ? new Date(d).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }) : ''; }
function formatDate(dateStr, t, locale) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const today = new Date();
  const yest = new Date(today); yest.setDate(yest.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return t('chat.today');
  if (d.toDateString() === yest.toDateString()) return t('chat.yesterday');
  return d.toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' });
}

function WindowBadge({ window: w, t }) {
  const [remaining, setRemaining] = useState(w?.seconds_remaining || 0);

  useEffect(() => {
    if (!w?.seconds_remaining) { setRemaining(0); return; }
    setRemaining(w.seconds_remaining);
    const interval = setInterval(() => {
      setRemaining(prev => {
        const next = prev - 1;
        if (next <= 0) { clearInterval(interval); return 0; }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [w?.seconds_remaining]);

  if (!w || !w.window_expires_at) return null;

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const isActive = remaining > 0;
  const isWarning = isActive && remaining <= 7200;

  const bgColor = !isActive ? '#FEE2E2' : isWarning ? '#FEF3C7' : '#DCFCE7';
  const textColor = !isActive ? '#991B1B' : isWarning ? '#92400E' : '#166534';
  const dotColor = !isActive ? '#EF4444' : isWarning ? '#F59E0B' : '#22C55E';

  return (
    <div data-testid="window-badge" className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold"
      style={{ background: bgColor, color: textColor }}>
      <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: dotColor }} />
      <Timer size={12} weight="bold" />
      {isActive ? (
        <span>{hours}{t('window.hours')} {String(minutes).padStart(2, '0')}{t('window.minutes')}</span>
      ) : (
        <span>{t('window.expired')}</span>
      )}
    </div>
  );
}

function TemplateModal({ conversation, onClose, onSent, t, language }) {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [sending, setSending] = useState(false);
  const [customerName, setCustomerName] = useState(conversation?.contact?.name || '');

  useEffect(() => {
    windowApi.getTemplates().then(res => {
      setTemplates(res.data || []);
      if (res.data?.length) setSelectedTemplate(res.data[0]);
    }).catch(() => {});
  }, []);

  const getPreview = () => {
    if (!selectedTemplate) return '';
    const lang = selectedTemplate.languages[language] ? language : 'ca';
    return selectedTemplate.languages[lang].replace('{{1}}', customerName || '...');
  };

  const handleSend = async () => {
    if (!selectedTemplate) return;
    setSending(true);
    try {
      await windowApi.sendTemplate(conversation.id, {
        template_id: selectedTemplate.id,
        language,
        variables: { customer_name: customerName },
      });
      toast.success(t('window.template_sent_ok'));
      onSent();
      onClose();
    } catch {
      toast.error(t('window.template_sent_error'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{t('window.template_select')}</h3>
          <button data-testid="close-template-modal" onClick={onClose} className="p-1 rounded hover:bg-[#F1F5F9]"><X size={16} /></button>
        </div>

        <div className="p-4 space-y-3">
          <div className="px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
            <WarningCircle size={14} className="inline mr-1" weight="bold" />
            {t('window.template_cost_warning')}
          </div>

          <div>
            <label className="text-xs font-medium text-[#475569] mb-1 block">{t('window.template_label')}</label>
            <select data-testid="template-select" value={selectedTemplate?.id || ''}
              onChange={e => setSelectedTemplate(templates.find(tp => tp.id === e.target.value))}
              className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]">
              {templates.map(tp => (
                <option key={tp.id} value={tp.id}>{tp.id.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-medium text-[#475569] mb-1 block">{t('window.variable_name')}</label>
            <input data-testid="template-customer-name" type="text" value={customerName} onChange={e => setCustomerName(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
          </div>

          <div>
            <label className="text-xs font-medium text-[#475569] mb-1 block">{t('window.preview')}</label>
            <div className="px-3 py-2 rounded-md bg-[#F1F5F9] text-sm text-[#0F172A] border border-[#E2E8F0]">
              {getPreview()}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-[#E2E8F0] flex items-center justify-end gap-2">
          <button data-testid="template-cancel" onClick={onClose} className="px-3 py-1.5 text-sm border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9]">
            {t('window.template_cancel')}
          </button>
          <button data-testid="template-send" onClick={handleSend} disabled={sending || !selectedTemplate}
            className="px-4 py-1.5 text-sm bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-40 flex items-center gap-1.5">
            <PaperPlaneTilt size={14} weight="bold" />
            {sending ? '...' : t('window.template_send')}
          </button>
        </div>
      </div>
    </div>
  );
}


function MediaContent({ msg, isOut }) {
  const url = msg.media_url;
  const type = msg.message_type;

  if (!url) return null;

  if (type === 'image' || type === 'sticker') {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className="block mb-1">
        <img src={url} alt={msg.body || type} className="max-w-full rounded-md max-h-[280px] object-cover cursor-pointer hover:opacity-90 transition-opacity" loading="lazy" />
      </a>
    );
  }

  if (type === 'audio') {
    return (
      <div className="mb-1">
        <audio controls preload="none" className="max-w-full h-9" style={{ width: '100%' }}>
          <source src={url} />
        </audio>
      </div>
    );
  }

  if (type === 'video') {
    return (
      <div className="mb-1 relative">
        <video controls preload="none" className="max-w-full rounded-md max-h-[280px]">
          <source src={url} />
        </video>
      </div>
    );
  }

  if (type === 'document') {
    const filename = msg.body || 'document';
    return (
      <a href={url} target="_blank" rel="noopener noreferrer"
        className={`flex items-center gap-2 px-3 py-2 rounded-md mb-1 transition-colors ${isOut ? 'bg-white/10 hover:bg-white/20' : 'bg-[#E2E8F0] hover:bg-[#CBD5E1]'}`}>
        <FileDoc size={24} weight="duotone" className={isOut ? 'text-blue-300' : 'text-[#475569]'} />
        <span className={`text-xs font-medium flex-1 truncate ${isOut ? '' : 'text-[#0F172A]'}`}>{filename}</span>
        <DownloadSimple size={16} className={isOut ? 'opacity-60' : 'text-[#64748B]'} />
      </a>
    );
  }

  return null;
}

export default function ChatView({
  conversation, messages, allMessages, loading, currentUserId,
  selectionMode, selectedMsgIds, selectedCaseId, msgFilter, cases,
  onSendMessage, onSendMedia, onToggleSelection, onToggleMsg, onCreateCase, onLinkMessages, onMsgFilterChange, onSelectCase, onTemplateSent
}) {
  const { t, locale, language } = useTranslation();
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [showLinkDropdown, setShowLinkDropdown] = useState(false);
  const [replyTo, setReplyTo] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const contact = conversation?.contact || {};
  const windowStatus = conversation?.window || {};
  const windowActive = windowStatus.window_active !== false || !windowStatus.window_expires_at;

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const msgMap = useMemo(() => {
    const map = {};
    (allMessages || []).forEach(m => { map[m.id] = m; });
    return map;
  }, [allMessages]);

  const caseColorMap = useMemo(() => {
    const map = {};
    (cases || []).forEach((c, i) => {
      map[c.id] = { ...CASE_COLORS[i % CASE_COLORS.length], title: c.title, status: c.status };
    });
    return map;
  }, [cases]);

  const handleReply = (msg) => { setReplyTo(msg); inputRef.current?.focus(); };
  const cancelReply = () => setReplyTo(null);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (ev) => setFilePreview(ev.target.result);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  };

  const cancelFile = () => { setPendingFile(null); setFilePreview(null); if (fileInputRef.current) fileInputRef.current.value = ''; };

  const handleSend = async (e) => {
    e.preventDefault();
    if (sending) return;

    if (pendingFile) {
      // Send file
      setSending(true);
      await onSendMedia(pendingFile, newMessage.trim(), replyTo?.id, replyTo?.case_id);
      setNewMessage('');
      setReplyTo(null);
      cancelFile();
      setSending(false);
      return;
    }

    if (!newMessage.trim()) return;
    setSending(true);
    await onSendMessage(newMessage.trim(), replyTo?.id, replyTo?.case_id);
    setNewMessage('');
    setReplyTo(null);
    setSending(false);
  };

  const grouped = [];
  let curDate = '';
  for (const msg of messages) {
    const date = formatDate(msg.sent_at, t, locale);
    if (date !== curDate) { grouped.push({ type: 'date', date }); curDate = date; }
    grouped.push({ type: 'message', data: msg });
  }

  const activeCases = cases.filter(c => c.is_active);
  const unclassifiedCount = allMessages.filter(m => m.needs_classification || !m.case_id).length;
  const showLegend = msgFilter === 'all' && Object.keys(caseColorMap).length > 0;
  const replyColor = replyTo?.case_id ? caseColorMap[replyTo.case_id] : null;

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Header */}
      <div className="min-h-[56px] px-4 flex items-center justify-between border-b border-[#E2E8F0] bg-white">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-[#E2E8F0] flex items-center justify-center text-sm font-bold text-[#475569]">
            {(contact.name || '?')[0]?.toUpperCase()}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-[#0F172A]" style={{ fontFamily: 'Manrope' }}>{contact.name || contact.phone || '?'}</h2>
            <p className="text-[11px] text-[#64748B]">{contact.phone}</p>
          </div>
          <WindowBadge window={windowStatus} t={t} />
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 bg-[#F1F5F9] rounded-md p-0.5">
            <button data-testid="msg-filter-all" onClick={() => onMsgFilterChange('all')} className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${msgFilter === 'all' ? 'bg-white text-[#0F172A] shadow-sm' : 'text-[#64748B]'}`}>{t('chat.view_all')}</button>
            {selectedCaseId && <button data-testid="msg-filter-case" onClick={() => onMsgFilterChange('case')} className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${msgFilter === 'case' ? 'bg-white text-[#0F172A] shadow-sm' : 'text-[#64748B]'}`}>{t('chat.view_case')}</button>}
            {unclassifiedCount > 0 && <button data-testid="msg-filter-unclassified" onClick={() => onMsgFilterChange('unclassified')} className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors flex items-center gap-1 ${msgFilter === 'unclassified' ? 'bg-white text-amber-700 shadow-sm' : 'text-amber-600'}`}>
              <WarningCircle size={12} /> {unclassifiedCount}
            </button>}
          </div>
          <button data-testid="toggle-selection" onClick={onToggleSelection} className={`px-2.5 py-1 text-xs font-medium rounded-md border transition-colors ${selectionMode ? 'bg-[#0F172A] text-white border-[#0F172A]' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9]'}`}>
            {selectionMode ? t('chat.cancel_selection') : t('chat.select_messages')}
          </button>
        </div>
      </div>

      {/* Selection action bar - show when any messages are selected (selection mode OR unclassified checkboxes) */}
      {selectedMsgIds.length > 0 && (
        <div className="px-4 py-2 bg-[#F1F5F9] border-b border-[#E2E8F0] flex items-center gap-2 animate-fade-in">
          <span className="text-xs font-medium text-[#475569]">{selectedMsgIds.length} {t('chat.selected')}</span>
          <button data-testid="create-case-from-msgs" onClick={onCreateCase} className="px-2.5 py-1 text-xs font-medium bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] flex items-center gap-1">
            <PlusCircle size={14} /> {t('chat.create_case')}
          </button>
          {activeCases.length > 0 && (
            <div className="relative">
              <button data-testid="add-to-case-btn" onClick={() => setShowLinkDropdown(!showLinkDropdown)} className="px-2.5 py-1 text-xs font-medium border border-[#E2E8F0] rounded-md hover:bg-white flex items-center gap-1">
                <ArrowsLeftRight size={14} /> {t('chat.add_to_case')}
              </button>
              {showLinkDropdown && (
                <div className="absolute z-20 mt-1 w-56 bg-white border border-[#E2E8F0] rounded-md shadow-lg max-h-40 overflow-y-auto">
                  {activeCases.map(c => {
                    const color = caseColorMap[c.id];
                    return (
                      <button key={c.id} data-testid={`link-case-${c.id}`} onClick={() => { onLinkMessages(c.id); setShowLinkDropdown(false); }} className="w-full text-left px-3 py-2 text-xs hover:bg-[#F1F5F9] flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color?.dot || '#64748B' }} />
                        <span className="font-medium truncate">{c.title}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Legend bar */}
      {showLegend && (
        <div data-testid="case-legend" className="px-4 py-1.5 bg-white border-b border-[#E2E8F0] flex items-center gap-3 overflow-x-auto">
          <Tag size={13} className="text-[#64748B] flex-shrink-0" />
          {cases.filter(c => c.is_active).map(c => {
            const color = caseColorMap[c.id];
            return (
              <button key={c.id} data-testid={`legend-case-${c.id}`} onClick={() => onSelectCase(c.id)}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0 border transition-all hover:shadow-sm cursor-pointer"
                style={{ background: color?.bg, color: color?.text, borderColor: color?.border }}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: color?.dot }} />
                <span className="truncate max-w-[120px]">{c.title}</span>
              </button>
            );
          })}
          {unclassifiedCount > 0 && (
            <button data-testid="legend-unclassified" onClick={() => onMsgFilterChange('unclassified')}
              className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0 border transition-all hover:shadow-sm cursor-pointer"
              style={{ background: UNCLASSIFIED_COLOR.bg, color: UNCLASSIFIED_COLOR.text, borderColor: UNCLASSIFIED_COLOR.border }}>
              <WarningCircle size={11} style={{ color: UNCLASSIFIED_COLOR.dot }} />
              <span>{t('chat.needs_classification')} ({unclassifiedCount})</span>
            </button>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 bg-[#F8FAFC]">
        {loading ? (
          <div className="text-center text-sm text-[#64748B] py-8">{t('chat.loading_messages')}</div>
        ) : grouped.length === 0 ? (
          <div className="text-center text-sm text-[#64748B] py-8">{t('chat.no_messages')}</div>
        ) : (
          grouped.map((item, idx) => {
            if (item.type === 'date') {
              return <div key={`d-${idx}`} className="flex justify-center my-4"><span className="text-[10px] font-medium text-[#64748B] bg-white px-3 py-1 rounded-full border border-[#E2E8F0]">{item.date}</span></div>;
            }
            const msg = item.data;
            const isOut = msg.direction === 'outgoing';
            const isSelected = selectedMsgIds.includes(msg.id);
            const needsClass = msg.needs_classification || (!msg.case_id && msg.direction === 'incoming');
            const caseInfo = msg.case_id ? caseColorMap[msg.case_id] : null;
            const repliedMsg = msg.reply_to_id ? msgMap[msg.reply_to_id] : null;
            const repliedCaseInfo = repliedMsg?.case_id ? caseColorMap[repliedMsg.case_id] : null;
            const hasMedia = msg.media_url && msg.message_type !== 'text';

            const showCheckbox = selectionMode || (needsClass && !isOut);

            return (
              <div key={msg.id} data-testid={`message-${msg.id}`} className={`group flex mb-2 animate-fade-in ${isOut ? 'justify-end' : 'justify-start'}`}>
                {showCheckbox && (
                  <button onClick={() => onToggleMsg(msg.id)} className="mr-2 mt-1 flex-shrink-0">
                    {isSelected ? <CheckSquare size={18} className="text-[#2563EB]" weight="fill" /> : <Square size={18} className="text-[#CBD5E1]" />}
                  </button>
                )}

                {!isOut && !showCheckbox && (
                  <button data-testid={`reply-btn-${msg.id}`} onClick={() => handleReply(msg)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity self-center mr-1.5 p-1 rounded-full hover:bg-[#E2E8F0] text-[#64748B]"
                    title={t('chat.reply')}>
                    <ArrowBendUpLeft size={16} weight="bold" />
                  </button>
                )}

                <div className={`relative ${hasMedia ? 'max-w-[65%]' : 'max-w-[60%]'} ${isOut ? 'bubble-outgoing' : 'bubble-incoming'} px-3 py-2 ${isSelected ? 'ring-2 ring-[#2563EB] ring-offset-1' : ''}`}
                  style={caseInfo && !isOut ? { borderLeft: `3px solid ${caseInfo.dot}` } : caseInfo && isOut ? { borderRight: `3px solid ${caseInfo.dot}` } : needsClass && !isOut ? { borderLeft: `3px solid ${UNCLASSIFIED_COLOR.dot}` } : {}}>

                  {/* Quoted reply */}
                  {repliedMsg && (
                    <div className="mb-1.5 px-2 py-1.5 rounded-md border-l-[3px] cursor-pointer"
                      style={{ background: isOut ? 'rgba(255,255,255,0.1)' : '#E8ECF1', borderLeftColor: repliedCaseInfo?.dot || '#94A3B8' }}>
                      <p className={`text-[10px] font-semibold ${isOut ? 'text-blue-300' : 'text-[#475569]'}`}>
                        {repliedMsg.direction === 'incoming' ? (contact.name || contact.phone) : (repliedMsg.sender_agent_name || t('chat.you_label'))}
                      </p>
                      <p className={`text-[11px] line-clamp-2 ${isOut ? 'opacity-70' : 'text-[#64748B]'}`}>{repliedMsg.body}</p>
                    </div>
                  )}

                  {/* Case tag */}
                  {!isOut && caseInfo && (
                    <div className="flex items-center gap-1 mb-1">
                      <button onClick={() => onSelectCase(msg.case_id)} className="inline-flex items-center gap-1 px-1.5 py-0 rounded text-[9px] font-medium hover:opacity-80 transition-opacity cursor-pointer" style={{ background: caseInfo.bg, color: caseInfo.text }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: caseInfo.dot }} /><span className="truncate max-w-[100px]">{caseInfo.title}</span>
                      </button>
                    </div>
                  )}

                  {needsClass && !isOut && !caseInfo && (
                    <div className="flex items-center gap-1 mb-1">
                      <span className="inline-flex items-center gap-1 px-1.5 py-0 rounded text-[9px] font-medium" style={{ background: UNCLASSIFIED_COLOR.bg, color: UNCLASSIFIED_COLOR.text }}>
                        <WarningCircle size={10} />{t('chat.needs_classification')}
                      </span>
                    </div>
                  )}

                  {isOut && msg.sender_agent_name && <p className="text-xs font-semibold opacity-90 mb-0.5">{msg.sender_agent_name}</p>}

                  {/* Media content */}
                  {hasMedia && <MediaContent msg={msg} isOut={isOut} />}

                  {/* Text body — hide if media is showing (only show real captions, not placeholders) */}
                  {msg.body && !(hasMedia && /^\[/.test(msg.body)) && (
                    <p className="text-sm whitespace-pre-wrap break-words">{msg.body}</p>
                  )}

                  <div className={`flex items-center gap-1.5 mt-1 ${isOut ? 'justify-end' : 'justify-between'}`}>
                    {isOut && caseInfo && (
                      <button onClick={() => onSelectCase(msg.case_id)} className="inline-flex items-center gap-1 text-[9px] opacity-60 hover:opacity-90 transition-opacity cursor-pointer">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: caseInfo.dot }} /><span className="truncate max-w-[80px]">{caseInfo.title}</span>
                      </button>
                    )}
                    {isOut && msg.delivery_status === 'failed' && (
                      <span data-testid={`msg-failed-${msg.id}`}
                        title={msg.delivery_error || t('chat.msg_not_delivered')}
                        className="inline-flex items-center gap-0.5 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-100">
                        <WarningCircle size={10} weight="fill" />
                        {t('chat.msg_failed')}
                      </span>
                    )}
                    <span className={`text-[10px] ${isOut ? 'opacity-60' : 'text-[#64748B]'}`}>{formatTime(msg.sent_at, locale)}</span>
                  </div>
                </div>

                {isOut && !selectionMode && (
                  <button data-testid={`reply-btn-${msg.id}`} onClick={() => handleReply(msg)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity self-center ml-1.5 p-1 rounded-full hover:bg-[#E2E8F0] text-[#64748B]"
                    title={t('chat.reply')}>
                    <ArrowBendUpLeft size={16} weight="bold" />
                  </button>
                )}
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>

      {/* Reply quote bar */}
      {replyTo && (
        <div data-testid="reply-bar" className="px-3 pt-2 pb-0 bg-white border-t border-[#E2E8F0] animate-fade-in">
          <div className="flex items-start gap-2 px-3 py-2 rounded-lg border-l-[3px] bg-[#F1F5F9]" style={{ borderLeftColor: replyColor?.dot || '#64748B' }}>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-[#475569]">
                <ArrowBendUpLeft size={12} className="inline mr-1" />
                {replyTo.direction === 'incoming' ? (contact.name || contact.phone) : (replyTo.sender_agent_name || t('chat.you_label'))}
                {replyColor && (
                  <span className="ml-2 inline-flex items-center gap-1 px-1.5 py-0 rounded text-[9px] font-medium" style={{ background: replyColor.bg, color: replyColor.text }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: replyColor.dot }} />{replyColor.title}
                  </span>
                )}
              </p>
              <p className="text-xs text-[#64748B] line-clamp-2 mt-0.5">{replyTo.body}</p>
            </div>
            <button data-testid="cancel-reply" onClick={cancelReply} className="p-0.5 rounded hover:bg-[#E2E8F0] text-[#64748B] flex-shrink-0"><X size={14} /></button>
          </div>
        </div>
      )}

      {/* File preview bar */}
      {pendingFile && (
        <div data-testid="file-preview-bar" className="px-3 pt-2 pb-0 bg-white border-t border-[#E2E8F0] animate-fade-in" style={replyTo ? { borderTop: 'none' } : {}}>
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[#F1F5F9]">
            {filePreview ? (
              <img src={filePreview} alt="preview" className="w-12 h-12 rounded-md object-cover" />
            ) : (
              <div className="w-12 h-12 rounded-md bg-[#E2E8F0] flex items-center justify-center">
                <FileDoc size={24} className="text-[#475569]" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-[#0F172A] truncate">{pendingFile.name}</p>
              <p className="text-[10px] text-[#64748B]">{(pendingFile.size / 1024).toFixed(0)} KB</p>
            </div>
            <button data-testid="cancel-file" onClick={cancelFile} className="p-1 rounded hover:bg-[#E2E8F0] text-[#64748B]"><X size={16} /></button>
          </div>
        </div>
      )}

      {/* Input - blocked when window expired */}
      {!windowActive ? (
        <div data-testid="window-expired-bar" className="p-3 border-t border-[#E2E8F0] bg-white">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-md bg-red-50 border border-red-200">
            <Lock size={18} weight="bold" className="text-red-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-red-800">{t('window.warning_title')}</p>
              <p className="text-[10px] text-red-600 mt-0.5">{t('window.warning_body')}</p>
            </div>
            <button data-testid="open-template-modal" onClick={() => setShowTemplateModal(true)}
              className="px-3 py-1.5 text-xs font-semibold bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] whitespace-nowrap flex items-center gap-1.5">
              <PaperPlaneTilt size={14} weight="bold" />
              {t('window.send_template')}
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSend} className="p-3 border-t border-[#E2E8F0] bg-white" style={(replyTo || pendingFile) ? { borderTop: 'none', paddingTop: '8px' } : {}}>
          <div className="flex items-center gap-2">
            <input type="file" ref={fileInputRef} onChange={handleFileSelect} className="hidden" accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" />
            <button data-testid="attach-file-btn" type="button" onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-md text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F172A] transition-colors" disabled={sending}>
              <Paperclip size={20} />
            </button>
            <input ref={inputRef} data-testid="message-input" type="text" value={newMessage} onChange={(e) => setNewMessage(e.target.value)}
              placeholder={pendingFile ? t('chat.caption_placeholder') : replyTo ? t('chat.reply_placeholder') : t('chat.input_placeholder')}
              className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#0F172A]" disabled={sending} />
            <button data-testid="send-message-button" type="submit" disabled={(!newMessage.trim() && !pendingFile) || sending} className="p-2 bg-[#0F172A] text-white rounded-md hover:bg-[#1E293B] disabled:opacity-30">
              <PaperPlaneRight size={18} weight="bold" />
            </button>
          </div>
        </form>
      )}

      {showTemplateModal && (
        <TemplateModal
          conversation={conversation}
          onClose={() => setShowTemplateModal(false)}
          onSent={() => onTemplateSent?.()}
          t={t}
          language={language}
        />
      )}
    </div>
  );
}
