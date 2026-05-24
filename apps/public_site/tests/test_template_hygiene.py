"""Template hygiene: catch the multi-line `{# #}` trap.

Django's `{# ... #}` comment syntax is single-line only. A multi-line
form looks like a comment but Django renders it as literal HTML, so
developer notes end up shown to users. This has happened three times
in this project, twice in the same conversation. A scanning test is
cheap insurance.

If you have a real multi-line comment, use `{% comment %} ... {%
endcomment %}` — which works correctly across lines.
"""

from pathlib import Path


def test_no_multiline_django_short_comments():
    project_root = Path(__file__).resolve().parents[3]
    templates_dir = project_root / "templates"
    assert templates_dir.is_dir(), f"templates dir not found at {templates_dir}"

    violations = []
    for path in templates_dir.rglob("*.html"):
        in_comment = False
        start_line = 0
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if not in_comment:
                j = line.find("{#")
                # opens but doesn't close on the same line ⇒ multi-line
                if j >= 0 and line.find("#}", j) == -1:
                    in_comment = True
                    start_line = i
            elif "#}" in line:
                violations.append(f"{path.relative_to(project_root)}:{start_line}-{i}")
                in_comment = False

    if violations:
        msg = (
            "Multi-line {# ... #} comment(s) found. Django parses these "
            "as literal HTML, so the developer note ends up rendered to "
            "the user. Use {% comment %} ... {% endcomment %} instead. "
            "Locations:\n  " + "\n  ".join(violations)
        )
        raise AssertionError(msg)
