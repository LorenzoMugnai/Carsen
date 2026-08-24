"""Python AST parser for modules, classes, functions and methods."""

from __future__ import annotations

import ast
from pathlib import Path

from ariadne_mcp.chunks.model import Chunk

from .base import read_text, rel_path


def _decorators(node: ast.AST) -> list[str]:
    return [ast.unparse(d) for d in getattr(node, "decorator_list", [])]


def parse_python(path: Path, knowledge_id: str, source_root: Path | None = None) -> list[Chunk]:
    text = read_text(path)
    lines = text.splitlines()
    tree = ast.parse(text)
    imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    source = rel_path(path, source_root)
    chunks: list[Chunk] = [Chunk(knowledge_id, source, "module", None, 1, max(1, len(lines)), text, 0, {"imports": imports, "path": source, "docstring": ast.get_docstring(tree)})]

    order = 1
    parents: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            nonlocal order
            name = ".".join([*parents, node.name])
            body = "\n".join(lines[node.lineno - 1: node.end_lineno or node.lineno])
            chunks.append(Chunk(knowledge_id, source, "class", name, node.lineno, node.end_lineno or node.lineno, body, order, {"docstring": ast.get_docstring(node), "decorators": _decorators(node), "imports": imports, "path": source}))
            order += 1
            parents.append(node.name)
            self.generic_visit(node)
            parents.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._function(node, "method" if parents else "function")

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._function(node, "method" if parents else "async_function")

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
            nonlocal order
            name = ".".join([*parents, node.name])
            body = "\n".join(lines[node.lineno - 1: node.end_lineno or node.lineno])
            chunks.append(Chunk(knowledge_id, source, kind, name, node.lineno, node.end_lineno or node.lineno, body, order, {"docstring": ast.get_docstring(node), "decorators": _decorators(node), "imports": imports, "path": source}))
            order += 1
            if not parents:
                self.generic_visit(node)

    Visitor().visit(tree)
    return chunks
