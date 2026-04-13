"""Requirement resolution framework.

Defines a tree of requirements where each node has a resolver function.
The runner walks the tree top-down, resolves args from already-resolved
results, and short-circuits children when a parent fails.

Addressing:
- "camera.calibration"  → tree path → returns .data of that node
- "camera:height"       → tree path "camera" → returns .data["height"]
- "camera.calibration:path" → tree path → returns .data["path"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RequirementSpec:
    """A node in the requirement tree definition."""

    name: str
    resolve: Callable[..., ResolverResult]
    args: tuple[str, ...] = ()
    children: list[RequirementSpec] = field(default_factory=list)


@dataclass
class ResolverResult:
    """What a resolver function returns."""

    ok: bool
    detail: str
    data: dict = field(default_factory=dict)


@dataclass
class RequirementResult:
    """A node in the resolved requirement tree."""

    ok: bool
    detail: str
    data: dict = field(default_factory=dict)
    children: dict[str, RequirementResult] = field(default_factory=dict)

    def __getitem__(self, path: str) -> Any:
        """Look up a value in the result tree rooted at this node.

        "camera"                    → children["camera"] (the node)
        "camera:height"             → children["camera"].data["height"]
        "camera:nested:key"         → children["camera"].data["nested"]["key"]
        "camera.calibration"        → ...children["calibration"] (the node)
        "camera.calibration:path"   → ...children["calibration"].data["path"]
        """
        tree_path, _, data_path = path.partition(":")

        parts = tree_path.split(".")
        node = self.children[parts[0]]
        for part in parts[1:]:
            node = node.children[part]

        if not data_path:
            return node

        value = node.data
        for key in data_path.split(":"):
            value = value[key]
        return value

    def to_dict(self) -> dict:
        """Build a flat display dict with dotted keys (e.g. "camera.calibration")."""
        result = {}

        def _walk(children, prefix=""):
            for name, node in children.items():
                key = f"{prefix}.{name}" if prefix else name
                result[key] = {"ok": node.ok, "detail": node.detail}
                if node.children:
                    _walk(node.children, key)

        _walk(self.children)
        return result


def run_requirements(specs: list[RequirementSpec]) -> RequirementResult:
    """Walk the spec tree and resolve each node.

    Returns a RequirementResult root node. Top-level results are in
    root.children. Use root["camera:height"] etc. to access resolved data.
    Children are skipped (ok=False, detail="skipped") when a parent fails.
    """
    root = RequirementResult(ok=True, detail="root")

    def _run(
        specs: list[RequirementSpec],
        target: dict[str, RequirementResult],
    ) -> None:
        for spec in specs:
            args = [root[a] for a in spec.args]
            resolved = spec.resolve(*args)
            result = RequirementResult(
                ok=resolved.ok,
                detail=resolved.detail,
                data=resolved.data,
            )
            target[spec.name] = result

            if result.ok and spec.children:
                _run(spec.children, result.children)
            elif spec.children:
                _skip(spec.children, result.children)

    def _skip(
        specs: list[RequirementSpec],
        target: dict[str, RequirementResult],
    ) -> None:
        for spec in specs:
            result = RequirementResult(ok=False, detail="skipped")
            target[spec.name] = result
            if spec.children:
                _skip(spec.children, result.children)

    _run(specs, root.children)

    # Root ok reflects whether all requirements passed.
    root.ok = all(_all_ok(root.children))

    return root


def _all_ok(children: dict[str, RequirementResult]) -> list[bool]:
    """Collect ok status from all nodes in the tree."""
    result = []
    for node in children.values():
        result.append(node.ok)
        result.extend(_all_ok(node.children))
    return result
