import { motion } from "framer-motion";
import type { ESSSummary } from "@/lib/api";

interface ESSGaugeProps {
  summary: ESSSummary;
}

function getEssColor(score: number): string {
  if (score >= 8) return "hsl(var(--risk-critical))";
  if (score >= 6) return "hsl(var(--risk-high))";
  if (score >= 4) return "hsl(var(--risk-medium))";
  return "hsl(var(--risk-low))";
}

export function ESSGauge({ summary }: ESSGaugeProps) {
  const color = getEssColor(summary.max_ess);
  const pct = (summary.max_ess / 10) * 100;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="rounded-lg border border-border bg-card p-6 text-center relative overflow-hidden"
    >
      <div className="absolute inset-0 scanline opacity-30" />
      <div className="relative z-10">
        <p className="text-xs text-muted-foreground tracking-widest uppercase mb-3">
          Exposure Severity Score
        </p>
        <div
          className="text-5xl font-display font-extrabold mb-1"
          style={{ color, textShadow: `0 0 20px ${color}40, 0 0 40px ${color}20` }}
        >
          {summary.max_ess.toFixed(1)}
        </div>
        <p className="text-xs text-muted-foreground mb-4">/ 10.0</p>

        {/* Bar */}
        <div className="h-2 rounded-full bg-muted overflow-hidden mb-3">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
            className="h-full rounded-full"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}60` }}
          />
        </div>

        <p
          className="text-sm font-semibold uppercase tracking-wider"
          style={{ color }}
        >
          {summary.label}
        </p>

        <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
          <div className="bg-muted rounded p-2">
            <span className="text-muted-foreground">Avg ESS</span>
            <p className="font-bold text-foreground">{summary.avg_ess.toFixed(1)}</p>
          </div>
          <div className="bg-muted rounded p-2">
            <span className="text-muted-foreground">Sources</span>
            <p className="font-bold text-foreground">{summary.total_sources}</p>
          </div>
        </div>

        {summary.all_types.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1 justify-center">
            {summary.all_types.map((t) => (
              <span
                key={t}
                className="px-2 py-0.5 rounded text-[10px] bg-muted text-muted-foreground border border-border"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
