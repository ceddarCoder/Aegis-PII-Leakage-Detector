"""
models.py — SQLAlchemy ORM models for Aegis.

Schema:
  User          — registered user account
  ScanHistory   — lightweight per-user scan history record
  ScanSession   — one scan run (covers one or more sources)
  LeakRecord    — one PII finding within a session
  Platform      — GitHub repo or Pastebin paste metadata
  ESSRecord     — Exposure Severity Score per source
"""

import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Text, Boolean,
    DateTime, ForeignKey, JSON, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class User(Base):
    """
    A registered Aegis user.
    Passwords are stored as bcrypt hashes — no plain-text is ever persisted.
    """
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    email           = Column(String(256), unique=True, nullable=False, index=True)
    full_name       = Column(String(256), nullable=False, default="")
    hashed_password = Column(String(512), nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)
    last_login      = Column(DateTime, nullable=True)

    scan_history = relationship("ScanHistory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class ScanHistory(Base):
    """
    Lightweight record of a completed scan, linked to a user.
    Full findings are stored on the client (localStorage); this table stores
    summary metadata for the Dashboard and History pages.
    """
    __tablename__ = "scan_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    scan_type       = Column(String(50))    # 'github', 'pastebin', 'social', 'combined'
    target          = Column(String(512))   # repo name / username / 'pastebin_recent'
    findings_count  = Column(Integer, default=0)
    max_ess         = Column(Float, default=0.0)
    ess_label       = Column(String(20), default="")
    sources_scanned = Column(Integer, default=0)
    scan_duration   = Column(Float, default=0.0)
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="scan_history")

    def __repr__(self):
        return f"<ScanHistory id={self.id} user_id={self.user_id} type={self.scan_type}>"

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "scan_type":        self.scan_type,
            "target":           self.target,
            "findings_count":   self.findings_count,
            "max_ess":          self.max_ess,
            "ess_label":        self.ess_label,
            "sources_scanned":  self.sources_scanned,
            "scan_duration":    self.scan_duration,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }


class ScanSession(Base):
    """
    Represents a single scan triggered by the user.
    Contains metadata about what was scanned and when.
    """
    __tablename__ = "scan_sessions"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    started_at     = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at   = Column(DateTime, nullable=True)
    scan_type      = Column(String(50))   # 'github', 'pastebin', 'combined'
    target         = Column(String(512))  # repo name, username, or 'pastebin_recent'
    total_files    = Column(Integer, default=0)
    total_findings = Column(Integer, default=0)
    max_ess        = Column(Float, default=0.0)
    avg_ess        = Column(Float, default=0.0)

    # Relationships
    platforms = relationship("Platform", back_populates="session", cascade="all, delete-orphan")
    leaks     = relationship("LeakRecord", back_populates="session", cascade="all, delete-orphan")
    ess_scores = relationship("ESSRecord", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ScanSession id={self.id} type={self.scan_type} target={self.target}>"


class Platform(Base):
    """
    A source that was scanned: a GitHub repo or a Pastebin paste.
    """
    __tablename__ = "platforms"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    platform     = Column(String(50))    # 'github' | 'pastebin'
    identifier   = Column(String(512))   # 'owner/repo' or paste_id
    url          = Column(String(1024), nullable=True)
    branch       = Column(String(100), nullable=True)
    scanned_at   = Column(DateTime, default=datetime.datetime.utcnow)
    file_count   = Column(Integer, default=0)
    finding_count = Column(Integer, default=0)
    ess_score    = Column(Float, default=0.0)
    is_public    = Column(Boolean, default=True)

    session = relationship("ScanSession", back_populates="platforms")
    leaks   = relationship("LeakRecord", back_populates="platform", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Platform {self.platform}:{self.identifier}>"


class LeakRecord(Base):
    """
    A single detected PII instance within a scanned source.
    """
    __tablename__ = "leak_records"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    platform_id  = Column(Integer, ForeignKey("platforms.id"), nullable=False)

    # Source location
    file_path    = Column(String(1024), nullable=True)   # e.g. "src/config.py"
    source_url   = Column(String(1024), nullable=True)   # direct link to file/paste
    line_start   = Column(Integer, nullable=True)
    char_start   = Column(Integer, nullable=True)
    char_end     = Column(Integer, nullable=True)

    # Detection details
    entity_type  = Column(String(100))   # e.g. 'AADHAAR', 'PAN'
    value_masked = Column(String(256))   # e.g. '1234****9012'
    snippet      = Column(Text)          # surrounding context (no raw PII stored)
    confidence   = Column(Float)
    risk         = Column(String(20))    # 'Critical' | 'High' | 'Medium' | 'Low'
    annotation   = Column(Text, nullable=True)  # validator notes

    # Scoring
    ess_contribution = Column(Float, default=0.0)

    # Timestamps
    detected_at  = Column(DateTime, default=datetime.datetime.utcnow)

    # Cross-platform linkage (for correlation)
    identity_cluster_id = Column(String(64), nullable=True)

    # Relationships
    session  = relationship("ScanSession", back_populates="leaks")
    platform = relationship("Platform", back_populates="leaks")

    def __repr__(self):
        return f"<LeakRecord {self.entity_type} @ {self.file_path} conf={self.confidence}>"

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "entity_type":   self.entity_type,
            "value_masked":  self.value_masked,
            "snippet":       self.snippet,
            "confidence":    self.confidence,
            "risk":          self.risk,
            "annotation":    self.annotation,
            "file_path":     self.file_path,
            "source_url":    self.source_url,
            "detected_at":   self.detected_at.isoformat() if self.detected_at else None,
        }


class ESSRecord(Base):
    """
    Exposure Severity Score per source, per session.
    """
    __tablename__ = "ess_records"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    session_id         = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    platform_id        = Column(Integer, ForeignKey("platforms.id"), nullable=True)

    source_identifier  = Column(String(512))
    ess_score          = Column(Float)
    ess_label          = Column(String(20))   # 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
    base_score         = Column(Float)
    toxic_combo        = Column(String(100))
    toxic_multiplier   = Column(Float)
    exposure_multiplier = Column(Float)
    types_found        = Column(JSON)          # list of entity type strings
    breakdown          = Column(JSON)          # full scoring breakdown
    calculated_at      = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ScanSession", back_populates="ess_scores")

    def __repr__(self):
        return f"<ESSRecord {self.source_identifier} score={self.ess_score} label={self.ess_label}>"
