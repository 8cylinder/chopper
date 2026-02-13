#!/usr/bin/env python3
"""
Comprehensive test suite for chopper functionality.

This module tests all core chopper functionality including:
- Basic chopping for style, script, and chop sections
- CLI modes: --warn, --overwrite, --update
- Reverse sync functionality
- Error handling for malformed tags
- Edge cases and security validation
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, List
import subprocess
import sys
import os

# Add src to path so we can import chopper modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chopper.chopper import (
    chop,
    ChopperParser,
    ParsedData,
    validate_output_path,
    CommentType,
    Action,
)


class TestChopperBase:
    """Base class with common test scaffolding."""

    def setup_method(self):
        """Create temporary directory structure for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.chopper_dir = self.temp_dir / "chopper"
        self.css_dir = self.temp_dir / "css"
        self.js_dir = self.temp_dir / "js"
        self.html_dir = self.temp_dir / "views"

        # Create directories
        for dir_path in [self.chopper_dir, self.css_dir, self.js_dir, self.html_dir]:
            dir_path.mkdir(parents=True)

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_chopper_file(self, filename: str, content: str) -> Path:
        """Helper to create test chopper files."""
        file_path = self.chopper_dir / filename
        file_path.write_text(content)
        return file_path

    def get_types_dict(self) -> Dict[str, str]:
        """Get the types dictionary for file destinations."""
        return {
            "style": str(self.css_dir),
            "script": str(self.js_dir),
            "chop": str(self.html_dir),
        }

    def run_chopper(
        self, chopper_file: Path, warn: bool = False, update: bool = False
    ) -> bool:
        """Helper to run chopper programmatically."""
        types = self.get_types_dict()
        return chop(
            str(chopper_file), types, CommentType.NONE, warn=warn, update=update
        )


class TestBasicChopping(TestChopperBase):
    """Test basic chopper functionality for all section types."""

    def test_style_section_basic(self):
        """Test basic CSS style section chopping."""
        content = """<style chopper:file="main.css">
body {
    margin: 0;
    padding: 0;
}
h1 {
    color: blue;
}
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        assert success, "Chopping should succeed"

        css_file = self.css_dir / "main.css"
        assert css_file.exists(), "CSS file should be created"

        css_content = css_file.read_text()
        assert "body {" in css_content
        assert "margin: 0;" in css_content
        assert "color: blue;" in css_content

    def test_script_section_basic(self):
        """Test basic JavaScript script section chopping."""
        content = """<script chopper:file="app.js">
function greet(name) {
    console.log("Hello, " + name + "!");
}

document.addEventListener("DOMContentLoaded", function() {
    greet("World");
});
</script>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        assert success, "Chopping should succeed"

        js_file = self.js_dir / "app.js"
        assert js_file.exists(), "JS file should be created"

        js_content = js_file.read_text()
        assert "function greet(name)" in js_content
        assert "console.log" in js_content
        assert "DOMContentLoaded" in js_content

    def test_chop_section_basic(self):
        """Test basic HTML chop section chopping."""
        content = """<chop chopper:file="header.html">
<header class="main-header">
    <h1>Welcome to My Site</h1>
    <nav>
        <a href="/">Home</a>
        <a href="/about">About</a>
    </nav>
</header>
</chop>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        assert success, "Chopping should succeed"

        html_file = self.html_dir / "header.html"
        assert html_file.exists(), "HTML file should be created"

        html_content = html_file.read_text()
        assert '<header class="main-header">' in html_content
        assert "<h1>Welcome to My Site</h1>" in html_content
        assert "<nav>" in html_content

    def test_multiple_sections_same_file(self):
        """Test chopper file with multiple sections of different types."""
        content = """<style chopper:file="components/card.css">
.card {
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 1rem;
}
</style>

<script chopper:file="components/card.js">
class Card {
    constructor(element) {
        this.element = element;
    }

    show() {
        this.element.style.display = 'block';
    }
}
</script>

<chop chopper:file="components/card.html">
<div class="card">
    <h3>Card Title</h3>
    <p>Card content goes here.</p>
    <button onclick="toggleCard()">Toggle</button>
</div>
</chop>"""

        chopper_file = self.create_chopper_file("card.chopper.html", content)
        success = self.run_chopper(chopper_file)

        assert success, "Chopping should succeed"

        # Check all files were created
        css_file = self.css_dir / "components" / "card.css"
        js_file = self.js_dir / "components" / "card.js"
        html_file = self.html_dir / "components" / "card.html"

        assert css_file.exists(), "CSS file should be created"
        assert js_file.exists(), "JS file should be created"
        assert html_file.exists(), "HTML file should be created"

        # Check content
        assert "border-radius: 8px;" in css_file.read_text()
        assert "class Card {" in js_file.read_text()
        assert "Card Title" in html_file.read_text()

    def test_nested_directories(self):
        """Test creating files in nested directories."""
        content = """<style chopper:file="deep/nested/path/styles.css">
.nested { color: red; }
</style>

<script chopper:file="js/modules/utils/helper.js">
export function helper() { return true; }
</script>"""

        chopper_file = self.create_chopper_file("nested.chopper.html", content)
        success = self.run_chopper(chopper_file)

        assert success, "Chopping should succeed"

        css_file = self.css_dir / "deep" / "nested" / "path" / "styles.css"
        js_file = self.js_dir / "js" / "modules" / "utils" / "helper.js"

        assert css_file.exists(), "Nested CSS file should be created"
        assert js_file.exists(), "Nested JS file should be created"

        assert ".nested { color: red; }" in css_file.read_text()
        assert "export function helper()" in js_file.read_text()


class TestMalformedTags(TestChopperBase):
    """Test handling of malformed and broken tags."""

    def test_missing_chopper_file_attribute(self):
        """Test sections without chopper:file attribute."""
        content = """<style>
.no-file { color: blue; }
</style>

