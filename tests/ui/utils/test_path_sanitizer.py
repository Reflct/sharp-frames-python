"""
Tests for Sharp Frames UI path sanitizer utilities.

The path sanitizer is critical for UX - it needs to handle various
edge cases while preserving valid paths.
"""

import pytest
from sharp_frames.ui.utils.path_sanitizer import PathSanitizer, sanitize_path_input


class TestPathSanitizerQuoteRemoval:
    """Test cases for quote pattern removal."""
    
    def test_double_quotes(self):
        """Test removal of double quotes."""
        result, changes = PathSanitizer.sanitize('"/path/to/file"')
        assert result == "/path/to/file"
        assert "removed double quotes" in changes
    
    def test_single_quotes(self):
        """Test removal of single quotes."""
        result, changes = PathSanitizer.sanitize("'/path/to/file'")
        assert result == "/path/to/file"
        assert "removed single quotes" in changes
    
    def test_mixed_quotes_double_outside(self):
        """Test removal of mixed quotes with double quotes outside."""
        result, changes = PathSanitizer.sanitize('"\'"/path/to/file"\'"')
        assert result == '"/path/to/file"'  # Inner quotes preserved as they don't match pattern
        assert "removed double-quoted single quotes" in changes
    
    def test_mixed_quotes_single_outside(self):
        """Test removal of mixed quotes with single quotes outside."""
        result, changes = PathSanitizer.sanitize('\'"/path/to/file"\'')
        assert result == "/path/to/file"
        assert "removed single-quoted double quotes" in changes
    
    def test_no_quotes(self):
        """Test that paths without quotes are unchanged."""
        result, changes = PathSanitizer.sanitize("/path/to/file")
        assert result == "/path/to/file"
        assert len([c for c in changes if "quote" in c]) == 0
    
    def test_partial_quotes(self):
        """Test that partial quotes are not removed."""
        test_cases = [
            '"/path/to/file',      # Opening quote only
            'path/to/file"',       # Closing quote only
        ]
        
        for test_input in test_cases:
            result, changes = PathSanitizer.sanitize(test_input)
            # Should not remove partial quotes - these might be legitimate
            assert result == test_input.strip()
    
    def test_multiple_quoted_segments(self):
        """Test handling of multiple quoted segments."""
        # This is a complex case - the sanitizer will try to remove outer quotes
        test_input = '"path" and "file"'
        result, changes = PathSanitizer.sanitize(test_input)
        # This should remove the outer quotes if they match the pattern
        assert result == 'path" and "file'
        assert "removed double quotes" in changes
    
    def test_quotes_with_spaces(self):
        """Test quotes around paths with spaces."""
        result, changes = PathSanitizer.sanitize('"/path/with spaces/file"')
        assert result == "/path/with spaces/file"
        assert "removed double quotes" in changes
    
    def test_empty_quotes(self):
        """Test empty quoted strings."""
        result, changes = PathSanitizer.sanitize('""')
        # Empty quotes should be removed, leaving empty string
        assert result == ""
        assert "removed empty double quotes" in changes


class TestPathSanitizerShellPrefixes:
    """Test cases for shell command prefix removal."""
    
    def test_ampersand_prefix(self):
        """Test removal of ampersand prefix."""
        result, changes = PathSanitizer.sanitize("& /path/to/file")
        assert result == "/path/to/file"
        assert "removed ampersand prefix" in changes
    
    def test_cd_command(self):
        """Test removal of cd command."""
        result, changes = PathSanitizer.sanitize("cd /path/to/directory")
        assert result == "/path/to/directory"
        assert "removed cd command" in changes
    
    def test_ls_command(self):
        """Test removal of ls command."""
        result, changes = PathSanitizer.sanitize("ls /path/to/directory")
        assert result == "/path/to/directory"
        assert "removed ls command" in changes
    
    def test_open_command(self):
        """Test removal of open command (macOS)."""
        result, changes = PathSanitizer.sanitize("open /path/to/file")
        assert result == "/path/to/file"
        assert "removed open command" in changes
    
    def test_cat_command(self):
        """Test removal of cat command."""
        result, changes = PathSanitizer.sanitize("cat /path/to/file.txt")
        assert result == "/path/to/file.txt"
        assert "removed cat command" in changes
    
    def test_cp_command_source(self):
        """Test extraction of source from cp command."""
        result, changes = PathSanitizer.sanitize("cp /source/file /dest/file")
        assert result == "/source/file"
        assert "removed cp source" in changes
    
    def test_mv_command_source(self):
        """Test extraction of source from mv command."""
        result, changes = PathSanitizer.sanitize("mv /old/path /new/path")
        assert result == "/old/path"
        assert "removed mv source" in changes
    
    def test_case_insensitive_commands(self):
        """Test that command detection is case insensitive."""
        result, changes = PathSanitizer.sanitize("CD /path/to/directory")
        assert result == "/path/to/directory"
        assert "removed cd command" in changes
    
    def test_commands_with_extra_spaces(self):
        """Test commands with extra whitespace."""
        result, changes = PathSanitizer.sanitize("cd    /path/to/directory")
        assert result == "/path/to/directory"
        assert "removed cd command" in changes


