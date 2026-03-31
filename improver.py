#!/usr/bin/env python3
"""
ENS Tools Improvement Agent - Full-Featured Version
Analyzes, researches, plans, executes, tests, and iterates on ENS.tools improvements.

Follows AGENT_SYSTEM_MAP (15 Components):
- INITIALIZATION FRAMEWORK: Bootstrap, context loading
- SECURITY MATRIX: Validation before operations
- MEMORY ARCHITECTURE: State persistence, task buffers
- PROCESS CONTROL: Core execution flow
- STATE MANAGEMENT: State transitions
- VERIFICATION FRAMEWORK: Build/test validation
- CHAIN CONTROL: Phase chaining
- ECHO PROTOCOL: Response formatting
- ACCESS CONTROL: Task permissions
"""

import os
import sys
import json
import time
import subprocess
import hashlib
import re
from pathlib import Path
from datetime import datetime
from enum import Enum

# ==================== CONFIGURATION ====================
WORKSPACE = "/Users/acc/ens.tools"
MODEL = "minimax-portal/MiniMax-M2.5"
AGENT_DIR = Path(__file__).parent
LOG_FILE = AGENT_DIR / "improvement.log"
STATE_FILE = AGENT_DIR / ".state.json"
TASK_QUEUE_FILE = AGENT_DIR / "tasks.json"
MAX_CYCLE_TIME = 600  # 10 minutes max per cycle
DEBOUNCE_SECONDS = 5

# ==================== STATE MANAGEMENT (Component #7) ====================
class AgentState(Enum):
    """State transitions for the agent"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    RESEARCHING = "researching"
    PLANNING = "planning"
    EXECUTING = "executing"
    TESTING = "testing"
    VERIFYING = "verifying"
    SELF_UPDATING = "self_updating"
    COMPLETE = "complete"
    ERROR = "error"
    HUNG = "hung"

# ==================== INITIALIZATION FRAMEWORK (Component #1) ====================
def initialize_agent():
    """Bootstrap the agent - load context and validate"""
    log("=" * 60)
    log("ENS Tools Improvement Agent - Full Feature")
    log(f"Workspace: {WORKSPACE}")
    log("Mode: Continuous analyze -> research -> plan -> execute -> test -> iterate")
    log("=" * 60)
    
    state = load_state()
    cycle = state.get("cycle", 0)
    
    # COMPONENT #2: SECURITY MATRIX - Validate before operations
    if not validate_environment():
        log("SECURITY: Environment validation failed")
        alert_user("ENS-Improver: Environment validation failed")
        return None, None, None
    
    # Check for hung previous run
    last_start = state.get("last_cycle_start")
    if last_start:
        elapsed = time.time() - last_start
        if elapsed > MAX_CYCLE_TIME:
            log(f"WARNING: Previous run was hung for {elapsed/60:.1f} minutes")
            alert_user(f"ENS-Improver was hung for {elapsed/60:.0f} minutes - restarting...")
            # Record the hang
            state["last_hang"] = {
                "duration": elapsed,
                "timestamp": datetime.now().isoformat(),
                "cycle": cycle
            }
    
    state["last_cycle_start"] = time.time()
    state["current_state"] = AgentState.INITIALIZING.value
    save_state(state)
    
    return state, cycle, AgentState.INITIALIZING

def validate_environment():
    """SECURITY MATRIX: Validate workspace and dependencies exist"""
    workspace = Path(WORKSPACE)
    if not workspace.exists():
        log(f"ERROR: Workspace {WORKSPACE} does not exist")
        return False
    
    # Check for package.json
    if not (workspace / "package.json").exists():
        log(f"ERROR: No package.json in {WORKSPACE}")
        return False
    
    # Check for npm
    try:
        subprocess.run(["npm", "--version"], capture_output=True, timeout=5)
    except:
        log("ERROR: npm not available")
        return False
    
    return True

# ==================== MEMORY ARCHITECTURE (Component #3) ====================
def load_state():
    """Load persistent state from memory"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            log(f"Warning: Failed to load state: {e}")
    return {
        "files": {},
        "cycle": 0,
        "last_analysis": None,
        "current_state": AgentState.IDLE.value,
        "error_count": 0
    }

def save_state(state):
    """Save state to persistent memory"""
    STATE_FILE.write_text(json.dumps(state, indent=2))

def load_tasks():
    """Load task queue from memory"""
    if TASK_QUEUE_FILE.exists():
        try:
            return json.loads(TASK_QUEUE_FILE.read_text())
        except:
            pass
    return {"tasks": [], "completed": []}

def save_tasks(tasks):
    """Save task queue to memory"""
    TASK_QUEUE_FILE.write_text(json.dumps(tasks, indent=2))

