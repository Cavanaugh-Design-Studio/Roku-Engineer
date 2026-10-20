import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

from engineer_bridge import dispatch, scoped, digest, apply_changes


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.root / "manifest").write_text("title=Test Channel\n", encoding="utf-8")

    def call(self, action, **kwargs):
        return dispatch({"action": action, "root": str(self.root), **kwargs})

    def test_project_does_not_list_hidden_credentials_or_symlinks(self):
        (self.root / ".env").write_text("ANTHROPIC_API_KEY=not-a-real-key")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "secret.json").write_text("{}")
        (self.root / "source").mkdir()
        (self.root / "source" / "main.brs").write_text("sub Main()\nend sub")
        project = self.call("project")
        self.assertEqual(project["title"], "Test Channel")
        self.assertEqual({f["path"] for f in project["files"]}, {"manifest", "source/main.brs"})

    def test_path_boundaries(self):
        for candidate in ("../escape.brs", ".env", ".git/config", "source/../../escape.brs", "C:/Windows/system.ini", "source\\main.brs", ".engineer/history/a.json", "private.key"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                scoped(self.root, candidate)

    def test_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as outside:
            try:
                (self.root / "linked").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks requires developer mode or privilege on this host")
            with self.assertRaises(ValueError):
                self.call("apply", changes=[{"path": "linked/escape.brs", "content": "no", "beforeSha256": None}])

    def test_conflict_checks_entire_change_set_before_writing(self):
        before = (self.root / "manifest").read_bytes()
        with self.assertRaisesRegex(ValueError, "changed on disk"):
            self.call("apply", changes=[{"path": "new.brs", "content": "new", "beforeSha256": None}, {"path": "manifest", "content": "changed", "beforeSha256": "wrong"}])
        self.assertFalse((self.root / "new.brs").exists())
        self.assertEqual((self.root / "manifest").read_bytes(), before)

    def test_write_keeps_backup_and_rejects_stale_hash(self):
        original = self.call("read", path="manifest")
        changes = [{"path": "manifest", "content": "title=Edited", "beforeSha256": original["sha256"]}]
        result = self.call("apply", changes=changes)
        backup = self.root / ".engineer/history" / result["backupId"]
        self.assertEqual((backup / "0").read_bytes(), original["content"].encode("utf-8"))
        self.assertEqual((self.root / "manifest").read_text(), "title=Edited")
        with self.assertRaisesRegex(ValueError, "changed on disk"):
            self.call("apply", changes=changes)

    def test_duplicate_changes_are_rejected(self):
        change = {"path": "new.brs", "content": "new", "beforeSha256": None}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            apply_changes(self.root, [change, change])

    def test_generator_preview_is_read_only_then_apply_is_explicit(self):
        before = self.call("project")
        proposal = self.call("preview", generator="feed")
        self.assertEqual(self.call("project"), before)
        self.assertGreater(len(proposal["changes"]), 0)
        result = self.call("apply", changes=proposal["changes"])
        self.assertEqual(set(result["changed"]), {c["path"] for c in proposal["changes"]})

    def test_every_generator_produces_reviewable_files(self):
        for generator in self.call("status")["generators"]:
            with self.subTest(generator=generator["id"]):
                result = self.call("preview", generator=generator["id"])
                self.assertTrue(result["changes"])
                self.assertTrue(all(c["beforeSha256"] is None for c in result["changes"]))
                if generator["id"] == "feed":
                    by_path = {c["path"]: c["content"] for c in result["changes"]}
                    self.assertNotIn("components/ContentFeedTask.brs", by_path)
                    xml = ET.fromstring(by_path["components/ContentFeedTask/ContentFeedTask.xml"])
                    self.assertEqual(xml.find("./interface/field[@id='output']").get("type"), "node")
                    self.assertEqual(by_path["components/ContentFeedTask/ContentFeedTask.brs"].count("request.GetToString()"), 1)
                for change in result["changes"]:
                    if change["path"].endswith(".xml"):
                        ET.fromstring(change["content"])

    def test_packaging_excludes_credentials_caches_and_archives(self):
        (self.root / ".env").write_text("secret")
        (self.root / "credentials.env").write_text("secret")
        (self.root / "server.key").write_text("secret")
        (self.root / "previous.zip").write_bytes(b"old")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "private.json").write_text("{}")
        (self.root / "images").mkdir()
        (self.root / "images/icon.png").write_bytes(b"image")
        result = self.call("package")
        with zipfile.ZipFile(result["path"]) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest", "images/icon.png"})
        second = self.call("package")
        self.assertEqual(second["sha256"], result["sha256"])

    def test_scaffold_grid_has_one_main_scene_and_real_assets(self):
        created = self.call("scaffold", name="GridChannel", kind="grid")
        root = Path(created["root"])
        definitions = [p for p in root.rglob("*.xml") if 'component name="MainScene"' in p.read_text()]
        self.assertEqual(len(definitions), 1)
        self.assertIn('RowList', definitions[0].read_text())
        for line in (root / "manifest").read_text().splitlines():
            if "=pkg:/images/" in line:
                self.assertTrue((root / line.split("=pkg:/", 1)[1]).is_file(), line)

    def test_scaffold_cannot_overwrite_project_or_escape_parent(self):
        for name in ("../escape", "bad/name", "CON", "NUL", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.call("scaffold", name=name)
        self.call("scaffold", name="Channel")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.call("scaffold", name="Channel")

    def test_json_bridge_works_without_provider_credentials(self):
        import os
        env = {k: v for k, v in os.environ.items() if k not in {"ANTHROPIC_API_KEY", "TAVILY_API_KEY"}}
        result = subprocess.run([sys.executable, "engineer_bridge.py"], input=json.dumps({"action": "validate", "root": str(self.root)}), capture_output=True, text=True, env=env, timeout=40)
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["data"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
