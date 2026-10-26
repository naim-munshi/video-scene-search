"""Guard the Streamlit 1.66+ UI against deprecated width parameters."""
import ast
import unittest
from pathlib import Path


class StreamlitCompatibilityTests(unittest.TestCase):
    def test_app_uses_supported_width_argument(self):
        code = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(code)
        render_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"image", "dataframe"}
        ]
        self.assertGreaterEqual(len(render_calls), 2)
        for node in render_calls:
            keys = {keyword.arg for keyword in node.keywords}
            self.assertNotIn("use_container_width", keys)
            self.assertIn("width", keys)
            values = [kw.value for kw in node.keywords if kw.arg == "width"]
            self.assertTrue(all(isinstance(v, ast.Constant) and v.value == "stretch"
                                for v in values))

    def test_accessible_tabs_styles_present(self):
        css = (Path(__file__).resolve().parents[1] / ".streamlit" / "style.css").read_text()
        self.assertIn('data-baseweb="tab"][aria-selected="true"]', css)
        self.assertIn('focus-visible', css)


if __name__ == "__main__":
    unittest.main()
