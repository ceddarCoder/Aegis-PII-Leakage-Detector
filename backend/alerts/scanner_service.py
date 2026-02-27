"""
alerts/scanner_service.py - Background scanner that runs every N minutes
and broadcasts findings via WebSocket
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

from backend.detection.presidio_engine import presidio_scan
from backend.scrapers.github_scraper import get_all_files, fetch_file_content
from backend.scrapers.pastebin_scraper import get_recent_pastes, fetch_paste_raw
from backend.scrapers.telegram_scraper import scrape_telegram_channels_async
from backend.scoring.ess_calculator import calculate_ess

logger = logging.getLogger(__name__)

class AlertScanner:
    def __init__(self, websocket_manager):
        self.manager = websocket_manager
        self.running = False
        self.scan_interval = 300  # seconds (5 minutes default)
        self.last_findings: Dict[str, List[dict]] = {}  # Track previous findings to avoid duplicates
        self.scan_targets = {
            "github_repos": [],  # List of repos to scan
            "pastebin": True,     # Whether to scan pastebin
            "telegram_channels": []  # List of telegram channels
        }

    async def start(self, interval_seconds: int = 300):
        """Start the background scanner"""
        self.scan_interval = interval_seconds
        self.running = True
        logger.info(f"Alert scanner started, interval: {interval_seconds}s")
        
        while self.running:
            try:
                findings = await self.run_scan()
                
                if findings:
                    # Group findings by type/severity
                    critical = [f for f in findings if f.get("risk") == "Critical"]
                    high = [f for f in findings if f.get("risk") == "High"]
                    medium = [f for f in findings if f.get("risk") == "Medium"]
                    
                    # Prepare alert message
                    alert = {
                        "type": "alert_batch",
                        "timestamp": datetime.now().isoformat(),
                        "summary": {
                            "total": len(findings),
                            "critical": len(critical),
                            "high": len(high),
                            "medium": len(medium)
                        },
                        "findings": findings[:10],  # Send top 10 most severe
                        "sample_size": min(10, len(findings))
                    }
                    
                    # Broadcast to all connected clients
                    await self.manager.broadcast(alert)
                    
                    logger.info(f"Broadcast {len(findings)} findings")
                
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await self.manager.broadcast({
                    "type": "error",
                    "message": f"Scan failed: {str(e)}"
                })
            
            # Wait for next scan
            await asyncio.sleep(self.scan_interval)

    async def run_scan(self) -> List[dict]:
        """Execute the actual scan based on configured targets"""
        all_findings = []
        
        # Scan GitHub repos
        for repo in self.scan_targets["github_repos"]:
            try:
                files = get_all_files(repo["name"], repo.get("branch", "main"))
                text_files = [f for f in files if f["route"] == "text"][:repo.get("max_files", 20)]
                
                for file in text_files:
                    content = fetch_file_content(file["download_url"])
                    if content:
                        findings = presidio_scan(content, use_nlp=True)
                        for f in findings:
                            f["source"] = f"github:{repo['name']}"
                            f["source_url"] = file["download_url"]
                            f["detected_at"] = datetime.now().isoformat()
                            all_findings.append(f)
            except Exception as e:
                logger.error(f"GitHub scan error for {repo}: {e}")
        
        # Scan Pastebin
        if self.scan_targets["pastebin"]:
            try:
                pastes = get_recent_pastes(limit=10)
                for paste in pastes:
                    content = fetch_paste_raw(paste["raw_url"])
                    if content:
                        findings = presidio_scan(content, use_nlp=True)
                        for f in findings:
                            f["source"] = f"pastebin:{paste['paste_id']}"
                            f["source_url"] = paste["url"]
                            f["detected_at"] = datetime.now().isoformat()
                            all_findings.append(f)
            except Exception as e:
                logger.error(f"Pastebin scan error: {e}")
        
        # Scan Telegram channels
        for channel in self.scan_targets["telegram_channels"]:
            try:
                messages = await scrape_telegram_channels_async([channel], limit=20)
                for msg in messages:
                    findings = presidio_scan(msg["content"], use_nlp=True)
                    for f in findings:
                        f["source"] = f"telegram:{channel}"
                        f["source_url"] = msg["url"]
                        f["detected_at"] = datetime.now().isoformat()
                        all_findings.append(f)
            except Exception as e:
                logger.error(f"Telegram scan error for {channel}: {e}")
        
        # Deduplicate by content hash
        unique = {}
        for f in all_findings:
            key = f"{f['type']}:{f['value']}"
            if key not in unique:
                unique[key] = f
        
        return list(unique.values())

    def configure_targets(self, github_repos: list = None, 
                          scan_pastebin: bool = True,
                          telegram_channels: list = None):
        """Update scan targets"""
        if github_repos is not None:
            self.scan_targets["github_repos"] = github_repos
        self.scan_targets["pastebin"] = scan_pastebin
        if telegram_channels is not None:
            self.scan_targets["telegram_channels"] = telegram_channels

    def stop(self):
        """Stop the scanner"""
        self.running = False
        logger.info("Alert scanner stopped")