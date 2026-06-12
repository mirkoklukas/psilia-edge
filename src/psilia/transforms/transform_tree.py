import itertools
import logging
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from psilia.utils import load_yaml, save_yaml
from psilia.transforms.transform import Transform

logger = logging.getLogger(__name__)
console = Console()


class Tree:
    """A simple tree of nodes."""

    def __init__(self, edges: list, strict: bool = True, name: str = ""):
        """
        Initialize a tree from a list of edges.

        Args:
            edges: A list of edges in the format [(parent, child), ...].
            strict: If True, we only try to the edges in the list. If False we
                also try the reverse edges in case the first attempt fails.
        """
        self.name = name
        self.edges = []
        self.nodes = set()
        self.children = {}
        self.parent = {}
        self.strict = strict

        for parent, child in edges:
            if strict:
                self._add_edge(parent, child)
            else:
                self._add_edges_or_inverse(parent, child)

    def get_root(self, node: str | None = None):
        """
        Get the root of the tree component containing the node.

        If no node is provided, we take the **first node** in the tree and
        return the root of the tree component containing that node.
        """
        if node is None:
            node = next(iter(self.nodes))

        while self.parent[node] is not None:
            node = self.parent[node]

        return node

    def get_depth(self, node: str | None = None):
        """
        Get the depth of the tree component containing the node.

        If no node is
        provided, we take the **first node** in the tree.
        """
        all_paths = self.get_all_paths(self.get_root(node))
        return max([len(p) - 1 for p in all_paths])

    @property
    def root(self):
        return self.get_root(None)

    def add_edge(self, parent: str, child: str):
        """Add an edge to the tree."""
        if self.strict:
            self._add_edge(parent, child)
        else:
            self._add_edges_or_inverse(parent, child)

    def _add_node(self, node: str):
        """Add a node (without any edges) to the tree."""
        if node in self.nodes:
            msg = f"Node {node} already in tree"
            raise ValueError(msg)

        self.nodes.add(node)
        self.parent[node] = None
        self.children[node] = []
        return self

    def _remove_node(self, node: str):
        """Remove a node and all its edges (if any) from the tree."""
        if node not in self.nodes:
            msg = f'Node "{node}" not in tree'
            raise ValueError(msg)

        self.nodes.remove(node)
        for e in self.edges:
            if e[0] == node or e[1] == node:
                self._remove_edge(*e)

        del self.parent[node]
        del self.children[node]

    def _add_edge(self, parent: str, child: str):
        """
        Add an edge to the tree.

        If the nodes are not in the tree, they are added to the tree.
        """
        assert parent != child, f"This is not a valid edge: ({parent}, {child})"
        # We will first add the nodes to the tree if they are not already
        # in the tree. We will later add the edge.
        if child not in self.nodes:
            # Child is a new node, so we need to add it to the tree
            # and if parent is not in the tree, we need to add it too.
            self._add_node(child)
            if parent not in self.nodes:
                # parent is the root of a new
                # component with one child
                self._add_node(parent)
        elif self.parent[child] is None:
            # Child is currently the root, and
            # parent becomes the new root
            # if parent in self.nodes:
            if parent not in self.nodes:
                self._add_node(parent)
            elif parent in self.get_component(child):
                msg = f'Trying to add ("{parent}", "{child}"), but creating a loop!'
                logger.error(msg)
                raise ValueError(msg)
        else:
            msg = f'Trying to add ("{parent}", "{child}"), '
            msg += f'but "{child}" is in there already (and not a root)!'
            logger.error(msg)
            raise ValueError(msg)

        # Add the edge to the tree
        self.parent[child] = parent
        self.children[parent].append(child)
        self.edges.append((parent, child))

        return self

    def _remove_edge(self, parent: str, child: str):
        if (parent, child) not in self.edges:
            msg = f'Edge ("{parent}", "{child}") not in tree'
            raise ValueError(msg)

        self.children[parent].remove(child)
        self.parent[child] = None
        self.edges.remove((parent, child))

        return self

    def _add_edges_or_inverse(self, parent: str, child: str):
        try:
            self._add_edge(parent, child)
        except ValueError:
            logger.warning(f"Trying to add inverse edge instead: ({child},{parent})")
            self._add_edge(child, parent)

    def remove_leaf(self, node: str):
        self._remove_leaf(node)
        return self

    def _remove_leaf(self, node: str):
        if len(self.children[node]) > 0:
            msg = f'Node "{node}" has children'
            raise ValueError(msg)

        if node not in self.nodes:
            msg = f'Node "{node}" not in tree'
            raise ValueError(msg)

        parent = self.parent[node]
        self.children[parent].remove(node)
        del self.parent[node]
        del self.children[node]
        self.edges.remove((parent, node))
        self.nodes.remove(node)
        return self

    def move_node(self, node: str, new_parent: str):
        old_parent = self.parent[node]
        if old_parent is not None:
            self._remove_edge(old_parent, node)

        self.add_edge(new_parent, node)
        return self

    def get_path(self, node: str, target: str, visited: list | None = None):
        if visited is None:
            visited = []

        if node in visited:
            msg = f"Sure this is a tree?? Node {node} already visited!"
            raise ValueError(msg)

        if node == target:
            return [node]

        visited.append(node)

        queue = [
            n
            for n in self.children[node] + [self.parent[node]]
            if (n not in visited) and (n is not None)
        ]
        path = []
        for child in queue:
            subpath = self.get_path(child, target, visited)
            if len(subpath) > 0:
                path = [node, *subpath]
                break

        return path

    def get_all_paths(self, node: str, visited=None):
        if visited is None:
            visited = []

        if node in visited:
            msg = f"Sure this is a tree?? Node {node} already visited!"
            raise ValueError(msg)

        visited.append(node)

        queue = [
            n
            for n in self.children[node] + [self.parent[node]]
            if (n not in visited) and (n is not None)
        ]
        paths = [[node]]
        for n in queue:
            subpaths = self.get_all_paths(n, visited)
            for path in subpaths:
                paths.append([node, *path])

        return paths

    def traverse(
        self,
        node: str,
        visited: list | None = None,
        on_visit: Callable = lambda node, visited: None,
    ):
        """Depth-first search traversal of the tree."""
        if visited is None:
            visited = []

        if node in visited:
            msg = f"Sure this is a tree? Node {node} already visited!"
            logger.error(msg)
            raise ValueError(msg)

        # Call `on_visit`` before appending to visited
        # so visited and node are not overlapping
        on_visit(node, visited)
        visited.append(node)

        queue = [
            n
            for n in self.children[node] + [self.parent[node]]
            if (n not in visited) and (n is not None)
        ]
        edges = []
        for child in queue:
            edges.append((node, child))
            edges += self.traverse(child, visited, on_visit)[1]

        return visited, edges

    def rebase(self, root: str):
        """Returns a new tree with the given root."""
        _, edges = self.traverse(root)
        root_component = self.get_component(root)
        remaining_edges = [
            (parent, child)
            for parent, child in self.edges
            if parent not in root_component and child not in root_component
        ]
        return Tree(edges + remaining_edges, strict=self.strict)

    def is_connected(self):
        """Check if the tree is connected."""
        visited = []
        self.traverse(self.get_root(), visited)
        return set(visited) == self.nodes

    def get_component(self, node: str):
        """Return the connected component of the tree containing the node."""
        visited = []
        self.traverse(node, visited)
        return visited

    def components(self):
        """Return the connected components of the tree."""
        visited_global = []
        components = []
        while len(visited_global) < len(self.nodes):
            remaining_nodes = self.nodes.difference(set(visited_global))
            if len(remaining_nodes) == 0:
                break
            node = next(iter(remaining_nodes))
            visited = []
            self.traverse(node, visited)
            components.append(visited)
            visited_global.extend(visited)

        return components

    def _str_component(self, nodes, prefix=""):
        # The idea is to go from a list of all
        # paths in the component
        # ````
        #   paths = [
        #     ['a'],
        #     ['a', 'b'],
        #     ['a', 'b', 'c1'],
        #     ['a', 'b', 'c2']
        #   ]
        # to an array of lines like this
        #   lines = [
        #     ['a'],
        #     ['├──', 'b'],
        #     ['│  ', '└──', 'c'],
        #     ['└──', 'x']
        #   ]
        paths = self.get_all_paths(self.get_root(nodes[0]))

        line_coords = {}
        lines = []

        free = "    "
        ell = "└── "
        tee = "├── "
        vert = "│   "

        # First add lines for each path and store the line coordinates
        # of each node, e.g. 'c' in the above lies at (2, 2). We will then
        # replace the free space with the node names and the vertical lines
        # with the appropriate connectors.
        for i, p in enumerate(paths):
            lines.append([free] * len(p))
            node = p[-1]
            nodes.append(node)
            line_coords[node] = (i, len(p) - 1)

        for node in nodes:
            i0, j0 = line_coords[node]
            lines[i0][j0] = "" + node

            # If the node has no children, we are done with it
            if node not in self.children or len(self.children[node]) == 0:
                continue

            # Otherwise, we need to add the connections to the children
            children_coords = [line_coords[child] for child in self.children[node]]
            children_coords.sort(key=lambda x: x[0])
            rest, last = children_coords[:-1], children_coords[-1]

            lines[last[0]][last[1] - 1] = ell
            for i in range(i0 + 1, last[0]):
                lines[i][last[1] - 1] = vert

            for i, _ in rest:
                lines[i][last[1] - 1] = tee

        return "\n".join([prefix + "".join(line) for line in lines])

    def __repr__(self) -> str:
        if self.name != "":
            s = f'Tree(name="{self.name}", strict={self.strict}, edges='
        else:
            s = f"Tree(strict={self.strict}, edges="
        s += " + ".join([str(c) for c in self.components()])
        s += ")"
        return s

    def __str__(self) -> str:
        """Return a string representation for rich printing."""
        components = self.components()
        if self.name != "":
            s = f'Tree("{self.name}"):\n'
        else:
            s = "Tree:\n"

        for i, c in enumerate(components):
            if i > 0:
                s += "\n"
            if len(components) > 1:
                s += f"Component {i}\n"
            else:
                s += ""
            s += self._str_component(c, prefix="")

        return s

    def __rich__(self):
        """Return a string representation for rich printing."""
        components = self.components()
        if self.name != "":
            s = f'[bold]Tree("{self.name}")[/bold]\n'
        else:
            s = "[bold]Tree[/bold]\n"

        for i, c in enumerate(components):
            if i > 0:
                s += "\n"
            if len(components) > 1:
                s += f"[deep_sky_blue1]Component {i}[/][green]\n"
            else:
                s += "[green]"
            s += self._str_component(c, prefix="")
            s += "[/]"

        return s


