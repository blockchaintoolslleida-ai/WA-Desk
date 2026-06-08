import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from '../contexts/LanguageContext';
import { useNavigate } from 'react-router-dom';
import { conversationsApi, messagesApi, casesApi, agentsApi, mediaApi } from '../lib/api';
import { toast } from 'sonner';
import ConversationList from '../components/ConversationList';
import ChatView from '../components/ChatView';
import DetailPanel from '../components/DetailPanel';
import AppHeader from '../components/AppHeader';
import CreateCaseModal from '../components/CreateCaseModal';

export default function InboxPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [msgLoading, setMsgLoading] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedMsgIds, setSelectedMsgIds] = useState([]);
  const [showCreateCase, setShowCreateCase] = useState(false);
  const [msgFilter, setMsgFilter] = useState('all');
  const pollRef = useRef(null);
  const selectedIdRef = useRef(null);

  // Keep ref in sync so polling callback sees latest value
  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);

  const loadConversations = useCallback(async () => {
    try {
      const params = {};
      if (filter !== 'all') params.filter = filter;
      if (search) params.search = search;
      const res = await conversationsApi.list(params);
      setConversations(res.data || []);
    } catch (err) {
      if (err.response?.status !== 401) console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filter, search]);

  const loadMessages = useCallback(async (convId) => {
    if (!convId) return;
    try {
      const res = await conversationsApi.messages(convId);
      setMessages(res.data || []);
    } catch {}
  }, []);

  const loadConvDetail = useCallback(async (id) => {
    if (!id) return;
    setMsgLoading(true);
    try {
      const [convRes, msgsRes] = await Promise.all([
        conversationsApi.get(id),
        conversationsApi.messages(id),
      ]);
      setSelectedConv(convRes.data);
      setMessages(msgsRes.data || []);
      conversationsApi.markRead(id).catch(() => {});
    } catch (err) {
      console.error(err);
    } finally {
      setMsgLoading(false);
    }
  }, []);

  const handleDeleteConversation = async (convId) => {
    try {
      await conversationsApi.delete(convId);
      if (selectedId === convId) {
        setSelectedId(null);
        setSelectedConv(null);
        setMessages([]);
      }
      loadConversations();
    } catch (err) { console.error('Delete failed:', err); }
  };

  useEffect(() => {
    agentsApi.list().then(res => setAgents(res.data || [])).catch(() => {});
  }, []);

  // Single unified polling: conversations + messages together
  useEffect(() => {
    loadConversations();

    const poll = async () => {
      await loadConversations();
      const currentId = selectedIdRef.current;
      if (currentId) {
        await loadMessages(currentId);
      }
    };

    pollRef.current = setInterval(poll, 6000);
    return () => clearInterval(pollRef.current);
  }, [loadConversations, loadMessages]);

  // Load conversation detail when selection changes
  useEffect(() => {
    if (selectedId) {
      loadConvDetail(selectedId);
    }
  }, [selectedId, loadConvDetail]);

  const handleSendMessage = async (body, replyToId, replyCaseId) => {
    if (!selectedId) return;
    const caseToUse = replyCaseId || selectedCaseId;
    try {
      const res = await messagesApi.send(selectedId, body, caseToUse, replyToId);
      const [msgsRes] = await Promise.all([
        conversationsApi.messages(selectedId),
        loadConversations(),
      ]);
      setMessages(msgsRes.data || []);
      // Surface Meta delivery failure clearly to the operator
      if (res.data && res.data.whatsapp_sent === false) {
        toast.error(`${t('chat.msg_not_delivered')}: ${res.data.whatsapp_error || ''}`, { duration: 8000 });
      } else {
        toast.success(t('chat.msg_sent'));
      }
    } catch { toast.error(t('chat.msg_error')); }
  };

  const handleSendMedia = async (file, caption, replyToId, replyCaseId) => {
    if (!selectedId) return;
    const caseToUse = replyCaseId || selectedCaseId;
    try {
      await mediaApi.send(selectedId, file, caption, caseToUse, replyToId);
      const [msgsRes] = await Promise.all([
        conversationsApi.messages(selectedId),
        loadConversations(),
      ]);
      setMessages(msgsRes.data || []);
      toast.success(t('chat.file_sent'));
    } catch { toast.error(t('chat.file_error')); }
  };

  const handleCreateCase = async (caseData) => {
    try {
      await casesApi.create({ ...caseData, conversation_id: selectedId, message_ids: selectedMsgIds });
      setShowCreateCase(false);
      setSelectionMode(false);
      setSelectedMsgIds([]);
      await Promise.all([loadConvDetail(selectedId), loadConversations()]);
      toast.success(t('case.created_ok'));
    } catch { toast.error(t('case.create_error')); }
  };

  const handleLinkMessages = async (caseId) => {
    try {
      await casesApi.linkMessages(caseId, selectedMsgIds);
      setSelectionMode(false);
      setSelectedMsgIds([]);
      await loadConvDetail(selectedId);
      toast.success(t('case.messages_linked'));
    } catch { toast.error(t('case.link_error')); }
  };

  const handleCaseStatusChange = async (caseId, status) => {
    try {
      await casesApi.changeStatus(caseId, status);
      await Promise.all([loadConvDetail(selectedId), loadConversations()]);
    } catch { toast.error(t('general.error')); }
  };

  const handleCaseAssign = async (caseId, agentId) => {
    try {
      await casesApi.assign(caseId, agentId);
      await Promise.all([loadConvDetail(selectedId), loadConversations()]);
    } catch { toast.error(t('general.error')); }
  };

  const filteredMessages = messages.filter(m => {
    if (msgFilter === 'unclassified') return m.needs_classification || !m.case_id;
    if (msgFilter === 'case' && selectedCaseId) return m.case_id === selectedCaseId;
    return true;
  });

  return (
    <div className="h-screen flex flex-col bg-[#F8FAFC]">
      <AppHeader currentPage="inbox" onNavigate={(p) => navigate(p === 'dashboard' ? '/dashboard' : p === 'agents' ? '/agents' : p === 'admin' ? '/admin' : '/')} />

      <div className="flex-1 flex overflow-hidden">
        {/* Left */}
        <div className="w-[340px] min-w-[340px] border-r border-[#E2E8F0] bg-white flex flex-col">
          <ConversationList
            conversations={conversations}
            selectedId={selectedId}
            filter={filter}
            search={search}
            loading={loading}
            onSelect={(id) => { setSelectedId(id); setSelectedCaseId(null); setMsgFilter('all'); setSelectionMode(false); setSelectedMsgIds([]); }}
            onFilterChange={setFilter}
            onSearchChange={setSearch}
            onDelete={handleDeleteConversation}
          />
        </div>

        {/* Center */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedId && selectedConv ? (
            <ChatView
              conversation={selectedConv}
              messages={filteredMessages}
              allMessages={messages}
              loading={msgLoading}
              currentUserId={user?.id}
              selectionMode={selectionMode}
              selectedMsgIds={selectedMsgIds}
              selectedCaseId={selectedCaseId}
              msgFilter={msgFilter}
              onSendMessage={handleSendMessage}
              onSendMedia={handleSendMedia}
              onToggleSelection={() => { setSelectionMode(!selectionMode); setSelectedMsgIds([]); }}
              onToggleMsg={(id) => setSelectedMsgIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
              onCreateCase={() => setShowCreateCase(true)}
              onLinkMessages={handleLinkMessages}
              onMsgFilterChange={setMsgFilter}
              onSelectCase={(id) => { setSelectedCaseId(id); setMsgFilter('case'); }}
              cases={selectedConv?.cases || []}
              onTemplateSent={() => Promise.all([loadConvDetail(selectedId), loadConversations()])}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-[#64748B]">
              <div className="text-center">
                <p className="text-lg font-medium" style={{ fontFamily: 'Manrope' }}>{t('chat.select_conversation')}</p>
                <p className="text-sm mt-1">{t('chat.select_hint')}</p>
              </div>
            </div>
          )}
        </div>

        {/* Right */}
        {selectedId && selectedConv && (
          <div className="w-[360px] min-w-[360px] border-l border-[#E2E8F0] bg-white flex flex-col overflow-y-auto">
            <DetailPanel
              conversation={selectedConv}
              agents={agents}
              currentUserId={user?.id}
              selectedCaseId={selectedCaseId}
              onSelectCase={(id) => { setSelectedCaseId(id); if (id) setMsgFilter('case'); else setMsgFilter('all'); }}
              onCaseStatusChange={handleCaseStatusChange}
              onCaseAssign={handleCaseAssign}
              onCreateCase={() => setShowCreateCase(true)}
              onContactUpdated={() => loadConvDetail(selectedId)}
            />
          </div>
        )}
      </div>

      {showCreateCase && (
        <CreateCaseModal
          agents={agents}
          onClose={() => { setShowCreateCase(false); }}
          onCreate={handleCreateCase}
          selectedCount={selectedMsgIds.length}
          currentUserId={user?.id}
        />
      )}
    </div>
  );
}
