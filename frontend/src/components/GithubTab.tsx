import { useState } from "react";
import { motion } from "framer-motion";
import { Github, Search, ToggleLeft, ToggleRight } from "lucide-react";
import { scanGithubSingle, scanGithubUser, type ScanResponse } from "@/lib/api";
import { ScanProgress } from "./ScanProgress";
import { ScanResults } from "./ScanResults";

export function GithubTab() {
  const [mode, setMode] = useState<"single" | "user">("single");
  const [repo, setRepo] = useState("ceddarCoder/1b-1");
  const [branch, setBranch] = useState("main");
  const [username, setUsername] = useState("");
  const [maxFiles, setMaxFiles] = useState(40);
  const [maxRepos, setMaxRepos] = useState(5);
  const [useNlp, setUseNlp] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setResults(null);
    try {
      const res = mode === "single"
        ? await scanGithubSingle(repo, branch, maxFiles, useNlp)
        : await scanGithubUser(username, maxRepos, maxFiles, useNlp);
      setResults(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="rounded-lg border border-border bg-card p-6 space-y-4"
      >
        <div className="flex items-center gap-2 mb-2">
          <Github className="w-5 h-5 text-foreground" />
          <h2 className="font-display font-bold text-foreground">GitHub Repository Scanner</h2>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setMode("single")}
            className={`px-3 py-1.5 rounded text-xs font-medium border transition-all ${
              mode === "single"
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            Single Repo
          </button>
          <button
            onClick={() => setMode("user")}
            className={`px-3 py-1.5 rounded text-xs font-medium border transition-all ${
              mode === "user"
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            All User Repos
          </button>
        </div>

        {mode === "single" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Repository (owner/repo)</label>
              <input
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
                placeholder="owner/repo"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Branch</label>
              <input
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">GitHub Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
                placeholder="octocat"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Max Repos</label>
              <input
                type="number"
                value={maxRepos}
                onChange={(e) => setMaxRepos(Number(e.target.value))}
                min={1}
                max={30}
                className="mt-1 w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>
          </div>
        )}

        <div className="flex items-center gap-6">
          <div>
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Max Files / Repo</label>
            <input
              type="range"
              value={maxFiles}
              onChange={(e) => setMaxFiles(Number(e.target.value))}
              min={5}
              max={150}
              step={5}
              className="mt-1 w-32 accent-primary"
            />
            <span className="ml-2 text-xs text-foreground font-mono">{maxFiles}</span>
          </div>
          <button
            onClick={() => setUseNlp(!useNlp)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {useNlp ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
            NLP Filter
          </button>
        </div>

        <button
          onClick={handleScan}
          disabled={scanning || (mode === "single" ? !repo : !username)}
          className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 box-glow"
        >
          <Search className="w-4 h-4" />
          Scan GitHub
        </button>
      </motion.div>

      <ScanProgress scanning={scanning} message="Scanning GitHub repositories..." />
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
      {results && (
        <ScanResults
          results={results}
          scanType="github"
          target={mode === "single" ? repo : `user:${username}`}
        />
      )}
    </div>
  );
}
