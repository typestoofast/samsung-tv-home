"""Create a private Home setup plan from a saved TV inventory. No device access."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys


LOGOS = {
    "appletv": "appletv",
    "switch": "nintendoswitch",
    "switch2": "nintendoswitch",
    "nintendoswitch": "nintendoswitch",
    "nintendoswitch2": "nintendoswitch",
    "steam": "steam",
    "steammachine": "steam",
    "stremio": "stremio",
}
GENERIC_NAMES = {
    "unknown", "unknowndevice", "externaldevice", "device", "pc",
    "gameconsole", "console", "cablebox", "bluray", "blurayplayer", "blu-ray", "blu-rayplayer",
}


def normalized(name):
    return re.sub(r"\s+", "", name).casefold()


def generic_source(name):
    value = normalized(name)
    return (value in GENERIC_NAMES or
            re.fullmatch(r"(?:hdmi|input|source)[-:#]?\d*(?:[/()-]*(?:dvi|arc|earc|stb)[()]*)?", value)
            is not None)


def plan(inventory, requested_apps=(), excluded_ports=()):
    result = {"schemaVersion": 1, "shortcuts": [], "unresolved": []}
    unresolved = result["unresolved"]
    shortcuts = result["shortcuts"]
    if (not isinstance(inventory, dict) or type(inventory.get("schemaVersion")) is not int or
            inventory["schemaVersion"] != 1 or
            any(not isinstance(inventory.get(field), list) for field in ("sources", "apps", "errors"))):
        unresolved.append({"code": "invalid_inventory"})
        return result

    for error in inventory["errors"]:
        api = error.get("api") if isinstance(error, dict) else None
        if api != "apps" or requested_apps:
            unresolved.append({"code": "api_error", "api": api, "error": error})

    sources = []
    for index, source in enumerate(inventory["sources"]):
        if (not isinstance(source, dict) or type(source.get("port")) is not int or
                source["port"] < 1 or type(source.get("connected")) is not bool or
                not isinstance(source.get("name"), str)):
            unresolved.append({"code": "invalid_source", "index": index})
        elif source["port"] not in excluded_ports:
            sources.append(source)
    ports = Counter(source["port"] for source in sources)
    names = Counter(normalized(source["name"]) for source in sources)

    def add(shortcut):
        shortcuts.append(shortcut)
        if shortcut["logo"] is None:
            unresolved.append({"code": "missing_logo", "key": shortcut["key"]})

    duplicate_ports = set()
    for source in sources:
        port, name = source["port"], source["name"]
        key = "hdmi-" + str(port)
        if ports[port] > 1:
            if port not in duplicate_ports:
                unresolved.append({"code": "duplicate_port", "port": port, "key": key})
                duplicate_ports.add(port)
        elif not name.strip() or generic_source(name):
            unresolved.append({"code": "source_name_required", "port": port, "key": key})
        elif names[normalized(name)] > 1:
            unresolved.append({"code": "ambiguous_source_name", "port": port, "key": key})
        else:
            add({"key": key, "label": name, "kind": "hdmi", "logo": LOGOS.get(normalized(name)),
                 "port": port, "sourceName": name})

    if requested_apps:
        apps = []
        for index, app in enumerate(inventory["apps"]):
            if (not isinstance(app, dict) or not isinstance(app.get("id"), str) or
                    not app["id"].strip() or not isinstance(app.get("name"), str) or
                    not app["name"].strip() or not isinstance(app.get("iconPath"), str)):
                unresolved.append({"code": "invalid_app", "index": index})
            else:
                apps.append(app)
        app_ids = Counter(app["id"] for app in apps)
        requests = Counter(normalized(name) for name in requested_apps)
        for index, request in enumerate(requested_apps):
            key = "app-" + str(index)
            issue = {"key": key, "request": request}
            matches = [app for app in apps if normalized(app["name"]) == normalized(request)]
            if requests[normalized(request)] > 1:
                unresolved.append(dict(issue, code="duplicate_app_request"))
            elif not matches:
                unresolved.append(dict(issue, code="app_not_installed"))
            elif len(matches) > 1:
                unresolved.append(dict(issue, code="ambiguous_app_name"))
            elif app_ids[matches[0]["id"]] > 1:
                unresolved.append(dict(issue, code="duplicate_app_id"))
            else:
                app = matches[0]
                add({"key": key, "label": app["name"], "kind": "app",
                     "logo": LOGOS.get(normalized(app["name"])), "appId": app["id"]})

    labels = {}
    for shortcut in shortcuts:
        labels.setdefault(normalized(shortcut["label"]), []).append(shortcut["key"])
    for keys in labels.values():
        if len(keys) > 1:
            unresolved.append({"code": "ambiguous_label", "keys": keys})

    if not 1 <= len(shortcuts) <= 8:
        unresolved.append({"code": "shortcut_count", "count": len(shortcuts), "minimum": 1, "maximum": 8})
    return result


def positive_port(value):
    port = int(value)
    if port < 1:
        raise argparse.ArgumentTypeError("Ports must be positive integers")
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apps", nargs="+", default=[])
    parser.add_argument("--exclude-ports", type=positive_port, nargs="+", default=[])
    args = parser.parse_args(argv)
    try:
        inventory = json.loads(args.inventory.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("Could not read inventory JSON.", file=sys.stderr)
        return 1
    result = plan(inventory, args.apps, args.exclude_ports)
    try:
        args.out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(result, output, indent=2, ensure_ascii=False)
            output.write("\n")
    except OSError:
        print("Could not create a new private plan file.", file=sys.stderr)
        return 1
    print(f"Plan written: {len(result['shortcuts'])} shortcuts, {len(result['unresolved'])} unresolved.")
    return 2 if result["unresolved"] else 0


if __name__ == "__main__":
    sys.exit(main())
