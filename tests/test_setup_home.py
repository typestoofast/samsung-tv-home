import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "setup_home", Path(__file__).parents[1] / "tools" / "setup-home.py"
)
setup_home = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_home)


def inventory(sources=(), apps=(), errors=()):
    return {"schemaVersion": 1, "sources": list(sources), "apps": list(apps), "errors": list(errors)}


def source(port, name, connected=True):
    return {"port": port, "name": name, "connected": connected}


def app(app_id, name):
    return {"id": app_id, "name": name, "iconPath": "/private/icon.png"}


def codes(result):
    return [issue["code"] for issue in result["unresolved"]]


class SetupHomeTest(unittest.TestCase):
    def test_swapped_ports_follow_inventory_and_preserve_labels(self):
        data = inventory([source(3, "Apple TV"), source(1, "Nintendo Switch 2"), source(2, "Steam")])
        before = copy.deepcopy(data)
        result = setup_home.plan(data)
        self.assertEqual(result["unresolved"], [])
        self.assertEqual([(item["key"], item["port"], item["logo"]) for item in result["shortcuts"]],
                         [("hdmi-3", 3, "appletv"), ("hdmi-1", 1, "nintendoswitch"),
                          ("hdmi-2", 2, "steam")])
        self.assertEqual(result["shortcuts"][1]["label"], "Nintendo Switch 2")
        self.assertEqual(result["shortcuts"][1]["sourceName"], "Nintendo Switch 2")
        self.assertEqual(data, before)

    def test_known_aliases_require_exact_normalized_name(self):
        for name, logo in ((" Apple  TV ", "appletv"), ("switch 2", "nintendoswitch"),
                           ("Steam Machine", "steam"), ("Stremio", "stremio")):
            with self.subTest(name=name):
                result = setup_home.plan(inventory([source(2, name)]))
                self.assertEqual(result["shortcuts"][0]["label"], name)
                self.assertEqual(result["shortcuts"][0]["logo"], logo)
                self.assertEqual(result["unresolved"], [])
        result = setup_home.plan(inventory([source(1, "Living room Apple TV")]))
        self.assertIsNone(result["shortcuts"][0]["logo"])
        self.assertIn("missing_logo", codes(result))

    def test_missing_and_generic_source_names_need_resolution(self):
        for name in ("", "  ", "HDMI", "HDMI 1", "HDMI-1", "HDMI 2 (ARC)",
                     "HDMI1/DVI", "Input 3", "PC", "Blu-ray player"):
            with self.subTest(name=name):
                result = setup_home.plan(inventory([source(1, name)]))
                self.assertEqual(result["shortcuts"], [])
                self.assertIn("source_name_required", codes(result))

    def test_duplicate_ports_and_names_do_not_create_guessed_shortcuts(self):
        for records, code in (
            ([source(1, "Steam"), source(1, "Apple TV")], "duplicate_port"),
            ([source(1, "Apple TV"), source(2, " apple  tv ")], "ambiguous_source_name"),
        ):
            with self.subTest(code=code):
                result = setup_home.plan(inventory(records))
                self.assertEqual(result["shortcuts"], [])
                self.assertIn(code, codes(result))

    def test_disconnected_sources_are_included_unless_explicitly_excluded(self):
        data = inventory([source(1, "Steam", False), source(2, "HDMI 2", False)])
        result = setup_home.plan(data, excluded_ports=[2])
        self.assertEqual(result["unresolved"], [])
        self.assertEqual([item["port"] for item in result["shortcuts"]], [1])

    def test_unknown_logo_keeps_named_shortcut_for_agent_resolution(self):
        result = setup_home.plan(inventory([source(4, "My console")]))
        self.assertEqual(result["shortcuts"], [{"key": "hdmi-4", "label": "My console",
                         "kind": "hdmi", "logo": None, "port": 4, "sourceName": "My console"}])
        self.assertEqual(result["unresolved"], [{"code": "missing_logo", "key": "hdmi-4"}])

    def test_no_default_owner_apps(self):
        result = setup_home.plan(inventory([source(2, "Steam")], [app("actual.id", "Stremio")]))
        self.assertEqual([item["kind"] for item in result["shortcuts"]], ["hdmi"])
        self.assertEqual(result["unresolved"], [])

    def test_explicit_app_uses_actual_installed_id_and_display_name(self):
        data = inventory(apps=[app("installed.1234", "Stremio"), app("unrequested", "Other app")])
        result = setup_home.plan(data, [" STRE MIO "])
        self.assertEqual(result["shortcuts"], [{"key": "app-0", "label": "Stremio", "kind": "app",
                         "logo": "stremio", "appId": "installed.1234"}])
        self.assertEqual(result["unresolved"], [])

    def test_hdmi_and_app_label_collision_requires_agent_resolution(self):
        for app_name in ("Apple TV", " apple  TV "):
            with self.subTest(app_name=app_name):
                data = inventory([source(1, "Apple TV")], [app("installed.apple", app_name)])
                before = copy.deepcopy(data)
                result = setup_home.plan(data, ["Apple TV"])
                self.assertEqual(result["unresolved"],
                                 [{"code": "ambiguous_label", "keys": ["hdmi-1", "app-0"]}])
                self.assertEqual([item["label"] for item in result["shortcuts"]], ["Apple TV", app_name])
                self.assertEqual(result["shortcuts"][0]["sourceName"], "Apple TV")
                self.assertEqual(result["shortcuts"][1]["appId"], "installed.apple")
                self.assertEqual(data, before)

    def test_cli_reports_label_collision_as_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "inventory.json"
            output = Path(directory) / "plan.json"
            saved.write_text(json.dumps(inventory([source(1, "Apple TV")],
                                                   [app("installed.apple", "Apple TV")])))
            with contextlib.redirect_stdout(io.StringIO()):
                status = setup_home.main(["--inventory", str(saved), "--out", str(output),
                                          "--apps", "Apple TV"])
            self.assertEqual(status, 2)
            result = json.loads(output.read_text())
            self.assertEqual(len(result["shortcuts"]), 2)
            self.assertEqual(codes(result), ["ambiguous_label"])

    def test_uninstalled_and_ambiguous_apps_are_not_guessed(self):
        for apps, code in (([], "app_not_installed"),
                           ([app("one", "Stremio"), app("two", "STREMIO")], "ambiguous_app_name"),
                           ([app("same", "Stremio"), app("same", "Other")], "duplicate_app_id")):
            with self.subTest(code=code):
                result = setup_home.plan(inventory(apps=apps), ["Stremio"])
                self.assertEqual(result["shortcuts"], [])
                self.assertIn(code, codes(result))

    def test_duplicate_app_requests_do_not_create_duplicate_tiles(self):
        result = setup_home.plan(inventory(apps=[app("one", "Stremio")]), ["Stremio", " STREMIO "])
        self.assertEqual(result["shortcuts"], [])
        self.assertIn("duplicate_app_request", codes(result))

    def test_unknown_app_logo_is_unresolved_despite_inventory_icon_path(self):
        result = setup_home.plan(inventory(apps=[app("my.id", "My player")]), ["My player"])
        self.assertEqual(result["shortcuts"][0]["appId"], "my.id")
        self.assertIsNone(result["shortcuts"][0]["logo"])
        self.assertEqual(result["unresolved"], [{"code": "missing_logo", "key": "app-0"}])

    def test_relevant_api_errors_prevent_silent_partial_success(self):
        errors = [{"api": api, "code": "Denied", "message": "Unavailable"}
                  for api in ("sources", "apps", "unknown")]
        data = inventory([source(1, "Steam")], [app("one", "Stremio")], errors)
        result = setup_home.plan(data)
        self.assertEqual([issue["api"] for issue in result["unresolved"]], ["sources", "unknown"])
        result = setup_home.plan(data, ["Stremio"])
        self.assertEqual([issue["error"] for issue in result["unresolved"]], errors)

    def test_empty_and_oversized_plans_remain_unresolved(self):
        self.assertIn("shortcut_count", codes(setup_home.plan(inventory())))
        result = setup_home.plan(inventory([source(port, "Device " + str(port)) for port in range(1, 10)]))
        self.assertEqual(len(result["shortcuts"]), 9)
        self.assertIn("shortcut_count", codes(result))

    def test_malformed_inventory_and_boolean_port_are_rejected(self):
        self.assertEqual(codes(setup_home.plan({"schemaVersion": True})), ["invalid_inventory"])
        result = setup_home.plan(inventory([source(True, "Steam")]))
        self.assertEqual(result["shortcuts"], [])
        self.assertIn("invalid_source", codes(result))

    def test_cli_writes_private_unresolved_plan_with_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "inventory.json"
            output = Path(directory) / "plan.json"
            saved.write_text(json.dumps(inventory([source(1, "Private household device")])))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = setup_home.main(["--inventory", str(saved), "--out", str(output)])
            self.assertEqual(status, 2)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(json.loads(output.read_text())["shortcuts"][0]["label"], "Private household device")
            self.assertEqual(stdout.getvalue(), "Plan written: 1 shortcuts, 1 unresolved.\n")
            original = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(setup_home.main(["--inventory", str(saved), "--out", str(output)]), 1)
            self.assertEqual(output.read_bytes(), original)

    def test_cli_complete_plan_and_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "inventory.json"
            output = Path(directory) / "plan.json"
            saved.write_text(json.dumps(inventory([source(1, "HDMI 1"), source(2, "Steam")],
                                                   [app("actual.789", "Stremio")])))
            with contextlib.redirect_stdout(io.StringIO()):
                status = setup_home.main(["--inventory", str(saved), "--out", str(output),
                                          "--exclude-ports", "1", "--apps", "Stremio"])
            self.assertEqual(status, 0)
            result = json.loads(output.read_text())
            self.assertEqual([item["key"] for item in result["shortcuts"]], ["hdmi-2", "app-0"])
            self.assertEqual(result["unresolved"], [])


if __name__ == "__main__":
    unittest.main()
