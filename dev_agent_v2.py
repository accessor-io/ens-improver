
#!/usr/bin/env python3
"""
ENS.tools Autonomous Development Agent v2 (ENS-AUTO-DEV)
========================================================

Enterprise‑grade autonomous development agent implementing:
- AUTONOMOUS_CYCLE_ENGINE
- CODE_ANALYSIS_FRAMEWORK
- IMPROVEMENT_GENERATION_SYSTEM
- TEST_AUTOMATION_FRAMEWORK
- FRONTEND_VALIDATION_MATRIX
- AUTONOMOUS_IMPLEMENTATION_ENGINE
- COMPREHENSIVE_LOGGING_SYSTEM

Architecture: AGENT_SYSTEM_MAP + AUTONOMOUS_ENGINE v2
"""

import ast
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

# =============================================================================
# CONFIGURATION
# =============================================================================
WORKSPACE = "/Users/acc/ens.tools"
AGENT_DIR = Path(__file__).parent
LOG_FILE = AGENT_DIR / "autonomous_dev.log"
STATE_FILE = AGENT_DIR / ".autonomous_state.json"
ERROR_LOG = AGENT_DIR / "errors.log"
SUCCESS_LOG = AGENT_DIR / "success.log"
IMPROVEMENTS_FILE = AGENT_DIR / "improvements.log"

MODEL = "openrouter/nvidia/nemotron-3-nano-30b-a3b:free"
CYCLE_INTERVAL = 60
MAX_ERRORS_BEFORE_PAUSE = 5
VERBOSE = True  # Stream subprocess output, extra traces. Use -q to disable.

T = TypeVar("T")

def trace(msg: str, flush: bool = True) -> None:
    """Print to stdout immediately (unbuffered). Use -q to reduce output."""
    if VERBOSE:
        print(msg, flush=flush)

# =============================================================================
# BASE CLASSES
# =============================================================================

@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    category: str
    message: str
    details: Optional[str] = None


class AgentComponent(ABC):
    """Base class for all agent components."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize component."""
        ...

    @abstractmethod
    def validate(self) -> bool:
        """Validate component state."""
        ...

# =============================================================================
# LOGGING SYSTEM
# =============================================================================

