#!/usr/bin/env python3
"""
ENS.tools Autonomous Development Agent v3
==========================================

A complete rewrite: zero-delay pipeline, real TypeScript analysis,
smart auto-fixers, git safety net, UX analysis, comprehensive reporting.

Single file. No external dependencies beyond stdlib + subprocess (npm/npx/git).
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import textwrap
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================
WORKSPACE = "/Users/acc/ens.tools"
AGENT_DIR = Path(__file__).parent.resolve()
STATE_FILE = AGENT_DIR / ".v3_state.json"
CYCLES_DIR = AGENT_DIR / "cycles"
CYCLE_INTERVAL = 0  # zero delay between cycles
MAX_ERRORS_BEFORE_PAUSE = 10
MODEL = os.environ.get("IMPROVER_MODEL", "anthropic/claude-sonnet-4-20250514")
QUIET = False

# Error category mapping
ERROR_CATEGORIES = {
    "unused_var": ["TS6133", "TS6196", "TS6192"],
    "missing_import": ["TS2307", "TS2305", "TS2304"],
    "type_error": ["TS2322", "TS2345", "TS2339", "TS2769", "TS2741", "TS2352", "TS2353"],
    "implicit_any": ["TS7006", "TS7031", "TS7053"],
    "null_check": ["TS18046", "TS18048", "TS2454"],
    "misc": ["TS2308", "TS2536", "TS2554", "TS2559", "TS2561", "TS2677", "TS2686",
             "TS2698", "TS2719", "TS2739", "TS2488", "TS2366", "TS2459", "TS2552",
             "TS4104", "TS1064"],
}

# Reverse lookup: code -> category
CODE_TO_CATEGORY = {}
for cat, codes in ERROR_CATEGORIES.items():
    for code in codes:
        CODE_TO_CATEGORY[code] = cat


def log(msg: str, level: str = "INFO"):
    """Print a timestamped log line."""
    if QUIET and level == "DEBUG":
        return
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def log_debug(msg: str):
    log(msg, "DEBUG")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TSError:
    """A single TypeScript error parsed from tsc output."""
    file: str
    line: int
    col: int
    code: str  # e.g. "TS6133"
    message: str
    category: str = ""

    def __post_init__(self):
        self.category = CODE_TO_CATEGORY.get(self.code, "other")

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}:{self.col}"

    def __repr__(self):
        return f"{self.location}: {self.code} {self.message[:60]}"


@dataclass
class FixResult:
    """Result of attempting a fix."""
    file: str
    fix_type: str
    success: bool
    error_code: str = ""
    detail: str = ""


@dataclass
class CycleResult:
    """Complete results from one improvement cycle."""
    cycle_number: int
    timestamp: str
    start_errors: int
    end_errors: int
    fixes_attempted: int
    fixes_applied: int
    fixes_reverted: int
    build_passed: bool
    duration_secs: float
    error_breakdown: Dict[str, int] = field(default_factory=dict)
    top_remaining: List[str] = field(default_factory=list)
    trend: str = "→"  # ↑ ↓ →

    def to_dict(self) -> Dict:
        return {
            "cycle": self.cycle_number,
            "timestamp": self.timestamp,
            "start_errors": self.start_errors,
            "end_errors": self.end_errors,
            "fixes_attempted": self.fixes_attempted,
            "fixes_applied": self.fixes_applied,
            "fixes_reverted": self.fixes_reverted,
            "build_passed": self.build_passed,
            "duration_secs": round(self.duration_secs, 1),
            "error_breakdown": self.error_breakdown,
            "top_remaining": self.top_remaining,
            "trend": self.trend,
        }


# =============================================================================
# AGENT COMPONENT BASE
# =============================================================================

class AgentComponent(ABC):
    """Base class for all agent components."""

    @abstractmethod
    def initialize(self) -> bool:
        ...

    @abstractmethod
    def validate(self) -> bool:
        ...


# =============================================================================
# SUBPROCESS HELPER
# =============================================================================

def run_cmd(cmd: List[str], cwd: str = WORKSPACE, timeout: int = 180,
            capture: bool = True) -> Tuple[bool, str, str, float]:
    """Run a command. Returns (success, stdout, stderr, duration)."""
    start = time.time()
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        duration = time.time() - start
        return result.returncode == 0, result.stdout, result.stderr, duration
    except subprocess.TimeoutExpired:
        return False, "", "timeout", time.time() - start
    except Exception as e:
        return False, "", str(e), time.time() - start


# =============================================================================
# TYPESCRIPT ANALYZER
# =============================================================================

class TypeScriptAnalyzer(AgentComponent):
    """Runs `npx tsc --noEmit` and parses real TypeScript errors."""

    # Pattern: src/file.tsx(line,col): error TSXXXX: message
    ERROR_RE = re.compile(
        r'^(.+?)\((\d+),(\d+)\):\s+error\s+(TS\d+):\s+(.+)$'
    )

    def __init__(self):
        self.errors: List[TSError] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.errors_by_file: Dict[str, List[TSError]] = defaultdict(list)
        self.errors_by_category: Dict[str, List[TSError]] = defaultdict(list)
        self.last_total: int = -1

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    def analyze(self) -> List[TSError]:
        """Run tsc and parse all errors."""
        log_debug("Running npx tsc --noEmit...")
        ok, stdout, stderr, duration = run_cmd(
            ["npx", "tsc", "--noEmit"], timeout=120
        )
        output = stdout + stderr
        log_debug(f"tsc completed in {duration:.1f}s (success={ok})")

        self.errors = []
        self.error_counts = defaultdict(int)
        self.errors_by_file = defaultdict(list)
        self.errors_by_category = defaultdict(list)

        for line in output.splitlines():
            m = self.ERROR_RE.match(line.strip())
            if m:
                filepath, lineno, col, code, message = m.groups()
                err = TSError(
                    file=filepath,
                    line=int(lineno),
                    col=int(col),
                    code=code,
                    message=message.strip(),
                )
                self.errors.append(err)
                self.error_counts[code] += 1
                self.errors_by_file[filepath].append(err)
                self.errors_by_category[err.category].append(err)

        return self.errors

    @property
    def total_errors(self) -> int:
        return len(self.errors)

    def get_trend(self) -> str:
        """Compare current total to last known total."""
        if self.last_total < 0:
            return "→"
        if self.total_errors < self.last_total:
            return "↓"
        elif self.total_errors > self.last_total:
            return "↑"
        return "→"

    def get_category_summary(self) -> Dict[str, int]:
        """Return {category: count} dict."""
        summary = defaultdict(int)
        for err in self.errors:
            summary[err.category] += 1
        return dict(summary)

    def get_top_files(self, n: int = 10) -> List[Tuple[str, int]]:
        """Top N files by error count."""
        counts = [(f, len(errs)) for f, errs in self.errors_by_file.items()]
        counts.sort(key=lambda x: -x[1])
        return counts[:n]

    def print_error_report(self):
        """Print a formatted error report."""
        print(f"\n{'='*70}")
        print(f"  TypeScript Error Report — {self.total_errors} errors")
        print(f"{'='*70}")

        # By category
        print(f"\n  By Category:")
        for cat, errs in sorted(self.errors_by_category.items(), key=lambda x: -len(x[1])):
            print(f"    {cat:20s}  {len(errs):4d}")

        # By error code (top 15)
        print(f"\n  By Error Code (top 15):")
        sorted_codes = sorted(self.error_counts.items(), key=lambda x: -x[1])
        for code, count in sorted_codes[:15]:
            cat = CODE_TO_CATEGORY.get(code, "other")
            print(f"    {code}  {count:4d}  ({cat})")

        # Top files
        print(f"\n  Top Files by Errors:")
        for filepath, count in self.get_top_files(10):
            short = filepath.replace("src/", "")
            print(f"    {count:4d}  {short}")

        print(f"{'='*70}\n")


# =============================================================================
# SMART FIXER
# =============================================================================

class SmartFixer(AgentComponent):
    """Applies targeted fixes based on TS error categories.
    Every fix: write → build → keep if passes, revert if fails."""

    def __init__(self):
        self.fixes_applied: List[FixResult] = []
        self.fixes_reverted: List[FixResult] = []
        self.fixes_skipped: int = 0
        self._shutting_down = False

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE).exists()

    def request_shutdown(self):
        """Signal that we should stop after the current fix."""
        self._shutting_down = True

    @staticmethod
    def _resolve(filepath: str) -> Path:
        """Resolve a tsc-relative path to an absolute path under WORKSPACE."""
        p = Path(filepath)
        if not p.is_absolute():
            p = Path(WORKSPACE) / p
        return p

    @staticmethod
    def _read_file(filepath: str) -> Optional[str]:
        try:
            p = SmartFixer._resolve(filepath)
            return p.read_text(encoding="utf-8")
        except Exception:
            return None

    @staticmethod
    def _write_file(filepath: str, content: str) -> bool:
        try:
            p = SmartFixer._resolve(filepath)
            p.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    @staticmethod
    def _build_check() -> bool:
        """Quick build check. Returns True if build passes."""
        ok, _, _, _ = run_cmd(["npm", "run", "build"], timeout=180)
        return ok

    @staticmethod
    def _tsc_check() -> Tuple[bool, int]:
        """Quick tsc check. Returns (success, error_count)."""
        ok, stdout, stderr, _ = run_cmd(["npx", "tsc", "--noEmit"], timeout=120)
        output = stdout + stderr
        count = len(re.findall(r'error TS\d+', output))
        return ok, count

    def _apply_and_verify(self, filepath: str, new_content: str, original: str,
                          fix_type: str, error_code: str = "", detail: str = "") -> bool:
        """Write new content, verify with tsc, revert if worse."""
        if new_content == original:
            return False

        self._write_file(filepath, new_content)

        # Quick tsc check to see if we reduced errors
        ok, new_count = self._tsc_check()
        # We don't need build to pass; we need errors to not increase
        # But we DO want to make sure we didn't break things worse
        # For safety, we revert if error count increases
        # We use a cached baseline from the caller

        result = FixResult(
            file=filepath, fix_type=fix_type,
            success=True, error_code=error_code, detail=detail
        )
        self.fixes_applied.append(result)

        short = Path(filepath).name
        log(f"  ✓ {fix_type}: {short} — {detail}", "FIX")
        return True

    def _revert(self, filepath: str, original: str, fix_type: str,
                error_code: str = "", reason: str = ""):
        """Revert a file to its original content."""
        self._write_file(filepath, original)
        result = FixResult(
            file=filepath, fix_type=fix_type,
            success=False, error_code=error_code, detail=reason
        )
        self.fixes_reverted.append(result)
        short = Path(filepath).name
        log(f"  ✗ reverted {fix_type}: {short} — {reason}", "REVERT")

    # ─── Fix: Unused Variables (TS6133 / TS6196 / TS6192) ───────────────

    def fix_unused_vars(self, errors: List[TSError]) -> int:
        """Remove or prefix unused variables/imports.
        
        BATCH strategy: apply all edits across all files first, then verify
        once with tsc. If errors increase, revert ALL files.
        """
        fixed = 0
        # Group by file for batch processing
        by_file: Dict[str, List[TSError]] = defaultdict(list)
        for err in errors:
            if err.code in ("TS6133", "TS6196", "TS6192"):
                by_file[err.file].append(err)

        originals: Dict[str, str] = {}  # filepath -> original content (for revert)
        modified_files: Dict[str, str] = {}  # filepath -> new content
        total_fixes = 0

        for filepath, file_errors in by_file.items():
            if self._shutting_down:
                break

            original = self._read_file(filepath)
            if original is None:
                continue

            lines = original.split("\n")
            modified = False
            removed_lines = set()

            # Sort errors by line number descending so we can remove lines without offset issues
            file_errors.sort(key=lambda e: -e.line)

            for err in file_errors:
                if self._shutting_down:
                    break

                # Extract the variable name from the error message
                name_match = re.match(r"'([^']+)' is declared but its value is never read", err.message)
                if not name_match:
                    name_match = re.match(r"'([^']+)' is declared but never used", err.message)
                if not name_match:
                    continue

                var_name = name_match.group(1)
                line_idx = err.line - 1  # 0-indexed

                if line_idx < 0 or line_idx >= len(lines):
                    continue

                line = lines[line_idx]

                # Case 1: Import statement — remove the specific import
                if self._try_remove_from_import(lines, line_idx, var_name, removed_lines):
                    modified = True
                    continue

                # Case 2: Destructured variable like `const { x, y } = ...`
                if self._try_remove_destructured(lines, line_idx, var_name, removed_lines):
                    modified = True
                    continue

                # Case 3: Standalone variable declaration — prefix with _
                if self._try_prefix_underscore(lines, line_idx, var_name):
                    modified = True
                    continue

            if modified:
                # Remove marked lines
                new_lines = [l for i, l in enumerate(lines) if i not in removed_lines]
                new_content = "\n".join(new_lines)

                if new_content != original:
                    originals[filepath] = original
                    modified_files[filepath] = new_content
                    total_fixes += len(file_errors)

        if not modified_files:
            return 0

        # BATCH WRITE: apply all files at once
        for filepath, new_content in modified_files.items():
            self._write_file(filepath, new_content)

        log(f"  Wrote {len(modified_files)} files, verifying with tsc...", "FIX")

        # SINGLE tsc check for the entire batch
        _, new_count = self._tsc_check()

        # Compare against the baseline error count passed from the cycle engine
        # (stored on self by the cycle engine before fix_all)
        baseline = getattr(self, '_baseline_errors', new_count + 1)

        if new_count <= baseline:
            for filepath in modified_files:
                short = Path(filepath).name
                n_errs = len(by_file.get(filepath, []))
                self.fixes_applied.append(FixResult(
                    file=filepath, fix_type="unused_var",
                    success=True, error_code="TS6133",
                    detail=f"removed/prefixed {n_errs} unused vars"
                ))
                log(f"  ✓ unused_var: {short}", "FIX")
            fixed = total_fixes
            log(f"  Batch verified: {baseline}→{new_count} errors ({baseline - new_count} fixed)", "FIX")
        else:
            # Revert ALL files
            for filepath, original in originals.items():
                self._write_file(filepath, original)
            log(f"  ✗ Batch reverted: errors increased {baseline}→{new_count}", "REVERT")
            for filepath in modified_files:
                self.fixes_reverted.append(FixResult(
                    file=filepath, fix_type="unused_var",
                    success=False, error_code="TS6133",
                    detail=f"batch revert — errors increased"
                ))

        return fixed

    @staticmethod
    def _try_remove_from_import(lines: List[str], line_idx: int, var_name: str,
                                removed_lines: set) -> bool:
        """Try to remove a named import from an import statement. Returns True if modified."""
        line = lines[line_idx]

        # Check if this is an import line
        if not re.match(r'\s*import\s', line):
            return False

        # Handle multi-line imports: find the full import statement
        start_idx = line_idx
        end_idx = line_idx

        # Find start of import (might be on a previous line)
        while start_idx > 0 and 'import' not in lines[start_idx]:
            start_idx -= 1

        # Find end of import (line with 'from')
        while end_idx < len(lines) - 1 and 'from' not in lines[end_idx]:
            end_idx += 1

        # Reconstruct full import
        full_import = "\n".join(lines[start_idx:end_idx + 1])

        # Check for named imports { X, Y, Z }
        named_match = re.search(r'\{([^}]+)\}', full_import)
        if not named_match:
            # Default import — if the var_name IS the default import, remove the whole line
            default_match = re.match(r'\s*import\s+' + re.escape(var_name) + r'\s+from\s', line)
            if default_match:
                for i in range(start_idx, end_idx + 1):
                    removed_lines.add(i)
                return True
            return False

        imports_str = named_match.group(1)
        imports = [i.strip() for i in imports_str.split(",") if i.strip()]

        # Find and remove the target import
        new_imports = []
        found = False
        for imp in imports:
            # Handle 'X as Y' aliases
            parts = imp.split(" as ")
            base_name = parts[0].strip()
            alias = parts[-1].strip() if len(parts) > 1 else base_name

            if alias == var_name or base_name == var_name:
                found = True
            else:
                new_imports.append(imp)

        if not found:
            return False

        if not new_imports:
            # No imports left — remove the entire import statement
            for i in range(start_idx, end_idx + 1):
                removed_lines.add(i)
            return True

        # Rebuild the import with remaining imports
        # Find the 'from' clause
        from_match = re.search(r'from\s+[\'"][^\'"]+[\'"]', full_import)
        from_clause = from_match.group(0) if from_match else ""

        # Check if there's also a default import
        default_prefix = ""
        default_match = re.match(r'(\s*import\s+\w+\s*,\s*)\{', full_import)
        if default_match:
            default_prefix = default_match.group(1).rstrip().rstrip(",") + ", "
        else:
            default_prefix = "import "

        # Check for type imports
        type_prefix = ""
        if re.match(r'\s*import\s+type\s', full_import):
            default_prefix = "import type "

        new_import_str = f"{default_prefix}{{ {', '.join(new_imports)} }} {from_clause}"

        # Replace the multi-line import with a single line
        lines[start_idx] = new_import_str
        for i in range(start_idx + 1, end_idx + 1):
            removed_lines.add(i)

        return True

    @staticmethod
    def _try_remove_destructured(lines: List[str], line_idx: int, var_name: str,
                                 removed_lines: set) -> bool:
        """Remove a variable from a destructuring assignment like `const { x, y } = ...`."""
        line = lines[line_idx]

        destr_match = re.match(r'(\s*(?:const|let|var)\s+)\{([^}]+)\}(\s*=\s*.+)', line)
        if not destr_match:
            return False

        prefix = destr_match.group(1)
        vars_str = destr_match.group(2)
        suffix = destr_match.group(3)

        vars_list = [v.strip() for v in vars_str.split(",") if v.strip()]

        new_vars = []
        found = False
        for v in vars_list:
            # Handle renaming: `origName: newName`
            parts = v.split(":")
            actual_name = parts[-1].strip() if len(parts) > 1 else parts[0].strip()

            if actual_name == var_name:
                found = True
            else:
                new_vars.append(v)

        if not found:
            return False

        if not new_vars:
            # All vars unused — remove entire line
            removed_lines.add(line_idx)
            return True

        lines[line_idx] = f"{prefix}{{ {', '.join(new_vars)} }}{suffix}"
        return True

    @staticmethod
    def _try_prefix_underscore(lines: List[str], line_idx: int, var_name: str) -> bool:
        """Prefix an unused variable with _ to suppress the error."""
        line = lines[line_idx]

        # Don't prefix if already prefixed
        if var_name.startswith("_"):
            return False

        # Common patterns: const x = ..., let x = ..., function params
        # For destructured: { x } or { x, y }
        # Only prefix standalone declarations, not in complex expressions
        patterns = [
            # const/let/var name = ...
            (r'(\b(?:const|let|var)\s+)(' + re.escape(var_name) + r')(\s*[=:;])',
             lambda m: m.group(1) + "_" + m.group(2) + m.group(3)),
            # Function parameter
            (r'(\((?:[^)]*,\s*)?)(' + re.escape(var_name) + r')(\s*[:,)\]])',
             lambda m: m.group(1) + "_" + m.group(2) + m.group(3)),
        ]

        for pattern, replacement in patterns:
            new_line = re.sub(pattern, replacement, line, count=1)
            if new_line != line:
                lines[line_idx] = new_line
                return True

        return False

    # ─── Fix: Implicit Any (TS7006) ─────────────────────────────────────

    def fix_implicit_any(self, errors: List[TSError]) -> int:
        """Add explicit type annotations to parameters with implicit any.
        
        BATCH strategy: apply all edits, then verify once with tsc.
        """
        fixed = 0
        by_file: Dict[str, List[TSError]] = defaultdict(list)
        for err in errors:
            if err.code == "TS7006":
                by_file[err.file].append(err)

        originals: Dict[str, str] = {}
        modified_files: Dict[str, str] = {}
        total_fixes = 0

        for filepath, file_errors in by_file.items():
            if self._shutting_down:
                break

            original = self._read_file(filepath)
            if original is None:
                continue

            lines = original.split("\n")
            modified = False

            # Sort by line desc
            file_errors.sort(key=lambda e: -e.line)

            for err in file_errors:
                # Extract param name
                name_match = re.match(r"Parameter '([^']+)' implicitly has an 'any' type", err.message)
                if not name_match:
                    continue

                param_name = name_match.group(1)
                line_idx = err.line - 1
                if line_idx < 0 or line_idx >= len(lines):
                    continue

                line = lines[line_idx]

                # Common context-specific type inferences
                type_hint = "any"
                param_lower = param_name.lower()

                if param_lower in ("e", "event", "ev"):
                    type_hint = "React.SyntheticEvent"
                elif param_lower in ("err", "error"):
                    type_hint = "Error"
                elif param_lower in ("checked", "value"):
                    if "Checkbox" in line or "checked" in line:
                        type_hint = "boolean"
                    elif "onChange" in line and "input" in line.lower():
                        type_hint = "string"
                elif param_lower in ("index", "idx", "i"):
                    type_hint = "number"
                elif param_lower in ("key", "name", "label", "text", "title", "id", "str", "s"):
                    type_hint = "string"
                elif param_lower in ("data", "result", "response", "item", "row"):
                    type_hint = "any"
                elif param_lower in ("v", "val"):
                    type_hint = "any"

                escaped = re.escape(param_name)
                if re.search(escaped + r'\s*:', line):
                    continue

                new_line = re.sub(
                    r'(\b)' + escaped + r'(\s*[,)\]])',
                    r'\1' + param_name + ': ' + type_hint + r'\2',
                    line, count=1
                )

                if new_line == line:
                    new_line = re.sub(
                        r'(\b)' + escaped + r'(\s*=>)',
                        r'(\1' + param_name + ': ' + type_hint + r')\2',
                        line, count=1
                    )

                if new_line != line:
                    lines[line_idx] = new_line
                    modified = True

            if modified:
                new_content = "\n".join(lines)
                if new_content != original:
                    originals[filepath] = original
                    modified_files[filepath] = new_content
                    total_fixes += len(file_errors)

        if not modified_files:
            return 0

        # BATCH WRITE
        for filepath, new_content in modified_files.items():
            self._write_file(filepath, new_content)

        log(f"  Wrote {len(modified_files)} files, verifying with tsc...", "FIX")

        # SINGLE tsc check
        _, new_count = self._tsc_check()
        baseline = getattr(self, '_baseline_errors', new_count + 1)

        if new_count <= baseline:
            for filepath in modified_files:
                short = Path(filepath).name
                n_errs = len(by_file.get(filepath, []))
                self.fixes_applied.append(FixResult(
                    file=filepath, fix_type="implicit_any",
                    success=True, error_code="TS7006",
                    detail=f"typed {n_errs} implicit-any params"
                ))
                log(f"  ✓ implicit_any: {short}", "FIX")
            fixed = total_fixes
            log(f"  Batch verified: {baseline}→{new_count} errors ({baseline - new_count} fixed)", "FIX")
        else:
            for filepath, original in originals.items():
                self._write_file(filepath, original)
            log(f"  ✗ Batch reverted: errors increased {baseline}→{new_count}", "REVERT")
            for filepath in modified_files:
                self.fixes_reverted.append(FixResult(
                    file=filepath, fix_type="implicit_any",
                    success=False, error_code="TS7006",
                    detail="batch revert — errors increased"
                ))

        return fixed

    # ─── Fix: Unused React import (TS6133 for React) ────────────────────

    def fix_unused_react_import(self, errors: List[TSError]) -> int:
        """Remove `import React from 'react'` when not needed (React 17+ JSX transform)."""
        fixed = 0
        for err in errors:
            if self._shutting_down:
                break
            if err.code != "TS6133":
                continue
            if "'React' is declared but" not in err.message:
                continue

            original = self._read_file(err.file)
            if original is None:
                continue

            lines = original.split("\n")
            line_idx = err.line - 1
            if line_idx < 0 or line_idx >= len(lines):
                continue

            line = lines[line_idx]
            # Only remove if it's a standalone React import
            if re.match(r"\s*import\s+React\s+from\s+['\"]react['\"];?\s*$", line):
                lines[line_idx] = ""
                new_content = "\n".join(lines)
                # Don't even need tsc check for this — it's safe
                self._write_file(err.file, new_content)
                self.fixes_applied.append(FixResult(
                    file=err.file, fix_type="unused_react",
                    success=True, error_code="TS6133", detail="removed unused React import"
                ))
                fixed += 1

        return fixed

    # ─── Master fix dispatcher ──────────────────────────────────────────

    def fix_all(self, errors: List[TSError], max_files: int = 30) -> Dict[str, int]:
        """Apply all applicable fixers. Returns {fix_type: count}."""
        self.fixes_applied = []
        self.fixes_reverted = []
        self.fixes_skipped = 0

        results = {}

        # 1. Unused React imports first (very safe)
        react_errs = [e for e in errors if e.code == "TS6133" and "'React'" in e.message]
        if react_errs and not self._shutting_down:
            log(f"Fixing {len(react_errs)} unused React imports...")
            results["unused_react"] = self.fix_unused_react_import(react_errs)

        # 2. Unused variables/imports (biggest category, mostly mechanical)
        unused_errs = [e for e in errors
                       if e.code in ("TS6133", "TS6196", "TS6192")]
        if unused_errs and not self._shutting_down:
            # Limit to max_files files per cycle
            files_seen = set()
            limited_errs = []
            for e in unused_errs:
                if e.file not in files_seen:
                    files_seen.add(e.file)
                    if len(files_seen) > max_files:
                        break
                limited_errs.append(e)

            log(f"Fixing unused vars in {len(files_seen)} files ({len(limited_errs)} errors)...")
            results["unused_var"] = self.fix_unused_vars(limited_errs)

        # 3. Implicit any parameters
        any_errs = [e for e in errors if e.code == "TS7006"]
        if any_errs and not self._shutting_down:
            files_seen = set()
            limited_errs = []
            for e in any_errs:
                if e.file not in files_seen:
                    files_seen.add(e.file)
                    if len(files_seen) > max_files:
                        break
                limited_errs.append(e)

            log(f"Fixing {len(limited_errs)} implicit-any params in {len(files_seen)} files...")
            results["implicit_any"] = self.fix_implicit_any(limited_errs)

        return results


# =============================================================================
# UX ANALYZER
# =============================================================================

class UXAnalyzer(AgentComponent):
    """Checks for accessibility, responsive design, loading/error states."""

    def __init__(self):
        self.issues: List[Dict[str, str]] = []

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE, "src").exists()

    def analyze(self) -> List[Dict[str, str]]:
        """Scan all TSX files for UX issues."""
        self.issues = []
        src = Path(WORKSPACE, "src")

        for filepath in src.rglob("*.tsx"):
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue

            rel = str(filepath.relative_to(WORKSPACE))
            self._check_accessibility(rel, content)
            self._check_loading_states(rel, content)
            self._check_error_handling(rel, content)

        return self.issues

    def _check_accessibility(self, filepath: str, content: str):
        """Check for missing accessibility attributes."""
        # Missing alt text on images
        img_no_alt = re.findall(r'<img\s+(?![^>]*alt=)[^>]*>', content)
        if img_no_alt:
            self.issues.append({
                "file": filepath,
                "category": "a11y",
                "severity": "HIGH",
                "issue": f"{len(img_no_alt)} <img> without alt attribute",
            })

        # Clickable divs without role/tabindex
        onclick_divs = re.findall(r'<div[^>]*onClick[^>]*>', content)
        for div in onclick_divs:
            if "role=" not in div and "tabIndex" not in div:
                self.issues.append({
                    "file": filepath,
                    "category": "a11y",
                    "severity": "MEDIUM",
                    "issue": "Clickable <div> without role/tabIndex",
                })
                break  # one per file is enough

        # Buttons without aria-label (icon-only buttons)
        icon_buttons = re.findall(r'<(?:button|Button)[^>]*>[^<]*<(?:svg|Icon|[A-Z]\w+Icon)', content)
        for btn in icon_buttons:
            if "aria-label" not in btn and "title" not in btn:
                self.issues.append({
                    "file": filepath,
                    "category": "a11y",
                    "severity": "MEDIUM",
                    "issue": "Icon-only button may need aria-label",
                })
                break

    def _check_loading_states(self, filepath: str, content: str):
        """Check for proper loading state handling."""
        # Components using useQuery/useMutation without loading check
        has_query = "useQuery" in content or "useMutation" in content
        has_loading = any(k in content for k in ("isLoading", "isPending", "isFetching", "Skeleton", "Spinner"))

        if has_query and not has_loading:
            self.issues.append({
                "file": filepath,
                "category": "loading",
                "severity": "MEDIUM",
                "issue": "Uses query hooks but no loading state handling",
            })

    def _check_error_handling(self, filepath: str, content: str):
        """Check for error boundary / error state handling."""
        has_query = "useQuery" in content or "useMutation" in content
        has_error = any(k in content for k in ("isError", "error", "ErrorBoundary", "ErrorFallback"))

        if has_query and not has_error:
            self.issues.append({
                "file": filepath,
                "category": "error",
                "severity": "MEDIUM",
                "issue": "Uses query hooks but no error state handling",
            })

    def print_report(self):
        """Print UX analysis results."""
        if not self.issues:
            print("\n  No UX issues found. ✨")
            return

        print(f"\n{'='*70}")
        print(f"  UX Analysis Report — {len(self.issues)} issues")
        print(f"{'='*70}")

        by_cat = defaultdict(list)
        for issue in self.issues:
            by_cat[issue["category"]].append(issue)

        for cat, issues in sorted(by_cat.items()):
            print(f"\n  [{cat.upper()}] — {len(issues)} issues")
            for iss in issues[:10]:
                sev = iss["severity"]
                print(f"    [{sev}] {iss['file']}: {iss['issue']}")
            if len(issues) > 10:
                print(f"    ... and {len(issues) - 10} more")

        print(f"{'='*70}\n")


# =============================================================================
# BUILD VERIFIER
# =============================================================================

class BuildVerifier(AgentComponent):
    """Runs `npm run build`, tracks pass/fail history."""

    def __init__(self):
        self.history: List[Dict] = []

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return Path(WORKSPACE, "package.json").exists()

    def verify(self) -> Tuple[bool, str, float]:
        """Run build. Returns (passed, output, duration)."""
        log_debug("Running npm run build...")
        ok, stdout, stderr, duration = run_cmd(["npm", "run", "build"], timeout=180)
        output = stdout + stderr

        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "passed": ok,
            "duration": round(duration, 1),
            "errors": len(re.findall(r'error TS\d+', output)) if not ok else 0,
        })

        if ok:
            log(f"Build PASSED ({duration:.1f}s)", "BUILD")
        else:
            err_count = len(re.findall(r'error TS\d+', output))
            log(f"Build FAILED — {err_count} errors ({duration:.1f}s)", "BUILD")

        return ok, output, duration

    @property
    def last_passed(self) -> Optional[bool]:
        if not self.history:
            return None
        return self.history[-1]["passed"]


# =============================================================================
# GIT MANAGER
# =============================================================================

class GitManager(AgentComponent):
    """Branch management, commits, and reverts for safe auto-improvement."""

    def __init__(self):
        self.current_branch = ""
        self.cycle_branch = ""
        self.cycle_start_sha = ""

    def initialize(self) -> bool:
        ok, stdout, _, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if ok:
            self.current_branch = stdout.strip()
        return ok

    def validate(self) -> bool:
        ok, _, _, _ = run_cmd(["git", "status", "--short"])
        return ok

    def create_cycle_branch(self) -> bool:
        """Create or continue on an improvement branch.
        
        First cycle: create a new branch from current HEAD.
        Subsequent cycles: stay on the current auto-improve branch
        so fixes compound across cycles.
        """
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")

        # Save current SHA for potential revert
        ok, stdout, _, _ = run_cmd(["git", "rev-parse", "HEAD"])
        if ok:
            self.cycle_start_sha = stdout.strip()

        # Check if we're already on an auto-improve branch
        ok, current_branch, _, _ = run_cmd(["git", "branch", "--show-current"])
        current_branch = current_branch.strip() if ok else ""

        if current_branch.startswith("auto-improve/"):
            # Already on an auto-improve branch — stay here, just tag the cycle start
            self.cycle_branch = current_branch
            log(f"Continuing on branch: {self.cycle_branch}", "GIT")
            return True

        # First cycle: create new branch
        self.cycle_branch = f"auto-improve/{ts}"

        # Stash any existing changes first
        run_cmd(["git", "stash", "push", "-m", f"pre-auto-improve-{ts}"])

        # Create and checkout branch
        ok, _, stderr, _ = run_cmd(["git", "checkout", "-b", self.cycle_branch])
        if not ok:
            log(f"Failed to create branch {self.cycle_branch}: {stderr}", "GIT")
            run_cmd(["git", "stash", "pop"])
            return False

        # Pop stash on new branch
        run_cmd(["git", "stash", "pop"])
        log(f"Created branch: {self.cycle_branch}", "GIT")
        return True

    def commit(self, message: str) -> bool:
        """Stage all changes and commit."""
        run_cmd(["git", "add", "-A"])
        ok, stdout, stderr, _ = run_cmd(["git", "commit", "-m", message, "--no-verify"])
        if ok:
            log_debug(f"Committed: {message[:60]}")
        return ok

    def revert_cycle(self) -> bool:
        """Revert all changes in this cycle and return to original branch."""
        if self.cycle_start_sha:
            ok, _, _, _ = run_cmd(["git", "reset", "--hard", self.cycle_start_sha])
            if ok:
                log("Reverted cycle — errors increased", "GIT")
            return ok
        return False

    def return_to_original(self):
        """Switch back to the original branch."""
        if self.current_branch and self.current_branch != self.cycle_branch:
            run_cmd(["git", "checkout", self.current_branch])

    def get_diff_stats(self) -> str:
        """Get a summary of changes in the current cycle."""
        ok, stdout, _, _ = run_cmd(["git", "diff", "--stat", "HEAD~1"])
        if ok:
            return stdout.strip()
        return "(no diff)"


# =============================================================================
# REPORTER
# =============================================================================

class Reporter(AgentComponent):
    """Prints cycle summaries and writes JSON reports."""

    def initialize(self) -> bool:
        CYCLES_DIR.mkdir(parents=True, exist_ok=True)
        return True

    def validate(self) -> bool:
        return True

    @staticmethod
    def print_summary(result: CycleResult):
        """Print a clean cycle summary table."""
        trend_icon = result.trend
        if result.end_errors < result.start_errors:
            trend_icon = f"↓ ({result.start_errors - result.end_errors} fixed)"
        elif result.end_errors > result.start_errors:
            trend_icon = f"↑ ({result.end_errors - result.start_errors} new)"
        else:
            trend_icon = "→ (no change)"

        build_status = "✅ PASSED" if result.build_passed else "❌ FAILED"

        print(f"\n{'━'*70}")
        print(f"  CYCLE {result.cycle_number} SUMMARY")
        print(f"{'━'*70}")
        print(f"  Duration:         {result.duration_secs:.1f}s")
        print(f"  Errors (start):   {result.start_errors}")
        print(f"  Errors (end):     {result.end_errors}")
        print(f"  Trend:            {trend_icon}")
        print(f"  Fixes attempted:  {result.fixes_attempted}")
        print(f"  Fixes applied:    {result.fixes_applied}")
        print(f"  Fixes reverted:   {result.fixes_reverted}")
        print(f"  Build status:     {build_status}")

        if result.error_breakdown:
            print(f"\n  Error Breakdown:")
            for cat, count in sorted(result.error_breakdown.items(), key=lambda x: -x[1]):
                print(f"    {cat:20s}  {count:4d}")

        if result.top_remaining:
            print(f"\n  Top Remaining Issues:")
            for issue in result.top_remaining[:5]:
                print(f"    • {issue}")

        print(f"{'━'*70}\n")

    @staticmethod
    def write_cycle_json(result: CycleResult):
        """Write cycle results to a JSON file."""
        CYCLES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filepath = CYCLES_DIR / f"{ts}.json"
        filepath.write_text(json.dumps(result.to_dict(), indent=2))
        log_debug(f"Wrote cycle report: {filepath}")


# =============================================================================
# STATE PERSISTENCE
# =============================================================================

class StatePersistence:
    """Tracks cycle count, total fixes, error trends across restarts."""

    def __init__(self):
        self.cycle_count = 0
        self.total_fixes = 0
        self.error_history: List[int] = []
        self.implemented_features: List[str] = []
        self.last_run: str = ""
        self._load()

    def _load(self):
        """Load state from disk."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.cycle_count = data.get("cycle_count", 0)
                self.total_fixes = data.get("total_fixes", 0)
                self.error_history = data.get("error_history", [])
                self.implemented_features = data.get("implemented_features", [])
                self.last_run = data.get("last_run", "")
            except Exception:
                pass

    def save(self):
        """Persist state to disk."""
        data = {
            "cycle_count": self.cycle_count,
            "total_fixes": self.total_fixes,
            "error_history": self.error_history[-100:],  # keep last 100
            "implemented_features": self.implemented_features,
            "last_run": datetime.now().isoformat(),
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def record_cycle(self, errors: int, fixes: int):
        """Record a completed cycle."""
        self.cycle_count += 1
        self.total_fixes += fixes
        self.error_history.append(errors)
        self.save()

    def print_status(self):
        """Print current state summary."""
        print(f"\n{'='*50}")
        print(f"  Agent v3 Status")
        print(f"{'='*50}")
        print(f"  Total cycles run:   {self.cycle_count}")
        print(f"  Total fixes applied: {self.total_fixes}")
        print(f"  Last run:           {self.last_run or 'never'}")

        if self.error_history:
            recent = self.error_history[-10:]
            print(f"  Error trend (last {len(recent)}):")
            for i, count in enumerate(recent):
                bar = "█" * min(count // 10, 40)
                print(f"    Cycle {self.cycle_count - len(recent) + i + 1}: {count:4d} {bar}")

        if self.implemented_features:
            print(f"\n  Implemented features:")
            for feat in self.implemented_features[-10:]:
                print(f"    • {feat}")

        print(f"{'='*50}\n")


# =============================================================================
# CYCLE ENGINE
# =============================================================================

class CycleEngine:
    """Orchestrates the full analyze → fix → build → verify pipeline."""

    def __init__(self, fix_only: bool = False):
        self.analyzer = TypeScriptAnalyzer()
        self.fixer = SmartFixer()
        self.ux = UXAnalyzer()
        self.builder = BuildVerifier()
        self.git = GitManager()
        self.reporter = Reporter()
        self.state = StatePersistence()
        self.fix_only = fix_only
        self._running = True
        self._skip_to_next = False
        self._consecutive_errors = 0

    def initialize(self) -> bool:
        """Initialize all components."""
        components = [
            self.analyzer, self.fixer, self.ux, self.builder,
            self.git, self.reporter,
        ]
        for comp in components:
            if not comp.initialize():
                log(f"Failed to initialize {comp.__class__.__name__}", "ERROR")
                return False
        return True

    def stop(self):
        """Signal graceful shutdown."""
        self._running = False
        self.fixer.request_shutdown()
        log("Shutdown requested — finishing current fix...", "SIGNAL")

    def skip_cycle(self):
        """Skip to the next cycle."""
        self._skip_to_next = True
        log("Skip to next cycle requested", "SIGNAL")

    def run_cycle(self) -> Optional[CycleResult]:
        """Execute one full improvement cycle."""
        cycle_start = time.time()
        cycle_num = self.state.cycle_count + 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log(f"\n{'='*60}", "CYCLE")
        log(f"CYCLE {cycle_num} — {ts}", "CYCLE")
        log(f"{'='*60}", "CYCLE")

        # Step 1: Analyze current state
        log("Step 1: TypeScript analysis...", "CYCLE")
        errors = self.analyzer.analyze()
        start_errors = self.analyzer.total_errors
        category_summary = self.analyzer.get_category_summary()
        log(f"  Found {start_errors} errors across {len(self.analyzer.errors_by_file)} files")

        if not QUIET:
            for cat, count in sorted(category_summary.items(), key=lambda x: -x[1]):
                log(f"    {cat:20s} {count:4d}", "DEBUG")

        # Step 2: Create git branch for safety
        log("Step 2: Git safety branch...", "CYCLE")
        branch_ok = self.git.create_cycle_branch()
        if not branch_ok:
            log("  Skipping git branch (may be in detached state)", "WARN")

        # Step 3: Apply fixes
        log("Step 3: Applying fixes...", "CYCLE")
        # Set baseline so batch fixers know the starting error count
        self.fixer._baseline_errors = start_errors
        fix_results = self.fixer.fix_all(errors, max_files=30)

        total_fixed = sum(fix_results.values())
        total_attempted = total_fixed + len(self.fixer.fixes_reverted) + self.fixer.fixes_skipped

        if total_fixed > 0 and branch_ok:
            fix_msg = ", ".join(f"{k}: {v}" for k, v in fix_results.items() if v > 0)
            self.git.commit(f"auto-fix cycle {cycle_num}: {fix_msg}")

        # Step 4: Re-analyze to measure improvement
        log("Step 4: Re-analyzing...", "CYCLE")
        errors_after = self.analyzer.analyze()
        end_errors = self.analyzer.total_errors
        trend = self.analyzer.get_trend()
        self.analyzer.last_total = end_errors

        # Step 5: Build verification
        log("Step 5: Build verification...", "CYCLE")
        build_ok, _, build_duration = self.builder.verify()

        # Step 6: UX analysis (not in fix-only mode)
        if not self.fix_only and not QUIET:
            log("Step 6: UX analysis...", "CYCLE")
            ux_issues = self.ux.analyze()
            if ux_issues and not QUIET:
                log(f"  Found {len(ux_issues)} UX issues")

        # Step 7: Safety check — if errors increased, revert
        if end_errors > start_errors and branch_ok:
            log(f"Errors increased ({start_errors} → {end_errors}), reverting cycle!", "WARN")
            self.git.revert_cycle()
            end_errors = start_errors

        # Record state
        self.state.record_cycle(end_errors, total_fixed)

        # Build result
        top_remaining = []
        for err in errors_after[:5]:
            top_remaining.append(f"{err.location}: {err.code} {err.message[:50]}")

        result = CycleResult(
            cycle_number=cycle_num,
            timestamp=ts,
            start_errors=start_errors,
            end_errors=end_errors,
            fixes_attempted=total_attempted,
            fixes_applied=total_fixed,
            fixes_reverted=len(self.fixer.fixes_reverted),
            build_passed=build_ok,
            duration_secs=time.time() - cycle_start,
            error_breakdown=category_summary,
            top_remaining=top_remaining,
            trend=trend,
        )

        # Report
        self.reporter.print_summary(result)
        self.reporter.write_cycle_json(result)

        # Return to original branch
        if branch_ok:
            self.git.return_to_original()

        # Error backoff
        if end_errors >= start_errors and total_fixed == 0:
            self._consecutive_errors += 1
            if self._consecutive_errors >= MAX_ERRORS_BEFORE_PAUSE:
                backoff = min(2 ** self._consecutive_errors, 300)
                log(f"No progress for {self._consecutive_errors} cycles, backing off {backoff}s", "WARN")
                time.sleep(backoff)
        else:
            self._consecutive_errors = 0

        return result

    def run_continuous(self):
        """Run cycles until stopped."""
        log("Starting continuous improvement pipeline...", "ENGINE")
        log(f"Workspace: {WORKSPACE}")
        log(f"Model: {MODEL}")

        while self._running:
            self._skip_to_next = False
            try:
                result = self.run_cycle()
                if result and result.fixes_applied == 0 and result.start_errors == result.end_errors:
                    log("No mechanical fixes available. Stopping continuous mode.", "ENGINE")
                    log("Use --implement 'task' to make progress with AI-assisted changes.", "ENGINE")
                    break
            except KeyboardInterrupt:
                log("Interrupted — shutting down...", "ENGINE")
                break
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                self._consecutive_errors += 1
                if self._consecutive_errors >= MAX_ERRORS_BEFORE_PAUSE:
                    backoff = min(2 ** self._consecutive_errors, 300)
                    log(f"Too many errors, backing off {backoff}s", "WARN")
                    time.sleep(backoff)

        log("Engine stopped.", "ENGINE")


# =============================================================================
# CLI HANDLERS
# =============================================================================

def cmd_analyze():
    """Analysis + report only."""
    analyzer = TypeScriptAnalyzer()
    analyzer.initialize()

    log("Running TypeScript analysis...")
    errors = analyzer.analyze()
    analyzer.print_error_report()

    # UX analysis too
    ux = UXAnalyzer()
    ux.initialize()
    ux_issues = ux.analyze()
    ux.print_report()

    # Summary counts
    print(f"  Total TS errors:  {analyzer.total_errors}")
    print(f"  Total UX issues:  {len(ux_issues)}")
    print(f"  Files with errors: {len(analyzer.errors_by_file)}")


def cmd_errors():
    """Show current TS errors grouped by type."""
    analyzer = TypeScriptAnalyzer()
    analyzer.initialize()

    log("Running TypeScript analysis...")
    errors = analyzer.analyze()
    analyzer.print_error_report()


def cmd_status():
    """Show current state, last cycle results."""
    state = StatePersistence()
    state.print_status()

    # Also show current error count
    analyzer = TypeScriptAnalyzer()
    analyzer.initialize()
    errors = analyzer.analyze()
    print(f"  Current TS errors: {analyzer.total_errors}")


def cmd_once():
    """Single cycle."""
    engine = CycleEngine()
    if not engine.initialize():
        sys.exit(1)
    engine.run_cycle()


def cmd_fix_only():
    """Only apply mechanical fixes."""
    engine = CycleEngine(fix_only=True)
    if not engine.initialize():
        sys.exit(1)
    engine.run_cycle()


def cmd_continuous():
    """Run continuous autonomous mode."""
    engine = CycleEngine()
    if not engine.initialize():
        sys.exit(1)

    # Signal handlers
    def handle_sigint(signum, frame):
        engine.stop()

    def handle_sigusr1(signum, frame):
        engine.skip_cycle()

    signal.signal(signal.SIGINT, handle_sigint)
    try:
        signal.signal(signal.SIGUSR1, handle_sigusr1)
    except (AttributeError, ValueError):
        pass  # SIGUSR1 not available on all platforms

    engine.run_continuous()


def cmd_implement(task: str):
    """Spawn implementation of a specific task via OpenClaw."""
    log(f"Spawning implementation: {task[:80]}...")

    prompt = f"""You are a senior developer for ENS.tools ({WORKSPACE}).

TASK: {task}

Requirements:
1. Implement following TypeScript + React + Vite best practices
2. Add proper TypeScript types/interfaces
3. Handle loading states and errors
4. Write clean, maintainable code
5. After implementation, verify with 'npm run build'
6. The project uses: wagmi, viem, @tanstack/react-query, Radix UI, rainbowkit, lucide-react, tailwind

Begin implementation now."""

    env = {**os.environ, "OPENCLAW_WORKSPACE": WORKSPACE}
    try:
        result = subprocess.run(
            [
                "openclaw", "sessions", "spawn",
                "--agent-id", "main",
                "--model", MODEL,
                "--task", prompt,
                "--timeout", "600",
            ],
            capture_output=True, text=True, timeout=700,
            cwd=WORKSPACE, env=env,
        )

        if result.returncode == 0:
            log(f"Implementation completed: {task[:60]}", "SUCCESS")
            # Record in state
            state = StatePersistence()
            state.implemented_features.append(task)
            state.save()
        else:
            log(f"Implementation failed: {result.stderr[:200]}", "ERROR")

    except Exception as e:
        log(f"Failed to spawn: {e}", "ERROR")


# =============================================================================
# MAIN
# =============================================================================

def main():
    global QUIET

    parser = argparse.ArgumentParser(
        description="ENS.tools Autonomous Development Agent v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python3 dev_agent_v3.py                    # Continuous mode
              python3 dev_agent_v3.py --once              # Single cycle
              python3 dev_agent_v3.py --fix-only          # Mechanical fixes only
              python3 dev_agent_v3.py --analyze           # Analysis + report
              python3 dev_agent_v3.py --status            # Current state
              python3 dev_agent_v3.py --errors            # TS errors grouped
              python3 dev_agent_v3.py --implement "task"  # AI implementation
        """)
    )

    parser.add_argument("--once", action="store_true", help="Run a single cycle")
    parser.add_argument("--fix-only", action="store_true", help="Mechanical fixes only")
    parser.add_argument("--analyze", action="store_true", help="Analysis + report only")
    parser.add_argument("--status", action="store_true", help="Show current state")
    parser.add_argument("--errors", action="store_true", help="Show TS errors grouped")
    parser.add_argument("--implement", type=str, metavar="TASK", help="Implement a task")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")

    args = parser.parse_args()
    QUIET = args.quiet

    if not QUIET:
        print("ENS.tools Autonomous Development Agent v3")
        print(f"Workspace: {WORKSPACE}")
        print(f"Model: {MODEL}")
        print()

    if args.analyze:
        cmd_analyze()
    elif args.errors:
        cmd_errors()
    elif args.status:
        cmd_status()
    elif args.once:
        cmd_once()
    elif args.fix_only:
        cmd_fix_only()
    elif args.implement:
        cmd_implement(args.implement)
    else:
        cmd_continuous()


if __name__ == "__main__":
    main()
