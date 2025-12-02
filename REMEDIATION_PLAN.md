# Chopper Code Remediation Plan

This document outlines a systematic approach to address security vulnerabilities, bugs, and improvements identified in the Chopper codebase during the comprehensive code review.

## Executive Summary

**Critical Issues Found**: 2 security vulnerabilities, 4 major bugs
**Priority**: Security fixes must be addressed immediately before any production use
**Estimated Effort**: 3-5 days for critical fixes, 2-3 weeks for complete remediation

---

## 🔴 PHASE 1: CRITICAL SECURITY FIXES (IMMEDIATE)

**Priority**: P0 - Must be completed before any production deployment
**Estimated Time**: 1-2 days
**Risk Level**: HIGH - Potential for system compromise

### Task 1.1: Fix Path Traversal Vulnerability
**Files**: `src/chopper/chopper.py:248`, `src/chopper/chopper.py:315`

**Issue**: No validation on `chopper:file` attribute allows directory traversal attacks

**Implementation Steps**:
1. Create path validation function:
   ```python
   def validate_output_path(file_path: str, base_path: str) -> bool:
       """Validate that output path stays within base directory."""
       try:
           resolved = Path(base_path, file_path).resolve()
           base_resolved = Path(base_path).resolve()
           return resolved.is_relative_to(base_resolved)
       except (ValueError, OSError):
           return False
   ```

2. Add validation in `chop()` function before processing blocks
3. Add validation in `new_or_overwrite_file()` before file creation
4. Log and reject any attempts to write outside designated directories

**Acceptance Criteria**:
- [ ] Cannot write files outside of configured directories
- [ ] Paths like `../../../etc/passwd` are rejected
- [ ] Valid relative paths still work correctly
- [ ] Error messages don't expose internal paths

**Testing**:
- [ ] Test with malicious paths: `../`, `../../etc/passwd`, `/tmp/malicious`
- [ ] Test with valid relative paths: `subfolder/file.css`
- [ ] Test with absolute paths (should be rejected)

### Task 1.2: Secure Environment Variable Loading
**Files**: `src/chopper/chopper.py:36-40`

**Issue**: Unsafe upward directory traversal for config files

