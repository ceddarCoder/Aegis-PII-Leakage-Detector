import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Github, FileText, MessageCircle, Link, Terminal, ChevronDown } from "lucide-react";
import { Header, HeroSection } from "@/components/Header";
import { ApiConfig } from "@/components/ApiConfig";
import { GithubTab } from "@/components/GithubTab";
import { PastebinTab } from "@/components/PastebinTab";
import { SocialTab } from "@/components/SocialTab";
import { CombinedTab } from "@/components/CombinedTab";

const tabs = [
  { id: "github", label: "GitHub", icon: Github, desc: "Scan repositories" },
  { id: "pastebin", label: "Pastebin", icon: FileText, desc: "Scan public pastes" },
  { id: "social", label: "Social", icon: MessageCircle, desc: "Reddit & Telegram" },
  { id: "combined", label: "Combined", icon: Link, desc: "Multi-platform scan" },
] as const;

type TabId = (typeof tabs)[number]["id"];

const Index = () => {
  const [activeTab, setActiveTab] = useState<TabId>("github");

  return (
    <div className="min-h-screen bg-background grid-bg relative">
      {/* Scanline overlay */}
      <div className="fixed inset-0 scanline pointer-events-none z-50" />

      <Header />

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Hero */}
        <HeroSection />

        {/* Warning banner */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="rounded-lg border border-risk-medium/20 bg-risk-medium/5 px-4 py-2.5 flex items-center gap-3"
        >
          <Terminal className="w-4 h-4 text-risk-medium flex-shrink-0" />
          <p className="text-[11px] text-risk-medium">
            <strong>DEMO MODE</strong> — Use only public repositories and test data. Do not scan repositories containing real PII without authorization.
          </p>
        </motion.div>

        {/* Tab nav + API config */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex gap-1 bg-card border border-border rounded-lg p-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 rounded-md text-xs font-medium transition-all ${
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-primary/10 border border-primary/20 rounded-md"
                      style={{ boxShadow: "0 0 15px hsl(135 100% 50% / 0.1)" }}
                      transition={{ type: "spring", duration: 0.4 }}
                    />
                  )}
                  <span className="relative flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5" />
                    <span className="hidden md:inline">{tab.label}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <ApiConfig />
        </motion.div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === "github" && <GithubTab />}
            {activeTab === "pastebin" && <PastebinTab />}
            {activeTab === "social" && <SocialTab />}
            {activeTab === "combined" && <CombinedTab />}
          </motion.div>
        </AnimatePresence>

        {/* Footer */}
        <footer className="border-t border-border pt-6 pb-10">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-[10px] text-muted-foreground tracking-wider">
              AEGIS PII SCANNER · HACKWITHAI 2026 · NO RAW PII STORED
            </p>
            <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
              <span>Python · NLP · spaCy · Presidio</span>
              <span className="text-border">|</span>
              <span>Web Scraping · Regex · FastAPI</span>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
};

export default Index;