class TransformTree(Tree):
    """A tree of transforms. Or a tree of poses. Or a tree of frames. Whatever."""

    def __init__(self, tfs: list, strict: bool = True):
        """Initialize a transform tree from a list of transforms."""
        # I store the actual **transforms** by (source/child, target/parent).
        # Hoverever, the tree **edges** are stored as (parent, child).
        # Oh well. Why? Because I view the entries in tf_map from
        # a mapping perspective, and the edges from a pose tree perspective.
        self.tf_map = {}
        edges = []
        for tf in tfs:
            if isinstance(tf, dict):
                tf = Transform.from_dict(tf)  # noqa: PLW2901
            self.tf_map[(tf.child, tf.parent)] = tf
            self.tf_map[(tf.parent, tf.child)] = tf.inv()
            edges.append((tf.parent, tf.child))

        self._sort_keys = dict(zip(edges, range(len(edges)), strict=False))

        super().__init__(edges, strict=strict)

    @classmethod
    def from_yaml(cls, yaml_file: Path, strict: bool = True):
        """Load a transform tree from a YAML file."""
        data = load_yaml(yaml_file)
        tfs = [Transform.from_dict(tf) for tf in data["transforms"]]
        return cls(tfs, strict=strict)

    @classmethod
    def load_yaml(cls, yaml_file: Path, strict: bool = True):
        """Load a transform tree from a YAML file."""
        data = load_yaml(yaml_file)
        tfs = [Transform.from_dict(tf) for tf in data["transforms"]]
        return cls(tfs, strict=strict)

    @classmethod
    def load(cls, yaml_file: Path, strict: bool = True):
        """Load a transform tree from a YAML file."""
        data = load_yaml(yaml_file)
        tfs = [Transform.from_dict(tf) for tf in data["transforms"]]
        return cls(tfs, strict=strict)

    @classmethod
    def from_tf_static_yaml(cls, yaml_file: Path, strict: bool = True):
        data = load_yaml(yaml_file)
        tfs = [Transform.from_dict(tf) for tf in data["tf_static"]["insert"]]
        return cls(tfs, strict=strict)

    def get_transform(self, child, parent):
        path = self.get_path(child, parent)
        tfs = [
            self.tf_map[(source, target)] for source, target in itertools.pairwise(path)
        ]
        tf = tfs[0]
        for t in tfs[1:]:
            tf = tf >> t
        return tf

    def add_transform(self, tf: Transform):
        self.tf_map[(tf.child, tf.parent)] = tf
        self.tf_map[(tf.parent, tf.child)] = tf.inv()
        self.add_edge(tf.parent, tf.child)

    def move_node(self, node: str, new_parent: str):
        tf = self.get_transform(node, new_parent)
        self.tf_map[(node, new_parent)] = tf
        self.tf_map[(new_parent, node)] = tf.inv()

        old_parent = self.parent[node]
        if old_parent is not None:
            del self.tf_map[(old_parent, node)]
            del self.tf_map[(node, old_parent)]

        super().move_node(node, new_parent)

    def remove_leaf(self, node: str):
        # First remove transforms involving this node
        parent = self.parent[node]
        if parent is not None:
            del self.tf_map[(node, parent)]
            del self.tf_map[(parent, node)]

        for child in self.children[node]:
            del self.tf_map[(child, node)]
            del self.tf_map[(node, child)]

        # Remove node from tree
        super().remove_leaf(node)

    def sorted_edges(self, key: Callable | None = None):
        """Sort the edges of the tree using a custom key."""

        def _key(edge):
            if key is not None:
                return key(edge)
            if edge in self._sort_keys:
                return self._sort_keys[edge]
            return float("inf")

        return sorted(self.edges, key=_key)

    def rebase(self, root: str):
        super().__init__(super().rebase(root).edges, strict=self.strict)
        return self

    def save(
        self,
        fname: Path,
        rotation_type: str = "EULER",
        seq: str = "XYZ",
        degrees: bool = True,
        sort_key: Callable | None = None,
        description: str = "",
    ):
        edges = self.sorted_edges(sort_key)
        data = {
            "transforms": [
                self.tf_map[(child, parent)].as_dict(
                    rotation_type=rotation_type, seq=seq, degrees=degrees
                )
                for parent, child in edges
            ],
        }

        if description != "":
            data["description"] = description

        save_yaml(
            data,
            fname,
        )

    # TODO: Retire this in the future
    def save_yaml(
        self,
        yaml_file: Path,
        rotation_type: str = "EULER_DEG",
        sort_key: Callable | None = None,
    ):
        save_yaml(
            self.as_dict(rotation_type=rotation_type, sort_key=sort_key),
            yaml_file,
        )

    # TODO: Retire this in the future
    def to_yaml(self, *args, **kwargs):
        return self.save_yaml(*args, **kwargs)

    def save_sorted(
        self,
        yaml_file: Path,
        rotation_type: str = "EULER_DEG",
        sort_key: Callable | None = None,
    ):
        sorted_edges = self.sorted_edges(sort_key)
        return save_yaml(
            {
                "transforms": [
                    self.tf_map[(child, parent)].as_dict(rotation_type=rotation_type)
                    for parent, child in sorted_edges
                ],
            },
            yaml_file,
        )

    def as_dict(
        self,
        rotation_type: str = "EULER",
        seq="XYZ",
        degrees=False,
        sort_key: Callable | None = None,
    ):
        edges = self.sorted_edges(sort_key)
        return {
            "transforms": [
                self.tf_map[(child, parent)].as_dict(
                    rotation_type=rotation_type, seq=seq, degrees=degrees
                )
                for parent, child in edges
            ]
        }

    def _get_transform(self, source_frame, target_frame):
        path = self.get_path(source_frame, target_frame)
        tfs = [
            self.tf_map[(source, target)] for source, target in itertools.pairwise(path)
        ]
        tf = tfs[0]
        for t in tfs[1:]:
            tf = tf >> t
        return tf

    def __getitem__(self, parent_child: tuple[str, str]):
        assert isinstance(parent_child, tuple)
        assert len(parent_child) == 2

        parent, child = parent_child[0], parent_child[1]
        return self._get_transform(source_frame=child, target_frame=parent)

    def as_list(self):
        return [self[parent, child] for parent, child in self.edges]
