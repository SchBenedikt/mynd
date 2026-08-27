from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_context_validates_project_storage_shape_and_size():
    source = (ROOT / "frontend/lib/AppContext.js").read_text()
    assert "raw.length > 100000" in source
    assert "Array.isArray(parsed)" in source
    assert "project.id" in source
    assert "project.name" in source


def test_projects_page_uses_the_same_safe_project_loader():
    source = (ROOT / "frontend/app/projects/page.js").read_text()
    assert "function loadProjects()" in source
    assert "raw.length > 100000" in source
    assert "useState(loadProjects)" in source