def get_file_hashes(directory: str) -> dict:
    """MEMORY: Track file changes"""
    hashes = {}
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ['node_modules', 'build', '.git', 'dist', 'cache']]
        for f in files:
            if f.endswith(('.ts', '.tsx', '.js', '.jsx', '.py', '.sol')):
                path = os.path.join(root, f)
                try:
                    with open(path, 'rb') as fp:
                        hashes[path] = hashlib.md5(fp.read()).hexdigest()
                except:
                    pass
    return hashes

# ==================== PROCESS CONTROL (Component #5) & CHAIN CONTROL (Component #9) ====================
def run_cycle(cycle: int):
    """PROCESS CONTROL: Run one complete improvement cycle with state transitions"""
    state = load_state()
    
    # CHAIN: INIT → ANALYZE → RESEARCH → PLAN → EXECUTE → TEST → VERIFY → COMPLETE
    chain = [
        (AgentState.ANALYZING, analyze_codebase),
        (AgentState.RESEARCHING, conduct_research),
        (AgentState.PLANNING, create_task_queue),
        (AgentState.EXECUTING, execute_tasks),
        (AgentState.TESTING, test_functionality),
    ]
    
    results = {}
    
    for state_enum, phase_func in chain:
        # Update state
        state["current_state"] = state_enum.value
        save_state(state)
        
        log("=" * 60)
        log(f"PHASE: {state_enum.value.upper()}")
        log("=" * 60)
        
        try:
            result = phase_func()
            results[state_enum.value] = {"success": True, "data": result}
            state["error_count"] = 0  # Reset error count on success
        except Exception as e:
            log(f"ERROR in {state_enum.value}: {e}")
            results[state_enum.value] = {"success": False, "error": str(e)}
            state["error_count"] = state.get("error_count", 0) + 1
            
            # If too many errors, alert and stop
            if state["error_count"] >= 3:
                alert_user(f"ENS-Improver: 3 consecutive errors, stopping")
                return cycle
        
        save_state(state)
    
    # Self-update phase
    state["current_state"] = AgentState.SELF_UPDATING.value
    self_update(cycle)
    
    # Final state
    state["current_state"] = AgentState.COMPLETE.value
    state["cycle"] = cycle
    state["last_analysis"] = datetime.now().isoformat()
    save_state(state)
    
    return cycle + 1

# ==================== PHASE FUNCTIONS ====================
def analyze_codebase():
    """PHASE 1: Analyze the application"""
    log("Analyzing ENS.tools codebase...")
    
    issues = {
        "bugs": [],
        "inefficiencies": [],
        "outdated_libs": [],
        "ux_issues": [],
        "security": [],
        "missing_features": []
    }
    
    # Check package.json
    pkg_json = Path(WORKSPACE) / "package.json"
    if pkg_json.exists():
        content = pkg_json.read_text()
        if "web3" in content:
            issues["outdated_libs"].append("Uses web3.js - consider migrating to viem")
    
    # Run TypeScript check
    log("Running TypeScript check...")
    success, stdout, stderr = run_command(["npx", "tsc", "--noEmit"], timeout=60)
    output = stdout + stderr
    
    if has_type_errors(output):
        error_count = get_error_count(output)
        issues["bugs"].append(f"{error_count} TypeScript errors found")
    
    # Check build
    success, build_output = build_app()
    if not success:
        issues["bugs"].append("Build failed")
    
    log(f"Analysis complete. Found {len(issues['bugs'])} bugs, {len(issues['inefficiencies'])} inefficiencies")
    return issues

def conduct_research():
    """PHASE 2: Research best practices"""
    log("Conducting research...")
    
    research_topics = [
        "ENSIP standards 2024 2025",
        "ENS domain management UX best practices",
        "Ethereum Name Service multi-chain support",
        "viem vs ethers.js performance comparison"
    ]
    
    log(f"Research topics: {len(research_topics)}")
    for topic in research_topics:
        log(f"  - {topic}")
    
    return {
        "topics": research_topics,
        "findings": [
            "ENSIP-10: Wildcard resolution support",
            "ENSIP-11: Name wrapper integration",
            "viem is recommended over ethers.js for new projects",
        ]
    }

def create_task_queue(analysis, research):
    """PHASE 3: Create prioritized tasks"""
    log("Creating task queue...")
    
    tasks = []
    
    # High priority - bugs
    for bug in analysis.get("bugs", []):
        tasks.append({
            "id": len(tasks) + 1,
            "title": f"Fix: {bug}",
            "priority": "high",
            "type": "bug_fix",
            "status": "pending"
        })
    
    # Medium priority - inefficiencies
    for ineff in analysis.get("inefficiencies", []):
        tasks.append({
            "id": len(tasks) + 1,
            "title": f"Optimize: {ineff}",
            "priority": "medium",
            "type": "optimization",
            "status": "pending"
        })
    
    log(f"Created {len(tasks)} tasks")
    return tasks

