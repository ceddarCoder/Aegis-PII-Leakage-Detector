import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    User, Plus, Trash2, Save, Radar, Github, MessageCircle,
    Globe, Mail, AlertTriangle, CheckCircle, Clock, ChevronDown,
    ChevronUp, Shield, RefreshCw, Linkedin, Twitter,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Header } from "@/components/Header";
import {
    getProfile, saveProfile, scanProfile, getLastProfileScan,
    type ProfileEntry, type UserProfile, type ProfileScanResult,
} from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────

const KIND_OPTIONS = [
    { value: "github", label: "GitHub", icon: Github },
    { value: "reddit", label: "Reddit", icon: MessageCircle },
    { value: "telegram", label: "Telegram", icon: MessageCircle },
    { value: "twitter", label: "Twitter", icon: Twitter },
    { value: "linkedin", label: "LinkedIn", icon: Linkedin },
    { value: "email", label: "Email", icon: Mail },
    { value: "website", label: "Website", icon: Globe },
    { value: "custom", label: "Custom", icon: Globe },
];

const KIND_PLACEHOLDERS: Record<string, string> = {
    github: "torvalds (username or profile URL)",
    reddit: "u/spez or just spez",
    telegram: "@channelusername",
    twitter: "@jack",
    linkedin: "linkedin.com/in/yourprofile",
    email: "you@example.com",
    website: "https://yoursite.com",
    custom: "any text or URL",
};

const riskColors: Record<string, string> = {
    CRITICAL: "text-red-400",
    HIGH: "text-orange-400",
    MEDIUM: "text-yellow-400",
    LOW: "text-green-400",
};

const essColor = (ess: number) =>
    ess >= 8 ? "text-red-400" : ess >= 6 ? "text-orange-400" : ess >= 4 ? "text-yellow-400" : "text-green-400";

const KindIcon = ({ kind, className }: { kind: string; className?: string }) => {
    const opt = KIND_OPTIONS.find((k) => k.value === kind);
    const Icon = opt?.icon ?? Globe;
    return <Icon className={className} />;
};

// ── Component ──────────────────────────────────────────────────────

