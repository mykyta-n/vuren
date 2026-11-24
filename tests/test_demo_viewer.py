import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import viewer


class DemoViewerTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.project = Path(folder.name).resolve()
        self.rehearsal = self.project / "demo" / "pitch"
        self.rehearsal.mkdir(parents=True)
        self.write_run(self.rehearsal)

    def write_run(self, path):
        for name in ("trace.json", "verdict.json"):
            (path / name).write_text("{}", encoding="utf-8")

    def test_default_uses_the_same_project_folder_as_the_live_viewer(self):
        self.write_run(self.project)
        with patch.object(viewer, "ROOT", self.project), patch.object(viewer, "serve") as serve:
            with patch("sys.argv", ["demo-viewer", "--port", "0"]):
                viewer.demo_main()

        serve.assert_called_once_with(self.project, 0, demo=True)

    def test_missing_local_run_does_not_open_the_rehearsal(self):
        stderr = StringIO()
        with patch.object(viewer, "ROOT", self.project), patch.object(viewer, "serve") as serve:
            with patch("sys.argv", ["demo-viewer"]), redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as error:
                    viewer.demo_main()

        self.assertEqual(error.exception.code, 2)
        self.assertIn("trace.json, verdict.json", stderr.getvalue())
        self.assertIn("uv run demo-viewer demo/pitch", stderr.getvalue())
        serve.assert_not_called()

    def test_an_explicit_run_folder_can_select_the_rehearsal(self):
        self.write_run(self.project)
        with patch.object(viewer, "ROOT", self.project), patch.object(viewer, "serve") as serve:
            with patch("sys.argv", ["demo-viewer", str(self.rehearsal), "--port", "0"]):
                viewer.demo_main()

        serve.assert_called_once_with(self.rehearsal, 0, demo=True)
