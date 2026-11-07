"""Bind the owner's named sources during packaging, without a TV setup screen."""
import argparse
import json
import re
from pathlib import Path

ALIASES = {
    "apple": {"appletv"},
    "switch": {"switch", "switch2", "nintendoswitch", "nintendoswitch2"},
    "steam": {"steam", "steammachine"},
}


def bindings(records):
    result = {}
    for record in records:
        name = (record.get("EditName") or record.get("DetectedName") or "").strip()
        normalized = re.sub(r"\s+", "", name).lower()
        for destination, aliases in ALIASES.items():
            if normalized not in aliases:
                continue
            source_type = record.get("SourceType")
            if type(source_type) is not int or source_type not in (13, 14, 15, 16):
                raise ValueError(f"{destination}: unsupported native source type")
            if destination in result:
                raise ValueError(f"{destination}: more than one TV input has this name")
            result[destination] = {"port": source_type - 12, "assignedName": name}
    missing = sorted(set(ALIASES) - set(result))
    if missing:
        raise ValueError("Named TV inputs are missing: " + ", ".join(missing))
    ports = [value["port"] for value in result.values()]
    if len(set(ports)) != len(ports):
        raise ValueError("Two destinations refer to the same HDMI input")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", choices=["QN65Q70TAFXZC"], required=True)
    parser.add_argument("--firmware", choices=["T-NKMAKUC-2743.0"], required=True)
    args = parser.parse_args()
    mapping = bindings(json.loads(args.source.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("window.FourInputMap = " + json.dumps(mapping, separators=(",", ":")) + ";\n")
    for key, value in mapping.items():
        print(f"{key}: {value['assignedName']} -> HDMI {value['port']}")
