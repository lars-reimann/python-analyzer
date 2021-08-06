from typing import Any, Callable

import astroid


class ASTWalker:
    """A walker visiting a tree in preorder, calling on the handler:

    * enter_<class_name> on entering a node, where class name is the class of
    the node in lower case.

    * leave_<class_name> on leaving a node, where class name is the class of
    the node in lower case.
    """

    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self._cache = {}

    def walk(self, node: astroid.NodeNG) -> None:
        self._walk(node, set())

    def _walk(self, node: astroid.NodeNG, visited_nodes: set[astroid.NodeNG]) -> None:
        assert node not in visited_nodes
        visited_nodes.add(node)

        self._enter(node)
        for child_node in node.get_children():
            self._walk(child_node, visited_nodes)
        self._leave(node)

    def _enter(self, node: astroid.NodeNG) -> None:
        method = self._get_callbacks(node)[0]
        if method is not None:
            method(node)

    def _leave(self, node: astroid.NodeNG) -> None:
        method = self._get_callbacks(node)[1]
        if method is not None:
            method(node)

    def _get_callbacks(self, node: astroid.NodeNG) -> tuple[
        Callable[[astroid.NodeNG], None], Callable[[astroid.NodeNG], None]
    ]:
        klass = node.__class__
        methods = self._cache.get(klass)

        if methods is None:
            handler = self._handler
            class_name = klass.__name__.lower()
            enter_method = getattr(
                handler, f"visit_{class_name}", getattr(handler, "visit_default", None)
            )
            leave_method = getattr(
                handler, f"leave_{class_name}", getattr(handler, "leave_default", None)
            )
            self._cache[klass] = (enter_method, leave_method)
        else:
            enter_method, leave_method = methods

        return enter_method, leave_method
