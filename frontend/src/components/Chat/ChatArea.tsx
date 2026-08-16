import { useRef, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { MessageBubble } from './MessageBubble';
import { InputArea } from './InputArea';
import { StreamingDots } from './StreamingDots';
import { useAppStore } from '../../lib/store';
import {
  PanelRightOpen,
  PanelRightClose,
  Database,
  MessageSquare,
  X,
  ShieldCheck,
  Activity,
  LockKeyhole,
  Network,
} from 'lucide-react';
import { listConnectors } from '../../lib/connectors-api';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export function ChatArea() {
  const activeId = useAppStore((s) => s.activeId);
  const messages = useAppStore((s) => s.messages);
  const streamState = useAppStore((s) => s.streamState);
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);
  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);
  const wasStreaming = useRef(false);
  const lastScrollTop = useRef(0);
  const isCurrentChatStreaming = streamState.isStreaming && streamState.conversationId === activeId;
  const currentStreamContent = isCurrentChatStreaming ? streamState.content : '';

  const [hasConnectedSources, setHasConnectedSources] = useState<boolean | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    listConnectors()
      .then((list) => setHasConnectedSources(list.some((c) => c.connected)))
      .catch(() => setHasConnectedSources(null));
  }, []);

  useEffect(() => {
    if (isCurrentChatStreaming && !wasStreaming.current) {
      shouldAutoScroll.current = true;
    }
    wasStreaming.current = isCurrentChatStreaming;
    if (shouldAutoScroll.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, currentStreamContent, isCurrentChatStreaming]);

  const handleScroll = () => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    const distance = scrollHeight - scrollTop - clientHeight;
    const scrolledUp = scrollTop < lastScrollTop.current;
    lastScrollTop.current = scrollTop;
    if (scrolledUp && distance >= 1) {
      shouldAutoScroll.current = false;
    } else if (!scrolledUp) {
      shouldAutoScroll.current = distance < 2;
    }
  };

  const isEmpty = messages.length === 0 && !isCurrentChatStreaming;
  const PanelIcon = systemPanelOpen ? PanelRightClose : PanelRightOpen;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-3 py-1.5 shrink-0">
        <button
          onClick={toggleSystemPanel}
          className="p-1.5 rounded-lg transition-colors cursor-pointer"
          style={{ color: 'var(--color-text-tertiary)' }}
          title={`${systemPanelOpen ? 'Hide' : 'Show'} system panel (${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+I)`}
        >
          <PanelIcon size={16} />
        </button>
      </div>

      {hasConnectedSources === false && !bannerDismissed && (
        <div
          className="camcore-source-banner mx-4 mb-2 flex items-center gap-3 px-4 py-3 rounded-xl text-sm shrink-0"
          style={{ border: '1px solid var(--color-border)' }}
        >
          <Database size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
          <span style={{ color: 'var(--color-text-secondary)', flex: 1 }}>
            Connect trusted data sources to give Jarvis useful CamCore context.
          </span>
          <button
            onClick={() => navigate('/data-sources')}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer"
            style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)', border: 'none' }}
          >
            Connect
          </button>
          <button
            onClick={() => setBannerDismissed(true)}
            className="p-1 rounded cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)', background: 'transparent', border: 'none' }}
            aria-label="Dismiss data source notice"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div
        ref={listRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {isEmpty ? (
          <div className="flex items-center justify-center min-h-full px-4 py-8">
            <section className="camcore-hero" aria-labelledby="camcore-jarvis-greeting">
              <div className="camcore-hero-mark" aria-hidden="true">
                <ShieldCheck size={24} />
              </div>
              <p className="camcore-hero-eyebrow">Jarvis · CamCore AI</p>
              <h2 id="camcore-jarvis-greeting">
                {getGreeting()}. <span className="camcore-gradient-text">What needs attention?</span>
              </h2>
              <p className="camcore-hero-description">
                Your private operations assistant for CamCore. Ask about systems, investigate an issue,
                work with connected information, or plan a change before it touches production.
              </p>

              <div className="camcore-capabilities" aria-label="Jarvis operating principles">
                <span className="camcore-capability"><LockKeyhole size={12} /> Private by design</span>
                <span className="camcore-capability"><Activity size={12} /> Verify before change</span>
                <span className="camcore-capability"><Network size={12} /> CamCore aware</span>
              </div>

              <div className="camcore-quick-actions">
                <button className="camcore-quick-action" onClick={() => navigate('/dashboard')}>
                  <span className="camcore-quick-action-icon"><Activity size={16} /></span>
                  <span>
                    <strong>Open operations</strong>
                    <span>Review system activity, metrics and current state.</span>
                  </span>
                </button>
                <button className="camcore-quick-action" onClick={() => navigate('/data-sources')}>
                  <span className="camcore-quick-action-icon"><Database size={16} /></span>
                  <span>
                    <strong>Connect context</strong>
                    <span>Add approved sources Jarvis can use when answering.</span>
                  </span>
                </button>
                <button className="camcore-quick-action" onClick={() => navigate('/agents')}>
                  <span className="camcore-quick-action-icon"><Network size={16} /></span>
                  <span>
                    <strong>Manage agents</strong>
                    <span>Inspect scheduled and persistent Jarvis workloads.</span>
                  </span>
                </button>
                <button
                  className="camcore-quick-action"
                  onClick={() => {
                    navigate('/data-sources');
                    setTimeout(() => window.dispatchEvent(new CustomEvent('switch-tab', { detail: 'messaging' })), 100);
                  }}
                >
                  <span className="camcore-quick-action-icon"><MessageSquare size={16} /></span>
                  <span>
                    <strong>Messaging channels</strong>
                    <span>Configure approved ways to interact with Jarvis.</span>
                  </span>
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div className="max-w-[var(--chat-max-width)] mx-auto px-4 py-6">
            {messages.map((msg, i) => {
              const isLastAssistant = i === messages.length - 1 && msg.role === 'assistant';
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLive={isLastAssistant && isCurrentChatStreaming}
                />
              );
            })}
            {(() => {
              if (!isCurrentChatStreaming || streamState.content !== '') return null;
              const last = messages[messages.length - 1];
              if (last?.role === 'assistant' && last.isResearch) return null;
              return (
                <div className="flex justify-start mb-4">
                  <StreamingDots phase={streamState.phase} />
                </div>
              );
            })()}
          </div>
        )}
      </div>
      <InputArea />
    </div>
  );
}
