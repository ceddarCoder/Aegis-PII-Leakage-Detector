import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
    Shield, Github, FileText, MessageCircle, Link,
    AlertTriangle, Clock, Activity, TrendingUp, History,
    ArrowRight, Radar, Eye, Lock,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { getScanHistory, type ScanHistoryItem } from "@/lib/api";
import { Header } from "@/components/Header";

const riskColors: Record<string, string> = {
    CRITICAL: "text-red-400",
    HIGH: "text-orange-400",
    MEDIUM: "text-yellow-400",
    LOW: "text-green-400",
};

export default function Dashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [history, setHistory] = useState<ScanHistoryItem[]>([]);
    const [loadingHistory, setLoadingHistory] = useState(true);

    useEffect(() => {
        getScanHistory()
            .then(setHistory)
            .catch(() => setHistory([]))
            .finally(() => setLoadingHistory(false));
    }, []);

    const totalFindings = history.reduce((s, h) => s + h.findings_count, 0);
    const highestEss = history.length > 0 ? Math.max(...history.map((h) => h.max_ess)) : 0;
    const recentScans = history.slice(0, 5);

    return (
        <div className="min-h-screen bg-background grid-bg relative">
            <div className="fixed inset-0 scanline pointer-events-none z-50" />
            <Header />

            <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
                {/* Welcome */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border border-border bg-card overflow-hidden relative"
                >
                    <div className="absolute inset-0 grid-bg opacity-40" />
                    <div className="absolute top-0 right-0 w-80 h-64 bg-primary/5 blur-3xl rounded-full pointer-events-none" />
                    <div className="relative p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                        <div>
                            <p className="text-[10px] text-primary tracking-[0.3em] uppercase font-semibold mb-2">Welcome back</p>
                            <h2 className="text-3xl font-display font-extrabold text-foreground leading-tight">
                                {user?.full_name ? user.full_name : user?.email?.split("@")[0]}
                            </h2>
                            <p className="text-sm text-muted-foreground mt-1">{user?.email}</p>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
                            </span>
                            <span className="text-[10px] text-muted-foreground font-mono tracking-wider">ACTIVE SESSION</span>
                        </div>
                    </div>
                </motion.div>

                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: "Total Scans", value: history.length, icon: Radar, color: "text-primary" },
                        { label: "Total Findings", value: totalFindings, icon: AlertTriangle, color: "text-orange-400" },
                        { label: "Max ESS Score", value: highestEss.toFixed(1), icon: TrendingUp, color: highestEss >= 8 ? "text-red-400" : highestEss >= 6 ? "text-orange-400" : highestEss >= 4 ? "text-yellow-400" : "text-green-400" },
                        { label: "Sources Scanned", value: history.reduce((s, h) => s + h.sources_scanned, 0), icon: Eye, color: "text-accent" },
                    ].map(({ label, value, icon: Icon, color }, i) => (
                        <motion.div
                            key={label}
                            initial={{ opacity: 0, y: 15 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.08 }}
                            className="rounded-lg border border-border bg-card p-5 flex items-center gap-3"
                        >
                            <Icon className={`w-5 h-5 ${color} flex-shrink-0`} />
                            <div>
                                <p className="text-2xl font-display font-bold text-foreground">{value}</p>
                                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
                            </div>
                        </motion.div>
                    ))}
                </div>

                {/* Quick launch */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="rounded-xl border border-border bg-card p-6"
                >
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">Quick Scan</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                            { label: "GitHub", icon: Github, tab: "github" },
                            { label: "Pastebin", icon: FileText, tab: "pastebin" },
                            { label: "Social", icon: MessageCircle, tab: "social" },
                            { label: "Combined", icon: Link, tab: "combined" },
                        ].map(({ label, icon: Icon, tab }) => (
                            <button
                                key={tab}
                                onClick={() => navigate(`/?tab=${tab}`)}
                                className="flex items-center gap-2 p-3 rounded-lg border border-border hover:border-primary/40 hover:bg-primary/5 transition-all group text-left"
                            >
                                <Icon className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                                <span className="text-xs font-medium text-foreground">{label}</span>
                                <ArrowRight className="w-3 h-3 text-muted-foreground ml-auto group-hover:text-primary transition-colors" />
                            </button>
                        ))}
                    </div>
                </motion.div>

                {/* Recent scans */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="rounded-xl border border-border bg-card p-6"
                >
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent Scans</h3>
                        <button
                            onClick={() => navigate("/history")}
                            className="flex items-center gap-1 text-[11px] text-primary hover:text-primary/80 transition-colors"
                        >
                            <History className="w-3 h-3" />
                            View all
                        </button>
                    </div>

                    {loadingHistory ? (
                        <div className="flex items-center justify-center py-8">
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                                className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full"
                            />
                        </div>
                    ) : recentScans.length === 0 ? (
                        <div className="text-center py-8">
                            <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-40" />
                            <p className="text-sm text-muted-foreground">No scans yet. Run your first scan!</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-border">
                                        <th className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px]">Type</th>
                                        <th className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px]">Target</th>
                                        <th className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px]">Findings</th>
                                        <th className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px]">ESS</th>
                                        <th className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px]">Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentScans.map((scan, i) => (
                                        <motion.tr
                                            key={scan.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            transition={{ delay: i * 0.05 }}
                                            className="border-b border-border/50 hover:bg-muted/40 transition-colors"
                                        >
                                            <td className="py-2.5 px-3">
                                                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20 capitalize">
                                                    {scan.scan_type}
                                                </span>
                                            </td>
                                            <td className="py-2.5 px-3 font-mono text-foreground max-w-[150px] truncate">{scan.target}</td>
                                            <td className="py-2.5 px-3 text-foreground font-bold">{scan.findings_count}</td>
                                            <td className="py-2.5 px-3">
                                                <span className={`font-bold ${riskColors[scan.ess_label] || "text-muted-foreground"}`}>
                                                    {scan.max_ess.toFixed(1)}
                                                </span>
                                            </td>
                                            <td className="py-2.5 px-3 text-muted-foreground">
                                                {scan.created_at ? new Date(scan.created_at).toLocaleDateString() : "—"}
                                            </td>
                                        </motion.tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </motion.div>
            </main>
        </div>
    );
}
