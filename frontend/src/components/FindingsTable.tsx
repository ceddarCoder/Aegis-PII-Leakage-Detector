import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import type { Finding } from "@/lib/api";

interface FindingsTableProps {
  findings: Finding[];
}

const riskClasses: Record<string, string> = {
  Critical: "bg-risk-critical/10 text-risk-critical border-risk-critical/30",
  High: "bg-risk-high/10 text-risk-high border-risk-high/30",
  Medium: "bg-risk-medium/10 text-risk-medium border-risk-medium/30",
  Low: "bg-risk-low/10 text-risk-low border-risk-low/30",
};

export function FindingsTable({ findings }: FindingsTableProps) {
  if (findings.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center">
        <p className="text-primary text-glow text-sm">✓ No PII detected</p>
        <p className="text-muted-foreground text-xs mt-1">Scanned content appears clean</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-border bg-card overflow-hidden"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-muted">
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Type</th>
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Masked Value</th>
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Confidence</th>
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Risk</th>
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Source</th>
              <th className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">Note</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f, i) => (
              <motion.tr
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.02 }}
                className="border-b border-border/50 hover:bg-muted/50 transition-colors"
              >
                <td className="p-3">
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20">
                    {f.type}
                  </span>
                </td>
                <td className="p-3 font-mono text-foreground">{f.value_masked}</td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${f.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-muted-foreground">{(f.confidence * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskClasses[f.risk] || "text-muted-foreground"}`}>
                    {f.risk}
                  </span>
                </td>
                <td className="p-3">
                  {f.source_url ? (
                    <a
                      href={f.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:text-primary transition-colors inline-flex items-center gap-1"
                    >
                      <span className="truncate max-w-[150px] inline-block">{f.source || "Link"}</span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </a>
                  ) : (
                    <span className="text-muted-foreground">{f.source || "—"}</span>
                  )}
                </td>
                <td className="p-3 text-muted-foreground max-w-[200px] truncate">
                  {f.annotation || "—"}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-2 bg-muted border-t border-border text-[10px] text-muted-foreground">
        {findings.length} finding{findings.length !== 1 ? "s" : ""} detected
      </div>
    </motion.div>
  );
}
