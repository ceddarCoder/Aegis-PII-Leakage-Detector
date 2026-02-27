import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Shield, Activity, Radar, Eye, Lock,
  LayoutDashboard, History, LogOut, ChevronDown, User,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export function Header() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() ?? "U";

  return (
    <header className="border-b border-border relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-0 left-1/4 w-96 h-32 bg-primary/5 blur-3xl rounded-full" />
      <div className="absolute top-0 right-1/4 w-64 h-24 bg-accent/5 blur-3xl rounded-full" />

      <div className="max-w-7xl mx-auto px-6 py-5 relative">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4 cursor-pointer"
            onClick={() => navigate(isAuthenticated ? "/" : "/login")}
          >
            <div className="relative">
              <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center">
                <Shield className="w-6 h-6 text-primary" />
              </div>
              <div className="absolute -inset-1 bg-primary/20 rounded-lg blur-md -z-10" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-extrabold text-primary text-glow tracking-tight leading-none">
                AEGIS
              </h1>
              <p className="text-[10px] text-muted-foreground tracking-[0.25em] uppercase mt-0.5">
                Context-Aware Indian PII Leakage Scanner
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4"
          >
            {/* Live indicator */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-card">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              <span className="text-[10px] text-muted-foreground font-mono tracking-wider">ONLINE</span>
            </div>

            <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground">
              <Activity className="w-3 h-3 text-primary" />
              <span className="font-mono">v2.0</span>
            </div>

            <div className="hidden sm:block px-2.5 py-1 rounded-full border border-accent/30 bg-accent/5 text-[10px] text-accent font-semibold tracking-wider uppercase">
              HackWithAI 2026
            </div>

            {/* User menu */}
            {isAuthenticated ? (
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card hover:border-primary/30 transition-all"
                >
                  <div className="w-6 h-6 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center text-[10px] font-bold text-primary">
                    {initials}
                  </div>
                  <span className="hidden sm:block text-xs text-foreground max-w-[100px] truncate">
                    {user?.full_name || user?.email}
                  </span>
                  <ChevronDown className={`w-3 h-3 text-muted-foreground transition-transform ${menuOpen ? "rotate-180" : ""}`} />
                </button>

                <AnimatePresence>
                  {menuOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 top-full mt-2 w-48 rounded-lg border border-border bg-card shadow-xl z-50 overflow-hidden"
                    >
                      <div className="px-3 py-2 border-b border-border">
                        <p className="text-xs font-semibold text-foreground truncate">{user?.full_name || "User"}</p>
                        <p className="text-[10px] text-muted-foreground truncate">{user?.email}</p>
                      </div>
                      {[
                        { label: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
                        { label: "My Profile", icon: User, path: "/profile" },
                        { label: "Scan History", icon: History, path: "/history" },
                        { label: "Scanner", icon: Radar, path: "/" },
                      ].map(({ label, icon: Icon, path }) => (
                        <button
                          key={path}
                          onClick={() => { navigate(path); setMenuOpen(false); }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors text-left"
                        >
                          <Icon className="w-3.5 h-3.5" />
                          {label}
                        </button>
                      ))}
                      <div className="border-t border-border">
                        <button
                          onClick={handleLogout}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          <LogOut className="w-3.5 h-3.5" />
                          Sign Out
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <button
                onClick={() => navigate("/login")}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary/30 bg-primary/10 text-primary text-xs font-semibold hover:bg-primary/20 transition-all"
              >
                <Lock className="w-3 h-3" />
                Sign In
              </button>
            )}
          </motion.div>
        </div>
      </div>
    </header>
  );
}

export function HeroSection() {
  const features = [
    { icon: Radar, label: "NLP + Regex Detection", desc: "spaCy & Presidio-powered scanning" },
    { icon: Eye, label: "Multi-Platform", desc: "GitHub, Pastebin, Reddit, Telegram" },
    { icon: Lock, label: "PII Classification", desc: "Aadhaar, PAN, phone, email & more" },
    { icon: Shield, label: "ESS Scoring", desc: "Exposure Severity Score 0-10" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="relative rounded-xl border border-border bg-card overflow-hidden"
    >
      <div className="absolute inset-0 grid-bg opacity-50" />
      <div className="absolute top-0 right-0 w-80 h-80 bg-primary/3 blur-3xl rounded-full" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-accent/3 blur-3xl rounded-full" />

      <div className="relative p-8">
        <div className="max-w-2xl">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <p className="text-[10px] text-primary tracking-[0.3em] uppercase font-semibold mb-3">
              Automated PII Leakage Detection
            </p>
            <h2 className="text-3xl md:text-4xl font-display font-extrabold text-foreground leading-tight mb-3">
              Scan. Detect. <span className="text-primary text-glow">Protect.</span>
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-lg">
              NLP-powered scanner that detects leaked PII across GitHub repos, Pastebin pastes,
              Reddit profiles, and Telegram channels. Classifies entity types and generates
              severity-scored alert reports.
            </p>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-8"
        >
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.08 }}
                className="rounded-lg border border-border/60 bg-muted/30 p-3 hover:border-primary/30 hover:bg-primary/5 transition-all group"
              >
                <Icon className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors mb-2" />
                <p className="text-xs font-semibold text-foreground">{f.label}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{f.desc}</p>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </motion.div>
  );
}
