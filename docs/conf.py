import os
import sys
sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../vyperdatum"))

project = "Vyperdatum"
copyright = "2024, Mohammad Ashkezari"
author = "Mohammad Ashkezari"
release = "0.3.4"

extensions = ["sphinx.ext.todo", "sphinx.ext.viewcode", "sphinx.ext.autodoc", "notfound.extension"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
