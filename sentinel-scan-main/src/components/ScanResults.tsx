import { useEffect } from "react";
import { motion } from "framer-motion";
import { Clock, FileSearch, AlertTriangle } from "lucide-react";
import { useApi } from "@/contexts/ApiContext";
import { ReportDownloadButton } from "./ReportDownloadButton";
import type { ScanResponse } from "@/lib/api";
import { saveScanHistory } from "@/lib/api";
import { ESSGauge } from "./ESSGauge";
import { FindingsTable } from "./FindingsTable";

interface ScanResultsProps {
  results: ScanResponse;
  scanType: string;
  target: string;
}

export function ScanResults({ results, scanType, target }: ScanResultsProps) {
  const { apiUrl } = useApi();

  // Defensive defaults
  const findings = results?.findings ?? [];
  const ess_summary = results?.ess_summary;
  const total_sources_scanned = results?.total_sources_scanned ?? 0;
  const scan_duration = results?.scan_duration ?? 0;

  // Auto-save to history on mount (once per result set)
  useEffect(() => {
    saveScanHistory({
      scan_type: scanType,
      target,
      findings_count: findings.length,
      max_ess: ess_summary?.max_ess ?? 0,
      ess_label: ess_summary?.label ?? "",
      sources_scanned: total_sources_scanned,
      scan_duration,
    }).catch(() => {
      // Silently ignore — history save is best-effort
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-primary" />
          <div>
            <p className="text-2xl font-display font-bold text-foreground">
              {findings.length}
            </p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Findings
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-3">
          <FileSearch className="w-5 h-5 text-accent" />
          <div>
            <p className="text-2xl font-display font-bold text-foreground">
              {total_sources_scanned}
            </p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Sources
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-3">
          <Clock className="w-5 h-5 text-muted-foreground" />
          <div>
            <p className="text-2xl font-display font-bold text-foreground">
              {scan_duration.toFixed(1)}s
            </p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Duration
            </p>
          </div>
        </div>
      </div>

      {/* ESS + Table */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {ess_summary && (
          <div className="lg:col-span-1">
            <ESSGauge summary={ess_summary} />
          </div>
        )}
        <div className={ess_summary ? "lg:col-span-3" : "lg:col-span-4"}>
          <FindingsTable findings={findings} />
        </div>
      </div>

      {/* Download button – only if findings exist */}
      {findings.length > 0 && (
        <div className="flex justify-end">
          <ReportDownloadButton
            findings={findings}
            scanType={scanType}
            target={target}
            filesScanned={total_sources_scanned}
            apiUrl={apiUrl}
          />
        </div>
      )}
    </motion.div>
  );
}