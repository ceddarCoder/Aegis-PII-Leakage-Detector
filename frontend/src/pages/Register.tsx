import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Shield, Mail, Lock, Eye, EyeOff, User, AlertCircle } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function Register() {
    const { register } = useAuth();
    const navigate = useNavigate();

    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!fullName || !email || !password || !confirmPassword) {
            setError("Please fill in all fields");
            return;
        }
        if (password.length < 6) {
            setError("Password must be at least 6 characters");
            return;
        }
        if (password !== confirmPassword) {
            setError("Passwords do not match");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            await register(email, password, fullName);
            navigate("/", { replace: true });
        } catch (err: any) {
            setError(err.message || "Registration failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background grid-bg relative flex items-center justify-center px-4">
            <div className="fixed inset-0 scanline pointer-events-none z-50" />
            <div className="fixed top-0 left-1/4 w-96 h-64 bg-primary/5 blur-3xl rounded-full pointer-events-none" />
            <div className="fixed bottom-0 right-1/4 w-64 h-64 bg-accent/5 blur-3xl rounded-full pointer-events-none" />

            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="w-full max-w-md"
            >
                {/* Logo */}
                <div className="text-center mb-8">
                    <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: 0.1 }}
                        className="inline-flex items-center gap-3 mb-4"
                    >
                        <div className="relative">
                            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center">
                                <Shield className="w-7 h-7 text-primary" />
                            </div>
                            <div className="absolute -inset-1 bg-primary/20 rounded-xl blur-md -z-10" />
                        </div>
                        <div className="text-left">
                            <h1 className="text-2xl font-display font-extrabold text-primary text-glow tracking-tight">AEGIS</h1>
                            <p className="text-[10px] text-muted-foreground tracking-[0.2em] uppercase">PII Scanner</p>
                        </div>
                    </motion.div>
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.2 }}
                        className="text-sm text-muted-foreground"
                    >
                        Create a new account
                    </motion.p>
                </div>

                {/* Card */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="rounded-xl border border-border bg-card p-8 relative overflow-hidden"
                >
                    <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none" />
                    <div className="relative z-10">
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {error && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-sm"
                                >
                                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                    <span>{error}</span>
                                </motion.div>
                            )}

                            {/* Full Name */}
                            <div>
                                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">Full Name</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <input
                                        type="text"
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        placeholder="John Doe"
                                        autoComplete="name"
                                        className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border bg-input text-sm text-foreground font-mono placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-colors"
                                    />
                                </div>
                            </div>

                            {/* Email */}
                            <div>
                                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">Email</label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="you@example.com"
                                        autoComplete="email"
                                        className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border bg-input text-sm text-foreground font-mono placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-colors"
                                    />
                                </div>
                            </div>

                            {/* Password */}
                            <div>
                                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">Password</label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="Min 6 characters"
                                        autoComplete="new-password"
                                        className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-border bg-input text-sm text-foreground font-mono placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-colors"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>

                            {/* Confirm Password */}
                            <div>
                                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 block">Confirm Password</label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        placeholder="Repeat password"
                                        autoComplete="new-password"
                                        className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border bg-input text-sm text-foreground font-mono placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-colors"
                                    />
                                </div>
                            </div>

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 box-glow mt-2"
                            >
                                {loading ? (
                                    <motion.div
                                        animate={{ rotate: 360 }}
                                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                                        className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full"
                                    />
                                ) : (
                                    <>
                                        <Shield className="w-4 h-4" />
                                        Create Account
                                    </>
                                )}
                            </button>
                        </form>

                        <div className="mt-5 text-center">
                            <p className="text-xs text-muted-foreground">
                                Already have an account?{" "}
                                <Link to="/login" className="text-primary hover:text-primary/80 font-medium transition-colors">
                                    Sign in
                                </Link>
                            </p>
                        </div>
                    </div>
                </motion.div>

                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="text-center text-[10px] text-muted-foreground mt-6 tracking-wider"
                >
                    AEGIS PII SCANNER · HACKWITHAI 2026 · SECURE ACCESS
                </motion.p>
            </motion.div>
        </div>
    );
}