class TestPathSanitizerEscapeSequences:
    """Test cases for escape sequence handling."""
    
    def test_space_escaping(self):
        """Test unescaping of spaces."""
        result, changes = PathSanitizer.sanitize("/path/with\\ spaces/file")
        assert result == "/path/with spaces/file"
        assert "unescaped 1 character" in changes
    
    def test_multiple_escapes(self):
        """Test unescaping of multiple characters."""
        result, changes = PathSanitizer.sanitize("/path\\(with\\)\\[brackets\\]/file")
        assert result == "/path(with)[brackets]/file"
        assert "unescaped 4 characters" in changes
    
    def test_backslash_escaping(self):
        """Test that backslashes in Windows paths are preserved."""
        result, changes = PathSanitizer.sanitize("/path\\\\with\\\\backslashes")
        # These should not be unescaped as they're not safe chars
        assert result == "/path\\\\with\\\\backslashes"
        assert len([c for c in changes if "unescaped" in c]) == 0
    
    def test_no_escapes(self):
        """Test that paths without escapes are unchanged."""
        result, changes = PathSanitizer.sanitize("/path/to/file")
        assert result == "/path/to/file"
        assert len([c for c in changes if "unescaped" in c]) == 0


class TestPathSanitizerWhitespace:
    """Test cases for whitespace handling."""
    
    def test_leading_whitespace(self):
        """Test removal of leading whitespace."""
        result, changes = PathSanitizer.sanitize("   /path/to/file")
        assert result == "/path/to/file"
        assert "removed leading/trailing whitespace" in changes
    
    def test_trailing_whitespace(self):
        """Test removal of trailing whitespace."""
        result, changes = PathSanitizer.sanitize("/path/to/file   ")
        assert result == "/path/to/file"
        assert "removed leading/trailing whitespace" in changes
    
    def test_both_whitespace(self):
        """Test removal of both leading and trailing whitespace."""
        result, changes = PathSanitizer.sanitize("   /path/to/file   ")
        assert result == "/path/to/file"
        assert "removed leading/trailing whitespace" in changes
    
    def test_internal_spaces_preserved(self):
        """Test that internal spaces are preserved."""
        result, changes = PathSanitizer.sanitize("/path/with spaces/file")
        assert result == "/path/with spaces/file"
        # Should not report whitespace removal for internal spaces
        assert len([c for c in changes if "whitespace" in c]) == 0
    
    def test_quotes_with_internal_whitespace(self):
        """Test that whitespace inside quotes is preserved after quote removal."""
        result, changes = PathSanitizer.sanitize('" /path/with spaces/file "')
        # After removing quotes, the internal spaces should be trimmed by final cleanup
        assert result == "/path/with spaces/file"
        assert "removed double quotes" in changes


class TestPathSanitizerComplexCases:
    """Test cases for complex combinations of issues."""
    
    def test_quoted_shell_command(self):
        """Test shell command with quoted path."""
        result, changes = PathSanitizer.sanitize('cd "/path/with spaces"')
        assert result == "/path/with spaces"
        assert "removed cd command" in changes
        assert "removed double quotes" in changes
    
    def test_escaped_quoted_path(self):
        """Test quoted path with escape sequences."""
        result, changes = PathSanitizer.sanitize('"/path/with\\ spaces/file"')
        assert result == "/path/with spaces/file"
        assert "removed double quotes" in changes
        assert "unescaped 1 character" in changes
    
    def test_shell_command_with_escapes(self):
        """Test shell command with escaped characters."""
        result, changes = PathSanitizer.sanitize("open /path/with\\ spaces")
        assert result == "/path/with spaces"
        assert "removed open command" in changes
        assert "unescaped 1 character" in changes
    
    def test_everything_combined(self):
        """Test a complex case with multiple issues."""
        # Simplified test case that should work step by step
        complex_input = '  cd "/path/with\\ spaces/file"  '
        result, changes = PathSanitizer.sanitize(complex_input)
        # This should process step by step: whitespace -> cd -> quotes -> escapes
        assert result == "/path/with spaces/file"
        
        # Should have applied multiple transformations
        change_types = set(changes)
        assert any("whitespace" in c for c in change_types)
        assert any("cd command" in c for c in change_types)
        assert any("quote" in c for c in change_types)
        assert any("unescaped" in c for c in change_types)


