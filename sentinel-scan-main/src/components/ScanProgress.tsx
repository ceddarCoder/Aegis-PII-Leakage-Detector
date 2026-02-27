import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";

interface ScanProgressProps {
  scanning: boolean;
  message?: string;
}

export function ScanProgress({ scanning, message }: ScanProgressProps) {
  return (
    <AnimatePresence>
      {scanning && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex items-center gap-3"
        >
          <Loader2 className="w-4 h-4 text-primary animate-spin" />
          <div>
            <p className="text-sm text-primary font-medium">{message || "Scanning..."}</p>
            <div className="mt-2 h-1 w-48 bg-muted rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-primary rounded-full"
                initial={{ width: "0%" }}
                animate={{ width: "100%" }}
                transition={{ duration: 30, ease: "linear" }}
              />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