**Implementation Steps**:
1. Limit search depth to reasonable maximum (e.g., 5 levels up)
2. Handle missing config files gracefully (don't raise exceptions)
3. Add validation for config file contents
4. Consider security implications of loading arbitrary .env files

**Implementation**:
```python
def find_file_upwards(start_dir: Path, target_files: list[str],
                     max_depth: int = 5) -> Path | None:
    """Find config file with bounded upward search."""
    current_dir = start_dir.resolve()
    depth = 0

    while current_dir != current_dir.parent and depth < max_depth:
        for target_file in target_files:
            target_path = current_dir / target_file
            if target_path.exists() and target_path.is_file():
                return target_path
        current_dir = current_dir.parent
        depth += 1
    return None
```

**Acceptance Criteria**:
- [ ] Search limited to 5 directories up maximum
- [ ] No exceptions thrown for missing config files
- [ ] Only loads files, not directories or special files
- [ ] Logs which config file is being used

---

## 🟠 PHASE 2: MAJOR BUG FIXES (HIGH PRIORITY)

**Priority**: P1 - Should be completed within 1 week
**Estimated Time**: 2-3 days

### Task 2.1: Fix Symlink Detection Bug
**Files**: `src/chopper/chopper.py:210`

**Issue**: `os.path.islink()` called on filename instead of full path

**Implementation**:
```python
# Replace line 210
full_path = Path(root, filename)
if not full_path.is_symlink() and filename.endswith(CHOPPER_NAME):
    chopper_files.append(str(full_path))
```

**Testing**:
- [ ] Create symlinked .chopper.html files
- [ ] Verify symlinks are properly detected and skipped
- [ ] Verify regular files are processed normally

### Task 2.2: Implement Dry-Run Functionality
**Files**: `src/chopper/chopper.py:43`, `src/chopper/cli.py:89`

**Issue**: `DRYRUN` global variable never set, dry-run mode broken

**Implementation**:
1. Remove global variable pattern
2. Pass `dry_run` parameter through function calls
3. Update all file write operations to respect dry-run mode

**Function Signature Changes**:
```python
def chop(source: str, types: dict[str, str], comments: CommentType,
         warn: bool = False, dry_run: bool = False) -> bool:

def new_or_overwrite_file(block: ParsedData, log: ChopperLog,
                         warn: bool = False, last: bool = False,
                         dry_run: bool = False) -> bool:
```

### Task 2.3: Fix Error Handling Logic
**Files**: `src/chopper/chopper.py:325-345`

**Issue**: Inconsistent error handling and confusing control flow

**Implementation**:
1. Restructure error handling logic for clarity
2. Ensure consistent return values
3. Improve error messages and logging
4. Add proper exception handling for file operations

### Task 2.4: Remove Dead Code
**Files**: Multiple locations throughout codebase

**Implementation**:
- [ ] Remove commented code blocks (lines 69-70, 122-123, 139-159, 262-269)
- [ ] Remove unused imports (`pprint as pp`)
- [ ] Clean up development debugging code
- [ ] Update version control to clean history if needed

---

## 🟡 PHASE 3: CODE QUALITY IMPROVEMENTS (MEDIUM PRIORITY)

**Priority**: P2 - Should be completed within 2 weeks
**Estimated Time**: 3-5 days

### Task 3.1: Standardize Path Handling
**Files**: Throughout codebase

**Objective**: Use `pathlib.Path` consistently instead of mixing with `os.path`

**Implementation Steps**:
1. Audit all path operations in codebase
2. Replace `os.path.join()` with `Path / Path` operations
3. Replace `os.path.exists()` with `Path.exists()`
4. Update function signatures to use `Path` objects

**Example Refactoring**:
```python
# Before
partial_file = Path(os.path.join(block.base_path, block.path))

# After
partial_file = Path(block.base_path) / block.path
```

### Task 3.2: Centralize Configuration Constants
**Files**: Create new `src/chopper/constants.py`

**Implementation**:
```python
# constants.py
from enum import Enum
from typing import NamedTuple

CHOPPER_FILE_EXTENSION = ".chopper.html"
MAX_CONFIG_SEARCH_DEPTH = 5
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

class CommentStyles(NamedTuple):
    open: str
    close: str

COMMENT_STYLES = {
    "php": CommentStyles("/* ", " */"),
    "html": CommentStyles("<!-- ", " -->"),
    # ... etc
}
```

### Task 3.3: Improve Data Classes
**Files**: `src/chopper/chopper.py:139-151`

**Issue**: Mutable dataclass fields modified after creation

**Implementation**:
1. Make ParsedData immutable where possible
2. Use factory methods for creating instances
3. Separate mutable state from immutable data

### Task 3.4: Add Complete Type Hints
**Files**: All Python files

**Implementation**:
1. Add missing type hints to all functions
2. Add return type annotations
3. Use `typing.Protocol` for duck typing where appropriate
4. Ensure mypy passes with strict settings

---

## 🟡 PHASE 4: ERROR HANDLING & PERFORMANCE (MEDIUM PRIORITY)

**Priority**: P2 - Should be completed within 2 weeks
**Estimated Time**: 2-3 days

### Task 4.1: Implement Comprehensive Input Validation
**Files**: `src/chopper/chopper.py`

**Implementation**:
1. Add HTML content validation before parsing
2. Implement file size limits
3. Validate file extensions and content types
4. Add encoding validation (ensure UTF-8)

**Validation Functions**:
```python
def validate_chopper_file(file_path: Path) -> tuple[bool, str]:
    """Validate chopper file is safe to process."""
    if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
        return False, f"File too large: {file_path}"

    try:
        content = file_path.read_text(encoding='utf-8')
        # Add HTML validation logic
        return True, ""
    except UnicodeDecodeError:
        return False, f"File not valid UTF-8: {file_path}"
```

### Task 4.2: Improve Watch Mode Error Handling
**Files**: `src/chopper/cli.py:171-182`

**Implementation**:
1. Handle additional exceptions beyond KeyboardInterrupt
2. Add logging for watch mode events
3. Implement graceful restart on errors
4. Add file system event debugging

### Task 4.3: Optimize Performance
**Files**: `src/chopper/chopper.py:205-216`

**Implementation**:
1. Remove unnecessary `os.stat()` calls
2. Implement file streaming for large files
3. Add caching for repeated operations
4. Optimize HTML parsing for large files

---

## 🔵 PHASE 5: TESTING & DOCUMENTATION (LOW PRIORITY)

**Priority**: P3 - Should be completed within 3 weeks
**Estimated Time**: 5-7 days

### Task 5.1: Implement Testing Framework
**Files**: Create `tests/` directory structure

**Test Structure**:
```
tests/
├── unit/
│   ├── test_chopper.py
│   ├── test_cli.py
│   └── test_parser.py
├── integration/
│   ├── test_file_processing.py
│   └── test_watch_mode.py
├── security/
│   └── test_path_traversal.py
└── fixtures/
    ├── valid_chopper_files/
    ├── invalid_chopper_files/
    └── malicious_inputs/
```

**Testing Priorities**:
1. **Security Tests**: Path traversal, malicious inputs
2. **Core Functionality**: File parsing, content extraction
3. **Edge Cases**: Empty files, malformed HTML, large files
4. **Integration Tests**: End-to-end workflow testing

### Task 5.2: Implement Logging Framework
**Files**: Throughout codebase

**Implementation**:
1. Replace print statements with proper logging
2. Add configurable log levels
3. Implement structured logging for debugging
4. Add performance metrics logging

**Example Implementation**:
```python
import logging

logger = logging.getLogger(__name__)

def chop(source: str, ...) -> bool:
    logger.info(f"Processing chopper file: {source}")
    # ... existing logic
    logger.debug(f"Extracted {len(data)} blocks from {source}")
```

### Task 5.3: Documentation Improvements
**Files**: Update README.md, add new documentation

**Documentation Tasks**:
- [ ] Security best practices guide
- [ ] Comprehensive API documentation
- [ ] Integration examples for different CMSs
- [ ] Troubleshooting guide
- [ ] Contributing guidelines

---

## Implementation Guidelines

### Development Workflow
1. **Create feature branch** for each phase
2. **Write tests first** for security-critical changes
3. **Run security tests** before merging any changes
4. **Update documentation** with each change
5. **Use code review** for all security-related changes

### Testing Requirements
- All security fixes must have accompanying tests
- Minimum 80% code coverage for new code
- Integration tests for all major workflows
- Performance benchmarks for large file processing

### Security Review Process
1. **Threat modeling** for any new features
2. **Penetration testing** for path handling changes
3. **Code review** by security-focused developer
4. **Static analysis** with security-focused tools

---

## Success Metrics

### Phase 1 Success Criteria
- [ ] All security vulnerabilities resolved
- [ ] Security test suite passes
- [ ] No path traversal attacks possible
- [ ] Safe configuration file loading

### Phase 2 Success Criteria
- [ ] All major bugs fixed
- [ ] Dry-run functionality works correctly
- [ ] Symlink handling works as expected
- [ ] Clean codebase with no dead code

### Phase 3 Success Criteria
- [ ] Consistent code style throughout
- [ ] All paths use pathlib consistently
- [ ] Complete type coverage
- [ ] Mypy passes with strict settings

### Final Success Criteria
- [ ] Comprehensive test coverage (>90%)
- [ ] All security tests pass
- [ ] Performance benchmarks met
- [ ] Documentation complete and accurate
- [ ] Ready for production deployment

---

## Risk Mitigation

### Security Risks
- **Code Review**: All security changes require peer review
- **Testing**: Comprehensive security test suite
- **Monitoring**: Runtime security monitoring in production
- **Updates**: Regular security dependency updates

### Implementation Risks
- **Backwards Compatibility**: Maintain API compatibility where possible
- **Performance**: Benchmark before/after performance changes
- **Reliability**: Extensive testing of error handling paths
- **Maintainability**: Clear documentation for all changes

---

## Timeline Summary

| Phase | Priority | Duration | Dependencies |
|-------|----------|----------|--------------|
| Phase 1: Security | P0 | 1-2 days | None |
| Phase 2: Major Bugs | P1 | 2-3 days | Phase 1 complete |
| Phase 3: Code Quality | P2 | 3-5 days | Phase 2 complete |
| Phase 4: Performance | P2 | 2-3 days | Phase 3 complete |
| Phase 5: Testing/Docs | P3 | 5-7 days | All phases |

**Total Estimated Time**: 3-5 weeks for complete remediation
**Minimum Viable Fix**: Phases 1-2 (1 week) for basic production readiness