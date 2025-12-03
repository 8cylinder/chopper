#!/usr/bin/env python3
"""
Unit tests for refactored helper functions in chopper.

These tests focus on individual helper functions extracted during
refactoring to ensure they work correctly in isolation.
"""

import io
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys

# Add src to path so we can import chopper modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chopper.chopper import (
    validate_and_resolve_output_path,
    open_file_for_write,
    handle_file_difference,
    read_file_content,
    ParsedData,
)


class TestValidateAndResolveOutputPath:
    """Test validate_and_resolve_output_path() function."""

    def test_no_path_returns_success_with_none(self):
        """Test that empty path returns success but no resolved path."""
        block = ParsedData(
            path="",
            file_type="css",
            base_path="/tmp/output",
            source_file="test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )
        is_valid, resolved_path, error_msg = validate_and_resolve_output_path(block)
        assert is_valid is True
        assert resolved_path is None
        assert error_msg == ""

    def test_valid_simple_path(self):
        """Test that valid simple path resolves correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            block = ParsedData(
                path="styles/main.css",
                file_type="css",
                base_path=tmpdir,
                source_file="test.chopper.html",
                tag="style",
                start=(1, 0),
                end=(5, 0),
                content="",
                comment_open="",
                comment_close="",
            )
            is_valid, resolved_path, error_msg = validate_and_resolve_output_path(block)
            assert is_valid is True
            assert resolved_path == Path(tmpdir) / "styles/main.css"
            assert error_msg == ""

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            block = ParsedData(
                path="../../../etc/passwd",
                file_type="",
                base_path=tmpdir,
                source_file="test.chopper.html",
                tag="style",
                start=(1, 0),
                end=(5, 0),
                content="",
                comment_open="",
                comment_close="",
            )
            is_valid, resolved_path, error_msg = validate_and_resolve_output_path(block)
            assert is_valid is False
            assert resolved_path is None
            assert "outside allowed directory" in error_msg

    def test_absolute_path_blocked(self):
        """Test that absolute paths trying to escape are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            block = ParsedData(
                path="/etc/passwd",
                file_type="",
                base_path=tmpdir,
                source_file="test.chopper.html",
                tag="style",
                start=(1, 0),
                end=(5, 0),
                content="",
                comment_open="",
                comment_close="",
            )
            is_valid, resolved_path, error_msg = validate_and_resolve_output_path(block)
            # On Unix, /etc/passwd won't be under tmpdir
            # On Windows, different drive letters won't be under tmpdir
            # Both should be blocked
            assert is_valid is False
            assert resolved_path is None
            assert "outside allowed directory" in error_msg

    def test_valid_nested_path(self):
        """Test that valid nested paths work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            block = ParsedData(
                path="deep/nested/dir/file.js",
                file_type="js",
                base_path=tmpdir,
                source_file="test.chopper.html",
                tag="script",
                start=(1, 0),
                end=(5, 0),
                content="",
                comment_open="",
                comment_close="",
            )
            is_valid, resolved_path, error_msg = validate_and_resolve_output_path(block)
            assert is_valid is True
            assert resolved_path == Path(tmpdir) / "deep/nested/dir/file.js"
            assert error_msg == ""


class TestOpenFileForWrite:
    """Test open_file_for_write() function."""

    def test_create_new_file(self):
        """Test opening a new file for writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new_file.txt"
            handle, is_new, error_msg = open_file_for_write(file_path, False)

            assert handle is not None
            assert is_new is True
            assert error_msg == ""
            handle.close()

    def test_open_existing_file(self):
        """Test opening an existing file for writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "existing.txt"
            file_path.write_text("existing content")

            handle, is_new, error_msg = open_file_for_write(file_path, False)

            assert handle is not None
            assert is_new is False
            assert error_msg == ""
            handle.close()

    def test_warn_mode_file_does_not_exist(self):
        """Test warn mode when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.txt"
            handle, is_new, error_msg = open_file_for_write(file_path, True)

            assert handle is None
            assert is_new is False
            assert error_msg == "DOES_NOT_EXIST"

    def test_warn_mode_file_exists(self):
        """Test warn mode when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "existing.txt"
            file_path.write_text("content")

            handle, is_new, error_msg = open_file_for_write(file_path, True)

            assert handle is not None
            assert is_new is False
            assert error_msg == ""
            handle.close()

    def test_is_directory_error(self):
        """Test that trying to open a directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir) / "subdir"
            dir_path.mkdir()

            handle, is_new, error_msg = open_file_for_write(dir_path, False)

            assert handle is None
            assert is_new is False
            assert "Destination is a directory" in error_msg

    def test_permission_error(self):
        """Test handling of permission errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "readonly.txt"
            file_path.write_text("content")
            file_path.chmod(0o444)  # Read-only

            try:
                handle, is_new, error_msg = open_file_for_write(file_path, False)

                # Behavior depends on OS/permissions
                # If we got a handle, close it
                if handle:
                    handle.close()
                else:
                    assert "Permission denied" in error_msg or "OS error" in error_msg
            finally:
                # Restore permissions for cleanup
                file_path.chmod(0o644)

    def test_nonexistent_parent_directory(self):
        """Test opening file in non-existent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent_dir" / "subdir" / "file.txt"
            handle, is_new, error_msg = open_file_for_write(file_path, False)

            assert handle is None
            assert is_new is False
            assert "File not found" in error_msg or "No such file" in error_msg