export default function Profile() {
    const { toast } = useToast();

    // Profile map state
    const [entries, setEntries] = useState<ProfileEntry[]>([]);
    const [notes, setNotes] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Scan state
    const [scanning, setScanning] = useState(false);
    const [lastScan, setLastScan] = useState<ProfileScanResult | null>(null);
    const [showFindings, setShowFindings] = useState(false);

    // Load profile + last scan on mount
    useEffect(() => {
        Promise.all([
            getProfile().catch(() => ({ entries: [], notes: "" } as UserProfile)),
            getLastProfileScan().catch(() => null),
        ]).then(([profile, scan]) => {
            setEntries(profile.entries ?? []);
            setNotes(profile.notes ?? "");
            setLastScan(scan);
        }).finally(() => setLoading(false));
    }, []);

    // Entry CRUD
    const addEntry = () =>
        setEntries((prev) => [...prev, { kind: "github", label: "", value: "" }]);

    const removeEntry = (idx: number) =>
        setEntries((prev) => prev.filter((_, i) => i !== idx));

    const updateEntry = (idx: number, field: keyof ProfileEntry, val: string) =>
        setEntries((prev) => prev.map((e, i) => (i === idx ? { ...e, [field]: val } : e)));

    // Save
    const handleSave = useCallback(async () => {
        setSaving(true);
        try {
            await saveProfile({ entries, notes: notes || undefined });
            toast({ title: "Profile saved", description: "Your profile map has been updated." });
        } catch (err: unknown) {
            toast({ title: "Save failed", description: (err as Error).message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    }, [entries, notes, toast]);

    // Scan
    const handleScan = useCallback(async () => {
        if (entries.length === 0) {
            toast({ title: "No entries", description: "Add at least one entry before scanning.", variant: "destructive" });
            return;
        }
        setScanning(true);
        try {
            // Auto-save first so backend has latest entries
            await saveProfile({ entries, notes: notes || undefined });
            const result = await scanProfile();
            setLastScan(result);
            setShowFindings(true);
            toast({ title: "Scan complete", description: `${result.total_findings} finding(s) found.` });
        } catch (err: unknown) {
            toast({ title: "Scan failed", description: (err as Error).message, variant: "destructive" });
        } finally {
            setScanning(false);
        }
    }, [entries, notes, toast]);

    if (loading) {
        return (
            <div className="min-h-screen bg-background grid-bg">
                <Header />
                <div className="flex items-center justify-center min-h-[60vh]">
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                        className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full"
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background grid-bg relative">
            <div className="fixed inset-0 scanline pointer-events-none z-50" />
            <Header />

            <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">

                {/* Page header */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border border-border bg-card overflow-hidden relative"
                >
                    <div className="absolute inset-0 grid-bg opacity-40" />
                    <div className="absolute top-0 right-0 w-72 h-48 bg-primary/5 blur-3xl rounded-full pointer-events-none" />
                    <div className="relative p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center">
                                <User className="w-6 h-6 text-primary" />
                            </div>
                            <div>
                                <p className="text-[10px] text-primary tracking-[0.3em] uppercase font-semibold mb-1">Digital Footprint</p>
                                <h2 className="text-2xl font-display font-extrabold text-foreground">My Profile Map</h2>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    Store your online presence and scan for exposed PII
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                id="profile-scan-btn"
                                onClick={handleScan}
                                disabled={scanning}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary text-xs font-semibold hover:bg-primary/20 transition-all disabled:opacity-50"
                            >
                                {scanning ? (
                                    <motion.div
                                        animate={{ rotate: 360 }}
                                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                                        className="w-3.5 h-3.5 border-2 border-primary border-t-transparent rounded-full"
                                    />
                                ) : (
                                    <Radar className="w-3.5 h-3.5" />
                                )}
                                {scanning ? "Scanning…" : "Scan Now"}
                            </button>
                            <button
                                id="profile-save-btn"
                                onClick={handleSave}
                                disabled={saving}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-card border border-border text-foreground text-xs font-semibold hover:border-primary/30 transition-all disabled:opacity-50"
                            >
                                {saving ? (
                                    <motion.div
                                        animate={{ rotate: 360 }}
                                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                                        className="w-3.5 h-3.5 border-2 border-muted-foreground border-t-transparent rounded-full"
                                    />
                                ) : (
                                    <Save className="w-3.5 h-3.5" />
                                )}
                                {saving ? "Saving…" : "Save Profile"}
                            </button>
                        </div>
                    </div>
                </motion.div>

                {/* Profile map editor */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    className="rounded-xl border border-border bg-card p-6 space-y-4"
                >
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Entries ({entries.length})
                        </h3>
                        <button
                            id="profile-add-entry-btn"
                            onClick={addEntry}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-primary/40 text-primary text-xs hover:bg-primary/5 transition-all"
                        >
                            <Plus className="w-3.5 h-3.5" />
                            Add Entry
                        </button>
                    </div>

                    {entries.length === 0 ? (
                        <div className="text-center py-10 border border-dashed border-border rounded-lg">
                            <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-40" />
                            <p className="text-sm text-muted-foreground">No entries yet — add your GitHub, Reddit, socials…</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <AnimatePresence>
                                {entries.map((entry, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, y: -8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, x: -20 }}
                                        transition={{ duration: 0.18 }}
                                        className="flex items-start gap-2 p-3 rounded-lg border border-border bg-muted/20 hover:border-primary/20 transition-colors"
                                    >
                                        {/* Kind icon */}
                                        <div className="mt-1 w-6 h-6 flex items-center justify-center text-muted-foreground flex-shrink-0">
                                            <KindIcon kind={entry.kind} className="w-4 h-4" />
                                        </div>

                                        {/* Kind picker */}
                                        <select
                                            id={`entry-kind-${idx}`}
                                            value={entry.kind}
                                            onChange={(e) => updateEntry(idx, "kind", e.target.value)}
                                            className="bg-transparent border border-border rounded-md text-xs text-foreground px-2 py-1.5 focus:outline-none focus:border-primary/50 transition-colors flex-shrink-0"
                                        >
                                            {KIND_OPTIONS.map((k) => (
                                                <option key={k.value} value={k.value}>{k.label}</option>
                                            ))}
                                        </select>

                                        {/* Label */}
                                        <input
                                            id={`entry-label-${idx}`}
                                            type="text"
                                            placeholder="Label (e.g. Main)"
                                            value={entry.label}
                                            onChange={(e) => updateEntry(idx, "label", e.target.value)}
                                            className="flex-1 bg-transparent border border-border rounded-md text-xs text-foreground placeholder:text-muted-foreground px-2 py-1.5 focus:outline-none focus:border-primary/50 transition-colors min-w-0"
                                        />

                                        {/* Value */}
                                        <input
                                            id={`entry-value-${idx}`}
                                            type="text"
                                            placeholder={KIND_PLACEHOLDERS[entry.kind] ?? "value"}
                                            value={entry.value}
                                            onChange={(e) => updateEntry(idx, "value", e.target.value)}
                                            className="flex-[2] bg-transparent border border-border rounded-md text-xs text-foreground placeholder:text-muted-foreground px-2 py-1.5 focus:outline-none focus:border-primary/50 transition-colors font-mono min-w-0"
                                        />

                                        {/* Remove */}
                                        <button
                                            id={`entry-remove-${idx}`}
                                            onClick={() => removeEntry(idx)}
                                            className="mt-0.5 p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors flex-shrink-0"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    )}

                    {/* Notes */}
                    <div className="pt-2">
                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1.5">
                            Notes (optional)
                        </label>
                        <textarea
                            id="profile-notes"
                            rows={2}
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="E.g. Scan these before any job application…"
                            className="w-full bg-transparent border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground px-3 py-2 resize-none focus:outline-none focus:border-primary/50 transition-colors"
                        />
                    </div>
                </motion.div>

                {/* Last scan summary */}
                {lastScan && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.2 }}
                        className="rounded-xl border border-border bg-card p-6 space-y-4"
                    >
                        {/* Summary header */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Last Scan Results</h3>
                                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                    <Clock className="w-3 h-3" />
                                    {new Date(lastScan.scanned_at).toLocaleString()}
                                    <button
                                        id="profile-rescan-btn"
                                        onClick={handleScan}
                                        disabled={scanning}
                                        className="flex items-center gap-1 ml-2 text-primary hover:text-primary/70 transition-colors disabled:opacity-50"
                                    >
                                        <RefreshCw className="w-3 h-3" />
                                        Re-scan
                                    </button>
                                </div>
                            </div>

                            {/* ESS badge */}
                            <div className="flex items-center gap-4">
                                <div className="text-center">
                                    <p className={`text-3xl font-display font-extrabold ${essColor(lastScan.max_ess)}`}>
                                        {lastScan.max_ess.toFixed(1)}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">ESS Score</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-3xl font-display font-extrabold text-foreground">
                                        {lastScan.total_findings}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Findings</p>
                                </div>
                                <div className="px-3 py-1 rounded-full border border-border text-[10px] font-semibold uppercase tracking-wider"
                                    style={{ color: lastScan.max_ess >= 8 ? "#f87171" : lastScan.max_ess >= 6 ? "#fb923c" : lastScan.max_ess >= 4 ? "#facc15" : "#4ade80" }}>
                                    {lastScan.ess_label || "LOW"}
                                </div>
                            </div>
                        </div>

                        {/* PII type breakdown */}
                        {lastScan.ess_summary && lastScan.ess_summary.all_types.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {[...new Set(lastScan.ess_summary.all_types)].map((t) => (
                                    <span key={t} className="px-2 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20 uppercase">
                                        {t}
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* Empty state */}
                        {lastScan.total_findings === 0 && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-400/5 border border-green-400/20">
                                <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                                <p className="text-xs text-green-400 font-medium">No PII found across your profile entries. You look clean!</p>
                            </div>
                        )}

                        {/* Toggle findings table */}
                        {lastScan.total_findings > 0 && (
                            <div>
                                <button
                                    id="profile-toggle-findings-btn"
                                    onClick={() => setShowFindings((v) => !v)}
                                    className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/70 transition-colors font-semibold"
                                >
                                    {showFindings ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                    {showFindings ? "Hide" : "View"} {lastScan.total_findings} finding(s)
                                </button>

                                <AnimatePresence>
                                    {showFindings && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="overflow-hidden"
                                        >
                                            <div className="mt-3 overflow-x-auto rounded-lg border border-border">
                                                <table className="w-full text-xs">
                                                    <thead>
                                                        <tr className="border-b border-border bg-muted/30">
                                                            {["Type", "Masked Value", "Risk", "Source", "Confidence"].map((h) => (
                                                                <th key={h} className="text-left py-2 px-3 text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">{h}</th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {lastScan.findings.map((f, i) => (
                                                            <motion.tr
                                                                key={i}
                                                                initial={{ opacity: 0 }}
                                                                animate={{ opacity: 1 }}
                                                                transition={{ delay: i * 0.02 }}
                                                                className="border-b border-border/50 hover:bg-muted/40 transition-colors"
                                                            >
                                                                <td className="py-2 px-3">
                                                                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20 uppercase">
                                                                        {f.type}
                                                                    </span>
                                                                </td>
                                                                <td className="py-2 px-3 font-mono text-foreground">{f.value_masked}</td>
                                                                <td className={`py-2 px-3 font-bold uppercase ${riskColors[f.risk] || "text-muted-foreground"}`}>
                                                                    <div className="flex items-center gap-1">
                                                                        <AlertTriangle className="w-3 h-3" />
                                                                        {f.risk}
                                                                    </div>
                                                                </td>
                                                                <td className="py-2 px-3 text-muted-foreground max-w-[200px] truncate">
                                                                    {f.source_url ? (
                                                                        <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors">
                                                                            {f.source || f.file_path}
                                                                        </a>
                                                                    ) : (
                                                                        f.source || f.file_path
                                                                    )}
                                                                </td>
                                                                <td className="py-2 px-3 text-muted-foreground">
                                                                    {(f.confidence * 100).toFixed(0)}%
                                                                </td>
                                                            </motion.tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        )}
                    </motion.div>
                )}

                {/* Call-to-action if no scan yet */}
                {!lastScan && entries.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.3 }}
                        className="rounded-xl border border-dashed border-primary/30 bg-primary/5 p-8 text-center"
                    >
                        <Radar className="w-8 h-8 text-primary mx-auto mb-3 opacity-60" />
                        <p className="text-sm text-muted-foreground mb-4">
                            Profile saved — run a scan to check your digital footprint for exposed PII.
                        </p>
                        <button
                            onClick={handleScan}
                            disabled={scanning}
                            className="px-6 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/80 transition-all disabled:opacity-50"
                        >
                            {scanning ? "Scanning…" : "Run First Scan"}
                        </button>
                    </motion.div>
                )}
            </main>
        </div>
    );
}
