import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from main import AudioAnnotator, _cli_export, _parse_time


class MainLogicTests(unittest.TestCase):
    def test_time_parse_and_format(self):
        self.assertEqual(_parse_time("01:02:03.50"), 3723.5)
        self.assertEqual(AudioAnnotator._fmt(3723.5), "01:02:03.50")
        self.assertEqual(AudioAnnotator._fmt(None), "00:00:00.00")

    def test_cli_export_csv_quotes_speaker_names(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "meeting"
            audio_path = str(base.with_suffix(".wav"))
            annot_path = Path(str(base) + "_标注.txt")
            export_path = Path(td) / "out.csv"
            annot_path.write_text(
                "讲话人\t开始时间\t结束时间\n"
                "张三, \"主持\"\t00:00:01.00\t00:00:03.50\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                _cli_export(audio_path, str(export_path))

            content = export_path.read_text(encoding="utf-8-sig")
            self.assertIn("讲话人,开始时间,结束时间,时长,内容", content)
            self.assertIn('"张三, ""主持""",00:00:01.00,00:00:03.50,00:00:02.50,', content)

    def test_cli_export_txt_keeps_tab_format(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "meeting"
            audio_path = str(base.with_suffix(".wav"))
            annot_path = Path(str(base) + "_标注.txt")
            export_path = Path(td) / "out.txt"
            annot_path.write_text("张三\t00:00:01.00\t00:00:02.00\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                _cli_export(audio_path, str(export_path))

            self.assertEqual(
                export_path.read_text(encoding="utf-8"),
                "讲话人\t开始时间\t结束时间\t时长\t内容\n"
                "张三\t00:00:01.00\t00:00:02.00\t00:00:01.00\t\n",
            )


if __name__ == "__main__":
    unittest.main()
