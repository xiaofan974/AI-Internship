"""Mocked tests for batch_ingest.py. No provider or live /ingest calls."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import batch_ingest


def _write_txt(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class BatchIngestTests(unittest.TestCase):
    def test_discovers_top_level_txt_sorted_and_ignores_other_types(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "b-policy.txt", "B")
            _write_txt(root, "a-policy.txt", "A")
            (root / "notes.md").write_text("# skip", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            _write_txt(nested, "hidden.txt", "no")
            files = batch_ingest.discover_text_files(root)
            self.assertEqual([path.name for path in files], ["a-policy.txt", "b-policy.txt"])

    def test_stable_ids_from_filename_and_prefix(self) -> None:
        path = Path("Remote Work.txt")
        self.assertEqual(batch_ingest.document_id_from_filename(path), "remote-work")
        self.assertEqual(
            batch_ingest.document_id_from_filename(path, "batch-addon5"),
            "batch-addon5-remote-work",
        )

    def test_plan_rejects_empty_documents(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "ok.txt", "ExampleCo help desk hours.")
            _write_txt(root, "empty.txt", "   \n")
            planned = batch_ingest.plan_documents(root, prefix="demo", source="batch-test")
            by_name = {item.path.name: item for item in planned}
            self.assertIsNone(by_name["ok.txt"].error)
            self.assertEqual(by_name["ok.txt"].document_id, "demo-ok")
            self.assertIsNotNone(by_name["empty.txt"].error)
            self.assertIn("empty", by_name["empty.txt"].error.lower())

    def test_dry_run_makes_no_http_calls(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "policy.txt", "ExampleCo remote days are Tuesday and Thursday.")
            with patch.object(batch_ingest, "post_ingest") as post:
                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    code = batch_ingest.main([str(root)])
            self.assertEqual(code, 0)
            post.assert_not_called()
            output = stdout.getvalue()
            self.assertIn("DRY-RUN", output)
            self.assertIn("policy.txt", output)
            self.assertIn("\tpolicy\t", output)
            self.assertIn("chunks indexed: 0", output)

    def test_live_without_allow_replace_or_prefix_does_not_call_api(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "policy.txt", "text")
            with patch.object(batch_ingest, "post_ingest") as post:
                with patch("sys.stdout", new=io.StringIO()):
                    code = batch_ingest.main([str(root), "--live"])
            self.assertEqual(code, 2)
            post.assert_not_called()

    def test_live_payload_and_auth_header(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "desk.txt", "Help desk 9 to 5.")
            with patch.dict(
                "os.environ",
                {"INGEST_API_KEY": "test-secret", "API_BASE_URL": "http://127.0.0.1:8000"},
                clear=False,
            ):
                with patch.object(
                    batch_ingest,
                    "post_ingest",
                    return_value=(200, {"document_id": "safe-desk", "chunks_indexed": 1, "status": "success"}),
                ) as post:
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = batch_ingest.main(
                            [
                                str(root),
                                "--live",
                                "--allow-replace",
                                "--id-prefix",
                                "safe",
                                "--source",
                                "batch-demo",
                            ]
                        )
            self.assertEqual(code, 0)
            post.assert_called_once()
            args, kwargs = post.call_args
            self.assertEqual(args[0], "http://127.0.0.1:8000")
            self.assertEqual(
                args[1],
                {
                    "document_id": "safe-desk",
                    "text": "Help desk 9 to 5.",
                    "source": "batch-demo",
                },
            )
            self.assertEqual(args[2], "test-secret")
            self.assertIn("Total documents: 1", stdout.getvalue())
            self.assertIn("chunks indexed: 1", stdout.getvalue())

    def test_stops_on_first_http_failure_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "a.txt", "first")
            _write_txt(root, "b.txt", "second")
            with patch.dict("os.environ", {"INGEST_API_KEY": "test-secret"}, clear=False):
                with patch.object(
                    batch_ingest,
                    "post_ingest",
                    return_value=(502, {"detail": "Document ingestion failed."}),
                ) as post:
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = batch_ingest.main(
                            [str(root), "--live", "--allow-replace", "--id-prefix", "safe"]
                        )
            self.assertEqual(code, 1)
            self.assertEqual(post.call_count, 1)
            self.assertIn("No automatic retries", stdout.getvalue())

    def test_empty_file_stops_live_before_http(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write_txt(root, "empty.txt", "")
            with patch.dict("os.environ", {"INGEST_API_KEY": "test-secret"}, clear=False):
                with patch.object(batch_ingest, "post_ingest") as post:
                    with patch("sys.stdout", new=io.StringIO()):
                        code = batch_ingest.main(
                            [str(root), "--live", "--allow-replace", "--id-prefix", "safe"]
                        )
            self.assertEqual(code, 1)
            post.assert_not_called()

    def test_post_ingest_does_not_enable_httpx_retries(self) -> None:
        with patch("batch_ingest.httpx.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "document_id": "x",
                "chunks_indexed": 1,
                "status": "success",
            }
            status, body = batch_ingest.post_ingest(
                "http://127.0.0.1:8000",
                {"document_id": "x", "text": "hi"},
                "secret",
            )
        self.assertEqual(status, 200)
        self.assertEqual(body["chunks_indexed"], 1)
        self.assertNotIn("retries", post.call_args.kwargs)
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Ingest-Key"], "secret")


if __name__ == "__main__":
    unittest.main()
