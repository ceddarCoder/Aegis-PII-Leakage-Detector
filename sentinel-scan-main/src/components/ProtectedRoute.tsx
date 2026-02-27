// src/components/ProtectedRoute.tsx
// Redirects unauthenticated users to /login; shows spinner during auth check

import { Navigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth();
    const location = useLocation();

    if (isLoading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                    className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent"
                />
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <>{children}</>;
}