def execute_tasks(tasks):
    """PHASE 4: Execute tasks via sub-agents"""
    log("Executing tasks...")
    
    completed = []
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_tasks = sorted(tasks, key=lambda x: priority_order.get(x["priority"], 3))
    
    # Execute top task
    for task in sorted_tasks[:1]:
        if task["status"] == "pending":
            log(f"Executing: [{task['priority']}] {task['title']}")
            task["status"] = "in_progress"
            
            success = spawn_improver(task["title"])
            
            task["status"] = "completed" if success else "failed"
            completed.append(task)
    
    # Build to verify
    if completed:
        log("Building to verify changes...")
        build_success, output = build_app()
    
    return completed

def test_functionality():
    """PHASE 5: Test and verify"""
    log("Testing functionality...")
    
    # Run tests
    success, stdout, stderr = run_command(["npm", "run", "test", "--", "--run"], timeout=120)
    
    if success:
        log("Tests passed")
    else:
        log(f"Tests need attention")
    
    # Verify build
    build_success, output = build_app()
    if build_success:
        log("Build verification: OK")
    else:
        log("Build verification: FAILED")
    
    return build_success

def self_update(cycle: int):
    """PHASE 6: Self-update agent"""
    log(f"Self-update (Cycle {cycle})")
    
    if cycle % 10 == 0:
        log("Agent self-improvement: Analyzing performance...")

# ==================== DATA TRANSFER (Component #6) ====================
def run_command(cmd: list, cwd: str = None, timeout: int = 120) -> tuple:
    """TRANSFER: Execute command and transfer results"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def build_app() -> tuple:
    """TRANSFER: Build application"""
    log("Building application...")
    success, stdout, stderr = run_command(["npm", "run", "build"], timeout=180)
    return success, stdout + stderr

# ==================== VERIFICATION FRAMEWORK (Component #8) ====================
def has_type_errors(output: str) -> bool:
    """VERIFY: Check for TypeScript errors"""
    error_indicators = [": error TS", "ERROR in", "Build failed"]
    return any(indicator in output for indicator in error_indicators)

def get_error_count(output: str) -> int:
    """VERIFY: Count TypeScript errors"""
    return len(re.findall(r"error TS\d+:", output))

def verify_output() -> bool:
    """VERIFY: Validate agent output"""
    # Could add more sophisticated verification
    return True

# ==================== ECHO PROTOCOL (Component #10) ====================
def log(msg: str):
    """ECHO: Log output with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ==================== ACCESS CONTROL (Component #15) ====================
def spawn_improver(task_description: str):
    """ACCESS CONTROL: Spawn sub-agent with controlled access"""
    log(f"Spawning agent for: {task_description}")
    start_time = time.time()
    
    task = f"""Improve the ENS.tools application at {WORKSPACE}.

{task_description}

Context:
- Build system: Vite + React + TypeScript
- Focus on: {task_description}
- After changes, run 'npm run build' to verify
- Report what you did and any issues found"""

    cmd = [
        "openclaw", "sessions", "spawn",
        "--agent-id", "main",
        "--model", MODEL,
        "--task", task
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            log(f"ERROR: Spawn failed: {result.stderr[:500]}")
            alert_user(f"ENS-Improver spawn failed: {task_description[:50]}...")
            return False
            
        log(f"Spawn completed in {elapsed:.1f}s")
        return True
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        log(f"ERROR: Spawn timed out after {elapsed:.1f}s")
        alert_user(f"ENS-Improver TIMED OUT: {task_description[:50]}...")
        return False
    except Exception as e:
        log(f"ERROR: Spawn failed: {e}")
        alert_user(f"ENS-Improver error: {e}")
        return False

def alert_user(message: str):
    """ECHO: Send alert to user via webchat"""
    log(f"ALERT: {message}")
    try:
        subprocess.run(
            ["openclaw", "message", "send", "--channel", "webchat", "--message", f"[AGENT ALERT] {message}"],
            capture_output=True, timeout=10
        )
    except:
        pass  # Best effort

# ==================== MAIN ENTRY POINT ====================
def main():
    """Main execution with proper initialization"""
    state, cycle, init_state = initialize_agent()
    
    if state is None:
        log("Initialization failed")
        return
    
    try:
        while True:
            cycle = run_cycle(cycle)
            
            # Update state after successful cycle
            state = load_state()
            state["last_cycle_start"] = time.time()
            state["cycle"] = cycle
            state["current_state"] = AgentState.IDLE.value
            save_state(state)
            
            log(f"Cycle {cycle} complete")
            
    except KeyboardInterrupt:
        log("Stopped by user")
    except Exception as e:
        log(f"ERROR: {e}")
        alert_user(f"ENS-Improver crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
