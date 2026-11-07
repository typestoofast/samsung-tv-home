import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "import_inputs", Path(__file__).parents[1] / "tools" / "import-inputs.py"
)
import_inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_inputs)


class InputBindingsTest(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"EditName": "Switch", "SourceType": 14},
            {"EditName": "Apple TV", "SourceType": 15},
            {"EditName": "Steam", "DetectedName": "PC", "SourceType": 16},
        ]

    def test_saved_names_resolve_to_their_ports(self):
        self.assertEqual(
            import_inputs.bindings(self.records),
            {
                "switch": {"port": 2, "assignedName": "Switch"},
                "apple": {"port": 3, "assignedName": "Apple TV"},
                "steam": {"port": 4, "assignedName": "Steam"},
            },
        )

    def test_aliases_and_detected_name_fallback(self):
        self.records[0]["EditName"] = "Nintendo Switch 2"
        self.records[1] = {"DetectedName": "apple TV", "SourceType": 13}
        self.assertEqual(import_inputs.bindings(self.records)["apple"]["port"], 1)

    def test_unknown_source_type_is_rejected(self):
        for value in (0, 12, 17, "14", True):
            with self.subTest(value=value):
                self.records[0]["SourceType"] = value
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    import_inputs.bindings(self.records)

    def test_ambiguous_names_are_rejected(self):
        self.records.append({"EditName": "Switch 2", "SourceType": 13})
        with self.assertRaisesRegex(ValueError, "more than one"):
            import_inputs.bindings(self.records)

    def test_duplicate_port_is_rejected(self):
        self.records[0]["SourceType"] = 15
        with self.assertRaisesRegex(ValueError, "same HDMI"):
            import_inputs.bindings(self.records)

    def test_missing_name_is_rejected(self):
        self.records[0]["EditName"] = "Console"
        with self.assertRaisesRegex(ValueError, "missing: switch"):
            import_inputs.bindings(self.records)