class TestPathSanitizerUtilityMethods:
    """Test cases for utility methods."""
    
    def test_needs_sanitization_true(self):
        """Test detection of paths that need sanitization."""
        test_cases = [
            '"/path/to/file"',
            "cd /path/to/directory",
            "/path/with\\ spaces",
            "   /path/to/file   ",
        ]
        
        for test_input in test_cases:
            assert PathSanitizer.needs_sanitization(test_input) is True
    
    def test_needs_sanitization_false(self):
        """Test detection of paths that don't need sanitization."""
        test_cases = [
            "/path/to/file",
            "/path/with spaces/file",
            "",
            "/simple/path",
        ]
        
        for test_input in test_cases:
            assert PathSanitizer.needs_sanitization(test_input) is False
    
    def test_preview_sanitization(self):
        """Test sanitization preview functionality."""
        test_input = '"/path/to/file"'
        preview = PathSanitizer.preview_sanitization(test_input)
        
        assert preview['original'] == test_input
        assert preview['sanitized'] == "/path/to/file"
        assert preview['needs_sanitization'] is True
        assert "removed double quotes" in preview['changes']
    
    def test_preview_sanitization_no_change(self):
        """Test preview when no sanitization is needed."""
        test_input = "/path/to/file"
        preview = PathSanitizer.preview_sanitization(test_input)
        
        assert preview['original'] == test_input
        assert preview['sanitized'] == test_input
        assert preview['needs_sanitization'] is False
        assert len(preview['changes']) == 0
    
    def test_preview_empty_input(self):
        """Test preview with empty input."""
        preview = PathSanitizer.preview_sanitization("")
        
        assert preview['original'] == ""
        assert preview['sanitized'] == ""
        assert preview['needs_sanitization'] is False
        assert len(preview['changes']) == 0


class TestConvenienceFunction:
    """Test cases for the convenience function."""
    
    def test_sanitize_path_input_function(self):
        """Test the simple convenience function."""
        result = sanitize_path_input('"/path/to/file"')
        assert result == "/path/to/file"
    
    def test_sanitize_path_input_no_change(self):
        """Test convenience function with clean input."""
        result = sanitize_path_input("/path/to/file")
        assert result == "/path/to/file"
    
    def test_sanitize_path_input_empty(self):
        """Test convenience function with empty input."""
        result = sanitize_path_input("")
        assert result == ""


class TestEdgeCases:
    """Test cases for edge cases and potential problems."""
    
    def test_none_input(self):
        """Test handling of None input."""
        result, changes = PathSanitizer.sanitize(None)
        assert result == ""
        assert changes == []
    
    def test_very_long_path(self):
        """Test handling of very long paths."""
        long_path = "/very/long/path/" + "a" * 1000 + "/file"
        quoted_long = f'"{long_path}"'
        
        result, changes = PathSanitizer.sanitize(quoted_long)
        assert result == long_path
        assert "removed double quotes" in changes
    
    def test_unicode_paths(self):
        """Test handling of unicode characters in paths."""
        unicode_path = "/path/with/ünïcødé/文件"
        quoted_unicode = f'"{unicode_path}"'
        
        result, changes = PathSanitizer.sanitize(quoted_unicode)
        assert result == unicode_path
        assert "removed double quotes" in changes
    
    def test_windows_paths(self):
        """Test handling of Windows-style paths."""
        win_path = "C:\\Users\\username\\Documents\\file.txt"
        quoted_win = f'"{win_path}"'
        
        result, changes = PathSanitizer.sanitize(quoted_win)
        # Windows paths should have quotes removed but backslashes preserved
        assert result == win_path
        assert "removed double quotes" in changes
    
    def test_only_whitespace(self):
        """Test input that is only whitespace."""
        result, changes = PathSanitizer.sanitize("   ")
        assert result == ""
        assert "removed leading/trailing whitespace" in changes
    
    def test_only_quotes(self):
        """Test input that is only quotes."""
        result, changes = PathSanitizer.sanitize('""')
        assert result == ""
        assert "removed empty double quotes" in changes 