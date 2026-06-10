import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

with open(_root / "pyproject.toml", "rb") as _f:
    _project = tomllib.load(_f)["project"]

project = "Vyperdatum"
author = "Mohammad Ashkezari"
copyright = "2024-2026, NOAA Office of Coast Survey"
release = _project["version"]
version = release

extensions = [
    "autoapi.extension",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "notfound.extension",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "_static/vyperdatum-logo-light.svg"
html_favicon = "_static/vyperdatum-icon.svg"
html_theme_options = {
    "logo_only": True,
}

# AutoAPI: the package source is parsed statically, so importing
# vyperdatum (which validates VYPER_GRIDS at import time) is not
# required for the documentation build.
autoapi_type = "python"
autoapi_dirs = [str(_root / "vyperdatum")]
autoapi_root = "api"
autoapi_add_toctree_entry = False
autoapi_keep_files = False
autoapi_ignore = [
    "*/scripts/*",
    "*/assets/*",
    "*/tests/*",
]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]

# Napoleon: the docstrings in the codebase follow the NumPy style.
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_include_init_with_doc = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pyproj": ("https://pyproj4.github.io/pyproj/stable/", None),
}

todo_include_todos = False
