from datetime import datetime
from typing import Optional, List
from orgparse.node import OrgNode

class Task:
    def __init__(self, node: OrgNode, task_map = None):
        """Wrapper around orgparse.OrgNode to provide access to any custom logic/attributes I need."""
        self._node: OrgNode = node
        self.urgency: float = 0.0
        self.score: float = 0.0
        self.active = False

        self._task_map = task_map

    def _register_map(self, task_map: dict):
        """
        Register the central task mapping.
        This is separate from the constructor so that debugging isn't a PITA later.
        This way, I can create Task objects on the fly if needed.
        """
        self._task_map = task_map

    @property
    def parent(self) -> Optional['Task']:
        """Fetch the parent object from the task map (if present)."""
        # AFAICT, Orgparse maintains a consistent tree of nodes
        # It /seems/ to pull parents and children by /reference/ rather than creating new objects
        # I can use this to index into my task dict.
        if self._task_map is not None:
            raw_parent = self._node.parent
            return self._task_map.get(raw_parent)
        else:
            print("Task map not registered; unable to locate parent")
            return None

    @property
    def children(self) -> List['Task']:
        """Fetch all children from the task map (if present)."""
        if self._task_map is not None:
            # TODO: Using 'in' with a dict? Probably a better solution.
            # CANC: 'in' is kinda slow, but for the scale I'm looking at it doesn't matter.
            return [self._task_map[child] for child in self._node.children if child in self._task_map]
        else:
            print("Task map not registered; unable to locate children")
            return None

    @property
    def lineage(self) -> List['Task']:
        """Returns an ordered list of all ancestors from root to the parent task for this task."""
        path = []
        t = self.parent
        while t is not None:
            path.append(t)
            t = t.parent
        return path[::-1] # Reverse to make sure we get root first
        

    @property
    def level(self) -> int:
        return self._node.level
        
    @property
    def heading(self) -> str:
        return self._node.heading

    @property
    def todo(self) -> Optional[str]:
        return self._node.todo

    @property
    def tags(self) -> set:
        return self._node.tags

    @property
    def shallow_tags(self) -> set:
        return self._node.shallow_tags

    @property
    def scheduled(self):
        return self._node.scheduled

    @property
    def deadline(self):
        return self._node.deadline

    @property
    def effort(self) -> float:
        # Effort should be passed as a float representing the expected number of hours to complete a task.
        e = self._node.get_property('Effort')
        if e is None:
            e = 0.0       
        return e

    @property
    def priority(self) -> Optional[str]:
        return self._node.priority
    

    @property
    def clocks(self) -> List:
        """Return the raw list of clock data."""
        return self._node.clock

    @property
    def clock_open(self) -> bool:
        """Checks whether latest clock entry is still open."""
        if not self.clocks:
            return False
        latest_clock = self.clocks[0]
        end_time = latest_clock.end
        return end_time is None

    @property
    def clock_total(self) -> float:
        """
        Calculate total time spent on this task across all completed clock entries.
        Ignores open clock entries.
        """
        if not self.clocks:
            return 0.0
        total = 0.0
        for c in self.clocks:
            if c.end is not None:
                total+=(c.duration.total_seconds() / 60.0)
        return total

    @property
    def clock_latest(self) -> Optional[datetime]:
        """Returns the latest datetime from the clock list."""
        if not self.clocks:
            return None

        latest_clock = self.clocks[0]
        start_time = latest_clock.start
        return start_time

    @property
    def clock_earliest(self) -> Optional[datetime]:
        """Returns the earliest datetime from the clock list."""
        if not self.clocks:
            return None
        earliest_clock = self.clocks[-1]
        start_time = earliest_clock.start
        return start_time

    @property
    def clock_age(self) -> float:
        first = self.clock_earliest
        if not first and self.scheduled:
            first = self.scheduled.start

        if not first:
            return 0.0
        return (datetime.now() - first).total_seconds() / 60.0

    @property
    def body(self) -> str:
        """Sanitizes body text, removing ':END:' and ':LOGBOOK:' tags."""
        raw = self._node.body
        if not raw:
            return ""
        import re
        return re.sub(r':[A-Z]+:.*?:END:', '', raw, flags=re.DOTALL).strip()

    def set_urgency(self, val: float) -> None:
        """Set a task's urgency"""
        self.urgency = val

    def __repr__(self) -> str:
        status = f"[{self.todo}] " if self.todo else ""
        return f"<Task: ({self.level}) {status}{self.heading} | Urgency: {self.urgency:.2f}>"

    def __str__(self) -> str:
        status = f"[{self.todo}] " if self.todo else ""
        head = self.heading[:15]
        return f"({self.level}) {status}{head}"



if __name__ == "__main__":
    from orgparse import load

    node = load('./test.org').children[0]
    test = Task(node.children[0].children[0])
    print(test)
    print(test.level)
    print(test.effort)
    print(test.priority)
    print(test.tags)
    # print(test.scheduled)
    # print(test.deadline)
    print(test.clocks)
    print(test.clock_open)
    print(test.clock_total)
    print(test.clock_latest)
    print(test.clock_earliest)
    print(test.clock_age)
    print(test.body)
    print(test.parent)
    print(test.children)
    print("Lineage:")
    print(test.lineage)