class TestReadFileContent:
    """Test read_file_content() function."""

    def test_read_normal_file(self):
        """Test reading content from normal file handle."""
        content = "Hello, world!\nThis is a test."
        f = io.StringIO(content)

        result, error_msg = read_file_content(f)

        assert result == content
        assert error_msg == ""

    def test_read_empty_file(self):
        """Test reading empty file."""
        f = io.StringIO("")

        result, error_msg = read_file_content(f)

        assert result == ""
        assert error_msg == ""

    def test_unsupported_operation(self):
        """Test handling of UnsupportedOperation (write-only file)."""
        # Create a write-only file handle
        f = io.StringIO()
        f.close()  # Closed file raises different exception
        # Better: use a mock
        mock_file = MagicMock()
        mock_file.read.side_effect = io.UnsupportedOperation("not readable")

        result, error_msg = read_file_content(mock_file)

        assert result == ""
        assert error_msg == ""

    def test_permission_error(self):
        """Test handling of permission errors."""
        mock_file = MagicMock()
        mock_file.read.side_effect = PermissionError("Access denied")

        result, error_msg = read_file_content(mock_file)

        assert result is None
        assert "Permission denied reading file" in error_msg


class TestHandleFileDifference:
    """Test handle_file_difference() function."""

    def test_no_warn_mode_returns_write_and_success(self):
        """Test that without warn mode, function allows writing."""
        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        should_write, success = handle_file_difference(
            block=block,
            content="new content",
            current_contents="old content",
            partial=Path("/tmp/test.css"),
            warn=False,
            update=False,
        )

        assert should_write is True
        assert success is True

    @patch("chopper.chopper.show_error")
    @patch("chopper.chopper.show_diff")
    @patch("chopper.chopper.remove_common_path")
    def test_warn_mode_without_update(
        self, mock_remove_path, mock_show_diff, mock_show_error
    ):
        """Test warn mode without update flag."""
        mock_remove_path.return_value = (
            Path("test.css"),
            Path("test.chopper.html"),
        )

        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="/tmp/test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        should_write, success = handle_file_difference(
            block=block,
            content="new content",
            current_contents="old content",
            partial=Path("/tmp/test.css"),
            warn=True,
            update=False,
        )

        assert should_write is False
        assert success is False
        mock_show_error.assert_called_once()
        mock_show_diff.assert_called_once()

    @patch("chopper.chopper.show_error")
    @patch("chopper.chopper.show_diff")
    @patch("chopper.chopper.remove_common_path")
    @patch("chopper.chopper.prompt_for_update")
    @patch("chopper.chopper.update_chopper_section")
    def test_warn_and_update_user_accepts(
        self,
        mock_update_section,
        mock_prompt,
        mock_remove_path,
        mock_show_diff,
        mock_show_error,
    ):
        """Test update mode when user accepts update."""
        mock_remove_path.return_value = (
            Path("test.css"),
            Path("test.chopper.html"),
        )
        mock_prompt.return_value = "y"
        mock_update_section.return_value = True

        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="/tmp/test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        should_write, success = handle_file_difference(
            block=block,
            content="new content",
            current_contents="old content",
            partial=Path("/tmp/test.css"),
            warn=True,
            update=True,
        )

        assert should_write is False  # Don't write, we updated source
        assert success is True  # But consider it success
        mock_update_section.assert_called_once()

    @patch("chopper.chopper.show_error")
    @patch("chopper.chopper.show_diff")
    @patch("chopper.chopper.remove_common_path")
    @patch("chopper.chopper.prompt_for_update")
    def test_warn_and_update_user_declines(
        self, mock_prompt, mock_remove_path, mock_show_diff, mock_show_error
    ):
        """Test update mode when user declines update."""
        mock_remove_path.return_value = (
            Path("test.css"),
            Path("test.chopper.html"),
        )
        mock_prompt.return_value = "n"

        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="/tmp/test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        should_write, success = handle_file_difference(
            block=block,
            content="new content",
            current_contents="old content",
            partial=Path("/tmp/test.css"),
            warn=True,
            update=True,
        )

        assert should_write is False
        assert success is False

    @patch("chopper.chopper.show_error")
    @patch("chopper.chopper.show_diff")
    @patch("chopper.chopper.remove_common_path")
    @patch("chopper.chopper.prompt_for_update")
    @patch("click.echo")
    def test_warn_and_update_user_cancels(
        self,
        mock_echo,
        mock_prompt,
        mock_remove_path,
        mock_show_diff,
        mock_show_error,
    ):
        """Test update mode when user cancels operation."""
        mock_remove_path.return_value = (
            Path("test.css"),
            Path("test.chopper.html"),
        )
        mock_prompt.return_value = "c"

        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="/tmp/test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        with pytest.raises(SystemExit):
            handle_file_difference(
                block=block,
                content="new content",
                current_contents="old content",
                partial=Path("/tmp/test.css"),
                warn=True,
                update=True,
            )

        mock_echo.assert_called_with("Operation cancelled")

    @patch("chopper.chopper.show_error")
    @patch("chopper.chopper.show_diff")
    @patch("chopper.chopper.remove_common_path")
    @patch("chopper.chopper.prompt_for_update")
    @patch("chopper.chopper.update_chopper_section")
    def test_warn_and_update_section_fails(
        self,
        mock_update_section,
        mock_prompt,
        mock_remove_path,
        mock_show_diff,
        mock_show_error,
    ):
        """Test update mode when update_chopper_section fails."""
        mock_remove_path.return_value = (
            Path("test.css"),
            Path("test.chopper.html"),
        )
        mock_prompt.return_value = "y"
        mock_update_section.return_value = False  # Update failed

        block = ParsedData(
            path="test.css",
            file_type="css",
            base_path="/tmp",
            source_file="/tmp/test.chopper.html",
            tag="style",
            start=(1, 0),
            end=(5, 0),
            content="",
            comment_open="",
            comment_close="",
        )

        should_write, success = handle_file_difference(
            block=block,
            content="new content",
            current_contents="old content",
            partial=Path("/tmp/test.css"),
            warn=True,
            update=True,
        )

        assert should_write is False
        assert success is False  # Update failed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
