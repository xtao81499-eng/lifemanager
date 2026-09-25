"""Ensure parse path never touches Streamlit (prevents SessionInfo errors)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class NoStreamlitDuringParseTests(unittest.TestCase):
    def test_generate_path_does_not_import_streamlit(self):
        import core.calendar_import as ci

        # Guard: if anything tries to import streamlit mid-call, fail
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name == "streamlit" or name.startswith("streamlit."):
                raise AssertionError("streamlit imported during Gemini generate path")
            return real_import(name, *args, **kwargs)

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.ok = True
        fake_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '[{"start_time":"23:30","end_time":"24:00","event":"睡觉","score":7,"notes":"","category":"睡眠"}]'}]
                }
            }]
        }

        with patch("builtins.__import__", side_effect=guarded_import), patch(
            "core.calendar_import.requests.get"
        ) as mock_get, patch("core.calendar_import.requests.post") as mock_post, patch(
            "core.calendar_import.load_examples", return_value=[]
        ):
            mock_get.return_value.ok = True
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json.return_value = {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            }
            mock_post.return_value = fake_response

            # Minimal 1x1 PNG
            from io import BytesIO
            from PIL import Image

            buf = BytesIO()
            Image.new("RGB", (8, 8), color=(255, 255, 255)).save(buf, format="PNG")

            events = ci.parse_schedule_screenshot(
                buf.getvalue(),
                "2026-09-01",
                api_key="test-key",
                preferred_model="gemini-2.5-flash-lite",
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "睡觉")
        self.assertEqual(events[0]["end"], "2026-09-02T00:00:00")

    def test_calendar_import_module_has_no_streamlit_import(self):
        import core.calendar_import as ci
        import inspect

        src = inspect.getsource(ci)
        self.assertNotIn("import streamlit", src)
        self.assertNotIn("st.secrets", src)


if __name__ == "__main__":
    unittest.main()
