import { useState } from "react";
import { motion } from "framer-motion";
import { Link, Search, ToggleLeft, ToggleRight } from "lucide-react";
import { scanGithubSingle, scanPastebin, type ScanResponse, type Finding } from "@/lib/api";
import { ScanProgress } from "./ScanProgress";
import { ScanResults } from "./ScanResults";

export function CombinedTab() {
  const [repo, setRepo] = useState("ceddarCoder/1b-1");
  const [branch, setBranch] = useState("main");
  const [pasteLimit, setPasteLimit] = useState(10);
  const [useNlp, setUseNlp] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setResults(null);
    try {
      const [ghRes, pbRes] = await Promise.all([
        scanGithubSingle(repo, branch, 40, useNlp),
        scanPastebin(pasteLimit, useNlp),
      ]);
      // Merge results
      const allFindings: Finding[] = [...ghRes.findings, ...pbRes.findings];
      const combined: ScanResponse = {
        findings: allFindings,
        ess_summary: ghRes.ess_summary || pbRes.ess_summary
          ? {
              max_ess: Math.max(ghRes.ess_summary?.max_ess || 0, pbRes.ess_summary?.max_ess || 0),
              avg_ess: ((ghRes.ess_summary?.avg_ess || 0) + (pbRes.ess_summary?.avg_ess || 0)) / 2,
              label: (ghRes.ess_summary?.max_ess || 0) >= (pbRes.ess_summary?.max_ess || 0)
                ? ghRes.ess_summary?.label || "Unknown"
                : pbRes.ess_summary?.label || "Unknown",
              color: (ghRes.ess_summary?.max_ess || 0) >= (pbRes.ess_summary?.max_ess || 0)
                ? ghRes.ess_summary?.color || "#888"
                : pbRes.ess_summary?.color || "#888",
              total_sources: (ghRes.ess_summary?.total_sources || 0) + (pbRes.ess_summary?.total_sources || 0),
              all_types: [...new Set([
                ...(ghRes.ess_summary?.all_types || []),
                ...(pbRes.ess_summary?.all_types || []),
              ])],
            }
          : null,
        total_sources_scanned: ghRes.total_sources_scanned + pbRes.total_sources_scanned,
        scan_duration: Math.max(ghRes.scan_duration, pbRes.scan_duration),
      };
      setResults(combined);
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
          <Link className="w-5 h-5 text-foreground" />
          <h2 className="font-display font-bold text-foreground">Combined Scan</h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Run GitHub + Pastebin scans in parallel with unified threat report.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">GitHub Repository</label>
            <input
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              className="w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              placeholder="owner/repo"
            />
            <input
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              className="w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              placeholder="Branch"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Pastebin Limit</label>
            <input
              type="range"
              value={pasteLimit}
              onChange={(e) => setPasteLimit(Number(e.target.value))}
              min={5}
              max={30}
              className="w-full accent-primary"
            />
            <span className="text-xs text-foreground font-mono">{pasteLimit} pastes</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setUseNlp(!useNlp)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {useNlp ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
            NLP Filter
          </button>
          <button
            onClick={handleScan}
            disabled={scanning || !repo}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 box-glow"
          >
            <Search className="w-4 h-4" />
            Run Combined Scan
          </button>
        </div>
      </motion.div>

      <ScanProgress scanning={scanning} message="Running combined GitHub + Pastebin scan..." />
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
      {results && <ScanResults results={results} />}
    </div>
  );
}
