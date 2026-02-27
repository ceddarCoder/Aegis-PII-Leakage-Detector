import { useState } from "react";
import { motion } from "framer-motion";
import { FileText, Search, ToggleLeft, ToggleRight } from "lucide-react";
import { scanPastebin, type ScanResponse } from "@/lib/api";
import { ScanProgress } from "./ScanProgress";
import { ScanResults } from "./ScanResults";

export function PastebinTab() {
  const [limit, setLimit] = useState(15);
  const [useNlp, setUseNlp] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setResults(null);
    try {
      setResults(await scanPastebin(limit, useNlp));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="rounded-lg border border-border bg-card p-6 space-y-4"
      >
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-5 h-5 text-foreground" />
          <h2 className="font-display font-bold text-foreground">Pastebin Scanner</h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Scans Pastebin's public archive for leaked PII.
        </p>

        <div className="flex items-center gap-6">
          <div>
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Recent Pastes</label>
            <input
              type="range"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={5}
              max={50}
              className="mt-1 w-40 accent-primary"
            />
            <span className="ml-2 text-xs text-foreground font-mono">{limit}</span>
          </div>
          <button
            onClick={() => setUseNlp(!useNlp)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {useNlp ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
            NLP Filter
          </button>
        </div>

        <button
          onClick={handleScan}
          disabled={scanning}
          className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 box-glow"
        >
          <Search className="w-4 h-4" />
          Scan Pastebin
        </button>
      </motion.div>

      <ScanProgress scanning={scanning} message="Scanning Pastebin pastes..." />
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
      {results && (
        <ScanResults
          results={results}
          scanType="pastebin"
          target={`pastebin_recent_${limit}`}
        />
      )}
    </div>
  );
}
