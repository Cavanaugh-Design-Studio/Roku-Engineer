"""Scoped JSON bridge between the desktop workspace and the existing Python engine.

One request on stdin, one JSON response on stdout. No AI keys are needed for
authoring, linting, validation, previews, or packaging. Paths are always relative
to a project explicitly selected by the user in the desktop file picker.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

GENERATORS = {
    "memory": ("Memory monitoring", "generate_memory_monitor"),
    "deeplink": ("Deep link routing", "generate_deep_link_handler"),
    "feed": ("Content feed task", "generate_content_feed_handler"),
    "ads": ("Advertising framework", "generate_raf_integration"),
    "payments": ("Roku Pay", "generate_roku_pay_integration"),
    "websocket": ("WebSocket task", "generate_websocket_handler"),
    "sse": ("Server-sent events", "generate_sse_handler"),
}
SKIP_DIRS = {".git", ".engineer", ".venv", "venv", "node_modules", "__pycache__", ".cache", "dist", "build"}
TEXT_EXTENSIONS = {".brs", ".bs", ".xml", ".json", ".md", ".txt", ".ts", ".csv"}
MAX_FILE = 2 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project_root(value: str) -> Path:
    root = Path(value).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Select a project folder first.")
    return root


def scoped(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Use a relative project path with forward slashes.")
    rel = Path(relative)
    if rel.is_absolute() or any(p.startswith(".") or p in SKIP_DIRS for p in rel.parts):
        raise ValueError("Hidden files, credentials, and paths outside the project are unavailable.")
    path = (root / rel).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Path must stay inside the selected project.")
    if path.name != "manifest" and path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("This file type is unavailable in the project editor.")
    return path


def file_map(root: Path) -> dict[str, bytes]:
    result = {}
    total_bytes = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if name.startswith(".") or path.is_symlink():
                continue
            if name != "manifest" and path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if path.stat().st_size > MAX_FILE:
                continue
            total_bytes += path.stat().st_size
            if len(result) >= 2000 or total_bytes > 20 * MAX_FILE:
                raise ValueError("Project exceeds the workspace limit (2,000 text files / 40 MB).")
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def engine():
    # Redirect Rich/optional dependency messages so stdout remains a JSON protocol.
    with contextlib.redirect_stdout(sys.stderr):
        import roku_engineer
    return roku_engineer


def summary(root: Path) -> dict:
    files = file_map(root)
    title = root.name
    manifest = files.get("manifest", b"").decode("utf-8", errors="replace")
    for line in manifest.splitlines():
        if line.startswith("title="):
            title = line.split("=", 1)[1]
    return {"root": str(root), "title": title, "files": [{"path": p, "size": len(b), "sha256": digest(b)} for p, b in files.items()]}


def read_file(root: Path, relative: str) -> dict:
    path = scoped(root, relative)
    if path.stat().st_size > MAX_FILE:
        raise ValueError("File exceeds the 2 MB editor limit.")
    data = path.read_bytes()
    return {"path": relative, "content": data.decode("utf-8-sig"), "sha256": digest(data)}


def apply_changes(root: Path, changes: list) -> dict:
    if not isinstance(changes, list) or not 1 <= len(changes) <= 80:
        raise ValueError("A change set must contain 1 to 80 files.")
    prepared = []
    seen = set()
    # Check the complete change set before touching any files.
    for change in changes:
        path = scoped(root, change["path"])
        if path in seen:
            raise ValueError("Duplicate path in change set.")
        seen.add(path)
        original = path.read_bytes() if path.exists() else None
        expected = change.get("beforeSha256")
        if (digest(original) if original is not None else None) != expected:
            raise ValueError(f"{change['path']} changed on disk. Refresh and review the proposal again.")
        content = change["content"]
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE:
            raise ValueError("Invalid file content or file exceeds 2 MB.")
        prepared.append((path, original, content.encode("utf-8")))
    backup_id = __import__("uuid").uuid4().hex
    backup_dir = root / ".engineer" / "history" / backup_id
    if (root / ".engineer").is_symlink() or (root / ".engineer" / "history").is_symlink():
        raise ValueError("Project history folder cannot be a symlink.")
    backup_dir.mkdir(parents=True)
    metadata = []
    for index, (path, original, content) in enumerate(prepared):
        if original is not None:
            (backup_dir / str(index)).write_bytes(original)
        metadata.append({"path": path.relative_to(root).as_posix(), "existed": original is not None, "afterSha256": digest(content)})
    (backup_dir / "changes.json").write_text(json.dumps(metadata), encoding="utf-8")
    applied = []
    try:
        for path, original, content in prepared:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, staging = tempfile.mkstemp(prefix=".engineer-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(content)
                os.replace(staging, path)
                applied.append((path, original))
            finally:
                if os.path.exists(staging):
                    os.unlink(staging)
    except Exception:
        for path, original in reversed(applied):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
    return {"changed": [m["path"] for m in metadata], "backupId": backup_id, "project": summary(root)}


def preview(root: Path, generator: str) -> dict:
    if generator not in GENERATORS:
        raise ValueError("Unknown generator.")
    before = file_map(root)
    with tempfile.TemporaryDirectory(prefix="roku-engineer-preview-") as temp:
        staging = Path(temp)
        for name, data in before.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        with contextlib.redirect_stdout(sys.stderr):
            function = getattr(engine(), GENERATORS[generator][1])
            result = asyncio.run(function(str(staging)))
        if isinstance(result, tuple) and result[0] is False:
            raise ValueError(str(result[1]))
        after = file_map(staging)
    changes = [{"path": name, "before": before.get(name, b"").decode("utf-8-sig"), "beforeSha256": digest(before[name]) if name in before else None, "content": data.decode("utf-8-sig")} for name, data in after.items() if before.get(name) != data]
    return {"title": GENERATORS[generator][0], "generator": generator, "changes": changes}


def package_project(root: Path) -> dict:
    if not (root / "manifest").is_file():
        raise ValueError("A channel package needs a manifest at the project root.")
    artifact_dir = root / ".engineer" / "artifacts"
    if (root / ".engineer").is_symlink() or artifact_dir.is_symlink():
        raise ValueError("Artifact folder cannot be a symlink.")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output = artifact_dir / f"{root.name}.zip"
    # Artifacts, credentials, symlinks, tooling folders, and the archive itself are excluded.
    packaged = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and not (Path(directory) / d).is_symlink())
            for name in sorted(files):
                path = Path(directory) / name
                if name.startswith(".") or path.is_symlink() or path.suffix.lower() in {".zip", ".pkg", ".log", ".env", ".pem", ".key", ".p12", ".pfx", ".py", ".pyc"}:
                    continue
                relative = path.relative_to(root).as_posix()
                archive.write(path, relative)
                packaged.append(relative)
    return {"path": str(output), "size": output.stat().st_size, "files": packaged, "sha256": digest(output.read_bytes())}


def dispatch(request: dict) -> dict:
    action = request.get("action")
    if action == "status":
        return {"python": sys.version.split()[0], "generators": [{"id": key, "title": value[0]} for key, value in GENERATORS.items()]}
    root = project_root(request.get("root", "."))
    if action == "project":
        return summary(root)
    if action == "read":
        return read_file(root, request["path"])
    if action == "apply":
        return apply_changes(root, request["changes"])
    if action == "preview":
        return preview(root, request["generator"])
    if action == "package":
        return package_project(root)
    if action == "validate":
        # Validate only the same scoped text snapshot available to the editor.
        # The legacy validator walks its input directly; an isolated snapshot
        # prevents symlinked files or hidden dependency folders bypassing scope.
        with tempfile.TemporaryDirectory(prefix="roku-engineer-check-") as temp:
            staging = Path(temp)
            for name, data in file_map(root).items():
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            with contextlib.redirect_stdout(sys.stderr):
                report = asyncio.run(engine().validate_roku_project(str(staging)))
        return {"report": report, "status": "failed" if "failed" in report.lower() or report.startswith("Error:") else "warnings" if "warnings" in report.lower() else "passed", "scope": "Local heuristic checks. Run official static analysis and device tests before publishing."}
    if action == "lint":
        content = request.get("content", "")
        if not isinstance(content, str) or len(content) > MAX_FILE:
            raise ValueError("Invalid content.")
        return {"report": engine().lint_brightscript(content)}
    if action == "scaffold":
        name = request.get("name", "")
        kind = request.get("kind", "basic")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}", name) or name.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
            raise ValueError("Use a channel name with 1–64 letters, numbers, spaces, underscores, or hyphens.")
        if kind not in {"basic", "grid", "sgdex"}:
            raise ValueError("Unknown project template.")
        destination = root / name
        if destination.exists():
            raise ValueError("This folder already exists. Choose a new channel name.")
        # Build in isolation; move into place only after all generation succeeds.
        with tempfile.TemporaryDirectory(prefix="roku-engineer-create-") as temp:
            with contextlib.redirect_stdout(sys.stderr):
                core = engine()
                success, message = asyncio.run(core.create_roku_project(name, temp, kind))
            if not success:
                raise ValueError(message)
            staging = Path(temp) / name
            # Real generated assets instead of dangling manifest image paths.
            from PIL import Image, ImageDraw
            for filename, size in {"icon_focus_hd.png": (336, 210), "icon_focus_sd.png": (246, 140), "splash_hd.jpg": (1280, 720), "splash_sd.jpg": (720, 480)}.items():
                image = Image.new("RGB", size, "#11141d")
                draw = ImageDraw.Draw(image)
                draw.rounded_rectangle((size[0]//4, size[1]//4, size[0]*3//4, size[1]*3//4), radius=12, outline="#a99bff", width=4)
                draw.text((size[0]//3, size[1]//2-6), name[:24], fill="#f1f3fa")
                image.save(staging / "images" / filename)
            # SGDEX is an external library, never silently claim the generated app includes it.
            if kind == "sgdex":
                (staging / "SGDEX-SETUP.md").write_text("# SGDEX dependency\n\nMainScene extends GridView. Add the official SGDEX components to this channel before sideloading: https://github.com/rokudev/SceneGraphDeveloperExtensions\n", encoding="utf-8")
            if kind == "grid":
                (staging / "components" / "MainScene" / "MainScene.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<component name="MainScene" extends="Scene">
  <script type="text/brightscript" uri="MainScene.brs" />
  <children>
    <Rectangle width="1920" height="1080" color="0x11141dff" />
    <Label text="Your channel" translation="[80, 55]" width="1760" height="80" />
    <RowList id="catalog" translation="[80, 180]" itemSize="[1760, 280]" rowItemSize="[[300, 210]]" numRows="3" itemComponentName="CatalogPoster" />
  </children>
</component>''', encoding="utf-8")
                (staging / "components" / "MainScene" / "MainScene.brs").write_text('''sub init()
    catalog = m.top.findNode("catalog")
    catalog.setFocus(true)
end sub
''', encoding="utf-8")
                (staging / "components" / "CatalogPoster.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<component name="CatalogPoster" extends="Group">
  <interface><field id="itemContent" type="node" onChange="showItem" /></interface>
  <script type="text/brightscript"><![CDATA[
    sub showItem()
      if m.top.itemContent <> invalid
        m.top.findNode("title").text = m.top.itemContent.title
        m.top.findNode("poster").uri = m.top.itemContent.hdPosterUrl
      end if
    end sub
  ]]></script>
  <children><Poster id="poster" width="300" height="170" /><Label id="title" translation="[0, 175]" width="300" height="35" /></children>
</component>''', encoding="utf-8")
            shutil.copytree(staging, destination)
        return summary(destination)
    raise ValueError("Unknown workspace action.")


def main():
    try:
        raw = sys.stdin.buffer.read(4 * MAX_FILE + 1)
        if len(raw) > 4 * MAX_FILE:
            raise ValueError("Request is too large.")
        request = json.loads(raw.decode("utf-8-sig"))
        result = dispatch(request)
        response = {"ok": True, "data": result}
    except Exception as error:
        response = {"ok": False, "error": str(error)}
    sys.stdout.buffer.write((json.dumps(response, ensure_ascii=True) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
