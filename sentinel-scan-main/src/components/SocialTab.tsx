import { useState } from "react";
import { motion } from "framer-motion";
import { MessageCircle, Search, ToggleLeft, ToggleRight } from "lucide-react";
import { scanSocial, type ScanResponse } from "@/lib/api";
import { ScanProgress } from "./ScanProgress";
import { ScanResults } from "./ScanResults";

export function SocialTab() {
  const [redditEnabled, setRedditEnabled] = useState(true);
  const [redditUser, setRedditUser] = useState("");
  const [redditPosts, setRedditPosts] = useState(20);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramChannels, setTelegramChannels] = useState("");
  const [telegramMsgs, setTelegramMsgs] = useState(50);
  const [useNlp, setUseNlp] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setResults(null);
    try {
      const channels = telegramEnabled
        ? telegramChannels.split("\n").map((c) => c.trim()).filter(Boolean)
        : undefined;
      setResults(
        await scanSocial({
          reddit_username: redditEnabled ? redditUser : undefined,
          reddit_max_posts: redditPosts,
          telegram_channels: channels,
          telegram_messages_per_channel: telegramMsgs,
          use_nlp: useNlp,
        })
      );
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
          <MessageCircle className="w-5 h-5 text-foreground" />
          <h2 className="font-display font-bold text-foreground">Social Media Scanner</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Reddit */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-reddit/10 text-reddit border border-reddit/30">
                Reddit
              </span>
              <button
                onClick={() => setRedditEnabled(!redditEnabled)}
                className="text-xs text-muted-foreground"
              >
                {redditEnabled ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
              </button>
            </div>
            <input
              value={redditUser}
              onChange={(e) => setRedditUser(e.target.value)}
              disabled={!redditEnabled}
              placeholder="username (without u/)"
              className="w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50 disabled:opacity-40"
            />
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Max Posts</label>
              <input
                type="range"
                value={redditPosts}
                onChange={(e) => setRedditPosts(Number(e.target.value))}
                min={5}
                max={50}
                step={5}
                disabled={!redditEnabled}
                className="mt-1 w-full accent-primary"
              />
              <span className="text-xs text-foreground font-mono">{redditPosts}</span>
            </div>
          </div>

          {/* Telegram */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-telegram/10 text-telegram border border-telegram/30">
                Telegram
              </span>
              <button
                onClick={() => setTelegramEnabled(!telegramEnabled)}
                className="text-xs text-muted-foreground"
              >
                {telegramEnabled ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
              </button>
            </div>
            <textarea
              value={telegramChannels}
              onChange={(e) => setTelegramChannels(e.target.value)}
              disabled={!telegramEnabled}
              placeholder={"channel1\nchannel2"}
              rows={3}
              className="w-full px-3 py-2 rounded border border-border bg-input text-sm font-mono text-foreground focus:outline-none focus:border-primary/50 disabled:opacity-40 resize-none"
            />
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Messages / Channel</label>
              <input
                type="range"
                value={telegramMsgs}
                onChange={(e) => setTelegramMsgs(Number(e.target.value))}
                min={10}
                max={200}
                step={10}
                disabled={!telegramEnabled}
                className="mt-1 w-full accent-primary"
              />
              <span className="text-xs text-foreground font-mono">{telegramMsgs}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 pt-2 border-t border-border">
          <button
            onClick={() => setUseNlp(!useNlp)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {useNlp ? <ToggleRight className="w-5 h-5 text-primary" /> : <ToggleLeft className="w-5 h-5" />}
            NLP Filter
          </button>
          <button
            onClick={handleScan}
            disabled={scanning || (!redditEnabled && !telegramEnabled)}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 box-glow"
          >
            <Search className="w-4 h-4" />
            Scan Social Media
          </button>
        </div>
      </motion.div>

      <ScanProgress scanning={scanning} message="Scanning social media..." />
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
      {results && (
        <ScanResults
          results={results}
          scanType="social"
          target={[
            redditEnabled && redditUser ? `reddit:${redditUser}` : null,
            telegramEnabled && telegramChannels.trim() ? `telegram:${telegramChannels.split('\n').map(c => c.trim()).filter(Boolean).join(',')}` : null
          ].filter(Boolean).join('+') || "social"}
        />
      )}
    </div>
  );
}
