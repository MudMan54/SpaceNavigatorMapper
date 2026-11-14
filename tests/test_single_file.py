"""The generated single-file edition starts and behaves like the source tree."""

import importlib.util
import pathlib

from test_session import ROOT, keys, run_session

spec = importlib.util.spec_from_file_location("build_single_file", ROOT / "tools" / "build_single_file.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_single_file_edition(tmp_path):
    target = builder.build(tmp_path / "dist")
    assert target.name.startswith("SpaceNavigator_Mapper_v") and target.name.endswith("_Complete.py")
    session = run_session(tmp_path, "full", kind="single", source=target)
    for label, checkpoint in session.items():
        assert not checkpoint.get("errors"), (label, checkpoint["errors"])
    assert keys(session["X strokes"]) == ["a down", "a up", "b down", "b up", "c down", "c up"]
    # v108.145: the README PDF and its Markdown come from inside the script.
    pdf = session["title right-click: README PDF"]["attrs"]["readme_pdf"]
    shipped = ROOT / "spnav_mapper" / "resources" / "SpaceNavigator_Mapper_README.pdf"
    assert pdf["pdf"] and pdf["size"] == shipped.stat().st_size
    text = session["title right-click: README window"]["attrs"]["readme"]["text"]
    assert text.startswith("# SpaceNavigator Mapper — Full Editor README")


def test_every_module_is_embedded(tmp_path):
    text = builder.build(tmp_path / "dist").read_text(encoding="utf-8")
    for path in (ROOT / "spnav_mapper").rglob("*.py"):
        if path.name != "__main__.py":
            assert f"_EMBEDDED_SOURCES['{builder.module_name(path)}']" in text, path
    assert pathlib.Path(builder.ICON).is_file()
