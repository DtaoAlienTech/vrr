"""Writes the website's TypeScript types for the public API from the backend's own schema.

The backend describes every public answer once (the Pydantic models). This turns that description
into `frontend/src/lib/content/api.generated.ts`, so the website cannot disagree with the API:
rename a field in the backend and the website's type check fails until the website follows.

    python -m app.typegen            write the file
    python -m app.typegen --check    fail if the file is out of date (used by scripts/check.sh)
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from app.main import app

TARGET = Path(__file__).resolve().parents[2] / "frontend/src/lib/content/api.generated.ts"

# The answers the website reads (GET only). Everything they mention is generated with them.
PUBLIC_PREFIXES = ("/api/v1/public/", "/api/v1/preview/")

HEADER = """\
// GENERATED from the backend API schema. Do not edit by hand.
// Update with: ./scripts/generate-types.sh   (it is checked by ./scripts/check.sh)
//
// A field that may be empty is optional here and never null: the public API leaves out empty
// values instead of sending null (response_model_exclude_none), so `cover?: MediaOut` is accurate.
"""

_REF = "#/components/schemas/"


def _ref_name(ref: str) -> str:
    return ref.removeprefix(_REF)


def _refs(node: Any) -> set[str]:
    """Names of the schemas mentioned anywhere inside `node`."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                found.add(_ref_name(value))
            else:
                found |= _refs(value)
    elif isinstance(node, list):
        for item in node:
            found |= _refs(item)
    return found


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _ts(node: dict[str, Any], indent: int, *, absent_not_null: bool = False) -> str:
    """One schema as a TypeScript type. `absent_not_null` drops `null` from a union (see HEADER)."""
    if "$ref" in node:
        return _ref_name(node["$ref"])
    if "const" in node:
        return _literal(node["const"])
    if "enum" in node:
        return " | ".join(_literal(value) for value in node["enum"])
    for union in ("anyOf", "oneOf"):
        if union in node:
            options = node[union]
            if absent_not_null:
                options = [option for option in options if option.get("type") != "null"]
            parts = [_ts(option, indent) for option in options]
            return " | ".join(dict.fromkeys(parts))
    kind = node.get("type")
    if isinstance(kind, list):
        return " | ".join(_ts({**node, "type": one}, indent) for one in kind)
    if kind == "string":
        return "string"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        inner = _ts(node.get("items", {}), indent)
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if kind == "object" or "properties" in node:
        return _object(node, indent)
    return "unknown"


def _object(node: dict[str, Any], indent: int) -> str:
    properties: dict[str, Any] = node.get("properties", {})
    if not properties:
        return "Record<string, unknown>"
    required = set(node.get("required", []))
    pad = "  " * (indent + 1)
    lines = ["{"]
    for name, schema in properties.items():
        # A value that may be null is left out when it is (response_model_exclude_none), so it
        # becomes "optional", never "null".
        nullable = any(option.get("type") == "null" for option in schema.get("anyOf", []))
        optional = name not in required or nullable
        if schema.get("description"):
            lines.append(f"{pad}/** {schema['description'].strip()} */")
        mark = "?" if optional else ""
        lines.append(f"{pad}{name}{mark}: {_ts(schema, indent + 1, absent_not_null=optional)};")
    lines.append("  " * indent + "}")
    return "\n".join(lines)


def public_schema_names(spec: dict[str, Any]) -> list[str]:
    """Schemas of the public answers, and of everything they contain."""
    schemas: dict[str, Any] = spec["components"]["schemas"]
    pending: list[str] = []
    for path, methods in spec["paths"].items():
        get = methods.get("get")
        if get and path.startswith(PUBLIC_PREFIXES):
            for status, response in get["responses"].items():
                if status.startswith("2"):  # not the generic 422 "validation error" answer
                    pending += sorted(_refs(response))
    wanted: set[str] = set()
    while pending:
        name = pending.pop()
        if name not in wanted:
            wanted.add(name)
            pending += sorted(_refs(schemas[name]))
    return sorted(wanted)


def generate(spec: dict[str, Any]) -> str:
    schemas: dict[str, Any] = spec["components"]["schemas"]
    blocks = [HEADER]
    for name in public_schema_names(spec):
        node = schemas[name]
        doc = f"/** {node['description'].strip()} */\n" if node.get("description") else ""
        blocks.append(f"{doc}export type {name} = {_ts(node, 0)};\n")
    return "\n".join(blocks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    parser.add_argument("--out", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    text = generate(app.openapi())
    if args.check:
        current = args.out.read_text() if args.out.exists() else None
        if current != text:
            print(f"{args.out} is out of date. Run ./scripts/generate-types.sh", file=sys.stderr)
            return 1
        print("API types are up to date.")
        return 0
    args.out.write_text(text)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
