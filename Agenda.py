from orgparse import load
from typing import List
from Task import Task

class Agenda:
    def __init__(self, file_path: str):
        self.root = load(file_path)
        self.task_map: dict[OrgNode, Task] = {}
        self._build()

    def _build(self):
        """
        Flatten the org file to a single dict using OrgEnv.
        Slice using [1:] to skip the root node.
        Skip the root node.
        """
        all_raw = self.root.env.nodes
        for node in all_raw[1:]:
            # Instantiate the task wrapper, and pass reference to the shared registry            
            self.task_map[node] = Task(node, self.task_map)

    @property
    def all_tasks(self) -> List[Task]:
        return list(self.task_map.values())

    @property
    def open_tasks(self) -> List[Task]:
        """
        Returns tasks that are still open (not done).
        Active tasks are determined using OrgEnv's 'done_keys' method.
        This means TODO keywords must be defined as a file-local variable in the org source.
        """
        # I use done_keys rather than todo_keys, because I assume there will be fewer entries.
        # This makes the 'in' operation faster.
        return [task for task in self.all_tasks if task.todo and task.todo not in self.root.env.done_keys]

    @property
    def active_tasks(self) -> List[Task]:
        """
        Returns tasks with a todo state of "Active", or in progress.
        """
        active_tasks = []
        for task in self.all_tasks:
            if task.todo == "ACTIVE":
                task.active = True
            if task.active == True:
                active_tasks.append(task)
        return active_tasks

    @property
    def root_tasks(self) -> List[Task]:
        """Returns top-level tasks."""
        # TODO: Iterate through entire dict just to get top level? Seems slow.
        # Determine whether this is a frequent operation. If so, restructure
        # CANC: To make this faster, I'd have to store tasks as tree-like objects, and maintain my task map as an array of trees. This would speed up access to root, but slow down literally everything else.
        return [task for task in self.task_map.values() if task.level == 1]


if __name__ == "__main__":
    test = Agenda("./test.org")
    test_item = test.all_tasks[2]
    #test_child = test_item.children[0]
    #test_parent = test_child.parent
    print("Original: ", test_item)
    #print("Child: ", test_child)
    #print("Parent: ", test_item)
    #print("Same: ", test_parent == test_item)
    print("Lineage: ", test_item.lineage)
    # print(test.all_tasks)
    # print(test.active_tasks)
    # print(test.root_tasks)

    
