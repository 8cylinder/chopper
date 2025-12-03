# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Chopper is a Python CLI tool that splits single files containing embedded HTML,
CSS, and JavaScript into separate component files. It's designed for server-side
CMS workflows where developers want to write partials with all their parts in
one file, then extract components for build tools like webpack.

## Development Commands

### Installation and Setup

```bash
# Clone and build
git clone <repo>
uv build

# Global installation
pipx install dist/chopper-X.X.X-py3-none-any.whl

# Development installation (editable)
uv tool install --editable .
```

### Development Workflow

```bash
# Run with help
uv run chopper -h

# Example development run with dry-run
uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/ --dry-run

# Debug mode with pudb
export PYTHONBREAKPOINT="pudb.set_trace"
uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/
```

### Writing code

- `pathlib.Path` is preferred over `os.path`.
- lines should not exceed 80 characters for all files including markdown files.
- When finishing a task, run `ruff format`.
- Use type hinting for all code written.
- Follow python best practices.
- When making changes run the tests to ensure functioning code.

### Code Quality

```bash
# Type checking
uv run mypy src/

# Linting
uv run ruff check

# Format code
uv run ruff format
```

## Architecture

### Core Components

- **`src/chopper/cli.py`**: CLI interface using Click framework with environment
  variable support
- **`src/chopper/chopper.py`**: Core parsing and file splitting logic
- **`ChopperParser`** (in chopper.py): HTML parser that extracts `<script>`,
  `<style>`, and `<chopper>` tags with `chopper:file` attributes
- **File watching**: Uses `watchdog` library for real-time file monitoring

### Key Concepts

**Input Format**: Files ending in `.chopper.html` with special attributes:

```html

<style chopper:file="headline.scss">/* CSS content */</style>
<script chopper:file="theme/headline.js">// JS content</script>
<chopper chopper:file="title.twig"><!-- HTML content --></chopper>
```

**Output**: Creates separate files in specified directories:

- Scripts → `--script-dir` / `CHOPPER_SCRIPT_DIR`
- Styles → `--style-dir` / `CHOPPER_STYLE_DIR`
- HTML → `--html-dir` / `CHOPPER_HTML_DIR`

### Configuration

**Environment Variables** (can be set in `.env` file):

```
CHOPPER_SOURCE_DIR=src/chopper
CHOPPER_SCRIPT_DIR=src/js
CHOPPER_STYLE_DIR=src/css
CHOPPER_HTML_DIR=src/views
CHOPPER_COMMENTS=true
CHOPPER_WARN=true
CHOPPER_WATCH=true
```

The tool automatically searches upwards for configuration files in this order:

1. `.chopper`
2. `chopper.conf`
3. `.env.chopper`
4. `.env`

### Comment Types

Supports various comment types for generated files:

- `php`: `/* comment */`
- `html`: `<!-- comment -->`
- `twig`: `{# comment #}`
- `antlers`: `{{# comment #}}`
- `js`/`css`: `/* comment */`
- `none`: No comments (default)

## Dependencies

**Runtime**:

- `click>=8` - CLI framework
- `python-dotenv>=1.0.1` - Environment variable loading
- `typing-extensions>=4.12.2` - Type system extensions
- `watchdog>=6.0.0` - File system monitoring

**Development**:

- `ipython>=8.30.0` - Enhanced REPL
- `mypy>=1.13.0` - Static type checking
- `pudb>=2024.1.3` - Visual debugger
- `ruff>=0.9.4` - Fast Python linter/formatter

## Testing

**Note**: This project currently has no formal testing framework set up. Testing
is done manually using the sample files in the `public/` directory.

## File Structure

```
src/chopper/
├── __init__.py           # Package initialization
├── cli.py               # Click-based CLI interface
└── chopper.py           # Core file parsing and splitting logic

public/                   # Sample/test files
├── chopper/             # Source .chopper.html files
├── css/                 # CSS output examples
├── js/                  # JavaScript output examples
└── views/               # HTML template output examples
```

## Integration Notes

**DDEV Integration**: Can be integrated into DDEV environments by:

1. Adding `pipx` to `webimage_extra_packages` in `.ddev/config.yaml`
2. Installing via `hooks: post-start` execution
3. Running in parallel with npm scripts using watch mode

**Build System**: Uses `hatchling` as the build backend with `uv` as the package
manager. Supports Python 3.11+.
