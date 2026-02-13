"""
Test for multiple section update bug fix.

This test verifies that when multiple sections from the same chopper file
are updated sequentially using --update mode, all sections are updated
correctly without corrupting or deleting parts of other sections.

The bug was: when updating 2+ sections from the same file, the second
update would use stale line positions and delete parts of the previous
section including its tags.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from chopper.chopper import chop, CommentType


class TestMultipleSectionUpdate:
    """Test that multiple section updates work correctly."""

    def setup_method(self):
        """Set up test directories and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.chopper_dir = Path(self.temp_dir) / "chopper"
        self.css_dir = Path(self.temp_dir) / "css"
        self.js_dir = Path(self.temp_dir) / "js"
        self.views_dir = Path(self.temp_dir) / "views"

        self.chopper_dir.mkdir()
        self.css_dir.mkdir()
        self.js_dir.mkdir()
        self.views_dir.mkdir()

        self.types = {
            "style": str(self.css_dir),
            "script": str(self.js_dir),
            "chop": str(self.views_dir),
        }

    def create_chopper_file_with_three_sections(self) -> Path:
        """Create a chopper file with three sections (style, script, chop)."""
        chopper_file = self.chopper_dir / "test.chopper.html"
        content = """<!-- Test Component -->

<style chopper:file="test.css">
  .original-css {
    color: red;
    background: blue;
  }
</style>

<script chopper:file="test.js">
  function originalFunction() {
    console.log('original');
    return 42;
  }
</script>

<chop chopper:file="test.html">
  <div class="original">
    <h1>Original Title</h1>
    <p>Original content</p>
  </div>
</chop>
"""
        chopper_file.write_text(content)
        return chopper_file

    def test_multiple_section_update_preserves_all_sections(self):
        """Test that updating multiple sections doesn't corrupt the file."""
        chopper_file = self.create_chopper_file_with_three_sections()

        # First, generate the output files
        result = chop(
            str(chopper_file),
            self.types,
            CommentType.NONE,
            warn=False,
            update=False,
        )
        assert result is True

        # Verify files were created
        css_file = self.css_dir / "test.css"
        js_file = self.js_dir / "test.js"
        html_file = self.views_dir / "test.html"

        assert css_file.exists()
        assert js_file.exists()
        assert html_file.exists()

        # Now modify ALL THREE output files
        css_file.write_text(
            css_file.read_text()
            + """
  /* Added CSS comment */
  .new-class {
    margin: 10px;
  }
"""
        )

        js_file.write_text(
            js_file.read_text()
            + """
  // Added JS comment
  function newFunction() {
    return 'new';
  }
"""
        )

        html_file.write_text(
            """  <div class="updated">
    <h1>Updated Title</h1>
    <p>Updated content with changes</p>
    <span>Extra element</span>
  </div>
"""
        )

        # Mock click.prompt at the module level where it's imported
        with patch("chopper.chopper.click.prompt") as mock_prompt:
            mock_prompt.return_value = "y"

            # Run update mode to sync changes back
            result = chop(
                str(chopper_file),
                self.types,
                CommentType.NONE,
                warn=True,
                update=True,
            )
            assert result is True

            # Should have prompted 3 times (once for each modified section)
            assert mock_prompt.call_count == 3

        # Read the updated chopper file
        updated_content = chopper_file.read_text()

        # Verify all three sections still exist with correct tags
        assert '<style chopper:file="test.css">' in updated_content
        assert "</style>" in updated_content
        assert '<script chopper:file="test.js">' in updated_content
        assert "</script>" in updated_content
        assert '<chop chopper:file="test.html">' in updated_content
        assert "</chop>" in updated_content

        # Verify the CSS section was updated with new content
        assert "/* Added CSS comment */" in updated_content
        assert ".new-class" in updated_content
        assert "margin: 10px;" in updated_content

        # Verify the JS section was updated with new content
        assert "// Added JS comment" in updated_content
        assert "function newFunction()" in updated_content
        assert "return 'new';" in updated_content

        # Verify the HTML section was updated with new content
        assert '<div class="updated">' in updated_content
        assert "<h1>Updated Title</h1>" in updated_content
        assert "<p>Updated content with changes</p>" in updated_content
        assert "<span>Extra element</span>" in updated_content

        # Verify original content is preserved (not deleted)
        assert ".original-css" in updated_content
        assert "originalFunction" in updated_content

        # Count the number of opening and closing tags to ensure none were deleted
        assert updated_content.count("<style") == 1
        assert updated_content.count("</style>") == 1
        assert updated_content.count("<script") == 1
        assert updated_content.count("</script>") == 1
        assert updated_content.count("<chop") == 1
        assert updated_content.count("</chop>") == 1

    def test_sequential_updates_maintain_correct_line_positions(self):
        """Test that line positions are recalculated after each update."""
        chopper_file = self.create_chopper_file_with_three_sections()

        # Generate initial files
        chop(
            str(chopper_file),
            self.types,
            CommentType.NONE,
            warn=False,
            update=False,
        )

        # Modify output files with content that changes line counts
        css_file = self.css_dir / "test.css"
        js_file = self.js_dir / "test.js"
        html_file = self.views_dir / "test.html"

        # Add many lines to CSS (this will shift line numbers significantly)
        css_additions = "\n".join([f"  /* Line {i} */" for i in range(1, 21)])
        css_file.write_text(css_file.read_text() + "\n" + css_additions)

        # Add many lines to JS (this will further shift line numbers)
        js_additions = "\n".join([f"  // Line {i}" for i in range(1, 21)])
        js_file.write_text(js_file.read_text() + "\n" + js_additions)

        # Modify HTML significantly
        html_file.write_text(
            "\n".join([f"  <p>Paragraph {i}</p>" for i in range(1, 11)])
        )

        # Store original length
        original_length = len(chopper_file.read_text().splitlines())

        # Update all sections
        with patch("chopper.chopper.click.prompt") as mock_prompt:
            mock_prompt.return_value = "y"

            result = chop(
                str(chopper_file),
                self.types,
                CommentType.NONE,
                warn=True,
                update=True,
            )
            assert result is True

        updated_content = chopper_file.read_text()
        updated_lines = updated_content.splitlines()

        # The file should be significantly longer (about 50 lines added)
        assert len(updated_lines) > original_length + 40, (
            "File should have grown significantly"
        )

        # Verify all sections are still present and valid
        # CSS section should contain all 20 comment lines
        css_section_found = False
        for i in range(1, 21):
            if f"/* Line {i} */" in updated_content:
                css_section_found = True
            else:
                css_section_found = False
                break
        assert css_section_found, "CSS section should contain all added lines"

        # JS section should contain all 20 comment lines
        js_section_found = False
        for i in range(1, 21):
            if f"// Line {i}" in updated_content:
                js_section_found = True
            else:
                js_section_found = False
                break
        assert js_section_found, "JS section should contain all added lines"

        # HTML section should contain all 10 paragraphs
        html_section_found = False
        for i in range(1, 11):
            if f"<p>Paragraph {i}</p>" in updated_content:
                html_section_found = True
            else:
                html_section_found = False
                break
        assert html_section_found, "HTML section should contain all added paragraphs"

        # Most importantly: verify no content from one section leaked into another
        lines = updated_content.splitlines()
        in_style = False
        in_script = False
        in_chop = False

        for line in lines:
            if "<style" in line:
                in_style = True
                in_script = False
                in_chop = False
            elif "</style>" in line:
                in_style = False
            elif "<script" in line:
                in_script = True
                in_style = False
                in_chop = False
            elif "</script>" in line:
                in_script = False
            elif "<chop" in line:
                in_chop = True
                in_style = False
                in_script = False
            elif "</chop>" in line:
                in_chop = False

            # Verify content is in the right section
            if "/* Line" in line:
                assert in_style, "CSS comment should only appear in style section"
            if "// Line" in line:
                assert in_script, "JS comment should only appear in script section"
            if "<p>Paragraph" in line:
                assert in_chop, "HTML paragraph should only appear in chop section"

    def test_update_with_empty_sections(self):
        """Test that updating works even when some sections are empty."""
        chopper_file = self.chopper_dir / "empty.chopper.html"
        content = """<style chopper:file="empty.css">
</style>

<script chopper:file="empty.js">
  console.log('has content');
</script>

<chop chopper:file="empty.html">
</chop>
"""
        chopper_file.write_text(content)

        # Generate files
        chop(
            str(chopper_file),
            self.types,
            CommentType.NONE,
            warn=False,
            update=False,
        )

        # Modify the JS file (the one with content)
        js_file = self.js_dir / "empty.js"
        js_file.write_text("console.log('updated content');\n")

        # Also add content to the previously empty CSS
        css_file = self.css_dir / "empty.css"
        css_file.write_text(".new { color: blue; }\n")

        # Update
        with patch("chopper.chopper.click.prompt") as mock_prompt:
            mock_prompt.return_value = "y"

            result = chop(
                str(chopper_file),
                self.types,
                CommentType.NONE,
                warn=True,
                update=True,
            )
            assert result is True

        updated_content = chopper_file.read_text()

        # Verify all tags are still present
        assert '<style chopper:file="empty.css">' in updated_content
        assert "</style>" in updated_content
        assert '<script chopper:file="empty.js">' in updated_content
        assert "</script>" in updated_content
        assert '<chop chopper:file="empty.html">' in updated_content
        assert "</chop>" in updated_content

        # Verify updates were applied
        assert ".new { color: blue; }" in updated_content
        assert "console.log('updated content');" in updated_content

    def teardown_method(self):
        """Clean up test directories."""
        import shutil

        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
