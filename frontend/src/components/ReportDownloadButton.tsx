import { useState } from "react";
import { Download } from "lucide-react";
import { motion } from "framer-motion";

interface ReportDownloadButtonProps {
  findings: any[];           // The findings from the scan
  scanType: string;           // e.g., "github", "social", "combined"
  target: string;             // e.g., repo name or username
  filesScanned: number;       // Total items scanned
  apiUrl: string;             // Base API URL from config
}

export const ReportDownloadButton = ({
  findings,
  scanType,
  target,
  filesScanned,
  apiUrl,
}: ReportDownloadButtonProps) => {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    if (findings.length === 0) return;

    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/report/html`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          findings,
          ess_results: [],           // Optional; could be passed if available
          scan_type: scanType,
          target: target,
          files_scanned: filesScanned,
        }),
      });

      if (!response.ok) throw new Error("Report generation failed");

      const html = await response.text();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aegis_report_${target.replace(/[^a-zA-Z0-9]/g, "_")}_${scanType}.html`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download error:", error);
      alert("Failed to generate report. Check console for details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={handleDownload}
      disabled={loading || findings.length === 0}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${
        findings.length === 0
          ? "bg-muted text-muted-foreground cursor-not-allowed"
          : "bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20"
      }`}
    >
      <Download className="w-3.5 h-3.5" />
      {loading ? "Generating..." : "Download Report"}
    </motion.button>
  );
};