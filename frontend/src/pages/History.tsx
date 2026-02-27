import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
    History, Trash2, Shield, AlertTriangle, ChevronDown, ChevronUp, ExternalLink,
} from "lucide-react";
import { getScanHistory, deleteScanHistory, type ScanHistoryItem } from "@/lib/api";
import { Header } from "@/components/Header";

const riskColors: Record<string, string> = {
    CRITICAL: "text-red-400 border-red-400/30 bg-red-400/10",
    HIGH: "text-orange-400 border-orange-400/30 bg-orange-400/10",
    MEDIUM: "text-yellow-400 border-yellow-400/30 bg-yellow-400/10",
    LOW: "text-green-400 border-green-400/30 bg-green-400/10",
};

export default function HistoryPage() {
    const navigate = useNavigate();
    const [records, setRecords] = useState<ScanHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleting, setDeleting] = useState<number | null>(null);

    useEffect(() => {
        getScanHistory()
            .then(setRecords)
            .catch(() => setRecords([]))
            .finally(() => setLoading(false));
    }, []);

    const handleDelete = async (id: number) => {
        setDeleting(id);
        try {
            await deleteScanHistory(id);
            setRecords((prev) => prev.filter((r) => r.id !== id));
        } catch {
            /* ignore */
        } finally {
            setDeleting(null);
        }
    };

    return (
        <div className="min-h-screen bg-background grid-bg relative">
            <div className="fixed inset-0 scanline pointer-events-none z-50" />
            <Header />

            <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
                {/* Page header */}
                <motion.div
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center justify-between"
                >
                    <div>
                        <h2 className="text-xl font-display font-bold text-foreground flex items-center gap-2">
                            <History className="w-5 h-5 text-primary" />
                            Scan History
                        </h2>
                        <p className="text-xs text-muted-foreground mt-0.5">{records.length} scan{records.length !== 1 ? "s" : ""} recorded</p>
                    </div>
                </motion.div>

                {/* Table */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="rounded-xl border border-border bg-card overflow-hidden"
                >
                    {loading ? (
                        <div className="flex items-center justify-center py-16">
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                                className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full"
                            />
                        </div>
                    ) : records.length === 0 ? (
                        <div className="text-center py-16">
                            <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-30" />
                            <p className="text-sm text-muted-foreground">No scan history yet.</p>
                            <button
                                onClick={() => navigate("/")}
                                className="mt-3 text-xs text-primary hover:text-primary/80 transition-colors"
                            >
                                Run your first scan →
                            </button>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-border bg-muted">
                                        {["Date", "Type", "Target", "Sources", "Findings", "ESS Score", ""].map((h) => (
                                            <th key={h} className="text-left p-3 text-muted-foreground font-semibold tracking-wider uppercase text-[10px]">
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <AnimatePresence>
                                        {records.map((r, i) => (
                                            <motion.tr
                                                key={r.id}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                exit={{ opacity: 0, x: 10 }}
                                                transition={{ delay: i * 0.03 }}
                                                className="border-b border-border/50 hover:bg-muted/40 transition-colors"
                                            >
                                                <td className="p-3 text-muted-foreground whitespace-nowrap">
                                                    {r.created_at
                                                        ? new Date(r.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
                                                        : "—"}
                                                </td>
                                                <td className="p-3">
                                                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20 capitalize">
                                                        {r.scan_type}
                                                    </span>
                                                </td>
                                                <td className="p-3 font-mono text-foreground max-w-[180px] truncate" title={r.target}>
                                                    {r.target}
                                                </td>
                                                <td className="p-3 text-foreground">{r.sources_scanned}</td>
                                                <td className="p-3">
                                                    <span className="flex items-center gap-1">
                                                        {r.findings_count > 0 && <AlertTriangle className="w-3 h-3 text-orange-400" />}
                                                        <span className={r.findings_count > 0 ? "text-orange-400 font-bold" : "text-muted-foreground"}>
                                                            {r.findings_count}
                                                        </span>
                                                    </span>
                                                </td>
                                                <td className="p-3">
                                                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskColors[r.ess_label] || "text-muted-foreground border-border"}`}>
                                                        {r.max_ess.toFixed(1)} {r.ess_label || "—"}
                                                    </span>
                                                </td>
                                                <td className="p-3">
                                                    <button
                                                        onClick={() => handleDelete(r.id)}
                                                        disabled={deleting === r.id}
                                                        className="p-1.5 rounded border border-border hover:border-destructive/40 hover:bg-destructive/10 transition-all disabled:opacity-40"
                                                        title="Delete record"
                                                    >
                                                        {deleting === r.id ? (
                                                            <motion.div
                                                                animate={{ rotate: 360 }}
                                                                transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                                                                className="w-3 h-3 border border-muted-foreground border-t-transparent rounded-full"
                                                            />
                                                        ) : (
                                                            <Trash2 className="w-3 h-3 text-muted-foreground" />
                                                        )}
                                                    </button>
                                                </td>
                                            </motion.tr>
                                        ))}
                                    </AnimatePresence>
                                </tbody>
                            </table>
                            <div className="px-3 py-2 bg-muted border-t border-border text-[10px] text-muted-foreground">
                                {records.length} record{records.length !== 1 ? "s" : ""} total
                            </div>
                        </div>
                    )}
                </motion.div>
            </main>
        </div>
    );
}
