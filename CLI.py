#!/usr/bin/env python3
import sys
import argparse
import logging
from datetime import datetime as dt

logging.getLogger("Planner").setLevel(logging.WARNING)

from Planner import Planner
from Task import Task

# ANSI Escape Sequences for terminal coloring
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

# This code was heavily assisted by AI for the terminal display logic.
# All actual cognitive logic is handled elsewhere in code I wrote myself.
# AI just helped me with rendering to the terminal

def render_bucket(title: str, tasks: list, show_math: bool, color: str):
    print(f"\n{BOLD}{color}== {title.upper()} BUCKET ({len(tasks)} tasks) =={RESET}")
    print("-" * 60)
    if not tasks:
        print("  * No tasks in this bucket.")
        return

    for task in tasks:
        marker = f"[{task.todo}]" if task.todo else "[ ]"
        
        # Display primary line
        if hasattr(task, 'score') and task.score is not None:
            print(f" * {marker} {task.heading:<35} | Score: {task.score:.2f}")
        else:
            print(f" * {marker} {task.heading:<35}")
            
        # Mathematical / Metadata breakdown breakdown if toggled
        if show_math:
            # body_preview = f" | {task.body[:40]}..." if task.body else ""
            # print(f"    {CYAN}[Level: {task.level} | Inherent U: {task.urgency:.2f}{body_preview}]{RESET}")
            print(f"    {CYAN}[Level: {task.level} | Inherent U: {task.urgency:.2f}]{RESET}")

def render_baseline_old(tasks: list):
    """Fallback standard chronological sorting for baseline validation."""
    print(f"\n{BOLD}{YELLOW}== CHRONOLOGICAL BASELINE AGENDA ({len(tasks)} tasks) =={RESET}")
    print("-" * 60)
    
    # Sort baseline: tasks with deadlines first, then scheduled, then priority string
    def baseline_key(t: Task):
        d_date = t.deadline.start if (t.deadline and t.deadline.start) else dt.max.date()
        s_date = t.scheduled.start if (t.scheduled and t.scheduled.start) else dt.max.date()
        prio = t.priority if t.priority else "Z"
        return (d_date, s_date, prio)

    sorted_baseline = sorted(tasks, key=baseline_key)
    
    for task in sorted_baseline:
        marker = f"[{task.todo}]" if task.todo else "[ ]"
        d_str = f" DL: {task.deadline.start}" if (task.deadline and task.deadline.start) else ""
        s_str = f" SCHED: {task.scheduled.start}" if (task.scheduled and task.scheduled.start) else ""
        p_str = f" Prio: {task.priority}" if task.priority else ""
        print(f" * {marker} {task.heading:<35} |{d_str}{s_str}{p_str}")

def render_baseline(tasks: list):
    """Fallback standard chronological sorting for baseline validation."""
    print(f"\n{BOLD}{YELLOW}== CHRONOLOGICAL BASELINE AGENDA ({len(tasks)} tasks) =={RESET}")
    print("-" * 60)
    
    # Sort baseline: Deadline -> Scheduled -> TODO State (NEXT then TODO) -> Priority
    def baseline_key(t: Task):
        d_date = t.deadline.start if (t.deadline and t.deadline.start) else dt.max.date()
        s_date = t.scheduled.start if (t.scheduled and t.scheduled.start) else dt.max.date()
        
        # Map TODO states to a ranking index: ACTIVE(0), NEXT (1, TODO (2), Others/None (3)
        todo_map = {"ACTIVE": 0, "NEXT": 1, "TODO": 2}
        todo_order = todo_map.get(t.todo, 3)
        
        prio = t.priority if t.priority else "Z"
        
        return (d_date, s_date, todo_order, prio)

    sorted_baseline = sorted(tasks, key=baseline_key)
    
    for task in sorted_baseline:
        marker = f"[{task.todo}]" if task.todo else "[ ]"
        d_str = f" DL: {task.deadline.start}" if (task.deadline and task.deadline.start) else ""
        s_str = f" SCHED: {task.scheduled.start}" if (task.scheduled and task.scheduled.start) else ""
        p_str = f" Prio: {task.priority}" if task.priority else ""
        print(f" * {marker} {task.heading:<35} |{d_str}{s_str}{p_str}")        

def main():
    parser = argparse.ArgumentParser(description="Cognitive Workflow Optimizer — CLI Interface")
    parser.add_argument("org_file", nargs="?", default="./test.org", help="Path to target org file")
    parser.add_argument("--ref-time", help="Reference time in YYYY-MM-DD HH:MM:SS format")
    parser.add_argument("--baseline", action="store_true", help="Run chronological baseline comparison")
    parser.add_argument("--show-math", action="store_true", help="Print advanced metadata and score vectors")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"{BOLD}COGNITIVE WORKFLOW OPTIMIZER — TERMINAL ENGINE{RESET}")
    print("=" * 60)
    
    try:
        planner = Planner(args.org_file)
        
        # Override the reference time if explicitly provided via CLI argument
        if args.ref_time:
            try:
                parsed_time = dt.strptime(args.ref_time, "%Y-%m-%d %H:%M:%S")
                planner.reference_time = parsed_time
                # Re-run initializations that rely on reference_time
                for task in planner.agenda.open_tasks:
                    planner.get_task_urgency(task)
                print(f"> Reference Time Overridden: {planner.reference_time}")
            except ValueError:
                print(f"{RED}[ERROR] Format ref-time as 'YYYY-MM-DD HH:MM:SS'{RESET}", file=sys.stderr)
                sys.exit(1)
        
        if args.baseline:
            render_baseline(planner.agenda.open_tasks)
        else:
            buckets = planner.get_buckets()
            
            if planner.current_task:
                print(f"\n> {BOLD}CURRENT COGNITIVE CONTEXT{RESET}: {planner.current_context}")
                print(f"> {BOLD}ACTIVE TASK{RESET}: {planner.current_task.heading}")
            else:
                print(f"\n> {BOLD}CURRENT COGNITIVE CONTEXT{RESET}: None")
                if buckets["Context"]:
                    print(f"> {BOLD}SUGGESTED ANCHOR TASK{RESET}: {buckets['Context'][0].heading}")

            render_bucket("Immediate Attention", buckets["Urgent"], args.show_math, RED)
            render_bucket("Attention-Clustered Focus", buckets["Context"], args.show_math, GREEN)
            render_bucket("Backlog / Low Activation", buckets["Backlog"], args.show_math, YELLOW)
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n{RED}[ERROR] Failed to execute pipeline: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
