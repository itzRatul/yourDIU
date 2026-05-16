"use client";
import { useState } from "react";
import toast from "react-hot-toast";
import Orb from "./Orb";
import TopBar, { type AppMode, type PanelSettings } from "./TopBar";
import SettingsCog, { type UserProfile } from "./SettingsCog";
import AssistantChat from "@/components/chat/AssistantChat";
import PDFScrapperPage from "@/components/pdf-scrapper/PDFScrapperPage";
import NoticesPage from "@/components/NoticesPage";
import HistoryPanel, { type ChatHistoryItem } from "./HistoryPanel";
import ActivityPanel, { type ActivityStep } from "./ActivityPanel";
import SearchResultsPanel, { type SearchData } from "./SearchResultsPanel";

// Mock logged-in user — replace with real session data when auth is wired
const MOCK_USER: UserProfile = {
  name: "Ratul Hossen",
  email: "itzratulhossen596@gmail.com",
  // avatar comes from Supabase Google OAuth session — undefined shows initial letter
};

interface AppShellProps {
  isGuest?: boolean;
  unreadCount?: number;
  children?: (ctx: AppShellCtx) => React.ReactNode;
}

export interface AppShellCtx {
  mode: AppMode;
  orbActive: boolean;
  setOrbActive: (b: boolean) => void;
  leftOpen: boolean;
  rightOpen: boolean;
}

