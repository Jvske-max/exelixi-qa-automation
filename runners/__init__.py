"""Test dispatchers and execution runners package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runners.doc_runner import DocRunner


def __getattr__(name: str):
    if name == "DocRunner":
        from runners.doc_runner import DocRunner

        return DocRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DocRunner"]
