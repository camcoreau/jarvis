import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router';
import {
  MessageSquare,
  Plus,
  BarChart3,
  Settings,
  Search,
  PanelLeftClose,
  PanelLeft,
  Cpu,
  Rocket,
  Bot,
  Sun,
  Moon,
  Monitor,
  Loader2,
  ScrollText,
  Database,
  ShieldCheck,
} from 'lucide-react';
import { ConversationList } from './ConversationList';
import { useAppStore } from '../../lib/store';

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');

  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const createConversation = useAppStore((s) => s.createConversation);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const serverInfo = useAppStore((s) => s.serverInfo);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const modelLoading = useAppStore((s) => s.modelLoading);
  const deepResearch = useAppStore((s) => s.deepResearch);

  const settings = useAppStore((s) => s.settings);
  const updateSettings = useAppStore((s) => s.updateSettings);

  const ThemeIcon = settings.theme === 'light' ? Sun : settings.theme === 'dark' ? Moon : Monitor;
  const nextTheme = settings.theme === 'light' ? 'dark' : settings.theme === 'dark' ? 'system' : 'light';

  const messages = useAppStore((s) => s.messages);
  const handleNewChat = () => {
    if (messages.length === 0) {
      navigate('/');
      return;
    }
    createConversation(selectedModel);
    navigate('/');
  };

  const primaryNav = [
    { path: '/', icon: MessageSquare, label: 'Chat' },
    { path: '/dashboard', icon: BarChart3, label: 'Operations' },
    { path: '/data-sources', icon: Database, label: 'Data Sources' },
    { path: '/agents', icon: Bot, label: 'Agents' },
  ];

  const systemNav = [
    { path: '/logs', icon: ScrollText, label: 'Activity Logs' },
    { path: '/settings', icon: Settings, label: 'Settings' },
    { path: '/get-started', icon: Rocket, label: 'Setup' },
  ];

  const renderNavItem = (item: (typeof primaryNav)[number]) => {
    const isActive = location.pathname === item.path;
    return (
      <button
        key={item.path}
        onClick={() => navigate(item.path)}
        data-active={isActive ? 'true' : 'false'}
        className="camcore-nav-item relative flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-colors w-full text-left cursor-pointer"
        style={{
          background: isActive ? 'var(--color-accent-subtle)' : 'transparent',
          color: isActive ? 'var(--color-text)' : 'var(--color-text-secondary)',
          fontWeight: isActive ? 650 : 480,
        }}
      >
        {isActive && (
          <span
            aria-hidden="true"
            className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full"
            style={{
              background: 'linear-gradient(180deg, #bcecf4, var(--color-accent), #419eea)',
              boxShadow: '0 0 10px var(--color-accent-glow)',
            }}
          />
        )}
        <item.icon size={16} style={isActive ? { color: 'var(--color-accent)' } : undefined} />
        {item.label}
      </button>
    );
  };

  return (
    <>
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed top-3 left-3 z-30 p-2 rounded-xl transition-colors cursor-pointer"
          style={{
            color: 'var(--color-text-secondary)',
            background: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-md)',
          }}
          title="Open navigation"
        >
          <PanelLeft size={18} />
        </button>
      )}

      <aside
        className={`camcore-sidebar
          flex flex-col h-full shrink-0 transition-all duration-200 ease-in-out
          fixed md:relative z-30
          ${sidebarOpen ? 'w-[272px]' : 'w-0 border-0!'}
        `}
      >
        <div className="flex flex-col h-full w-[270px]">
          <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-3">
            <button
              className="camcore-brand-lockup text-left cursor-pointer"
              onClick={() => navigate('/')}
              title="Jarvis | CamCore AI"
            >
              <span className="camcore-brand-mark" aria-hidden="true">
                <ShieldCheck size={20} />
              </span>
              <span className="camcore-brand-copy">
                <span className="camcore-brand-title">Jarvis</span>
                <span className="camcore-brand-subtitle">CamCore AI</span>
              </span>
            </button>
            <button
              onClick={toggleSidebar}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
              title="Collapse navigation"
            >
              <PanelLeftClose size={17} />
            </button>
          </div>

          <div className="flex items-center gap-1 px-3 pb-3">
            <button
              onClick={handleNewChat}
              className="flex-1 flex items-center justify-center gap-2 min-h-9 px-3 rounded-xl text-xs font-semibold cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, rgba(79,207,243,.14), rgba(65,158,234,.08))',
                border: '1px solid rgba(79,207,243,.18)',
                color: 'var(--color-text)',
              }}
            >
              <Plus size={15} style={{ color: 'var(--color-accent)' }} />
              New chat
            </button>
            <button
              onClick={() => updateSettings({ theme: nextTheme })}
              className="grid place-items-center w-9 h-9 rounded-xl cursor-pointer"
              style={{
                color: 'var(--color-text-secondary)',
                border: '1px solid var(--color-border)',
                background: 'rgba(255,255,255,.018)',
              }}
              title={`Theme: ${settings.theme} (click for ${nextTheme})`}
            >
              <ThemeIcon size={15} />
            </button>
          </div>

          <div className="camcore-section-label">Intelligence</div>
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="camcore-model-card mx-3 mb-3 flex items-center gap-2.5 px-3 py-2.5 text-xs transition-colors cursor-pointer"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {modelLoading ? (
              <Loader2 size={15} className="animate-spin" style={{ color: 'var(--color-accent)' }} />
            ) : (
              <Cpu size={15} style={{ color: 'var(--color-accent)' }} />
            )}
            <div className="flex-1 min-w-0">
              <span
                className="truncate block text-left font-medium"
                style={{ color: deepResearch ? 'var(--color-accent)' : 'var(--color-text)' }}
              >
                {deepResearch ? 'Deep Research' : selectedModel || serverInfo?.model || 'Select model'}
              </span>
              <span className="text-[10px] block text-left mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                {modelLoading ? 'Loading local model…' : 'Local-first inference'}
              </span>
            </div>
            {!modelLoading && (
              <kbd
                className="text-[9px] px-1.5 py-0.5 rounded font-mono"
                style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
              >
                ⌘K
              </kbd>
            )}
          </button>

          <div className="camcore-section-label">Workspace</div>
          <nav className="px-2 flex flex-col gap-0.5">
            {primaryNav.map(renderNavItem)}
          </nav>

          <div className="camcore-section-label mt-4!">Conversations</div>
          <div className="px-3 mb-2">
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm"
              style={{ background: 'rgba(255,255,255,.018)', border: '1px solid var(--color-border)' }}
            >
              <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
              <input
                type="text"
                placeholder="Search chats"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent outline-none text-xs"
                style={{ color: 'var(--color-text)' }}
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-2 min-h-[80px]">
            <ConversationList searchQuery={searchQuery} />
          </div>

          <div className="camcore-section-label">System</div>
          <nav className="px-2 pb-3 flex flex-col gap-0.5">
            {systemNav.map(renderNavItem)}
          </nav>
        </div>
      </aside>
    </>
  );
}