export default function AppShell({
  isGuest = true,
  unreadCount = 0,
  children,
}: AppShellProps) {
  const [mode, setMode]           = useState<AppMode>("assistant");
  const [leftOpen, setLeft]       = useState(false);
  const [rightOpen, setRight]     = useState(false);
  const [pdfSidebarOpen, setPdfSidebar]       = useState(true);
  const [noticeSidebarOpen, setNoticeSidebar] = useState(true);
  const [orbActive, setOrbActive] = useState(false);
  const [panelSettings, setPanelSettings] = useState<PanelSettings>({
    autoOpenThinking: true,
    autoOpenSearch:   true,
    autoOpenSources:  true,
  });

  // Activity steps (thinking flow)
  const [activitySteps, setActivitySteps] = useState<ActivityStep[]>([]);
  const [streaming, setStreaming]         = useState(false);

  // Search results (guest right panel)
  const [searchData, setSearchData] = useState<SearchData | null>(null);

  const ctx: AppShellCtx = { mode, orbActive, setOrbActive, leftOpen, rightOpen };

  const showOrb = mode === "assistant";

  // Mock history for logged-in (real integration in Step 5)
  const mockHistory: ChatHistoryItem[] = [
    { id: "1", title: "CSE department সম্পর্কে জানতে চাই", preview: "CSE বিভাগে মোট...", timestamp: new Date(Date.now() - 3600000) },
    { id: "2", title: "Main Gate থেকে Food Court", preview: "Main Gate 1 থেকে...", timestamp: new Date(Date.now() - 86400000) },
    { id: "3", title: "ভর্তির প্রক্রিয়া", preview: "DIU তে ভর্তির জন্য...", timestamp: new Date(Date.now() - 172800000) },
  ];

  // When user sends a message → auto-open relevant panels
  const handleSend = () => {
    setActivitySteps([]);
    if (panelSettings.autoOpenThinking) {
      if (isGuest) setLeft(true);   // guest: thinking on left
      else {
        setLeft(true);   // logged-in: history on left
        setRight(true);  // logged-in: activity on right
      }
    }
  };

  // When web search is used → auto-open search panel
  const handleSearchResult = (query: string) => {
    setSearchData({ query, answer: undefined, results: [] });
    if (panelSettings.autoOpenSearch) setRight(true);
  };

  const handleActivityStep = (step: ActivityStep) => {
    setActivitySteps(prev => [...prev, step]);
  };

  const handleOrbActive = (v: boolean) => {
    setOrbActive(v);
    setStreaming(v);
  };

  // TopBar toggle callbacks — different semantics per auth state
  const handleToggleLeft = () => setLeft(o => !o);
  const handleToggleRight = () => {
    if (isGuest) setLeft(o => !o);   // guest: activity button → left thinking panel
    else         setRight(o => !o);  // logged-in: activity button → right panel
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-bg-base flex flex-col">
      {/* Animated orb */}
      <div
        className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-0 transition-opacity duration-500 pointer-events-none ${
          showOrb ? (orbActive ? "opacity-100 animate-orb-pulse" : "opacity-40") : "opacity-0"
        }`}
        style={{ width: "min(640px, 80vw)", height: "min(640px, 80vw)" }}
      >
        <Orb variant="swirl" active={orbActive} hue={0} hoverIntensity={0.25} className="w-full h-full" />
      </div>

      {/* Top bar */}
      <TopBar
        mode={mode}
        onModeChange={setMode}
        isGuest={isGuest}
        unreadCount={unreadCount}
        // For logged-in: historyOpen tracks leftOpen; activityOpen tracks rightOpen
        // For guest: activityOpen tracks leftOpen (thinking); right panel is search (auto only)
        historyOpen={!isGuest && leftOpen}
        activityOpen={isGuest ? leftOpen : rightOpen}
        searchOpen={isGuest ? rightOpen : false}
        pdfListOpen={pdfSidebarOpen}
        noticeListOpen={noticeSidebarOpen}
        onToggleHistory={handleToggleLeft}
        onToggleActivity={handleToggleRight}
        onToggleSearch={() => setRight(o => !o)}
        onTogglePdfList={() => setPdfSidebar(o => !o)}
        onToggleNoticeList={() => setNoticeSidebar(o => !o)}
        settings={panelSettings}
        onSettingsChange={setPanelSettings}
        onOpenNotifications={() => toast("Notifications — coming Step 9")}
        onOpenCommunity={() => toast("Community — coming Step 8")}
        onNewChat={() => {
          setActivitySteps([]);
          setSearchData(null);
          setLeft(false);
          setRight(false);
        }}
      />

      {/* LEFT PANEL */}
      {isGuest ? (
        // Guest left = Thinking (ActivityPanel)
        <ActivityPanel
          open={leftOpen}
          steps={activitySteps}
          streaming={streaming}
          onClose={() => setLeft(false)}
          side="left"
        />
      ) : (
        // Logged-in left = History
        <HistoryPanel
          open={leftOpen}
          isGuest={false}
          history={mockHistory}
          onClose={() => setLeft(false)}
          onSelectChat={() => {}}
          onLoginClick={() => {}}
        />
      )}

      {/* RIGHT PANEL */}
      {isGuest ? (
        // Guest right = Web Search Results
        <SearchResultsPanel
          open={rightOpen}
          data={searchData}
          streaming={streaming}
          onClose={() => setRight(false)}
        />
      ) : (
        // Logged-in right = Activity (thinking + search)
        <ActivityPanel
          open={rightOpen}
          steps={activitySteps}
          streaming={streaming}
          onClose={() => setRight(false)}
          side="right"
          searchData={searchData}
        />
      )}

      {/* Main area */}
      <main className="relative z-10 flex-1 min-h-0 overflow-hidden">
        {children ? children(ctx) : (
          mode === "assistant"
            ? <AssistantChat
                isGuest={isGuest}
                setOrbActive={handleOrbActive}
                onActivityStep={handleActivityStep}
                onSend={handleSend}
                onSearchResult={handleSearchResult}
              />
            : mode === "pdf"
            ? <PDFScrapperPage
                sidebarOpen={pdfSidebarOpen}
                onCloseSidebar={() => setPdfSidebar(false)}
                autoOpenSources={panelSettings.autoOpenSources}
              />
            : mode === "notice"
            ? <NoticesPage
                sidebarOpen={noticeSidebarOpen}
                onCloseSidebar={() => setNoticeSidebar(false)}
              />
            : <ShellPlaceholder mode={mode} isGuest={isGuest} />
        )}
      </main>

      {/* Settings cog — bottom-left, fixed */}
      <SettingsCog
        isGuest={isGuest}
        user={isGuest ? undefined : MOCK_USER}
        onLoginWithGoogle={() => toast("Google OAuth — coming soon (Step 10 auth wiring)")}
        onSignOut={() => toast("Signed out — coming soon")}
      />
    </div>
  );
}

function ShellPlaceholder({ mode, isGuest }: { mode: AppMode; isGuest: boolean }) {
  const modeLabel = mode === "pdf" ? "PDF Scrapper" : "Notice";
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6 gap-3">
      <h2 className="text-2xl md:text-3xl font-semibold text-gradient">{modeLabel}</h2>
      <p className="text-ink-dim text-sm">Coming soon.</p>
      {isGuest && <p className="text-ink-muted text-xs">Browsing as guest</p>}
    </div>
  );
}
