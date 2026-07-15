import datetime
from datetime import datetime as dt
import math
from typing import Optional, List
from Agenda import Agenda
from Task import Task

import logging

# Configure logger format and default to INFO level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Planner")

class Planner:
    def __init__(self, file_path: str):
        self.agenda: Agenda = Agenda(file_path)
        self.current_task: Task = None
        self.current_context: List[str] = []
        self.last_updated: Optional[datetime.datetime] = None
        self.reference_time: Optional[datetime.datetime] = None

        self.delay_constant = 0.5 # scaled for seconds, I believe
        self.activation_chunk_size = 30 # Size of chunks in minutes to break clock sessions into
        self.uc_scaling_factor = 0.8 # scaling for inherited child urgency
        self.up_scaling_factor = 0.3 # scaling for inherited parent urgency
        self.ud_scaling_factor = 0.8 # scaling for urgency based on deadline
        self.us_scaling_factor = 0.5 # scaling for urgency based on scheduled
        self.priority_weights = {"A": 1.5, "B": 1.0, "C": 0.5}
        self.urgency_multiplier = 1.5 # scaling for urgency compared to activation
        self.task_switch_penalty = 1
        self.task_switch_weight_tag = 0.4 # Must add with "weight_tree" to make 1
        self.task_switch_weight_tree = 0.6 # Must add with "weight_tag" to make 1

        # Ensure this works in prod, but lets me set a test value without overriding
        if not self.reference_time:
            self.reference_time = dt.now()
        logger.debug(f"Reference time: {self.reference_time}")
        
        # Prepopulate all intrinsic task urgency values
        # (Inheritance is NOT handled at this step. That is calculated at runtime)
        logger.debug(" === Processing Task Urgency === ")
        for task in self.agenda.open_tasks:
            logger.debug(f" Task Urgency: {task.heading}")
            self.get_task_urgency(task)

    def process_all_scores(self) -> dict[Task, float]:
        
        open = self.agenda.open_tasks
        logger.debug(f"Tracking {len(open)} open tasks.")
        scores = {}
            
        self.last_updated = self.reference_time
        for task in open:
            logger.debug(f" === Processing: {task.heading} ===")
            score = self.get_score(task)
            task.score = score
            scores[task] = score
        return scores

    def process_active_tasks(self) -> None:
        self.current_context = []
        self.current_task = None
        active = self.agenda.active_tasks
        logger.debug(f"Active tasks ({len(active)}): {active}")
        if len(active) > 1:
            raise ValueError("There can only be one active task at a time.")
        else:
            active = active[0]
            tags = active.shallow_tags
            self.current_context.extend(tags)
            self.current_task = active

    def sort_agenda(self) -> List[Task]:
        self.process_active_tasks()
        self.process_all_scores()
        # Sort descending
        sorted_a = sorted(self.agenda.open_tasks, key=lambda t: getattr(t, 'score', -float('inf')), reverse=True)
        return sorted_a

    def get_score(self, task: Task) -> float:

        A = self.get_activation(task)
        U = self.get_urgency(task)
        S = self.get_switch_penalty(task)
        score = A + (self.urgency_multiplier * U) - (self.task_switch_penalty * S)
        logger.debug(f"   - Activation: {A}")
        logger.debug(f"   - Urgency: {U}")
        logger.debug(f"   - Switch: {S}")
        logger.debug(f"   - Score: {score}")
        # logger.debug(f"{A} + ({self.urgency_multiplier} * {U}) - ({self.task_switch_penalty} * {S}) = {score}")
        return score

    def get_activation(self, task: Task) -> float:
        if not task.clocks:
            return 0.0

        logger.debug(f"   - - Clocks: {len(task.clocks)}")

        current_time = self.reference_time
        total = 0.0
        epsilon = 30.0/86400.0

        for clock in task.clocks:
            start = clock.start
            end = clock.end if clock.end else current_time # does this conflict with epsilon method?

            tk = (current_time-end).total_seconds() / 86400.00
            tk = max(tk, epsilon) # if it's an open session, set to epsilon

            duration = (end-start).total_seconds() / 86400.0 # in hours
            if duration <= 0:
                # What edge case is this?
                continue

            # Scaling duration as a log keeps a few hours more heavily weighted than a few minutes
            # but keeps exceptionally long sessions from scaling too much
            weight = math.log1p(duration)
            total += weight * (tk ** -self.delay_constant)
            logger.debug(f"   - - Clock Weight: {weight} | Tk: {tk}")
        return math.log1p(total) if total > 0 else 0.0

    def get_urgency(self, task: Task) -> float:
        """Calculate a task's urgency, including inherited values"""
        # This function should NOT set a tasks urgency.
        # If we modify task properties in this function, we may cause urgency to baloon from inherited values
        task_urgency = task.urgency
        child_urgency = self.get_child_urgency_recursive(task)
        parent_urgency = self.get_parent_urgency_recursive(task)
        # Debug: logging is handled in component methods
        U = task_urgency + (self.uc_scaling_factor * child_urgency) + (self.up_scaling_factor * parent_urgency)
        return U
        
    def get_task_urgency(self, task: Task) -> float:
        """
        Calculate a task's urgency without inheritance.
        This should be run in a loop at init time, to pre-populate inherent urgency vals.
        Inherited urgency will be calculated at runtime as needed, and will fetch these values.
        """
        E: float = task.effort if task.effort else 0.0
        # Effort is in hours by default, so we need to convert to days
        E = E/24.0
        Ud: float = self.get_task_urgency_deadline(task)
        Us: float = self.get_task_urgency_scheduled(task)
        Up: float = self.priority_weights.get(task.priority, 1.0) if task.priority else 1.0        
        U_task = E + (Ud * Us * Up)
        # I set the object's urgency based off the task's properties.
        # I set it here because if I set it in the main function, it will be based off inheritance as well. This could cause a balooning effect. I set here to prevent this.
        task.set_urgency(U_task)
        logger.debug(f"  - U: {U_task} [E: {E} | Ud: {Ud} | Us: {Us} | Up: {Up}]")
        return U_task

    def get_task_urgency_deadline(self, task: Task) -> float:
        """Calculate urgency based on proximity to a task's deadline"""
        D = task.deadline.start
        if D is None:
            return 1.0 # Don't return 0, because then I remove all urgency
        elif isinstance(D, datetime.date):
            D = dt.combine(D, dt.min.time())
        T = self.reference_time
        delta = D - T
        days:float = delta.total_seconds() / 86400
        if days > 1:
            U = 1/(days ** self.ud_scaling_factor)
        else:
            U = 2.0-days
        logger.debug(f"  - Ud: {U} [days: {days}]")
        return U

    def get_task_urgency_scheduled(self, task: Task) -> float:
        """Calculate urgency based on proximity to a task's scheduled start date."""
        S = task.scheduled.start
        if S is None:
            return 1.0 # Don't return 0, it would remove all urgency
        elif isinstance(S, datetime.date):
            S = dt.combine(S, dt.min.time())
        T = self.reference_time
        delta = S-T
        days:float = delta.total_seconds() / 86400
        if days < 0:
            days = 0
        U = 1/(1+self.us_scaling_factor * days)
        logger.debug(f"  - Us: {U} [days: {days}]")
        return U

    
    def get_child_urgency(self, task: Task) -> float:
        """Deprecated in favor of improved recursive version."""
        C = []

        def flatten_all_children(task: Task) -> List[Task]:
            """Recursive function to return all children, not just direct descendants"""
            temp = [task]
            for child in task.children:
                temp.extend(flatten_all_children(child))
            return temp

        # Can't pass 'task' to the flatten function, otherwise we double count the task's effort
        for child in task.children:
            C.extend(flatten_all_children(child))

        if len(C) != 0:
            C_u = [item.urgency for item in C]
            U_c = max(C_u)
        else:
            U_c = 0.0            
        return U_c

    def get_child_urgency_recursive(self, task: Task) -> float:
        """
        Find the max urgency among all children.
        Recursively traverses the tree to make sure inherited values actually propogate
        """
        if not task.children:
            return 0.0

        child_urgencies = []
        for child in task.children:
            u_base = child.urgency
            u_child = self.uc_scaling_factor * self.get_child_urgency_recursive(child)
            u = u_base + u_child
            child_urgencies.append(u)
        return max(child_urgencies)
            
    def get_parent_urgency(self, task: Task) -> float:
        """Deprecated in favor of improved recursive version"""
        U_p = []
        t = task
        while t.parent is not None:
            U_p.append(t.parent.urgency)
            t = t.parent
        # Return the average parent urgency
        if len(U_p) != 0:
            return sum(U_p) / len(U_p)
        else:
            return 0.0

    def get_parent_urgency_recursive(self, task: Task) -> float:
        """
        Pull parent urgencis downward.
        Use recursion to make sure inherited urgency propogates downward.
        """
        if task.parent is None:
            return 0.0

        u_base = task.parent.urgency
        u_parent = self.get_parent_urgency_recursive(task.parent)
        u = u_base + (self.up_scaling_factor * u_parent)
        return u

    def get_hierarchy_switch_penalty(self, task: Task) -> float:
        active = self.current_task

        # Calculate lineage arrays.
        # When I case checked these, it only worked when the task itself was added on to the array.
        # I'm sure there's a mathematical explanation for this, but this is cognitive "science", not cognitive "theory"... so as long as it works I don't care :D
        path1 = active.lineage
        path1.append(active)
        path2 = task.lineage
        path2.append(task)

        # Add a fake "root" node to each path to make sure we don't fall back to common depth of 0 for separate trees.
        # This way, we can correctly calculate distance across distinct task hierarchies
        v_path1 = ["root"] + path1
        logger.debug(f"Active lineage: {v_path1}")
        v_path2 = ["root"] + path2
        logger.debug(f"New lineage: {v_path2}")

        # Find the depth of the lowest common ancestor
        common_depth = 0
        for ancestors in zip(v_path1, v_path2):
            if ancestors[0] == ancestors[1]:
                common_depth += 1
            else:
                break

        logger.debug(f"Common Depth: {common_depth}")

        # If they share absolutely nothing (different roots)
        if common_depth == 0:
            logger.debug(f"Hierarchy Task Switch: Returning 1.0 (no common parents)")
            return 1.0

        # Distance -> steps up to LCA + steps down to new task
        steps_up = len(v_path1) - common_depth
        steps_down = len(v_path2) - common_depth
        total = steps_up + steps_down
        max_possible = len(v_path1) + len(v_path2)
        logger.debug(f"Hierarchy Task Switch: {total} / {max_possible}")

        return total / max_possible if max_possible > 0 else 0.0

    def get_tag_switch_penalty(self, task: Task) -> float:
        """Measure linear distance between 2 tasks based on number of similar tags, then update the current task"""
        # If this is our first processed tag, there is nothing to compare to
        if not self.current_task:
            return 0.0
        # If there are no current tags and the current task has no tags, we have nothing to compare to
        if len(self.current_context) == 0 and not task.tags:
            return 0.0
        # If one or both tasks have tags, calculate difference
        current: set[str] = set(self.current_context) if len(self.current_context) != 0 else set()
        new: set[str] = task.shallow_tags
        # Length of diff and union sets. Don't care about contents
        all: int = len(current | new) # Set union
        different: int = len(current ^ new) # Set symmetric difference
        # Dividing diff by all will always be between 0 & 1
        logger.debug(f"Active tags: {len(current)} | New tags: {len(new)}")
        logger.debug(f"Different tags: {different} | Union: {all}")
        logger.debug(f"Switch penalty for {task.heading}: {different/all}")
        
        return different / all

    def get_switch_penalty(self, task: Task) -> float:
        """Calculate total task switching penalty from both tags and hierarchy. Combine with a weighted average."""

        S_tag = self.get_tag_switch_penalty(task)
        S_tree = self.get_hierarchy_switch_penalty(task)
        S = self.task_switch_penalty * ((self.task_switch_weight_tag * S_tag) + (self.task_switch_weight_tree * S_tree))
        return S

    def switch_task(self, task: Task):
        task.active = True
        self.process_active_tasks()

    def print_sorted(self) -> None:
        for task in self.sort_agenda():
            print(f"{task.heading}: {task.score}")

    def get_buckets(self) -> dict[str, List[Task]]:
        """
        Divides open tasks into three buckets.
        1. Urgent - tasks with high time pressure
        2. Context - tasks organized to minimize context switching
        3. Backlog - all the rest, in order to prevent starvation
        """
        sorted_tasks = self.sort_agenda()
        if not sorted_tasks:
            return {"Urgent": [], "Context": [], "Backlog": []}

        # Highest scoring task
        # This should nearly always be the active task
        top_task = sorted_tasks[0]

        urgent = []
        context = []
        backlog = []

        for task in sorted_tasks:
            # URGENT BUCKET
            # Any task due w/i 24 hours or overdue /should/ have a Ud > 1.0 b/c of the curve I used
            if self.get_task_urgency(task) > 1.0:
                urgent.append(task)
                continue

            # CONTEXT BUCKET
            # top recommended task should be in here too
            if task == top_task:
                pass
                # context.append(task)
                # continue
            # Low switch penalties relative to the active task
            tag_pen = self.get_tag_switch_penalty(task)
            tag_pen_cut = 0.5 # Tag penalty cutoff. tasks less than this value are contextually relevant
            tree_pen = self.get_hierarchy_switch_penalty(task)
            tree_pen_cut = 0.4 # Tree penalty cutoff. Tasks less than this are contextually relevant
            if tag_pen < tag_pen_cut or tree_pen < tree_pen_cut:
                context.append(task)
            else:
                backlog.append(task)

        return {
            "Urgent": urgent,
            "Context": context,
            "Backlog": backlog
        }
            

if __name__ == "__main__":
    p = Planner("./test.org")
    p.process_active_tasks()
    p.process_all_scores()

    # p.print_sorted()
    