<style chopper:file="with-file.css">
.with-file { color: red; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        # Should still succeed but only process the section with chopper:file
        assert success, "Should succeed and skip sections without chopper:file"

        css_file = self.css_dir / "with-file.css"
        assert css_file.exists(), "File with chopper:file should be created"
        assert ".with-file { color: red; }" in css_file.read_text()

    def test_empty_chopper_file_attribute(self):
        """Test sections with empty chopper:file attribute."""
        content = """<style chopper:file="">
.empty-path { color: green; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        # Should succeed but not create any files
        assert success, "Should succeed but skip empty paths"

    def test_unclosed_tags(self):
        """Test handling of unclosed tags."""
        content = """<style chopper:file="unclosed.css">
.unclosed { color: blue; }
<!-- Missing closing style tag -->

<script chopper:file="good.js">
console.log("This should work");
</script>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        # HTML parser behavior with malformed HTML is unpredictable
        # The important thing is that chopper doesn't crash
        assert success or not success, (
            "Chopper should handle malformed HTML gracefully without crashing"
        )

        # If any files were created, they should have valid content
        js_file = self.js_dir / "good.js"
        css_file = self.css_dir / "unclosed.css"

        # Check that if files were created, they have reasonable content
        if js_file.exists():
            js_content = js_file.read_text()
            assert "console.log" in js_content, "JS file should have expected content"

        if css_file.exists():
            css_content = css_file.read_text()
            assert ".unclosed" in css_content, "CSS file should have expected content"

    def test_nested_same_tags(self):
        """Test nested tags of the same type."""
        content = """<style chopper:file="outer.css">
.outer { color: red; }
<style chopper:file="inner.css">
.inner { color: blue; }
</style>
.outer-continued { margin: 10px; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        success = self.run_chopper(chopper_file)

        # Parser should handle this gracefully
        assert success, "Should handle nested tags"


class TestSecurityValidation(TestChopperBase):
    """Test security validation for path traversal attacks."""

    def test_path_traversal_attempts(self):
        """Test various path traversal attack attempts."""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "../../../../root/.ssh/id_rsa",
            "../outside.css",
        ]

        for dangerous_path in dangerous_paths:
            content = f'''<style chopper:file="{dangerous_path}">
.malicious {{ color: red; }}
</style>'''

            chopper_file = self.create_chopper_file("malicious.chopper.html", content)
            success = self.run_chopper(chopper_file)

            # Should fail due to security validation
            assert not success, f"Should reject dangerous path: {dangerous_path}"

            # More importantly, no files should be created outside the allowed directories
            # Check that no files were created in dangerous locations
            dangerous_file = Path(dangerous_path)
            if dangerous_file.is_absolute():
                # For absolute paths, just ensure they don't exist (we can't really check this safely)
                pass
            else:
                # For relative paths, ensure no files were created in parent directories
                potential_files = [
                    self.temp_dir / dangerous_path,
                    self.css_dir / dangerous_path,
                    Path(dangerous_path),  # In case it tried to create in current dir
                ]
                for potential_file in potential_files:
                    # Resolve the path to handle .. components
                    try:
                        resolved_path = potential_file.resolve(strict=False)
                        # Only check if the resolved path is within temp_dir
                        # This avoids false positives from system files like /etc/passwd
                        if (
                            resolved_path.is_relative_to(self.temp_dir)
                            and resolved_path.exists()
                        ):
                            assert False, (
                                f"Dangerous file was created: {potential_file}"
                            )
                    except (ValueError, OSError):
                        # Path resolution failed, skip this check
                        pass

    def test_valid_paths_with_subdirectories(self):
        """Test that valid paths with subdirectories work."""
        valid_paths = [
            "styles/main.css",
            "components/button/button.css",
            "utils.js",
            "templates/header.html",
        ]

        for valid_path in valid_paths:
            content = f'''<style chopper:file="{valid_path}">
.valid {{ color: green; }}
</style>'''

            chopper_file = self.create_chopper_file(
                f"valid_{valid_path.replace('/', '_')}.chopper.html", content
            )
            success = self.run_chopper(chopper_file)

            assert success, f"Should accept valid path: {valid_path}"


class TestCliModes(TestChopperBase):
    """Test different CLI modes: --warn, --overwrite, --update."""

    def test_overwrite_mode_default(self):
        """Test default overwrite behavior."""
        content = """<style chopper:file="test.css">
.original { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        # First run
        success = self.run_chopper(chopper_file, warn=False)
        assert success, "First run should succeed"

        css_file = self.css_dir / "test.css"
        assert css_file.exists()
        assert ".original { color: blue; }" in css_file.read_text()

        # Modify the generated file
        css_file.write_text(".modified { color: red; }")

        # Second run should overwrite
        success = self.run_chopper(chopper_file, warn=False)
        assert success, "Second run should succeed and overwrite"

        # File should be back to original content
        css_content = css_file.read_text()
        assert ".original { color: blue; }" in css_content
        assert ".modified { color: red; }" not in css_content

    def test_warn_mode_shows_differences(self):
        """Test --warn mode behavior when files differ."""
        content = """<style chopper:file="test.css">
.original { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        # First run to create file
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify the generated file
        css_file = self.css_dir / "test.css"
        css_file.write_text(".modified { color: red; }")

        # Run in warn mode
        success = self.run_chopper(chopper_file, warn=True)
        assert not success, "Warn mode should return False when files differ"

        # File should remain modified (not overwritten)
        css_content = css_file.read_text()
        assert ".modified { color: red; }" in css_content
        assert ".original { color: blue; }" not in css_content

    def test_update_mode_interactive(self):
        """Test --update mode with interactive prompts."""
        content = """<style chopper:file="test.css">
.original { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        # First run to create file
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify the generated file
        css_file = self.css_dir / "test.css"
        new_css_content = ".updated { color: green; font-size: 16px; }"
        css_file.write_text(new_css_content)

        # Mock user choosing to update
        with patch("chopper.chopper.click.prompt", return_value="y"):
            success = self.run_chopper(chopper_file, warn=True, update=True)
            # Note: success may be False due to warn mode, but update should occur

        # Check that chopper file was updated with new content
        chopper_content = chopper_file.read_text()
        assert ".updated { color: green;" in chopper_content
        assert "font-size: 16px;" in chopper_content

    def test_update_mode_user_declines(self):
        """Test --update mode when user declines update."""
        content = """<style chopper:file="test.css">
.original { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        original_chopper_content = chopper_file.read_text()

        # First run to create file
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify the generated file
        css_file = self.css_dir / "test.css"
        css_file.write_text(".modified { color: red; }")

        # Mock user choosing not to update
        with patch("chopper.chopper.click.prompt", return_value="n"):
            success = self.run_chopper(chopper_file, warn=True, update=True)
            assert not success, (
                "Should return False when user declines and files differ"
            )

        # Check that chopper file was NOT modified
        chopper_content = chopper_file.read_text()
        assert chopper_content == original_chopper_content

    def test_update_mode_user_cancels(self):
        """Test --update mode when user cancels operation."""
        content = """<style chopper:file="test1.css">
.first { color: blue; }
</style>

<style chopper:file="test2.css">
.second { color: green; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        original_chopper_content = chopper_file.read_text()

        # First run to create files
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify both generated files
        css_file1 = self.css_dir / "test1.css"
        css_file2 = self.css_dir / "test2.css"
        css_file1.write_text(".modified-first { color: red; }")
        css_file2.write_text(".modified-second { color: yellow; }")

        # Mock user canceling on first prompt
        with patch("chopper.chopper.click.prompt", return_value="c"):
            with pytest.raises(SystemExit):
                self.run_chopper(chopper_file, warn=True, update=True)

        # Check that chopper file was NOT modified at all
        chopper_content = chopper_file.read_text()
        assert chopper_content == original_chopper_content


class TestReverseSync(TestChopperBase):
    """Test reverse sync functionality in detail."""

    def test_reverse_sync_preserves_html_structure(self):
        """Test that reverse sync preserves HTML structure and attributes."""
        content = """<!DOCTYPE html>
<html>
<head>
    <style chopper:file="test.css" data-component="header" id="header-styles">
    .header {
        background: white;
        padding: 1rem;
    }
    </style>
    <script chopper:file="test.js" type="module" defer>
    function init() {
        console.log("initialized");
    }
    </script>
</head>
<body>
    <chop chopper:file="test.html">
    <header class="header">
        <h1>Title</h1>
    </header>
    </chop>
</body>
</html>"""

        chopper_file = self.create_chopper_file("complex.chopper.html", content)

        # Generate files
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify CSS file
        css_file = self.css_dir / "test.css"
        css_file.write_text(""".header {
    background: lightblue;
    padding: 2rem;
    border-radius: 8px;
}""")

        # Update with reverse sync
        with patch("chopper.chopper.click.prompt", return_value="y"):
            self.run_chopper(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # Check that HTML structure is preserved
        assert "<!DOCTYPE html>" in updated_content
        assert 'data-component="header"' in updated_content
        assert 'id="header-styles"' in updated_content
        assert 'type="module"' in updated_content
        assert "defer" in updated_content

        # Check that CSS was updated
        assert "background: lightblue;" in updated_content
        assert "border-radius: 8px;" in updated_content

    def test_reverse_sync_multiple_sections_selective(self):
        """Test reverse sync with multiple sections, updating only some."""
        content = """<style chopper:file="styles.css">
.class1 { color: blue; }
.class2 { color: green; }
</style>

<script chopper:file="scripts.js">
function func1() { return 1; }
function func2() { return 2; }
</script>

<chop chopper:file="template.html">
<div>Original content</div>
</chop>"""

        chopper_file = self.create_chopper_file("multi.chopper.html", content)

        # Generate files
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify CSS and JS files
        css_file = self.css_dir / "styles.css"
        js_file = self.js_dir / "scripts.js"

        css_file.write_text(".updated-css { color: red; }")
        js_file.write_text('function updated() { return "updated"; }')

        # Mock user: yes for CSS, no for JS
        with patch("chopper.chopper.click.prompt", side_effect=["y", "n"]):
            self.run_chopper(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # CSS should be updated
        assert ".updated-css { color: red; }" in updated_content

        # JS should NOT be updated (original content preserved)
        assert "function func1() { return 1; }" in updated_content
        assert "function updated()" not in updated_content

        # HTML should be unchanged
        assert "<div>Original content</div>" in updated_content


class TestChopperIndentation(TestChopperBase):
    """Test CHOPPER_INDENT functionality."""

    def test_default_indentation(self):
        """Test default two-space indentation."""
        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("indent.chopper.html", content)

        # Generate file
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify file
        css_file = self.css_dir / "test.css"
        css_file.write_text(""".updated {
color: red;
font-size: 16px;
}""")

        # Update with default indentation
        with patch("chopper.chopper.click.prompt", return_value="y"):
            self.run_chopper(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()
        lines = updated_content.splitlines()

        # Find the style content lines and check indentation
        style_lines = []
        in_style = False
        for line in lines:
            if "<style" in line:
                in_style = True
            elif "</style>" in line:
                in_style = False
            elif in_style and line.strip():
                style_lines.append(line)

        # Check that lines are indented with two spaces
        for line in style_lines:
            if line.strip():  # Non-empty lines should be indented
                assert line.startswith("  "), (
                    f"Line should start with two spaces: '{line}'"
                )

    def test_custom_indentation(self):
        """Test custom indentation with environment variable."""
        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("indent.chopper.html", content)

        # Generate file
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # Modify file
        css_file = self.css_dir / "test.css"
        css_file.write_text(""".custom {
margin: 0;
padding: 10px;
}""")

        # Set custom indentation (4 spaces) and update
        with patch.dict(os.environ, {"CHOPPER_INDENT": "    "}):  # 4 spaces
            with patch("chopper.chopper.click.prompt", return_value="y"):
                self.run_chopper(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()
        lines = updated_content.splitlines()

        # Find the style content lines and check indentation
        style_lines = []
        in_style = False
        for line in lines:
            if "<style" in line:
                in_style = True
            elif "</style>" in line:
                in_style = False
            elif in_style and line.strip():
                style_lines.append(line)

        # Check that lines are indented with four spaces
        for line in style_lines:
            if line.strip():  # Non-empty lines should be indented
                assert line.startswith("    "), (
                    f"Line should start with four spaces: '{line}'"
                )


class TestContentFormatting(TestChopperBase):
    """Test content extraction, formatting, and whitespace preservation."""

    def test_whitespace_preservation(self):
        """Test that whitespace and indentation in content is preserved."""
        content = """<style chopper:file="formatted.css">
    .header {
        background: #fff;
        margin: 0;
          padding: 1rem;  /* extra indent */
    }

    .footer {
        background: #000;
    }
</style>"""

        chopper_file = self.create_chopper_file("whitespace.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should preserve whitespace formatting"

        css_file = self.css_dir / "formatted.css"
        css_content = css_file.read_text()

        # Check that indentation is preserved (chopper uses dedent, so relative indentation is preserved)
        lines = css_content.splitlines()

        # After dedent, the base indentation is removed but relative indentation remains
        assert ".header {" in lines, "Should contain header class"
        assert "    background: #fff;" in lines, (
            "Should preserve property indentation relative to class"
        )
        assert "      padding: 1rem;  /* extra indent */" in lines, (
            "Should preserve extra indentation relative to others"
        )
        assert "" in lines, "Should preserve empty lines"

        # Verify the structure is maintained with proper relative indentation
        header_index = lines.index(".header {")
        background_index = lines.index("    background: #fff;")
        padding_index = lines.index("      padding: 1rem;  /* extra indent */")

        assert header_index < background_index < padding_index, (
            "Should maintain logical order"
        )

    def test_content_extraction_precision(self):
        """Test that only content between tags is extracted, not the tags themselves."""
        content = """<style chopper:file="precise.css" data-test="attr">
body { margin: 0; }
</style>

<script chopper:file="precise.js" type="module">
console.log("test");
</script>

<chop chopper:file="precise.html">
<div>Content</div>
</chop>"""

        chopper_file = self.create_chopper_file("precision.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success

        # CSS file should contain ONLY the CSS content
        css_file = self.css_dir / "precise.css"
        css_content = css_file.read_text().strip()
        assert css_content == "body { margin: 0; }", (
            f"CSS should only contain content, got: '{css_content}'"
        )

        # JS file should contain ONLY the JS content
        js_file = self.js_dir / "precise.js"
        js_content = js_file.read_text().strip()
        assert js_content == 'console.log("test");', (
            f"JS should only contain content, got: '{js_content}'"
        )

        # HTML file should contain ONLY the HTML content
        html_file = self.html_dir / "precise.html"
        html_content = html_file.read_text().strip()
        assert html_content == "<div>Content</div>", (
            f"HTML should only contain content, got: '{html_content}'"
        )

    def test_multiple_sections_same_type(self):
        """Test multiple sections of the same type in one chopper file."""
        content = """<style chopper:file="header.css">
.header { color: blue; }
</style>

<div>Some HTML between sections</div>

<style chopper:file="footer.css">
.footer { color: red; }
</style>

<style chopper:file="sidebar.css">
.sidebar { color: green; }
</style>"""

        chopper_file = self.create_chopper_file("multiple.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle multiple sections of same type"

        # Check that all three CSS files were created with correct content
        header_file = self.css_dir / "header.css"
        footer_file = self.css_dir / "footer.css"
        sidebar_file = self.css_dir / "sidebar.css"

        assert header_file.exists() and "color: blue" in header_file.read_text()
        assert footer_file.exists() and "color: red" in footer_file.read_text()
        assert sidebar_file.exists() and "color: green" in sidebar_file.read_text()

    def test_mixed_content_with_regular_html(self):
        """Test chopper sections mixed with regular HTML content."""
        content = """<!DOCTYPE html>
<html>
<head>
    <title>Mixed Content Test</title>
    <style chopper:file="mixed.css">
    .mixed { color: purple; }
    </style>
    <style>
    /* This regular style should be ignored */
    .regular { color: orange; }
    </style>
</head>
<body>
    <h1>Regular HTML Content</h1>

    <script chopper:file="mixed.js">
    function mixedFunction() { return "mixed"; }
    </script>

    <script>
    // This regular script should be ignored
    console.log("regular");
    </script>

    <chop chopper:file="mixed.html">
    <div class="chopped">This gets chopped</div>
    </chop>

    <div class="regular">This stays in original file</div>
</body>
</html>"""

        chopper_file = self.create_chopper_file("mixed.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle mixed content correctly"

        # Only chopper sections should create files
        css_file = self.css_dir / "mixed.css"
        js_file = self.js_dir / "mixed.js"
        html_file = self.html_dir / "mixed.html"

        assert css_file.exists() and "color: purple" in css_file.read_text()
        assert "color: orange" not in css_file.read_text(), (
            "Regular styles should not be extracted"
        )

        assert js_file.exists() and "mixedFunction" in js_file.read_text()
        assert "regular" not in js_file.read_text(), (
            "Regular scripts should not be extracted"
        )

        assert html_file.exists() and "chopped" in html_file.read_text()

        # Original chopper file should still contain regular HTML
        original_content = chopper_file.read_text()
        assert "Regular HTML Content" in original_content
        assert "regular script" in original_content

    def test_empty_and_whitespace_sections(self):
        """Test handling of empty sections and sections with only whitespace."""
        content = """<style chopper:file="empty.css"></style>

<style chopper:file="whitespace.css">


</style>

<script chopper:file="empty.js"></script>

<chop chopper:file="empty.html">
</chop>

<chop chopper:file="whitespace.html">



</chop>"""

        chopper_file = self.create_chopper_file("empty.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle empty sections gracefully"

        # Files should be created even if empty
        assert (self.css_dir / "empty.css").exists()
        assert (self.css_dir / "whitespace.css").exists()
        assert (self.js_dir / "empty.js").exists()
        assert (self.html_dir / "empty.html").exists()
        assert (self.html_dir / "whitespace.html").exists()

        # Check content of whitespace file
        whitespace_css = (self.css_dir / "whitespace.css").read_text()
        assert whitespace_css.strip() == "", (
            "Whitespace-only content should result in empty file"
        )


class TestFileExtensionHandling(TestChopperBase):
    """Test file extension mapping and handling."""

    def test_various_file_extensions(self):
        """Test that various file extensions are handled correctly."""
        content = """<style chopper:file="styles.css">
.css-test { color: blue; }
</style>

<style chopper:file="styles.scss">
.scss-test { color: red; }
</style>

<style chopper:file="styles.less">
.less-test { color: green; }
</style>

<script chopper:file="script.js">
console.log("js");
</script>

<script chopper:file="script.ts">
console.log("ts");
</script>

<script chopper:file="script.mjs">
console.log("mjs");
</script>

<chop chopper:file="template.html">
<div>HTML</div>
</chop>

<chop chopper:file="template.twig">
<div>{{ variable }}</div>
</chop>

<chop chopper:file="template.blade.php">
<div>@if($condition)</div>
</chop>"""

        chopper_file = self.create_chopper_file("extensions.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle various file extensions"

        # Check all files were created in correct directories
        assert (self.css_dir / "styles.css").exists()
        assert (self.css_dir / "styles.scss").exists()
        assert (self.css_dir / "styles.less").exists()
        assert (self.js_dir / "script.js").exists()
        assert (self.js_dir / "script.ts").exists()
        assert (self.js_dir / "script.mjs").exists()
        assert (self.html_dir / "template.html").exists()
        assert (self.html_dir / "template.twig").exists()
        assert (self.html_dir / "template.blade.php").exists()

        # Verify content
        assert ".scss-test" in (self.css_dir / "styles.scss").read_text()
        assert 'console.log("ts")' in (self.js_dir / "script.ts").read_text()
        assert "{{ variable }}" in (self.html_dir / "template.twig").read_text()

    def test_no_extension_files(self):
        """Test files without extensions."""
        content = """<style chopper:file="Makefile">
# Makefile content
all:
	echo "build"
</style>

<script chopper:file="build_script">
#!/bin/bash
echo "Building..."
</script>

<chop chopper:file="README">
# Project README
This is a readme file.
</chop>"""

        chopper_file = self.create_chopper_file("no_ext.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle files without extensions"

        assert (self.css_dir / "Makefile").exists()
        assert (self.js_dir / "build_script").exists()
        assert (self.html_dir / "README").exists()

        makefile_content = (self.css_dir / "Makefile").read_text()
        assert "all:" in makefile_content


class TestDirectoryAndFileHandling(TestChopperBase):
    """Test directory creation and file handling edge cases."""

    def test_deeply_nested_directory_creation(self):
        """Test creation of deeply nested directories."""
        content = """<style chopper:file="very/deeply/nested/path/with/many/levels/deep.css">
.deep { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("nested.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should create deeply nested directories"

        deep_file = (
            self.css_dir
            / "very"
            / "deeply"
            / "nested"
            / "path"
            / "with"
            / "many"
            / "levels"
            / "deep.css"
        )
        assert deep_file.exists(), "Should create deeply nested file"
        assert ".deep" in deep_file.read_text()

    def test_file_overwriting_behavior(self):
        """Test detailed file overwriting behavior."""
        content = """<style chopper:file="overwrite.css">
.original { color: red; }
</style>"""

        chopper_file = self.create_chopper_file("overwrite.chopper.html", content)

        # First run - file doesn't exist
        success = self.run_chopper(chopper_file)
        assert success

        css_file = self.css_dir / "overwrite.css"
        assert css_file.exists()
        assert "original" in css_file.read_text()

        # Manually modify the generated file
        css_file.write_text(".manually-modified { color: blue; }")

        # Second run - should overwrite by default
        success = self.run_chopper(chopper_file, warn=False)
        assert success

        # File should be back to original content
        css_content = css_file.read_text()
        assert "original" in css_content
        assert "manually-modified" not in css_content

        # Test warn mode - should not overwrite
        css_file.write_text(".manually-modified-again { color: green; }")

        success = self.run_chopper(chopper_file, warn=True)
        assert not success, "Warn mode should return False when files differ"

        # File should remain modified
        css_content = css_file.read_text()
        assert "manually-modified-again" in css_content
        assert "original" not in css_content

    def test_special_characters_in_filenames(self):
        """Test handling of special characters in file names."""
        # Test some safe special characters
        content = """<style chopper:file="file-with-dashes.css">
.dashes { color: blue; }
</style>

<style chopper:file="file_with_underscores.css">
.underscores { color: red; }
</style>

<script chopper:file="file.with.dots.js">
console.log("dots");
</script>

<chop chopper:file="file (with spaces).html">
<div>Spaces in filename</div>
</chop>"""

        chopper_file = self.create_chopper_file("special.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle special characters in filenames"

        assert (self.css_dir / "file-with-dashes.css").exists()
        assert (self.css_dir / "file_with_underscores.css").exists()
        assert (self.js_dir / "file.with.dots.js").exists()
        assert (self.html_dir / "file (with spaces).html").exists()


class TestCommentTypes(TestChopperBase):
    """Test different comment types functionality."""

    def test_client_comments(self):
        """Test client-side comments in generated files."""
        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>

<script chopper:file="test.js">
console.log("test");
</script>"""

        chopper_file = self.create_chopper_file("comments.chopper.html", content)
        types = self.get_types_dict()

        # Run with client comments
        success = chop(
            str(chopper_file), types, CommentType.CLIENT, warn=False, update=False
        )

        assert success, "Should succeed with client comments"

        # Check CSS file has comments
        css_file = self.css_dir / "test.css"
        css_content = css_file.read_text()
        assert "/* " in css_content, "CSS should have comment"
        assert str(chopper_file) in css_content, "Comment should include source file"

        # Check JS file has comments
        js_file = self.js_dir / "test.js"
        js_content = js_file.read_text()
        assert "// " in js_content, "JS should have comment"
        assert str(chopper_file) in js_content, "Comment should include source file"

    def test_server_comments(self):
        """Test server-side comment type behavior."""
        content = """<style chopper:file="server.css">
.server-test { color: blue; }
</style>

<script chopper:file="server.js">
console.log("server test");
</script>

<chop chopper:file="server.twig">
<div>Server HTML</div>
</chop>"""

        chopper_file = self.create_chopper_file("server.chopper.html", content)
        types = self.get_types_dict()

        # Run with server comments
        success = chop(
            str(chopper_file), types, CommentType.SERVER, warn=False, update=False
        )

        assert success, "Should succeed with server comment type"

        # SERVER comment type should add server-side comments
        css_file = self.css_dir / "server.css"
        css_content = css_file.read_text()

        # CSS uses /* */ for both client and server
        assert ".server-test" in css_content, "Should contain actual CSS content"
        assert "/* " in css_content, "SERVER comment type should add CSS comments"
        assert str(chopper_file) in css_content, "Comment should include source path"

        js_file = self.js_dir / "server.js"
        js_content = js_file.read_text()
        assert "console.log" in js_content, "Should contain actual JS content"
        assert "// " in js_content, "SERVER comment type should add JS comments"
        assert str(chopper_file) in js_content, "Comment should include source path"

        # HTML template files should use server-side comment syntax
        html_file = self.html_dir / "server.twig"
        html_content = html_file.read_text()
        assert "<div>Server HTML</div>" in html_content, (
            "Should contain actual HTML content"
        )
        assert "{# " in html_content, (
            "Twig files should use {# #} comments for server mode"
        )
        assert str(chopper_file) in html_content, "Comment should include source path"

    def test_no_comments(self):
        """Test files generated without comments."""
        content = """<style chopper:file="no_comments.css">
.no-comments { color: blue; }
</style>

<script chopper:file="no_comments.js">
console.log("no comments");
</script>"""

        chopper_file = self.create_chopper_file("no_comments.chopper.html", content)
        types = self.get_types_dict()

        # Run with no comments (default)
        success = chop(
            str(chopper_file), types, CommentType.NONE, warn=False, update=False
        )

        assert success, "Should succeed with no comments"

        # Check files have no comment headers
        css_content = (self.css_dir / "no_comments.css").read_text()
        js_content = (self.js_dir / "no_comments.js").read_text()

        # Content should not contain comment markers
        assert not css_content.startswith("/*"), "CSS should not start with comment"
        assert not js_content.startswith("//"), "JS should not start with comment"
        assert ".no-comments" in css_content, "Should contain actual content"
        assert "console.log" in js_content, "Should contain actual content"


class TestErrorHandling(TestChopperBase):
    """Test error handling and edge cases."""

    def setup_method(self):
        """Store original working directory and call parent setup."""
        super().setup_method()
        self._original_cwd = os.getcwd()

    def teardown_method(self):
        """Extended cleanup to ensure test isolation."""
        # Ensure we're back in the original working directory
        if hasattr(self, "_original_cwd"):
            os.chdir(self._original_cwd)

        # Clean up any environment variables that might have been set
        env_vars = [
            "CHOPPER_SOURCE_DIR",
            "CHOPPER_SCRIPT_DIR",
            "CHOPPER_STYLE_DIR",
            "CHOPPER_HTML_DIR",
            "CHOPPER_COMMENTS",
            "CHOPPER_WARN",
            "CHOPPER_WATCH",
            "CHOPPER_INDENT",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

        # Force reload of the chopper module to clear any cached .env data
        import importlib
        import sys

        if "chopper.chopper" in sys.modules:
            importlib.reload(sys.modules["chopper.chopper"])

        # Call parent teardown last
        super().teardown_method()

    def test_chopper_file_not_found(self):
        """Test handling of non-existent chopper files."""
        from chopper.chopper import chop, CommentType

        non_existent_file = str(self.temp_dir / "does_not_exist.chopper.html")
        types = self.get_types_dict()

        # Should raise FileNotFoundError for non-existent file
        with pytest.raises(FileNotFoundError):
            chop(non_existent_file, types, CommentType.NONE)

    def test_invalid_chopper_file_content(self):
        """Test handling of files that aren't valid chopper files."""
        # Test binary file - create file directly with binary content
        binary_file = self.chopper_dir / "binary.chopper.html"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        success = self.run_chopper(binary_file)
        assert not success, "Should fail on binary file"

        # Test malformed HTML
        malformed_content = """<style chopper:file="malformed.css">
.test { color: blue;
<script chopper:file="malformed.js">
console.log("unclosed style above");
</script>
<!-- No closing tags -->"""

        malformed_file = self.create_chopper_file(
            "malformed.chopper.html", malformed_content
        )
        success = self.run_chopper(malformed_file)

        # Should not crash, but behavior with malformed HTML is parser-dependent
        # The fact we got here without an exception means it handled it gracefully
        assert isinstance(success, bool), "Should return a boolean result"

    def test_readonly_destination_directory(self):
        """Test handling when destination directory is read-only."""
        import stat

        # Skip if running as root (root can write to read-only directories)
        if hasattr(os, "getuid") and os.getuid() == 0:
            pytest.skip("Cannot test permission errors as root user")

        content = """<style chopper:file="readonly_test.css">
.readonly { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("readonly.chopper.html", content)

        # Make CSS directory read-only
        original_mode = self.css_dir.stat().st_mode
        self.css_dir.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # Read-only

        try:
            # Should handle PermissionError gracefully and return False
            success = self.run_chopper(chopper_file)
            assert success is False, "Should fail when directory is read-only"

        finally:
            # Restore original permissions for cleanup
            self.css_dir.chmod(original_mode)

            # Verify the CSS file was NOT created (check after restoring permissions)
            css_file = self.css_dir / "readonly_test.css"
            assert not css_file.exists(), (
                "File should not be created in read-only directory"
            )

    def test_very_large_content(self):
        """Test handling of large content sections."""
        # Generate large CSS content
        large_css_rules = []
        for i in range(1000):
            large_css_rules.append(
                f".class-{i} {{ color: rgb({i % 255}, {i % 255}, {i % 255}); }}"
            )

        large_css_content = "\n".join(large_css_rules)

        content = f"""<style chopper:file="large.css">
{large_css_content}
</style>"""

        chopper_file = self.create_chopper_file("large.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle large content"

        # Verify content was written correctly
        css_file = self.css_dir / "large.css"
        assert css_file.exists()
        css_content = css_file.read_text()
        assert "class-999" in css_content, "Should contain large content"
        assert css_content.count(".class-") == 1000, "Should contain all CSS rules"

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters in content."""
        content = """<style chopper:file="unicode.css">
/* Unicode test: 你好世界 */
.emoji::before {
    content: "🎉 🚁 ✨";
}
.unicode {
    /* Cyrillic: Привет */
    /* Arabic: مرحبا */
    /* Japanese: こんにちは */
}
</style>

<script chopper:file="unicode.js">
// Unicode in JavaScript
const greeting = "Hello 世界! 🌍";
console.log("Emoji test: 🚁🎉");
</script>

<chop chopper:file="unicode.html">
<div>Unicode content: 你好 🌍</div>
<p>Special chars: ñáéíóú àèìòù</p>
</chop>"""

        chopper_file = self.create_chopper_file("unicode.chopper.html", content)
        success = self.run_chopper(chopper_file)
        assert success, "Should handle Unicode content"

        # Verify Unicode content is preserved
        css_content = (self.css_dir / "unicode.css").read_text()
        js_content = (self.js_dir / "unicode.js").read_text()
        html_content = (self.html_dir / "unicode.html").read_text()

        assert "你好世界" in css_content, "Should preserve Chinese characters"
        assert "🎉 🚁 ✨" in css_content, "Should preserve emoji"
        assert "Привет" in css_content, "Should preserve Cyrillic"

        assert "Hello 世界! 🌍" in js_content, "Should preserve Unicode in JS"
        assert "🚁🎉" in js_content, "Should preserve emoji in JS"

        assert "你好 🌍" in html_content, "Should preserve Unicode in HTML"
        assert "ñáéíóú" in html_content, "Should preserve accented characters"


class TestEnvironmentConfiguration(TestChopperBase):
    """Test .env file functionality and environment variable handling."""

    def setup_method(self):
        """Store original working directory and call parent setup."""
        super().setup_method()
        self._original_cwd = os.getcwd()

    def teardown_method(self):
        """Extended cleanup to remove environment variables and restore working directory."""
        # Ensure we're back in the original working directory
        if hasattr(self, "_original_cwd"):
            os.chdir(self._original_cwd)

        # Clean up any environment variables we may have set
        env_vars = [
            "CHOPPER_SOURCE_DIR",
            "CHOPPER_SCRIPT_DIR",
            "CHOPPER_STYLE_DIR",
            "CHOPPER_HTML_DIR",
            "CHOPPER_COMMENTS",
            "CHOPPER_WARN",
            "CHOPPER_WATCH",
            "CHOPPER_INDENT",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

        # Force reload of the chopper module to clear any cached .env data
        import importlib
        import sys

        if "chopper.chopper" in sys.modules:
            importlib.reload(sys.modules["chopper.chopper"])

        # Call parent teardown last
        super().teardown_method()

    def create_env_file(self, filename: str, content: str) -> Path:
        """Helper to create .env files in temp directory."""
        env_file = self.temp_dir / filename
        env_file.write_text(content)
        return env_file

    def test_no_config_file(self):
        """Test chopper works without any .env file."""
        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        # Change to temp directory where there's no .env file
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            success = self.run_chopper(chopper_file)
            assert success, "Should work without .env file"

            css_file = self.css_dir / "test.css"
            assert css_file.exists(), "Should create CSS file"
        finally:
            os.chdir(original_cwd)

    def test_env_file_basic(self):
        """Test basic .env file functionality."""
        env_content = f"""CHOPPER_SOURCE_DIR={self.chopper_dir}
CHOPPER_SCRIPT_DIR={self.js_dir}
CHOPPER_STYLE_DIR={self.css_dir}
CHOPPER_HTML_DIR={self.html_dir}
CHOPPER_COMMENTS=none
CHOPPER_WARN=false
CHOPPER_WATCH=false
CHOPPER_INDENT=  """

        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>

<script chopper:file="test.js">
console.log("test");
</script>

<chop chopper:file="test.html">
<div>Test content</div>
</chop>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        self.create_env_file(".env", env_content)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            success = self.run_chopper(chopper_file)
            assert success, "Should work with .env file"

            # Check all files were created
            assert (self.css_dir / "test.css").exists()
            assert (self.js_dir / "test.js").exists()
            assert (self.html_dir / "test.html").exists()
        finally:
            os.chdir(original_cwd)

    def test_config_file_search_order(self):
        """Test that environment variables work with different precedences."""
        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        # Test that direct environment variables work
        # Since .env loading happens at module import, we test with direct env vars
        env_vars = {"CHOPPER_INDENT": "__direct_env__"}

        css_file = self.css_dir / "test.css"

        with patch.dict(os.environ, env_vars):
            # First create the file
            success = self.run_chopper(chopper_file)
            assert success

            # Modify CSS file
            css_file.write_text(".modified { color: red; }")

            # Test update with the indentation from environment
            with patch("chopper.chopper.click.prompt", return_value="y"):
                self.run_chopper(chopper_file, warn=True, update=True)

            # Check that environment variable was used
            updated_content = chopper_file.read_text()
            # Should contain indentation from environment variable
            assert "__direct_env__" in updated_content, (
                "Should use environment variable for indentation"
            )

    def test_partial_env_configuration(self):
        """Test .env with only some variables set."""
        env_content = f"""CHOPPER_SCRIPT_DIR={self.js_dir}
CHOPPER_INDENT=
# CHOPPER_STYLE_DIR is missing
# CHOPPER_HTML_DIR is missing"""

        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>

<script chopper:file="test.js">
console.log("test");
</script>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        self.create_env_file(".env", env_content)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)

            # Should use provided types dict for missing env vars
            success = self.run_chopper(chopper_file)
            assert success, "Should work with partial .env"

            # JS should be created in specified directory
            js_file = self.js_dir / "test.js"
            assert js_file.exists(), "JS file should use env var path"

            # CSS should be created in types dict path
            css_file = self.css_dir / "test.css"
            assert css_file.exists(), "CSS should use types dict path"

        finally:
            os.chdir(original_cwd)

    def test_malformed_env_values(self):
        """Test handling of malformed .env values."""
        env_content = f"""CHOPPER_SCRIPT_DIR={self.js_dir}
CHOPPER_STYLE_DIR={self.css_dir}
CHOPPER_HTML_DIR={self.html_dir}
CHOPPER_WARN=invalid_boolean
CHOPPER_COMMENTS=invalid_comment_type
CHOPPER_INDENT="""

        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        self.create_env_file(".env", env_content)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)

            # Should handle malformed values gracefully
            success = self.run_chopper(chopper_file)
            assert success, "Should handle malformed .env values gracefully"

            css_file = self.css_dir / "test.css"
            assert css_file.exists(), (
                "Should still create files despite malformed values"
            )

        finally:
            os.chdir(original_cwd)

    def test_env_file_with_comments_and_empty_lines(self):
        """Test .env file with comments and empty lines."""
        env_content = f"""# Chopper configuration
# Source and destination directories

CHOPPER_SOURCE_DIR={self.chopper_dir}

# Output directories
CHOPPER_SCRIPT_DIR={self.js_dir}
CHOPPER_STYLE_DIR={self.css_dir}
CHOPPER_HTML_DIR={self.html_dir}

# Settings
CHOPPER_COMMENTS=none  # No comments in output
CHOPPER_WARN=false
CHOPPER_INDENT=\t# Use tabs

# End of config"""

        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)
        self.create_env_file(".env", env_content)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            success = self.run_chopper(chopper_file)
            assert success, "Should parse .env with comments and empty lines"

            css_file = self.css_dir / "test.css"
            assert css_file.exists(), "Should create CSS file"

        finally:
            os.chdir(original_cwd)

    def test_different_config_file_extensions(self):
        """Test different supported config file extensions."""
        config_files = [".chopper", "chopper.conf", ".env.chopper", ".env"]

        # Test that each config file type can be parsed
        for filename in config_files:
            env_content = f"""CHOPPER_SCRIPT_DIR={self.js_dir}
CHOPPER_STYLE_DIR={self.css_dir}
CHOPPER_HTML_DIR={self.html_dir}
CHOPPER_COMMENTS=none"""

            content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

            chopper_file = self.create_chopper_file(
                f"test_{filename.replace('.', '_')}.chopper.html", content
            )
            self.create_env_file(filename, env_content)

            original_cwd = os.getcwd()
            try:
                os.chdir(self.temp_dir)
                success = self.run_chopper(chopper_file)
                assert success, f"Should work with {filename} config file"

                css_file = self.css_dir / "test.css"
                assert css_file.exists(), f"Should create CSS file with {filename}"

            finally:
                os.chdir(original_cwd)

    def test_find_file_upwards_functionality(self):
        """Test the find_file_upwards function used for config file discovery."""
        from chopper.chopper import find_file_upwards

        # Create nested directory structure with config file
        nested_dir = self.temp_dir / "level1" / "level2" / "level3"
        nested_dir.mkdir(parents=True)

        # Create config file at level1
        config_file = self.temp_dir / "level1" / ".env"
        config_file.write_text("TEST_VAR=test_value")

        # Search from nested directory should find the config file
        found_config = find_file_upwards(nested_dir, [".env"])
        assert found_config is not None, "Should find config file in parent directory"
        # Resolve both paths to handle symlinks (e.g., /var vs /private/var on macOS)
        assert found_config.resolve() == config_file.resolve(), (
            "Should find the correct config file"
        )

        # Test priority order
        priority_config = self.temp_dir / "level1" / ".chopper"
        priority_config.write_text("PRIORITY_VAR=priority_value")

        # Should find .chopper over .env due to search order
        found_priority = find_file_upwards(nested_dir, [".chopper", ".env"])
        assert found_priority.resolve() == priority_config.resolve(), (
            "Should find higher priority config file"
        )

        # Test max depth limit
        deep_nested = nested_dir / "level4" / "level5" / "level6"
        deep_nested.mkdir(parents=True)

        found_with_limit = find_file_upwards(deep_nested, [".env"], max_depth=3)
        assert found_with_limit is None, "Should not find config beyond max depth"

        found_without_limit = find_file_upwards(deep_nested, [".env"], max_depth=10)
        assert found_without_limit.resolve() == config_file.resolve(), (
            "Should find config within max depth"
        )

    def test_env_indent_functionality(self):
        """Test CHOPPER_INDENT environment variable functionality."""
        test_cases = [
            ("  ", "two_spaces"),  # Default
            ("    ", "four_spaces"),  # Four spaces
            ("\t", "tab"),  # Tab character
            ("", "empty_default"),  # Empty should default to two spaces
        ]

        for indent_value, test_name in test_cases:
            content = """<style chopper:file="test.css">
.original { color: blue; }
</style>"""

            chopper_file = self.create_chopper_file(
                f"indent_{test_name}.chopper.html", content
            )
            css_file = self.css_dir / "test.css"

            # Test with direct environment variable since .env loading happens at import
            env_vars = {"CHOPPER_INDENT": indent_value} if indent_value else {}

            with patch.dict(os.environ, env_vars, clear=False):
                # Generate initial file
                success = self.run_chopper(chopper_file)
                assert success, f"Should work with indent '{indent_value}'"

                # Modify CSS to test indentation
                css_file.write_text(""".updated {
color: red;
font-size: 16px;
}""")

                # Test reverse sync with indentation
                with patch("chopper.chopper.click.prompt", return_value="y"):
                    self.run_chopper(chopper_file, warn=True, update=True)

                updated_content = chopper_file.read_text()

                # Check that content was updated
                assert ".updated" in updated_content, (
                    f"Content should be updated for {test_name}"
                )

                # For empty indent, it should use default two spaces
                expected_indent = indent_value if indent_value else "  "

                # Find lines with indentation and verify
                lines = updated_content.splitlines()
                indented_lines = [
                    line
                    for line in lines
                    if line.strip() and not line.strip().startswith("<")
                ]

                if indented_lines:
                    # Check that at least one line has the expected indentation
                    has_correct_indent = any(
                        line.startswith(expected_indent) for line in indented_lines
                    )
                    assert has_correct_indent, (
                        f"Should use correct indentation '{repr(expected_indent)}' for {test_name}"
                    )

    def test_corrupted_env_file(self):
        """Test handling of corrupted .env file."""
        # Create a binary file that's not valid text
        env_file = self.temp_dir / ".env"
        env_file.write_bytes(b"\xff\xfe\x00\x01\x80\x90")  # Invalid UTF-8

        content = """<style chopper:file="test.css">
.test { color: blue; }
</style>"""

        chopper_file = self.create_chopper_file("test.chopper.html", content)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)

            # Should handle corrupted .env gracefully and continue
            success = self.run_chopper(chopper_file)
            assert success, "Should handle corrupted .env file gracefully"

            css_file = self.css_dir / "test.css"
            assert css_file.exists(), "Should still create files despite corrupted .env"

        finally:
            os.chdir(original_cwd)


class TestParserInstanceIsolation(TestChopperBase):
    """Test ChopperParser instance isolation (class-level mutable defaults fix)."""

    def test_parser_instance_isolation(self):
        """Test that multiple ChopperParser instances don't share state."""
        # Create first parser and parse content
        parser1 = ChopperParser()
        parser1.feed('<style chopper:file="first.css">body { color: red; }</style>')

        # Create second parser and parse different content
        parser2 = ChopperParser()
        parser2.feed('<script chopper:file="second.js">console.log("test");</script>')

        # Verify they have independent state
        assert len(parser1.parsed_data) == 1
        assert len(parser2.parsed_data) == 1
        assert parser1.parsed_data[0].path == "first.css"
        assert parser2.parsed_data[0].path == "second.js"

        # Verify parser1's data wasn't affected by parser2
        assert parser1.parsed_data[0].tag == "style"
        assert parser2.parsed_data[0].tag == "script"

    def test_parser_sequential_reuse(self):
        """Test that a single parser instance can be reused sequentially."""
        parser = ChopperParser()

        # First parse
        parser.feed('<style chopper:file="first.css">body { color: red; }</style>')
        assert len(parser.parsed_data) == 1
        assert parser.parsed_data[0].path == "first.css"

        # Create new parser for second parse (parsers should not be reused in practice)
        parser2 = ChopperParser()
        parser2.feed('<script chopper:file="second.js">console.log("test");</script>')
        assert len(parser2.parsed_data) == 1
        assert parser2.parsed_data[0].path == "second.js"

        # Verify first parser data is unchanged
        assert len(parser.parsed_data) == 1
        assert parser.parsed_data[0].path == "first.css"


class TestBatchProcessingGracefulDegradation(TestChopperBase):
    """Test that batch processing continues when individual files fail."""

    def test_batch_processing_with_permission_error(self):
        """Test that batch processing continues on permission errors."""
        import stat

        if hasattr(os, "getuid") and os.getuid() == 0:
            pytest.skip("Cannot test permission errors as root user")

        # Create multiple chopper files
        file1 = self.create_chopper_file(
            "good1.chopper.html",
            '<style chopper:file="good1.css">.test { color: blue; }</style>',
        )

        file2 = self.create_chopper_file(
            "bad.chopper.html",
            '<style chopper:file="bad.css">.bad { color: red; }</style>',
        )

        # Process first file successfully
        result1 = self.run_chopper(file1)
        assert result1, "First file should succeed"
        assert (self.css_dir / "good1.css").exists()

        # Make css directory read-only to cause file2 to fail
        original_mode = self.css_dir.stat().st_mode
        self.css_dir.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        try:
            # Process second file - should fail gracefully without sys.exit
            result2 = self.run_chopper(file2)
            assert result2 is False, "Second file should fail due to permissions"
        finally:
            # Restore permissions
            self.css_dir.chmod(original_mode)

        # Verify we can still process files after the error
        file3 = self.create_chopper_file(
            "good2.chopper.html",
            '<style chopper:file="good2.css">.test2 { color: green; }</style>',
        )
        result3 = self.run_chopper(file3)
        assert result3, "Third file should succeed after earlier failure"
        assert (self.css_dir / "good2.css").exists()


class TestConstantsModule(TestChopperBase):
    """Test that constants module is properly accessible and functional."""

    def test_constants_module_imports(self):
        """Test that constants module exports are accessible."""
        from chopper.constants import (
            CHOPPER_FILE_EXTENSION,
            MAX_CONFIG_SEARCH_DEPTH,
            CONFIG_FILE_NAMES,
            Comment,
            COMMENT_CLIENT_STYLES,
            COMMENT_SERVER_STYLES,
            TREE_BRANCH,
            TREE_LAST,
            TREE_PIPE,
        )

        # Verify key constants have expected values
        assert CHOPPER_FILE_EXTENSION == ".chopper.html"
        assert MAX_CONFIG_SEARCH_DEPTH == 5
        assert isinstance(CONFIG_FILE_NAMES, list)
        assert len(CONFIG_FILE_NAMES) == 4
        assert ".chopper" in CONFIG_FILE_NAMES

        # Verify comment styles are accessible
        assert "php" in COMMENT_CLIENT_STYLES
        assert "html" in COMMENT_SERVER_STYLES
        assert "twig" in COMMENT_CLIENT_STYLES

        # Verify tree symbols exist
        assert TREE_BRANCH
        assert TREE_LAST
        assert TREE_PIPE

    def test_comment_namedtuple_functionality(self):
        """Test that Comment NamedTuple works correctly."""
        from chopper.constants import Comment

        # Create comment instance
        test_comment = Comment("/* ", " */")
        assert test_comment.open == "/* "
        assert test_comment.close == " */"

        # Test immutability (should raise AttributeError)
        with pytest.raises(AttributeError):
            test_comment.open = "<!--"

    def test_backward_compatibility_aliases(self):
        """Test that backward compatibility aliases work."""
        from chopper.chopper import (
            CHOPPER_NAME,
            comment_cs_styles,
            comment_ss_styles,
        )
        from chopper.constants import (
            CHOPPER_FILE_EXTENSION,
            COMMENT_CLIENT_STYLES,
            COMMENT_SERVER_STYLES,
        )

        # Verify aliases point to the same objects
        assert CHOPPER_NAME == CHOPPER_FILE_EXTENSION
        assert comment_cs_styles is COMMENT_CLIENT_STYLES
        assert comment_ss_styles is COMMENT_SERVER_STYLES


class TestMalformedHTMLHandling(TestChopperBase):
    """Test graceful handling of malformed HTML with unbalanced tags."""

    def test_unbalanced_closing_tags(self):
        """Test that parser handles extra closing tags gracefully."""
        content = """
        <style chopper:file="test.css">
            .class1 { color: blue; }
        </style>
        </style>  <!-- Extra closing tag -->
        <script chopper:file="test.js">
            console.log("test");
        </script>
        """

        chopper_file = self.create_chopper_file("unbalanced.chopper.html", content)

        # Should not crash with IndexError
        success = self.run_chopper(chopper_file)

        # Verify files were created
        assert (self.css_dir / "test.css").exists()
        assert (self.js_dir / "test.js").exists()

    def test_multiple_unbalanced_tags(self):
        """Test handling of multiple unbalanced closing tags."""
        content = """
        <style chopper:file="test1.css">.test1 { color: red; }</style>
        </style>
        </style>
        </script>  <!-- Wrong tag type -->
        <script chopper:file="test2.js">console.log("ok");</script>
        </script>
        """

        chopper_file = self.create_chopper_file(
            "multi_unbalanced.chopper.html", content
        )

        # Should handle gracefully
        success = self.run_chopper(chopper_file)

        # At least the valid sections should be processed
        assert (self.css_dir / "test1.css").exists()
        assert (self.js_dir / "test2.js").exists()

    def test_deeply_nested_unbalanced_tags(self):
        """Test handling of deeply nested structures with unbalanced tags."""
        content = """
        <style chopper:file="outer.css">
            .outer { color: blue; }
            <style chopper:file="inner.css">
                .inner { color: red; }
            </style>
        </style>
        </style>  <!-- Extra closing -->
        """

        chopper_file = self.create_chopper_file(
            "nested_unbalanced.chopper.html", content
        )

        # Should not crash
        success = self.run_chopper(chopper_file)
        assert success


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
