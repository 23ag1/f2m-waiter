from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TAXONOMY_PATH = Path("docs/runtime_taxonomy_resolved_v1.json")


class TaxonomyError(ValueError):
    """Raised when taxonomy axes or tags are invalid."""


@dataclass(frozen=True)
class RuntimeTaxonomy:
    version: str
    storage_axes: dict[str, Any]
    aliases: dict[str, str]
    storage_rules: dict[str, str]

    def resolve_tag(self, axis: str, tag: str) -> str:
        axis_key = axis.strip()
        if axis_key not in self.storage_axes:
            raise TaxonomyError(f"Unknown axis: {axis_key}")

        normalized = self.aliases.get(tag.strip(), tag.strip())
        allowed = self.allowed_tags(axis_key)
        if allowed is not None and normalized not in allowed:
            raise TaxonomyError(
                f"Tag '{tag}' resolved to '{normalized}' is not allowed for axis '{axis_key}'"
            )
        return normalized

    def is_allowed(self, axis: str, tag: str) -> bool:
        try:
            self.resolve_tag(axis=axis, tag=tag)
            return True
        except TaxonomyError:
            return False

    def allowed_tags(self, axis: str) -> set[str] | None:
        axis_value = self.storage_axes[axis]
        if isinstance(axis_value, list):
            return set(axis_value)
        if isinstance(axis_value, dict):
            tags: set[str] = set()
            for value in axis_value.values():
                if isinstance(value, list):
                    tags.update(value)
            return tags
        # Ingredient axis is dictionary-backed and open to dictionary keys.
        if isinstance(axis_value, str):
            return None
        raise TaxonomyError(f"Unexpected axis definition for '{axis}'")


def load_runtime_taxonomy(path: Path | None = None) -> RuntimeTaxonomy:
    effective_path = path or DEFAULT_TAXONOMY_PATH
    with effective_path.open("r", encoding="utf-8") as file_obj:
        raw = json.load(file_obj)

    return RuntimeTaxonomy(
        version=raw["version"],
        storage_axes=raw["storage_axes"],
        aliases=raw.get("aliases", {}),
        storage_rules=raw.get("storage_rules", {}),
    )
