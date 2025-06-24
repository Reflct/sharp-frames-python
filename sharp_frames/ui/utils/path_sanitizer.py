"""
Path sanitization utilities for Sharp Frames UI.

Handles common issues when users copy paths from various sources like:
- Quoted paths from file browsers
- Shell command outputs 
- Escaped paths from terminals
"""

import re
import os
from typing import Tuple, Optional
from pathlib import Path


class PathSanitizer:
    """Utility class for cleaning up user-provided file paths."""
    
    # Quote patterns - order matters (most specific first)
    QUOTE_PATTERNS = [
        (r'^"\'(.+)\'"$', "double-quoted single quotes"),         # "'path'"
        (r"^'\"(.+)\"'$", "single-quoted double quotes"),         # '"path"'
        (r'^"(.+)"$', "double quotes"),                           # "path"
        (r"^'(.+)'$", "single quotes"),                           # 'path'
        (r'^""$', "empty double quotes"),                         # ""
        (r"^''$", "empty single quotes"),                         # ''
    ]
    
    # Shell command prefixes that commonly appear when copying from terminals
    SHELL_PREFIXES = [
        (r'^&\s+(.+)$', "ampersand prefix"),                      # & path
        (r'^cd\s+(.+)$', "cd command"),                           # cd path
        (r'^ls\s+(.+)$', "ls command"),                           # ls path
        (r'^open\s+(.+)$', "open command"),                       # open path
        (r'^cat\s+(.+)$', "cat command"),                         # cat path
        (r'^cp\s+(.+?)\s+.+$', "cp source"),                      # cp source dest (extract source)
        (r'^mv\s+(.+?)\s+.+$', "mv source"),                      # mv source dest (extract source)
    ]
    
    @classmethod
    def sanitize(cls, raw_input: str) -> Tuple[str, list]:
        """
        Clean up a raw path input from user.
        
        Args:
            raw_input: Raw string input from user
            
        Returns:
            Tuple of (cleaned_path, list_of_changes_made)
        """
        # Handle None input gracefully
        if raw_input is None:
            return "", []
        
        if not raw_input:
            return raw_input, []
        
        changes = []
        current_path = str(raw_input)
        
        # Step 1: Strip leading/trailing whitespace
        stripped = current_path.strip()
        if stripped != current_path:
            changes.append("removed leading/trailing whitespace")
            current_path = stripped
        
        # Step 2: Remove shell command prefixes
        current_path, shell_changes = cls._remove_shell_prefixes(current_path)
        changes.extend(shell_changes)
        
        # Step 3: Remove quotes
        current_path, quote_changes = cls._remove_quotes(current_path)
        changes.extend(quote_changes)
        
        # Step 4: Unescape backslash sequences (but be careful with Windows paths)
        current_path, escape_changes = cls._unescape_path(current_path)
        changes.extend(escape_changes)
        
        # Step 5: Final whitespace cleanup (in case quotes contained extra spaces)
        final_stripped = current_path.strip()
        if final_stripped != current_path and final_stripped:
            changes.append("removed additional whitespace")
            current_path = final_stripped
        
        return current_path, changes
    
    @classmethod
    def _remove_shell_prefixes(cls, path: str) -> Tuple[str, list]:
        """Remove shell command prefixes from path."""
        changes = []
        
        for pattern, description in cls.SHELL_PREFIXES:
            match = re.match(pattern, path, re.IGNORECASE)
            if match:
                # For commands with multiple arguments, we want the first argument
                extracted = match.group(1).strip()
                changes.append(f"removed {description}")
                return extracted, changes
        
        return path, changes
    
    @classmethod
    def _remove_quotes(cls, path: str) -> Tuple[str, list]:
        """Remove various quote patterns from path."""
        changes = []
        
        # Handle empty quotes first
        if path == '""':
            changes.append("removed empty double quotes")
            return "", changes
        if path == "''":
            changes.append("removed empty single quotes")
            return "", changes
        
        for pattern, description in cls.QUOTE_PATTERNS:
            match = re.match(pattern, path)
            if match:
                # For empty quotes patterns, return empty string
                if "empty" in description:
                    changes.append(f"removed {description}")
                    return "", changes
                # For regular patterns, extract the content
                extracted = match.group(1)
                changes.append(f"removed {description}")
                return extracted, changes
        
        return path, changes
    
    @classmethod
    def _unescape_path(cls, path: str) -> Tuple[str, list]:
        """Unescape backslash sequences in path, but preserve Windows paths."""
        changes = []
        
        # Don't unescape if this looks like a Windows path
        if re.match(r'^[A-Za-z]:\\', path):
            return path, changes
        
        # Find all escape sequences that aren't part of Windows paths
        escape_matches = re.findall(r'\\(.)', path)
        if escape_matches:
            # Only unescape certain characters to avoid breaking Windows paths
            safe_unescape_chars = [' ', '(', ')', '[', ']', '{', '}', '&', '$', '!', '?', '*', ';', '|', '<', '>']
            unescaped = path
            unescape_count = 0
            
            for match in escape_matches:
                char = match
                if char in safe_unescape_chars:
                    unescaped = unescaped.replace(f'\\{char}', char, 1)
                    unescape_count += 1
            
            if unescape_count > 0:
                changes.append(f"unescaped {unescape_count} character{'s' if unescape_count != 1 else ''}")
                return unescaped, changes
        
        return path, changes
    
    @classmethod
    def needs_sanitization(cls, raw_input: str) -> bool:
        """
        Check if input needs sanitization without actually sanitizing.
        
        Args:
            raw_input: Raw string input from user
            
        Returns:
            True if sanitization would change the input
        """
        if not raw_input:
            return False
        
        sanitized, changes = cls.sanitize(raw_input)
        return len(changes) > 0
    
    @classmethod
    def preview_sanitization(cls, raw_input: str) -> dict:
        """
        Get a preview of what sanitization would do.
        
        Args:
            raw_input: Raw string input from user
            
        Returns:
            Dict with 'original', 'sanitized', 'changes', and 'needs_sanitization' keys
        """
        if not raw_input:
            return {
                'original': raw_input,
                'sanitized': raw_input,
                'changes': [],
                'needs_sanitization': False
            }
        
        sanitized, changes = cls.sanitize(raw_input)
        
        return {
            'original': raw_input,
            'sanitized': sanitized,
            'changes': changes,
            'needs_sanitization': len(changes) > 0
        }


def sanitize_path_input(raw_input: str) -> str:
    """
    Convenience function for simple path sanitization.
    
    Args:
        raw_input: Raw string input from user
        
    Returns:
        Cleaned path string
    """
    sanitized, _ = PathSanitizer.sanitize(raw_input)
    return sanitized 