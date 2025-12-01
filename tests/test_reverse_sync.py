#!/usr/bin/env python3
"""
Test suite for chopper reverse sync functionality (--warn --update).

This module tests the ability to update chopper source files with changes
made to destination files, providing interactive prompts for user approval.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, List
import subprocess
import sys

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


class TestReverseSyncFunctionality:
    """Test suite for --warn --update functionality."""

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

    def create_test_chopper_file(self, filename: str, content: str) -> Path:
        """Helper to create test chopper files."""
        file_path = self.chopper_dir / filename
        file_path.write_text(content)
        return file_path

    def create_basic_chopper_file(self) -> Path:
        """Create a basic chopper file for testing."""
        content = '''<style chopper:file="components/hero.css">
.hero {
    background: blue;
    padding: 2rem;
}
</style>

<script chopper:file="components/hero.js">
console.log("Hero component loaded");
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM ready");
});
</script>

<chop chopper:file="components/hero.html">
<div class="hero">
    <h1>Welcome</h1>
    <p>Hero section content</p>
</div>
</chop>'''
        return self.create_test_chopper_file("hero.chopper.html", content)

    def get_types_dict(self) -> Dict[str, str]:
        """Get the types dictionary for file destinations."""
        return {
            "style": str(self.css_dir),
            "script": str(self.js_dir),
            "chop": str(self.html_dir),
        }

    def run_chopper_command(self, chopper_file: Path, warn: bool = False, update: bool = False) -> bool:
        """
        Helper to run chopper command programmatically.

        Args:
            chopper_file: Path to the chopper file to process
            warn: Whether to run in warn mode
            update: Whether to run in update mode

        Returns:
            bool: Success status
        """
        types = self.get_types_dict()
        return chop(
            str(chopper_file),
            types,
            CommentType.NONE,
            warn=warn,
            update=update
        )

    def modify_destination_file(self, relative_path: str, new_content: str) -> Path:
        """
        Helper to modify a destination file.

        Args:
            relative_path: Path relative to appropriate directory (css/js/html)
            new_content: New content to write to the file

        Returns:
            Path: The modified file path
        """
        if relative_path.endswith('.css'):
            full_path = self.css_dir / relative_path
        elif relative_path.endswith('.js'):
            full_path = self.js_dir / relative_path
        else:
            full_path = self.html_dir / relative_path

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(new_content)
        return full_path


class TestBasicUpdateFlow(TestReverseSyncFunctionality):
    """Test basic update flow scenarios."""

    def test_basic_update_flow_css(self):
        """Test basic --warn --update with CSS changes and user saying 'y'."""
        # Create chopper file
        chopper_file = self.create_basic_chopper_file()

        # Run chopper to generate initial files
        success = self.run_chopper_command(chopper_file, warn=False, update=False)
        assert success, "Initial chopper run should succeed"

        # Verify CSS file was created
        css_file = self.css_dir / "components" / "hero.css"
        assert css_file.exists(), "CSS file should be created"

        # Modify the CSS file
        modified_css = '''.hero {
    background: red;
    padding: 3rem;
    border: 1px solid black;
}'''
        css_file.write_text(modified_css)

        # Mock user input to accept the update
        with patch('click.prompt', return_value='y'):
            # Run chopper in warn+update mode
            success = self.run_chopper_command(chopper_file, warn=True, update=True)
            # Note: This should return False because warn mode found differences
            # but the update functionality should have worked

        # Verify chopper file was updated
        updated_content = chopper_file.read_text()
        assert "background: red" in updated_content, "Chopper file should contain updated CSS"
        assert "padding: 3rem" in updated_content, "Chopper file should contain updated padding"
        assert "border: 1px solid black" in updated_content, "Chopper file should contain new border"

    def test_basic_update_flow_js(self):
        """Test basic --warn --update with JavaScript changes."""
        chopper_file = self.create_basic_chopper_file()

        # Generate initial files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify the JS file
        js_file = self.js_dir / "components" / "hero.js"
        modified_js = '''console.log("Hero component loaded - UPDATED");
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM ready - with additional logging");
    initHeroAnimations();
});

function initHeroAnimations() {
    console.log("Initializing hero animations");
}'''
        js_file.write_text(modified_js)

        # Mock user input to accept update
        with patch('click.prompt', return_value='y'):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        # Verify chopper file was updated
        updated_content = chopper_file.read_text()
        assert "UPDATED" in updated_content
        assert "initHeroAnimations" in updated_content
        assert "additional logging" in updated_content

    def test_basic_update_flow_html(self):
        """Test basic --warn --update with HTML changes."""
        chopper_file = self.create_basic_chopper_file()

        # Generate initial files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify the HTML file
        html_file = self.html_dir / "components" / "hero.html"
        modified_html = '''<div class="hero hero--enhanced">
    <h1>Welcome to Our Site</h1>
    <p>Hero section content with more details</p>
    <button class="cta-button">Get Started</button>
</div>'''
        html_file.write_text(modified_html)

        # Mock user input to accept update
        with patch('click.prompt', return_value='y'):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        # Verify chopper file was updated
        updated_content = chopper_file.read_text()
        assert "hero--enhanced" in updated_content
        assert "Welcome to Our Site" in updated_content
        assert "cta-button" in updated_content


class TestUserDecisions(TestReverseSyncFunctionality):
    """Test different user decision scenarios."""

    def test_user_declines_update(self):
        """Test --warn --update with user saying 'n'."""
        chopper_file = self.create_basic_chopper_file()
        original_content = chopper_file.read_text()

        # Generate files and modify CSS
        self.run_chopper_command(chopper_file, warn=False, update=False)
        css_file = self.css_dir / "components" / "hero.css"
        css_file.write_text(".hero { background: green; }")

        # Mock user input to decline update
        with patch('click.prompt', return_value='n'):
            success = self.run_chopper_command(chopper_file, warn=True, update=True)
            assert not success, "Should return False when files differ"

        # Verify chopper file was NOT modified
        assert chopper_file.read_text() == original_content
        assert "background: green" not in chopper_file.read_text()

    def test_user_cancels_operation(self):
        """Test --warn --update with user saying 'c'."""
        chopper_file = self.create_basic_chopper_file()
        original_content = chopper_file.read_text()

        # Generate files and modify both CSS and JS
        self.run_chopper_command(chopper_file, warn=False, update=False)

        css_file = self.css_dir / "components" / "hero.css"
        css_file.write_text(".hero { background: yellow; }")

        js_file = self.js_dir / "components" / "hero.js"
        js_file.write_text("console.log('CANCELLED TEST');")

        # Mock user input to cancel on first prompt
        with patch('click.prompt', return_value='c'):
            with pytest.raises(SystemExit):  # Should exit when cancelled
                self.run_chopper_command(chopper_file, warn=True, update=True)

        # Verify chopper file was NOT modified at all
        assert chopper_file.read_text() == original_content
        assert "background: yellow" not in chopper_file.read_text()
        assert "CANCELLED TEST" not in chopper_file.read_text()


class TestMultipleSections(TestReverseSyncFunctionality):
    """Test updating specific sections when chopper file has multiple tags."""

    def test_update_only_css_section(self):
        """Test that only CSS section is updated when only CSS file changes."""
        chopper_file = self.create_basic_chopper_file()
        original_content = chopper_file.read_text()

        # Generate files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify only the CSS file
        css_file = self.css_dir / "components" / "hero.css"
        css_file.write_text(".hero { background: purple; margin: 1rem; }")

        # Mock user input to accept update
        with patch('click.prompt', return_value='y'):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # CSS section should be updated
        assert "background: purple" in updated_content
        assert "margin: 1rem" in updated_content

        # JS and HTML sections should be unchanged
        assert "console.log(\"Hero component loaded\");" in updated_content
        assert "<h1>Welcome</h1>" in updated_content

    def test_update_multiple_sections_sequentially(self):
        """Test updating multiple sections with different user decisions."""
        chopper_file = self.create_basic_chopper_file()

        # Generate files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify both CSS and JS files
        css_file = self.css_dir / "components" / "hero.css"
        css_file.write_text(".hero { background: orange; }")

        js_file = self.js_dir / "components" / "hero.js"
        js_file.write_text("console.log('MULTIPLE SECTIONS TEST');")

        # Mock user input: yes for CSS, no for JS
        with patch('click.prompt', side_effect=['y', 'n']):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # CSS should be updated
        assert "background: orange" in updated_content

        # JS should NOT be updated (still original)
        assert "console.log(\"Hero component loaded\");" in updated_content
        assert "MULTIPLE SECTIONS TEST" not in updated_content


class TestPositionBasedReplacement(TestReverseSyncFunctionality):
    """Test that content replacement uses exact parser positions."""

    def test_complex_nested_structure(self):
        """Test precise replacement in complex nested HTML structure."""
        complex_content = '''<!DOCTYPE html>
<html>
<head>
    <style chopper:file="complex.css">
    .header {
        background: white;
        padding: 1rem;
    }
    .nav {
        display: flex;
    }
    </style>

    <script chopper:file="complex.js">
    function initHeader() {
        console.log("Header initialized");
    }
    </script>
</head>
<body>
    <chopper chopper:file="header.html">
    <header class="header">
        <nav class="nav">
            <a href="/">Home</a>
        </nav>
    </header>
    </chopper>

    <style chopper:file="footer.css">
    .footer {
        background: black;
        color: white;
    }
    </style>
</body>
</html>'''

        chopper_file = self.create_test_chopper_file("complex.chopper.html", complex_content)

        # Generate files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify only the header CSS (first style section)
        css_file = self.css_dir / "complex.css"
        css_file.write_text('''.header {
    background: lightblue;
    padding: 2rem;
    border-radius: 5px;
}
.nav {
    display: grid;
    gap: 1rem;
}''')

        # Mock user input to accept update
        with patch('click.prompt', return_value='y'):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # First style section should be updated
        assert "background: lightblue" in updated_content
        assert "border-radius: 5px" in updated_content
        assert "display: grid" in updated_content

        # Other sections should remain unchanged
        assert "function initHeader()" in updated_content
        assert '<a href="/">Home</a>' in updated_content
        assert "background: black" in updated_content  # Second style section unchanged
        assert "<!DOCTYPE html>" in updated_content  # HTML structure preserved
        assert "</html>" in updated_content

    def test_preserve_html_structure_and_attributes(self):
        """Test that HTML tag attributes and structure are preserved."""
        content_with_attrs = '''<style chopper:file="styled.css" data-test="css-section" id="main-styles">
.test {
    color: blue;
}
</style>

<script chopper:file="scripted.js" type="module" data-test="js-section">
console.log("test");
</script>'''

        chopper_file = self.create_test_chopper_file("attrs.chopper.html", content_with_attrs)

        # Generate files
        self.run_chopper_command(chopper_file, warn=False, update=False)

        # Modify CSS
        css_file = self.css_dir / "styled.css"
        css_file.write_text('.test {\n    color: red;\n    font-size: 16px;\n}')

        # Mock user input
        with patch('click.prompt', return_value='y'):
            self.run_chopper_command(chopper_file, warn=True, update=True)

        updated_content = chopper_file.read_text()

        # Content should be updated
        assert "color: red" in updated_content
        assert "font-size: 16px" in updated_content

        # Attributes should be preserved
        assert 'data-test="css-section"' in updated_content
        assert 'id="main-styles"' in updated_content
        assert 'type="module"' in updated_content
        assert 'data-test="js-section"' in updated_content

        # Original JS should be unchanged
        assert 'console.log("test");' in updated_content


# Placeholder classes for remaining test categories
class TestErrorHandling(TestReverseSyncFunctionality):
    """Test error handling scenarios."""

    def test_missing_destination_files(self):
        """Test handling when destination files don't exist."""
        # TODO: Implement after core functionality
        pass

    def test_permission_errors(self):
        """Test handling file permission errors."""
        # TODO: Implement after core functionality
        pass


class TestCLIIntegration(TestReverseSyncFunctionality):
    """Test CLI flag integration."""

    def test_update_requires_warn_flag(self):
        """Test that --update requires --warn flag."""
        # TODO: Implement CLI-level testing after core functionality
        pass

    def test_update_conflicts_with_watch(self):
        """Test that --update cannot be used with --watch."""
        # TODO: Implement after core functionality
        pass


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])