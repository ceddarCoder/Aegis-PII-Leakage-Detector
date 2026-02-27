import { useState } from "react";
import { motion } from "framer-motion";
import { Settings, Check, X, Wifi, WifiOff } from "lucide-react";
import { getApiUrl, setApiUrl, healthCheck } from "@/lib/api";

export function ApiConfig() {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(getApiUrl());
  const [status, setStatus] = useState<"idle" | "checking" | "ok" | "error">("idle");

  const handleSave = () => {
    setApiUrl(url);
    setOpen(false);
  };

  const handleCheck = async () => {
    setStatus("checking");
    const ok = await healthCheck();
    setStatus(ok ? "ok" : "error");
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded border border-border bg-card text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-all"
      >
        <Settings className="w-3 h-3" />
        <span className="font-mono">{getApiUrl()}</span>
      </button>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2"
    >
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        className="px-3 py-1.5 rounded border border-border bg-input text-xs font-mono text-foreground w-64 focus:outline-none focus:border-primary/50"
        placeholder="http://localhost:8000"
      />
      <button onClick={handleCheck} className="p-1.5 rounded border border-border hover:border-accent/50 transition-colors">
        {status === "checking" ? (
          <Wifi className="w-3 h-3 text-muted-foreground animate-pulse" />
        ) : status === "ok" ? (
          <Wifi className="w-3 h-3 text-primary" />
        ) : status === "error" ? (
          <WifiOff className="w-3 h-3 text-destructive" />
        ) : (
          <Wifi className="w-3 h-3 text-muted-foreground" />
        )}
      </button>
      <button onClick={handleSave} className="p-1.5 rounded border border-primary/30 bg-primary/10 hover:bg-primary/20 transition-colors">
        <Check className="w-3 h-3 text-primary" />
      </button>
      <button onClick={() => setOpen(false)} className="p-1.5 rounded border border-border hover:border-destructive/30 transition-colors">
        <X className="w-3 h-3 text-muted-foreground" />
      </button>
    </motion.div>
  );
}