class AutonomousLogger(AgentComponent):
    """Comprehensive logging for all agent activities."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.error_count = 0
        self.success_count = 0
        self.improvements_suggested = 0
        self.implementations_completed = 0
        self.log_history: List[LogEntry] = []

    # --------------------------------------------------------------------- #
    # Component lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        """Create log files if missing."""
        try:
            for f in [LOG_FILE, ERROR_LOG, SUCCESS_LOG, IMPROVEMENTS_FILE]:
                if not f.exists():
                    f.write_text("")
            return True
        except Exception:
            return False

    def validate(self) -> bool:
        """Check write permission on the main log file."""
        try:
            with open(LOG_FILE, "a") as f:
                f.write("")
            return True
        except Exception:
            return False

    # --------------------------------------------------------------------- #
    # Singleton accessor
    # --------------------------------------------------------------------- #
    @classmethod
    def instance(cls) -> "AutonomousLogger":
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --------------------------------------------------------------------- #
    # Low‑level logging helpers
    # --------------------------------------------------------------------- #
    def _write_log(self, category: str, message: str, file_path: Path, details: str = ""):
        """Append a JSON line to *file_path* and keep an in‑memory copy."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "category": category.upper(),
            "message": message,
            "details": details,
        }
        with open(file_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        self.log_history.append(
            LogEntry(timestamp=timestamp, category=category.upper(), message=message, details=details)
        )
        print(f"[{timestamp}] [{category.upper()}] {message}", flush=True)

    # --------------------------------------------------------------------- #
    # Public logging API
    # --------------------------------------------------------------------- #
    def log(self, category: str, message: str, details: str = ""):
        self._write_log(category, message, LOG_FILE, details)

    @classmethod
    def log_error(cls, component: str, error: str, context: str = "") -> None:
        """Record an error and pause if the error limit is reached."""
        instance = cls.instance()
        instance.error_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "component": component,
            "error": error,
            "context": context,
        }
        with open(ERROR_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        instance.log("ERROR", f"{component}: {error}")

        if instance.error_count >= MAX_ERRORS_BEFORE_PAUSE:
            instance.log("PAUSE", f"Too many errors ({instance.error_count}), pausing...")
            time.sleep(3)

    @classmethod
    def log_success(cls, action: str, result: str, details: str = "") -> None:
        """Record a successful operation."""
        instance = cls.instance()
        instance.success_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "action": action,
            "result": result,
            "details": details,
        }
        with open(SUCCESS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        instance.log("SUCCESS", f"{action}: {result}")

    @classmethod
    def log_improvement(cls, area: str, suggestion: str, priority: str) -> None:
        """Record an improvement suggestion."""
        instance = cls.instance()
        instance.improvements_suggested += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "area": area,
            "suggestion": suggestion,
            "priority": priority,
        }
        with open(IMPROVEMENTS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        instance.log("IMPROVE", f"[{priority}] {area}: {suggestion}")

    def get_stats(self) -> Dict[str, int]:
        """Return aggregated statistics."""
        return {
            "errors": self.error_count,
            "successes": self.success_count,
            "improvements": self.improvements_suggested,
            "implementations": self.implementations_completed,
        }

# =============================================================================
# CODE ANALYSIS ENGINE
# =============================================================================

class CodeAnalysisResult:
    """Result of a workspace analysis."""

    def __init__(self):
        self.file_count = 0
        self.line_count = 0
        self.function_count = 0
        self.issue_count = 0
        self.todo_count = 0
        self.fixme_count = 0
        self.components_found = 0
        self.hooks_found = 0
        self.type_violations = 0
        self.files_analyzed: List[Dict] = []

    def to_dict(self) -> Dict:
        return self.__dict__

    def summary(self) -> str:
        return f"Files: {self.file_count}, Issues: {self.issue_count}, TODOs: {self.todo_count}"


class CodeAnalyzer(AgentComponent):
    """Analyzes a codebase for potential improvements."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.components = defaultdict(list)
        self.analysis_result = CodeAnalysisResult()

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def count_issues(content: str) -> int:
        issues = 0
        if "console.log" in content:
            issues += content.count("console.log")
        if " any" in content:
            issues += content.count(" any")
        if "// @ts-ignore" in content:
            issues += content.count("// @ts-ignore")
        return issues

    @classmethod
    def analyze_file(cls, filepath: Path) -> Dict[str, Any]:
        """Return a dictionary with analysis data for *filepath*."""
        if not filepath.exists():
            return {}

        try:
            content = filepath.read_text()
            lines = content.split("\n")

            result = {
                "file": str(filepath),
                "hash": cls.hash_content(content),
                "lines": len(lines),
                "functions": [],
                "issues": [],
                "todos": [],
                "fixmes": [],
                "imports": [],
                "ast_errors": [],
                "types_used": [],
                "components": [],
            }

            # -----------------------------------------------------------------
            # Comment & TODO/FIXME detection
            # -----------------------------------------------------------------
            for i, line in enumerate(lines, 1):
                line_upper = line.upper()
                if "TODO" in line_upper:
                    result["todos"].append({"line": i, "content": line.strip()})
                if any(kw in line_upper for kw in ["FIXME", "BUG", "HACK", "XXX"]):
                    result["fixmes"].append({"line": i, "content": line.strip()})

            # -----------------------------------------------------------------
            # AST parsing for functions & type usage
            # -----------------------------------------------------------------
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        result["functions"].append(
                            {
                                "name": node.name,
                                "lineno": node.lineno,
                                "args": [arg.arg for arg in node.args.args],
                                "returns": getattr(node.returns, "id", "unknown")
                                if node.returns
                                else "void",
                            }
                        )
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                if target.id.endswith("Type") or target.id.endswith("Interface"):
                                    result["types_used"].append(target.id)
            except SyntaxError as e:
                result["ast_errors"].append(str(e))

            # -----------------------------------------------------------------
            # Simple issue detection
            # -----------------------------------------------------------------
            if "console.log" in content:
                result["issues"].append("Console statements present")
            if filepath.suffix in [".ts", ".tsx"]:
                if " any " in content:
                    result["issues"].append("TypeScript 'any' type usage")
                if "// @ts-ignore" in content:
                    result["issues"].append("TypeScript ignore directives")

            # -----------------------------------------------------------------
            # React component / hook detection (TSX only)
            # -----------------------------------------------------------------
            if filepath.suffix == ".tsx":
                component_match = re.search(r"export\s+(?:default\s+)?(?:function|const)\s+(\w+)", content)
                if component_match:
                    result["components"].append(component_match.group(1))

                hooks = re.findall(r"use[A-Z][a-zA-Z]+", content)
                if hooks:
                    result["hooks_used"] = list(set(hooks))

            return result

        except Exception as e:
            AutonomousLogger.log_error("CodeAnalyzer", str(e), str(filepath))
            return {}

    @staticmethod
    def extract_imports(content: str) -> List[str]:
        """Return a list of import paths."""
        return re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content, re.DOTALL)

    @staticmethod
    def check_dependencies(content: str) -> Dict[str, bool]:
        """Detect presence of common libraries."""
        lower = content.lower()
        return {
            "has_web3": "web3" in lower,
            "has_viem": "viem" in lower,
            "has_react_query": "react-query" in lower or "@tanstack/react-query" in lower,
            "has_wagmi": "wagmi" in lower,
            "has_zustand": "zustand" in lower,
            "has_redux": "redux" in lower,
        }

    # --------------------------------------------------------------------- #
    # Workspace‑wide analysis
    # --------------------------------------------------------------------- #
    def analyze_workspace(self) -> CodeAnalysisResult:
        workspace = Path(WORKSPACE)
        result = self.analysis_result
        result.files_analyzed = []

        if not workspace.exists():
            return result

        total = 0
        for filepath in workspace.rglob("*"):
            if not filepath.is_file() or filepath.name.startswith("."):
                continue

            ext = filepath.suffix.lower()
            if ext in [".ts", ".tsx"]:
                if VERBOSE and total > 0 and total % 25 == 0:
                    trace(f"  ... analyzed {total} TS/TSX files so far ...")
                analysis = self.analyze_file(filepath)
                if not analysis:
                    continue

                result.files_analyzed.append(analysis)
                result.file_count += 1
                result.line_count += analysis.get("lines", 0)
                result.function_count += len(analysis.get("functions", []))
                result.issue_count += len(analysis.get("issues", []))
                result.todo_count += len(analysis.get("todos", []))
                result.fixme_count += len(analysis.get("fixmes", []))

                if analysis.get("components"):
                    result.components_found += len(analysis["components"])
                if analysis.get("hooks_used"):
                    result.hooks_found += len(analysis["hooks_used"])
                total += 1

            elif ext in [".css", ".scss", ".json"]:
                result.file_count += 1

        return result

    def get_component_map(self) -> Dict[str, List[str]]:
        """Map source files to logical component categories."""
        workspace = Path(WORKSPACE)
        component_map = {
            "components": [],
            "hooks": [],
            "utils": [],
            "types": [],
            "pages": [],
            "services": [],
            "styles": [],
        }

        # ── React components & hooks ──
        for filepath in workspace.rglob("*.tsx"):
            name = filepath.stem
            content = filepath.read_text()

            if re.search(r"(?:function|const)\s+\w+\s*=\s*(?:props\s*=>|React\.(?:FC|memo))", content):
                component_map["components"].append(str(filepath))
            elif name.startswith("use"):
                component_map["hooks"].append(str(filepath))
            elif any(k in name.lower() for k in ("page", "view")):
                component_map["pages"].append(str(filepath))

        # ── TypeScript utils & types ──
        for filepath in workspace.rglob("*.ts"):
            if filepath.stem.endswith(".d"):
                component_map["types"].append(str(filepath))
            elif any(k in filepath.name.lower() for k in ("util", "helper")):
                component_map["utils"].append(str(filepath))

        # ── Services (network calls) ──
        for filepath in workspace.rglob("*.ts"):
            if any(k in filepath.read_text() for k in ("fetch(", "axios.", "http://", "https://")):
                component_map["services"].append(str(filepath))

        # ── Styles ──
        for filepath in workspace.rglob("*.css"):
            component_map["styles"].append(str(filepath))

        return component_map
# =============================================================================
# IMPROVEMENT GENERATOR
# =============================================================================

@dataclass
class ImprovementSuggestion:
    """Structure describing a suggested improvement."""
    area: str
    feature: str
    description: str
    priority: str
    estimated_effort: str
    dependencies: List[str]

    def to_dict(self) -> Dict:
        return self.__dict__


class ImprovementGenerator(AgentComponent):
    """Generates creative improvement suggestions for ENS.tools."""

    # ── Core feature catalogue ──
    ENS_CORE_FEATURES = [
        # ── Domain & Portfolio Management ──
        {
            "area": "portfolio",
            "feature": "Unified multi-chain ENS portfolio view",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "portfolio",
            "feature": "Bulk domain import from CSV / clipboard",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "portfolio",
            "feature": "Domain expiration & renewal alerts (email/push)",
            "priority": "HIGH",
            "effort": "LOW",
        },
        {
            "area": "portfolio",
            "feature": "Favorites / watchlist with expiry notifications",
            "priority": "HIGH",
            "effort": "LOW",
        },
        {
            "area": "portfolio",
            "feature": "Tagging & custom labels system",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "portfolio",
            "feature": "Smart grouping (by chain / namespace / owner)",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "portfolio",
            "feature": "Portfolio analytics (total value, gas spent…)",
            "priority": "LOW",
            "effort": "HIGH",
        },

        # ── Records & Profile ──
        {
            "area": "records",
            "feature": "Batch / multi-record editor & updater",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "records",
            "feature": "Record templates & presets (social, wallet…)",
            "priority": "HIGH",
            "effort": "LOW",
        },
        {
            "area": "records",
            "feature": "Rich profile builder (avatar, banner, description, social links)",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "records",
            "feature": "Reverse record (addr → name) quick toggle",
            "priority": "HIGH",
            "effort": "LOW",
        },
        {
            "area": "records",
            "feature": "Record change history & timeline view",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "records",
            "feature": "IPFS / content‑hash preview & basic browser",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "records",
            "feature": "Text & coin type auto‑suggestions",
            "priority": "MEDIUM",
            "effort": "LOW",
        },

        # ── Names & Subnames ──
        {
            "area": "names",
            "feature": "Subname hierarchy tree view + search",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "names",
            "feature": "Bulk subname minting / management",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "names",
            "feature": "Name wrapping / unwrapping wizard (CCIP‑read ready)",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "names",
            "feature": "Subname permission & role delegation UI",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "names",
            "feature": "Grace period & expiry auction monitoring",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "names",
            "feature": "Name transfer & sell listing helper",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },

        # ── DNS & DNSSEC ──
        {
            "area": "dns",
            "feature": "DNSSEC‑enabled offchain records support",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "dns",
            "feature": "Visual DNS zone / gateway editor",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "dns",
            "feature": "DNS propagation & resolution checker",
            "priority": "MEDIUM",
            "effort": "LOW",
        },
        {
            "area": "dns",
            "feature": "DNS record import from traditional providers",
            "priority": "LOW",
            "effort": "HIGH",
        },

        # ── UI/UX & Productivity ──
        {
            "area": "ui-ux",
            "feature": "Global fuzzy search across names & records",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "ui-ux",
            "feature": "Command palette (Ctrl+K / Cmd+K)",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "ui-ux",
            "feature": "Keyboard shortcuts for power users",
            "priority": "MEDIUM",
            "effort": "LOW",
        },
        {
            "area": "ui-ux",
            "feature": "Dark/light mode + system auto‑sync",
            "priority": "MEDIUM",
            "effort": "LOW",
        },
        {
            "area": "ui-ux",
            "feature": "Mobile‑responsive layout improvements",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "ui-ux",
            "feature": "In‑app guided tours & contextual tooltips",
            "priority": "LOW",
            "effort": "MEDIUM",
        },

        # ── Advanced / Power User / Developer ──
        {
            "area": "advanced",
            "feature": "Gas estimation & optimization suggestions",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "advanced",
            "feature": "Visual transaction / batch builder",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "advanced",
            "feature": "Queued batch transactions + simulation",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "advanced",
            "feature": "Multi‑chain dashboard & switcher",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "advanced",
            "feature": "Custom resolver deployment helper",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "advanced",
            "feature": "Offchain data (CCIP‑read) configuration wizard",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "advanced",
            "feature": "ENS name health check & security scanner",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
    ]

    # ── Innovative / Experimental Features ──
    ENS_INNOVATIVE_FEATURES = [
        {
            "area": "innovation",
            "feature": "ENS Setup Wizard 2.0",
            "description": "Personalized guided onboarding with chain abstraction, stablecoin fiat ramps, and quick profile/record presets",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "innovation",
            "feature": "AI‑Powered Domain Recommender & Availability Checker",
            "description": "Suggests creative, brandable .eth / subname ideas based on user interests, trends, and real‑time availability",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "innovation",
            "feature": "One‑Click Multi‑Chain Primary Name Switcher",
            "description": "Seamlessly set primary name across L2s (Base, Optimism, Arbitrum, etc.) with live resolution preview",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "innovation",
            "feature": "Dynamic ENS Profile Cards & Shareable OG Images",
            "description": "Beautiful, updatable social cards with avatar, bio, links; auto‑generated Open Graph for Twitter/Discord",
            "priority": "MEDIUM",
            "effort": "LOW",
        },
        {
            "area": "innovation",
            "feature": "Web3 Identity SEO Booster",
            "description": "Tools to make ENS names Google‑visible (metadata, structured data, optional DNS linkage)",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "innovation",
            "feature": "Advanced Portfolio Analytics Dashboard",
            "description": "Track total value, renewal costs, gas spent, name age, subname count, cross‑chain holdings, ROI trends",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "innovation",
            "feature": "AI Domain Valuation & Trend Predictor",
            "description": "ML‑based estimates using sales history, length, keywords, similar comps, plus future trend signals",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "innovation",
            "feature": "ENS Name Health & Security Scanner",
            "description": "Scores domain based on expiry risk, record completeness, phishing exposure, DNSSEC status, resolver trust",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "innovation",
            "feature": "Integrated Lightweight Domain Marketplace",
            "description": "Browse trending/expiring names, list for sale/auction, make offers — all inside the app (no full OpenSea replacement)",
            "priority": "MEDIUM",
            "effort": "HIGH",
        },
        {
            "area": "innovation",
            "feature": "Grace Period & Expiry Auction Alerts + Bidder",
            "description": "Real‑time notifications + one‑click bidding on expiring/grace‑period names",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
    ]

    # ── Code‑quality improvements ──
    CODE_QUALITY_IMPROVEMENTS = [
        {
            "area": "code-quality",
            "feature": "Eliminate all @ts‑ignore and @ts‑expect‑error",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "code-quality",
            "feature": "Comprehensive React Error Boundaries + Fallback UI",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "code-quality",
            "feature": "Add polished loading skeletons across all views",
            "priority": "HIGH",
            "effort": "LOW",
        },
        {
            "area": "code-quality",
            "feature": "Full React Suspense + data fetching integration",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "code-quality",
            "feature": "Unit + integration test coverage >70% on critical paths (registration, records, dashboard)",
            "priority": "HIGH",
            "effort": "HIGH",
        },
        {
            "area": "code-quality",
            "feature": "Improve WCAG 2.2 AA accessibility (ARIA, keyboard nav, color contrast, screen reader testing)",
            "priority": "HIGH",
            "effort": "MEDIUM",
        },
        {
            "area": "code-quality",
            "feature": "Type‑safe API clients & hooks (e.g. stricter wagmi/viem types)",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
        {
            "area": "code-quality",
            "feature": "Centralized error logging + user‑friendly toast messages",
            "priority": "MEDIUM",
            "effort": "LOW",
        },
        {
            "area": "code-quality",
            "feature": "Performance optimizations (memoization, virtualization for long lists, image optimization)",
            "priority": "MEDIUM",
            "effort": "MEDIUM",
        },
    ]

    # --------------------------------------------------------------------- #
    # Instance state
    # --------------------------------------------------------------------- #
    def __init__(self):
        self.suggested_features = set()
        self.suggestions: List[ImprovementSuggestion] = []

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    # --------------------------------------------------------------------- #
    # Generation helpers
    # --------------------------------------------------------------------- #
    @classmethod
    def from_analysis(cls, analysis: CodeAnalysisResult) -> List[ImprovementSuggestion]:
        """Create suggestions based on static analysis results."""
        suggestions = []

        if analysis.issue_count > 0:
            suggestions.append(
                ImprovementSuggestion(
                    area="code-quality",
                    feature="Fix TypeScript Issues",
                    description=f"Address {analysis.issue_count} TypeScript issues",
                    priority="HIGH",
                    estimated_effort="MEDIUM",
                    dependencies=[],
                )
            )

        if analysis.todo_count > 0:
            suggestions.append(
                ImprovementSuggestion(
                    area="code-quality",
                    feature="Complete TODO Items",
                    description=f"Address {analysis.todo_count} TODO comments",
                    priority="MEDIUM",
                    estimated_effort="LOW",
                    dependencies=[],
                )
            )
        return suggestions

    def generate_all(self) -> List[ImprovementSuggestion]:
        """Combine catalogue‑driven and analysis‑driven suggestions."""
        suggestions: List[ImprovementSuggestion] = []

        for feature in self.ENS_CORE_FEATURES:
            key = f"{feature['area']}:{feature['feature']}"
            if key in self.suggested_features:
                continue
            self.suggested_features.add(key)
            suggestions.append(
                ImprovementSuggestion(
                    area=feature["area"],
                    feature=feature["feature"],
                    description=feature.get("feature", ""),
                    priority=feature["priority"],
                    estimated_effort=feature.get("effort", "MEDIUM"),
                    dependencies=[],
                )
            )

        for feature in self.ENS_INNOVATIVE_FEATURES:
            suggestions.append(
                ImprovementSuggestion(
                    area=feature["area"],
                    feature=feature["feature"],
                    description=feature.get("description", ""),
                    priority=feature["priority"],
                    estimated_effort=feature.get("effort", "HIGH"),
                    dependencies=[],
                )
            )

        for feature in self.CODE_QUALITY_IMPROVEMENTS:
            suggestions.append(
                ImprovementSuggestion(
                    area=feature["area"],
                    feature=feature["feature"],
                    description="",
                    priority=feature["priority"],
                    estimated_effort=feature.get("effort", "MEDIUM"),
                    dependencies=[],
                )
            )

        self.suggestions = suggestions
        return suggestions

    @staticmethod
    def prioritize(suggestions: List[ImprovementSuggestion]) -> List[ImprovementSuggestion]:
        """Sort suggestions by priority (HIGH → MEDIUM → LOW)."""
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        return sorted(suggestions, key=lambda s: order.get(s.priority, 3))

# =============================================================================
# TEST ENGINE
# =============================================================================

class TestResult:
    """Encapsulates a single test execution result."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration = 0.0
        self.output = ""
        self.errors: List[str] = []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration": self.duration,
            "output": self.output,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


class TestEngine(AgentComponent):
    """Automated testing for all application components."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.results: Dict[str, TestResult] = {}
        self.history: List[Dict] = []

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    # --------------------------------------------------------------------- #
    # Command execution helper
    # --------------------------------------------------------------------- #
    @staticmethod
    def run_command(cmd: List[str], timeout: int = 120, stream: bool = False) -> tuple:
        """Execute *cmd* in the workspace. If stream=True or VERBOSE: print output live (tee to stdout)."""
        do_stream = stream or VERBOSE
        try:
            start = time.time()
            if do_stream:
                trace(f"  $ {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd,
                    cwd=WORKSPACE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                lines = []
                for line in iter(proc.stdout.readline, ""):
                    if not line:
                        break
                    lines.append(line)
                    print("    " + line.rstrip(), flush=True)
                out = "".join(lines)
                proc.wait(timeout=max(1, timeout - int(time.time() - start)))
                duration = time.time() - start
                return proc.returncode == 0, out, "", duration
            result = subprocess.run(
                cmd,
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start
            return result.returncode == 0, result.stdout, result.stderr, duration
        except Exception as e:
            return False, "", str(e), 0

    def _record_result(self, name: str, passed: bool, output: str, duration: float):
        """Persist a test result in memory."""
        result = TestResult(name)
        result.passed = passed
        result.output = output[:5000]
        result.duration = duration
        self.results[name] = result
        self.history.append(result.to_dict())

    # --------------------------------------------------------------------- #
    # Individual test suites
    # --------------------------------------------------------------------- #
    @classmethod
    def run_typecheck(cls) -> TestResult:
        logger = AutonomousLogger.instance()
        logger.log("TEST", "Running TypeScript type check...")

        result = TestResult("typecheck")
        success, stdout, stderr, duration = cls.run_command(
            ["npx", "tsc", "--noEmit"], timeout=120
        )
        result.duration = duration
        result.timestamp = datetime.now().isoformat()

        if success:
            result.passed = True
            logger.log_success("typecheck", "PASSED")
        else:
            error_count = len(re.findall(r"error TS\d+:", stdout + stderr))
            result.errors = [f"{error_count} TypeScript errors"]
            logger.log_error("typecheck", f"{error_count} TypeScript errors", stdout[:500])

        return result

    @classmethod
    def run_build(cls) -> TestResult:
        logger = AutonomousLogger.instance()
        logger.log("TEST", "Running build...")

        result = TestResult("build")
        success, stdout, stderr, duration = cls.run_command(
            ["npm", "run", "build"], timeout=180
        )
        result.duration = duration
        result.timestamp = datetime.now().isoformat()

        if success:
            result.passed = True
            logger.log_success("build", "PASSED")
        else:
            error_count = len(re.findall(r"error TS\d+:", stdout + stderr))
            result.errors = [f"Build failed with {error_count} errors"]
            logger.log_error("build", "Build failed", stdout[:500])

        return result

    @classmethod
    def run_tests(cls) -> TestResult:
        logger = AutonomousLogger.instance()
        logger.log("TEST", "Running unit tests...")

        result = TestResult("unit-tests")
        success, stdout, stderr, duration = cls.run_command(
            ["npm", "test", "--", "--run"], timeout=180
        )
        result.duration = duration
        result.timestamp = datetime.now().isoformat()

        if success:
            result.passed = True
            logger.log_success("tests", "PASSED")
        else:
            result.errors = ["Tests failed"]
            logger.log_error("tests", "Tests failed", stderr[:500])

        return result

    @classmethod
    def run_lint(cls) -> TestResult:
        logger = AutonomousLogger.instance()
        # Quick sanity check for ESLint installation
        check = subprocess.run(
            ["npm", "list", "eslint"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check.returncode != 0 or "empty" in check.stdout:
            logger.log("TEST", "Skipping ESLint (not installed)")
            result = TestResult("lint")
            result.passed = True
            result.timestamp = datetime.now().isoformat()
            result.output = "Skipped – ESLint not installed"
            return result

        logger.log("TEST", "Running ESLint...")
        result = TestResult("lint")
        success, stdout, stderr, duration = cls.run_command(
            ["npx", "eslint", "src", "--format", "json"], timeout=120
        )
        result.duration = duration
        result.timestamp = datetime.now().isoformat()

        if success:
            result.passed = True
            logger.log_success("lint", "PASSED")
        else:
            try:
                issues = json.loads(stdout)
                issue_count = sum(len(f.get("messages", [])) for f in issues)
                result.errors = [f"{issue_count} ESLint issues"]
                logger.log_error("lint", f"{issue_count} ESLint issues", "")
            except Exception:
                logger.log_error("lint", "Lint check failed", stderr[:500])

        return result

    @classmethod
    def run_audit(cls) -> TestResult:
        logger = AutonomousLogger.instance()
        logger.log("TEST", "Running npm audit...")

        result = TestResult("security-audit")
        success, stdout, stderr, duration = cls.run_command(
            ["npm", "audit", "--json"], timeout=120
        )
        result.duration = duration
        result.timestamp = datetime.now().isoformat()

        if success:
            result.passed = True
            logger.log_success("audit", "PASSED", "No vulnerabilities")
        else:
            try:
                data = json.loads(stdout)
                vuln_count = sum(data.get("vulnerabilities", {}).values())
                result.errors = [f"{vuln_count} vulnerabilities found"]
                logger.log_error("audit", f"{vuln_count} vulnerabilities found", "")
            except Exception:
                logger.log_error("audit", "Audit check failed", stderr[:500])

        return result

    # --------------------------------------------------------------------- #
    # Suite orchestration
    # --------------------------------------------------------------------- #
    def run_all_tests(self) -> Dict[str, TestResult]:
        """Execute the full test suite and return named results."""
        tests = [
            self.run_typecheck,
            self.run_build,
            self.run_lint,
            self.run_audit,
            self.run_tests,
        ]

        results: Dict[str, TestResult] = {}
        for test in tests:
            result = test()
            results[result.name] = result

        passed = sum(1 for r in results.values() if r.passed)
        AutonomousLogger.log("TEST", f"Test suite: {passed}/{len(results)} passed")
        return results

    def get_summary(self) -> Dict:
        """Return a high‑level summary of test activity."""
        return {
            "total_runs": len(self.history),
            "last_results": {k: v.to_dict() for k, v in self.results.items()},
        }

# =============================================================================
# FRONTEND VALIDATOR
# =============================================================================

class FrontendValidationResult:
    """Collects statistics about the React front‑end."""

    def __init__(self):
        self.components = {
            "total": 0,
            "typed": 0,
            "with_hooks": 0,
            "with_error_handling": 0,
            "with_loading_state": 0,
            "issues": 0,
        }
        self.routes = {"total": 0, "protected": 0}
        self.features: Dict[str, bool] = {}
        self.missing_features: List[str] = []
        self.issues: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "components": self.components,
            "routes": self.routes,
            "features": self.features,
            "missing_features": self.missing_features,
            "issues": self.issues,
        }

    def summary(self) -> str:
        return (
            f"Components: {self.components['total']}, "
            f"Routes: {self.routes['total']}, "
            f"Missing: {len(self.missing_features)}"
        )


class FrontendValidator(AgentComponent):
    """Validates React components, routing and feature coverage."""

    ENS_FEATURES = [
        "domain_search",
        "domain_details",
        "bulk_operations",
        "record_management",
        "subname_management",
        "dns_integration",
        "settings_panel",
        "wallet_connection",
        "gas_estimation",
        "batch_transactions",
        "export_functionality",
        "import_functionality",
        "multi_chain",
        "analytics_dashboard",
        "notification_system",
    ]

    def __init__(self):
        self.result = FrontendValidationResult()

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    # --------------------------------------------------------------------- #
    # Component analysis helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def analyze_component(filepath: Path) -> Dict:
        """Return a dict describing a single React component."""
        if not filepath.exists() or filepath.suffix != ".tsx":
            return {}

        content = filepath.read_text()
        component = {
            "file": str(filepath),
            "name": filepath.stem,
            "has_types": False,
            "has_hooks": False,
            "hooks": [],
            "has_error_boundary": False,
            "has_loading": False,
            "has_props_validation": False,
            "issues": [],
        }

        # TypeScript definitions
        if "interface" in content or ("type " in content and "type:" not in content):
            component["has_types"] = True
        else:
            component["issues"].append("Missing type definitions")

        # Hook usage detection
        hooks = re.findall(r"use[A-Z][a-zA-Z]+", content)
        if hooks:
            component["has_hooks"] = True
            component["hooks"] = list(set(hooks))

        # Error handling detection
        if any(k in content for k in ("ErrorBoundary", "catch", "error")):
            component["has_error_boundary"] = True
        else:
            component["issues"].append("No error handling")

        # Loading state detection
        if any(k in content for k in ("isLoading", "loading", "isFetching")):
            component["has_loading"] = True
        else:
            component["issues"].append("No loading state")

        # Prop‑validation detection
        if any(k in content for k in ("propTypes", "ValidationSchema", "zod")):
            component["has_props_validation"] = True

        return component

    @staticmethod
    def check_routes() -> List[Dict]:
        """Parse React Router definitions."""
        routes: List[Dict] = []
        src = Path(WORKSPACE) / "src"
        if not src.exists():
            return routes

        for filepath in src.rglob("*.tsx"):
            content = filepath.read_text()
            if "Route" not in content and "Routes" not in content:
                continue
            matches = re.findall(r'path=["\']([^"\']+)["\']', content)
            for path in matches:
                routes.append(
                    {
                        "file": str(filepath),
                        "path": path,
                        "has_protection": "Protected" in content or "Auth" in content,
                        "has_lazy": "lazy" in content.lower(),
                    }
                )
        return routes

    @staticmethod
    def check_ens_features() -> Dict[str, bool]:
        """Detect implementation of high‑level ENS features."""
        src = Path(WORKSPACE) / "src"
        features = {f: False for f in FrontendValidator.ENS_FEATURES}
        if not src.exists():
            return features

        content = src.read_text().lower()

        # Simple keyword heuristics per feature
        if any(k in content for k in ("search", "lookup", "query domain")):
            features["domain_search"] = True
        if any(k in content for k in ("detail", "info view")):
            features["domain_details"] = True
        if any(k in content for k in ("bulk", "batch")):
            features["bulk_operations"] = True
        if any(k in content for k in ("record", "text record")):
            features["record_management"] = True
        if any(k in content for k in ("subname", "sub-name")):
            features["subname_management"] = True
        if "dns" in content:
            features["dns_integration"] = True
        if "setting" in content:
            features["settings_panel"] = True
        if any(k in content for k in ("wallet", "connect")):
            features["wallet_connection"] = True
        if any(k in content for k in ("gas", "fee", "estimation")):
            features["gas_estimation"] = True
        if "transaction" in content:
            features["batch_transactions"] = True
        if any(k in content for k in ("export", "csv", "download")):
            features["export_functionality"] = True
        if any(k in content for k in ("import", "upload", "csv")):
            features["import_functionality"] = True
        if any(k in content for k in ("chain", "network", "polygon", "arbitrum")):
            features["multi_chain"] = True
        if any(k in content for k in ("analytics", "chart", "graph", "stat")):
            features["analytics_dashboard"] = True
        if any(k in content for k in ("notification", "toast", "alert", "notify")):
            features["notification_system"] = True

        return features

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def validate_frontend(self) -> FrontendValidationResult:
        """Run a full validation pass and populate ``self.result``."""
        logger = AutonomousLogger.instance()
        logger.log("VALIDATE", "Checking React components...")

        src = Path(WORKSPACE) / "src"
        if src.exists():
            for filepath in src.rglob("*.tsx"):
                analysis = self.analyze_component(filepath)
                if not analysis:
                    continue

                self.result.components["total"] += 1
                if analysis["has_types"]:
                    self.result.components["typed"] += 1
                if analysis["has_hooks"]:
                    self.result.components["with_hooks"] += 1
                if analysis["has_error_boundary"]:
                    self.result.components["with_error_handling"] += 1
                if analysis["has_loading"]:
                    self.result.components["with_loading_state"] += 1
                self.result.components["issues"] += len(analysis["issues"])

        logger.log("VALIDATE", "Checking routes...")
        routes = self.check_routes()
        self.result.routes["total"] = len(routes)
        self.result.routes["protected"] = sum(1 for r in routes if r.get("has_protection"))

        logger.log("VALIDATE", "Checking ENS feature coverage...")
        features = self.check_ens_features()
        self.result.features = features
        self.result.missing_features = [k for k, v in features.items() if not v]

        if self.result.missing_features:
            logger.log("VALIDATE", f"Missing features: {', '.join(self.result.missing_features)}")

        return self.result

    def get_result(self) -> FrontendValidationResult:
        return self.result


# =============================================================================
# LOCAL CODE EDITOR (direct file modifications - no OpenClaw dependency)
# =============================================================================

class LocalCodeEditor(AgentComponent):
    """Applies mechanical code fixes directly. Builds after each change; reverts if failed."""

    def __init__(self, verbose: bool = False):
        self.applied_fixes: List[Dict] = []
        self.reverted_fixes: List[Dict] = []
        self.verbose = verbose

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    @staticmethod
    def run_build() -> bool:
        """Run npm run build; return True if success."""
        ok, _, stderr, _ = TestEngine.run_command(["npm", "run", "build"], timeout=180)
        return ok

    def extract_actionable_fixes(self, analysis: "CodeAnalysisResult") -> List[Dict[str, Any]]:
        """From analysis, return a list of {file, fix_type, ...} for mechanical fixes."""
        fixes = []
        for fa in analysis.files_analyzed:
            filepath = Path(fa["file"])
            if not filepath.exists():
                continue
            content = filepath.read_text()
            # console.log removal (whole-statement or inline)
            if "console.log" in content:
                fixes.append({"file": str(filepath), "fix_type": "remove_console_log"})
            # @ts-ignore removal (standalone line)
            if "// @ts-ignore" in content or "// @ts-expect-error" in content:
                fixes.append({"file": str(filepath), "fix_type": "remove_ts_ignore"})
        return fixes[:10]  # cap per cycle

    def apply_fix(self, fix: Dict[str, Any]) -> bool:
        """Apply one fix. Run build. Revert if build fails. Return True if kept."""
        logger = AutonomousLogger.instance()
        filepath = Path(fix["file"])
        if not filepath.exists():
            return False
        original = filepath.read_text()
        fix_type = fix["fix_type"]

        if fix_type == "remove_console_log":
            # Remove lines that are only console.log(...) / console.debug etc.
            lines = original.split("\n")
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if re.match(r"^console\.(log|debug|info|warn)\([^)]*\);?\s*$", stripped):
                    continue
                if stripped.startswith("console.") and not stripped.startswith("//"):
                    continue
                new_lines.append(line)
            new_content = "\n".join(new_lines)
        elif fix_type == "remove_ts_ignore":
            lines = original.split("\n")
            new_lines = []
            for line in lines:
                if "// @ts-ignore" in line or "// @ts-expect-error" in line:
                    # Remove the comment; keep the rest of the line if any
                    new_line = re.sub(r"\s*//\s*@ts-(?:ignore|expect-error).*$", "", line).rstrip()
                    if new_line.strip():
                        new_lines.append(new_line)
                    else:
                        continue  # drop whole line
                else:
                    new_lines.append(line)
            new_content = "\n".join(new_lines)
        else:
            return False

        if new_content == original:
            return False

        try:
            filepath.write_text(new_content)
            self.applied_fixes.append({"file": str(filepath), "fix_type": fix_type})
            trace(f"  [EDIT] Applied {fix_type} → {filepath.name}")
        except Exception as e:
            logger.log_error("LocalCodeEditor", str(e), str(filepath))
            trace(f"  [FAIL] {fix_type} in {filepath.name}: {e}")
            return False

        trace(f"  [BUILD] Verifying build after {fix_type} in {filepath.name}...")
        if self.run_build():
            logger.log_success("LocalCodeEditor", f"{fix_type} in {filepath.name}")
            return True
        else:
            filepath.write_text(original)
            self.applied_fixes.pop()
            self.reverted_fixes.append(fix)
            logger.log("REVERT", f"Reverted {fix_type} in {filepath.name} (build failed)")
            trace(f"  [REVERT] Build failed → reverted {fix_type} in {filepath.name}")
            return False

    def apply_from_analysis(self, analysis: "CodeAnalysisResult") -> Dict[str, int]:
        """Apply all actionable fixes. Return counts {applied, reverted, skipped}."""
        fixes = self.extract_actionable_fixes(analysis)
        applied = reverted = skipped = 0
        for fix in fixes:
            ok = self.apply_fix(fix)
            if ok:
                applied += 1
            else:
                if self.reverted_fixes and self.reverted_fixes[-1] == fix:
                    reverted += 1
                else:
                    skipped += 1
        return {"applied": applied, "reverted": reverted, "skipped": skipped}


# =============================================================================
# AUTONOMOUS IMPLEMENTER
# =============================================================================

class AutonomousImplementer(AgentComponent):
    """Executes high‑priority improvements via a sub‑agent."""

    def __init__(self):
        self.implemented_features: List[str] = []
        self.failed_implementations: List[str] = []
        self.pending_implementations: List[str] = []

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    # --------------------------------------------------------------------- #
    # Prompt creation
    # --------------------------------------------------------------------- #
    @staticmethod
    def create_task_prompt(task: str, context: str = "") -> str:
        """Return a detailed prompt for the sub‑agent."""
        return f"""You are a senior developer for ENS.tools ({WORKSPACE}).

TASK: {task}

Requirements:
1. Implement the feature following TypeScript + React + Vite best practices
2. Add proper TypeScript types/interfaces
3. Handle loading states and errors properly
4. Write clean, maintainable code
5. After implementation, verify with 'npm run build'

CONTEXT: {context}

Begin implementation now.
"""

    # --------------------------------------------------------------------- #
    # Sub‑agent orchestration
    # --------------------------------------------------------------------- #
    def spawn_implementation(self, task: str, context: str = "") -> bool:
        """Start a sub‑agent session to implement *task*."""
        logger = AutonomousLogger.instance()
        logger.log("IMPLEMENT", f"Implementing: {task[:80]}...")

        full_task = self.create_task_prompt(task, context)

        try:
            env = {**os.environ, "OPENCLAW_WORKSPACE": WORKSPACE}
            result = subprocess.run(
                [
                    "openclaw",
                    "sessions",
                    "spawn",
                    "--agent-id",
                    "main",
                    "--model",
                    MODEL,
                    "--task",
                    full_task,
                    "--timeout",
                    "600",
                ],
                capture_output=True,
                text=True,
                timeout=700,
                cwd=WORKSPACE,
                env=env,
            )

            if result.returncode == 0:
                logger.log_success("implement", task[:50], "Completed")
                self.implemented_features.append(task)
                return True
            else:
                logger.log_error("implement", task[:50], result.stderr[:300])
                self.failed_implementations.append(task)
                return False

        except Exception as e:
            logger.log_error("implement", task[:50], str(e))
            self.failed_implementations.append(task)
            return False

    def implement_improvements(self, improvements: List[ImprovementSuggestion]):
        """Implement the top‑priority improvements (max 5, HIGH priority only)."""
        sorted_imps = ImprovementGenerator.prioritize(improvements)

        for imp in sorted_imps[:5]:
            if imp.priority == "HIGH":
                self.spawn_implementation(
                    imp.feature,
                    f"Priority: {imp.priority}\nArea: {imp.area}\nDescription: {imp.description}",
                )
                time.sleep(2)  # brief pause between spawns

    def get_stats(self) -> Dict:
        return {
            "implemented": len(self.implemented_features),
            "failed": len(self.failed_implementations),
            "pending": len(self.pending_implementations),
        }


# =============================================================================
# AUTONOMOUS CYCLE ENGINE
# =============================================================================

class AutonomousEngine(AgentComponent):
    """Coordinates the whole autonomous workflow."""

    def __init__(self, local_only: bool = False, verbose: bool = False):
        self.analyzer = CodeAnalyzer()
        self.generator = ImprovementGenerator()
        self.tester = TestEngine()
        self.validator = FrontendValidator()
        self.local_editor = LocalCodeEditor(verbose=verbose)
        self.implementer = AutonomousImplementer()
        self.cycle_count = 0
        self.is_running = True
        self.local_only = local_only
        self.verbose = verbose

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def initialize(self) -> bool:
        """Initialize every component; abort on first failure."""
        components = [
            (self.analyzer, "CodeAnalyzer"),
            (self.generator, "ImprovementGenerator"),
            (self.tester, "TestEngine"),
            (self.validator, "FrontendValidator"),
            (self.local_editor, "LocalCodeEditor"),
            (self.implementer, "AutonomousImplementer"),
        ]
        for comp, name in components:
            if not comp.initialize():
                AutonomousLogger.log_error(name, "Initialization failed")
                return False
        return True

    def validate(self) -> bool:
        """Validate all components."""
        return all(
            c.validate()
            for c in [
                self.analyzer,
                self.generator,
                self.tester,
                self.validator,
                self.local_editor,
                self.implementer,
            ]
        )

    # --------------------------------------------------------------------- #
    # One autonomous cycle
    # --------------------------------------------------------------------- #
    def run_cycle(self) -> Dict:
        """Execute a full analysis → improvement → test → implementation loop."""
        self.cycle_count += 1
        logger = AutonomousLogger.instance()
        logger.log("CYCLE", f"=== Starting Cycle {self.cycle_count} ===")

        results = {
            "cycle": self.cycle_count,
            "analysis": None,
            "local_fixes": {},
            "improvements": [],
            "tests": {},
            "frontend": None,
            "implementations": {},
        }

        try:
            # 1️⃣  Code analysis
            logger.log("CYCLE", "Step 1: Analyzing codebase...")
            trace("\n[Step 1] Analyzing codebase...")
            analysis = self.analyzer.analyze_workspace()
            results["analysis"] = analysis.to_dict()
            logger.log(
                "ANALYSIS",
                f"Found {analysis.file_count} files, {analysis.issue_count} issues",
            )
            trace(f"  Found {analysis.file_count} TS/TSX files, {analysis.issue_count} issues, {analysis.todo_count} TODOs, {analysis.fixme_count} FIXMEs")
            for fa in (analysis.files_analyzed or [])[:15]:
                issues = fa.get("issues", [])
                if issues or fa.get("todos") or fa.get("fixmes"):
                    rel = Path(fa["file"]).relative_to(WORKSPACE) if fa["file"].startswith(WORKSPACE) else fa["file"]
                    trace(f"    • {rel}: {issues[:3] or []}")

            # 2️⃣  LOCAL FIXES: Apply mechanical fixes (console.log, @ts-ignore) and build
            logger.log("CYCLE", "Step 2: Applying local code fixes...")
            fixes = self.local_editor.extract_actionable_fixes(analysis)
            trace(f"\n[Step 2] Actionable fixes: {len(fixes)}")
            for f in fixes[:10]:
                trace(f"    • {f.get('fix_type')} in {Path(f.get('file','')).name}")
            local_stats = self.local_editor.apply_from_analysis(analysis)
            results["local_fixes"] = local_stats
            if local_stats["applied"] > 0:
                logger.log("CYCLE", f"Applied {local_stats['applied']} local fixes (build verified)")
            trace(f"  Result: applied={local_stats['applied']}, reverted={local_stats['reverted']}, skipped={local_stats['skipped']}")

            # 3️⃣  Generate improvements
            logger.log("CYCLE", "Step 3: Generating improvements...")
            analysis_imps = ImprovementGenerator.from_analysis(analysis)
            all_imps = self.generator.generate_all() + analysis_imps
            prioritized = ImprovementGenerator.prioritize(all_imps)
            results["improvements"] = [i.to_dict() for i in prioritized[:10]]

            for imp in prioritized[:3]:
                logger.log_improvement(imp.area, imp.feature, imp.priority)

            # 4️⃣  Run test suite
            logger.log("CYCLE", "Step 4: Running test suite...")
            trace("\n[Step 4] Running test suite...")
            test_results = self.tester.run_all_tests()
            results["tests"] = {k: v.to_dict() for k, v in test_results.items()}
            for name, tr in test_results.items():
                status = "OK" if tr.passed else "FAIL"
                trace(f"    [{status}] {name}: {tr.duration:.1f}s" + (f" — {tr.errors}" if tr.errors else ""))

            # 5️⃣  Front‑end validation
            logger.log("CYCLE", "Step 5: Validating frontend...")
            fe_result = self.validator.validate_frontend()
            results["frontend"] = fe_result.to_dict()

            # 6️⃣  Implement top improvements (OpenClaw subagent, workspace=ens.tools)
            if not self.local_only:
                logger.log("CYCLE", "Step 6: Implementing improvements (OpenClaw)...")
                self.implementer.implement_improvements(prioritized)
                results["implementations"] = self.implementer.get_stats()
            else:
                logger.log("CYCLE", "Step 6: Skipping OpenClaw (--local-only)")
                results["implementations"] = {"implemented": 0, "failed": 0, "pending": 0}

            # 7️⃣  Verify build after implementation
            logger.log("CYCLE", "Step 7: Verifying build...")
            trace("\n[Step 7] Final build verification...")
            build_res = TestEngine.run_build()
            results["build_passed"] = build_res.passed
            trace(f"  Build: {'PASSED' if build_res.passed else 'FAILED'}")

            # Summary log
            passed = sum(1 for r in test_results.values() if r.passed)
            logger.log("CYCLE", f"=== Cycle {self.cycle_count} Complete ===")
            trace(f"\n=== Cycle {self.cycle_count} Complete === tests {passed}/{len(test_results)}, local_fixes {results.get('local_fixes',{}).get('applied',0)}, build {'OK' if results.get('build_passed') else 'FAIL'} ===\n")
            logger.log(
                "SUMMARY",
                f"Tests: {passed}/{len(test_results)}, "
                f"Features: {len(results['improvements'])}, "
                f"Implemented: {results['implementations'].get('implemented', 0)}",
            )
            return results

        except Exception as e:
            logger.log_error("CYCLE", str(e), "Cycle failed")
            results["error"] = str(e)
            return results

    # --------------------------------------------------------------------- #
    # Continuous execution
    # --------------------------------------------------------------------- #
    def run(self):
        """Run the engine continuously (or once, based on CLI flags)."""
        logger = AutonomousLogger.instance()
        logger.log("START", "ENS.tools Autonomous Development Agent v2 starting...")
        logger.log("CONFIG", f"Workspace: {WORKSPACE}")
        trace("ENS.tools Autonomous Development Agent v2")
        trace(f"Workspace: {WORKSPACE}")
        trace(f"Local-only: {self.local_only}\n")
        logger.log("CONFIG", f"Cycle interval: {CYCLE_INTERVAL}s")

        if not self.initialize():
            logger.log_error("STARTUP", "Initialization failed")
            return

        # First run (always)
        self.run_cycle()

        # Loop until stopped
        while self.is_running:
            time.sleep(CYCLE_INTERVAL)
            self.run_cycle()

    def stop(self):
        """Gracefully stop the continuous loop."""
        self.is_running = False
        AutonomousLogger.instance().log("STOP", "Autonomous agent stopping...")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Parse CLI arguments and dispatch to the appropriate subsystem."""
    import argparse

    trace("dev_agent_v2: starting...", flush=True)
    parser = argparse.ArgumentParser(
        description="ENS.tools Autonomous Development Agent v2"
    )
    parser.add_argument("--once", action="store_true", help="Run a single cycle then exit")
    parser.add_argument("--test", action="store_true", help="Run tests only")
    parser.add_argument("--validate", action="store_true", help="Validate frontend only")
    parser.add_argument("--analyze", action="store_true", help="Analyze codebase only")
    parser.add_argument(
        "--apply-local",
        action="store_true",
        help="Apply local fixes only (console.log, @ts-ignore), verify build, then exit",
    )
    parser.add_argument(
        "--implement",
        type=str,
        metavar="TASK",
        help="Implement a specific task directly",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only apply local fixes (console.log, @ts-ignore); skip OpenClaw spawn",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet: no subprocess streaming, minimal output",
    )

    args = parser.parse_args()
    global VERBOSE
    VERBOSE = not args.quiet
    verbose = not args.quiet
    engine = AutonomousEngine(local_only=args.local_only, verbose=verbose)

    if args.test:
        results = engine.tester.run_all_tests()
        print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2))
        return

    if args.validate:
        result = engine.validator.validate_frontend()
        print(json.dumps(result.to_dict(), indent=2))
        return

    if args.analyze:
        analysis = engine.analyzer.analyze_workspace()
        print(json.dumps(analysis.to_dict(), indent=2))
        return

    if args.apply_local:
        trace("ENS.tools Dev Agent — apply-local")
        trace(f"Workspace: {WORKSPACE}\n")
        analysis = engine.analyzer.analyze_workspace()
        fixes = engine.local_editor.extract_actionable_fixes(analysis)
        trace(f"Analysis: {analysis.file_count} files, {analysis.issue_count} issues")
        trace(f"Actionable fixes: {len(fixes)}")
        for f in fixes:
            trace(f"  • {f.get('fix_type')} in {Path(f.get('file','')).name}")
        trace("")
        stats = engine.local_editor.apply_from_analysis(analysis)
        print(json.dumps({"local_fixes": stats, "build": "verified per fix"}, indent=2), flush=True)
        return

    if args.implement:
        engine.implementer.spawn_implementation(args.implement)
        return

    # Default mode: autonomous cycles
    if args.once:
        engine.run_cycle()
    else:
        try:
            engine.run()
        except KeyboardInterrupt:
            engine.stop()


if __name__ == "__main__":
    main()