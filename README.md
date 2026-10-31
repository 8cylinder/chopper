
# Chopper 🚁
*Get to the choppa!* <br><br>


Split a single file into separate files.  This is designed mostly for
writing partials for server side CMSs.

Write server side partials with all their parts in one file.  Js, css
and html are extracted and written to separate files so they can be
then handled by whatever build tool you use, such as webpack.

## Features

- **Single-file components**: Keep HTML, CSS, and JavaScript together
- **Reverse sync**: Update source files when destination files change
  (`--update`)
- **Watch mode**: Automatically process files as they change
- **Security**: Path traversal protection and safe file operations
- **Flexible configuration**: CLI arguments, environment variables, or
  `.env` files
- **Bash completions**: Generate a static completion script with
  `--completions`
- **Type safe**: Full mypy --strict compliance
- **Well tested**: Comprehensive pytest suite covering all functionality


## Installation

This is a python package that can be installed with pipx, and it's
only available by checking out the git repo.  The [UV packaging
tool](https://docs.astral.sh/uv/getting-started/installation) is used
to build the package.

To install it globally,

``` Bash
git clone https://github.com/8cylinder/chopper.git
cd chopper
uv build
uv tool install dist/chopper-X.X.X-py3-none-any.whl
```

For an editable development install, run `make install` (or
`uv tool install --editable --force .`).


## Usage

Given a file in `src/chopper/` called `headline.chopper.html`:

``` html
<style chopper:file="headline.scss">
  h1{
    color: grey;
    & .title{
      font-size: 3rem;
    }
  }
</style>

<script chopper:file="theme/headline.js">
  console.log('This is a log')
</script>

<chopper chopper:file="title.twig">
  <h1 class="title">{{title}}</h1>
</chopper>
```

This command will create three new files:

``` bash
chopper --script=src/js --style=src/scss --html=private/templates src/chopper
```

It will walk through all the files in `src/chopper` and process all
the files that end in `.chopper.html`.  In this case these three files
will be created:

1. `src/scss/headline.scss`
1. `src/js/theme/headline.js`
1. `private/templates/title.twig`

A single file can be passed as the source argument and in that case
the script won't walk the filesystem looking for chopper files.

``` bash
chopper --script=src/js --style=src/scss --html=private/templates src/chopper/headline.chopper.html
```

### Command-line options

``` text
chopper [OPTIONS] SOURCE
```

`SOURCE` is a `.chopper.html` file or a directory that will be searched
recursively.

| Option | Environment variable | Description |
| --- | --- | --- |
| `-s`, `--script-dir DIR` | `CHOPPER_SCRIPT_DIR` | Destination for script files. |
| `-c`, `--style-dir DIR` | `CHOPPER_STYLE_DIR` | Destination for style files. |
| `-m`, `--html-dir DIR` | `CHOPPER_HTML_DIR` | Destination for HTML files. |
| `--comments STYLE` | `CHOPPER_COMMENTS` | Comment style: `server`, `client`, or `none`. |
| `-w`, `--warn` | `CHOPPER_WARN` | Warn instead of overwriting existing files. |
| `-o`, `--overwrite` | `CHOPPER_WARN` | Overwrite differing files on the initial run. |
| `--watch`, `--no-watch` | `CHOPPER_WATCH` | Re-chop files when they change. |
| `--update` | | Interactively sync destination changes back to the source. Requires `--warn`. |
| `--config` | | Print the discovered config file path and exit. |
| `--completions` | | Write bash completions and exit. |
| `--debug` | | Print debug information. |
| `--version` | | Show the version and exit. |
| `-h`, `--help` | | Show help and exit. |

### Reverse Sync (--update)

Chopper supports reverse sync functionality, allowing you to update the source
`*.chopper.html` files when destination files are modified. This is useful when
you edit the generated CSS, JS, or HTML files and want to sync those changes
back to the source.

``` bash
# Check for differences without overwriting (warn mode)
chopper --warn src/chopper -s src/js -c src/css -m src/views

# Interactively update chopper files with destination changes
chopper --warn --update src/chopper -s src/js -c src/css -m src/views
```

When using `--update`, you'll be prompted for each changed file:
- `y` - Update the chopper file with the destination changes
- `n` - Skip this file
- `c` - Cancel the entire operation

**Note:** `--update` requires the `--warn` flag and cannot be used with `--watch`.

### Security

Chopper includes robust security features to prevent path traversal attacks and
ensure safe file operations:

- **Path validation**: All output paths are validated to prevent writing outside
  designated directories
- **Bounded config search**: Configuration file search is limited to 5
  directories upward
- **Safe file operations**: Comprehensive error handling for permissions,
  missing files, and other edge cases

These security measures ensure that chopper can be safely used in automated
build environments.

### .env

Instead of passing the arguments to the command line, they can be set
in a `.env` file.

Example:
``` dotenv
CHOPPER_SOURCE_DIR=src/chopper
CHOPPER_SCRIPT_DIR=src/js
CHOPPER_STYLE_DIR=src/css
CHOPPER_HTML_DIR=src/views
CHOPPER_COMMENTS=server
CHOPPER_WARN=true
CHOPPER_WATCH=true
CHOPPER_INDENT="  "
```

Chopper will automatically search upward from the current directory for
configuration files in this order: `.chopper`, `chopper.conf`, `.env.chopper`,
`.env`

To print the path of the configuration file Chopper would use:

``` bash
chopper --config
```

If no configuration file is found, the command prints an error and exits
with status 1.

### Shell completions

Chopper can install a static bash completion script:

``` bash
chopper --completions
```

The script is written to
`$XDG_DATA_HOME/bash-completion/completions/chopper`, or
`~/.local/share/bash-completion/completions/chopper` when
`XDG_DATA_HOME` is not set.  The command prints the path and the
`source` command needed to enable completions in the current terminal.

Completions require bash 4.4 or newer and bash-completion 2.x.  Chopper
warns when the `bash` on `PATH` is older than 4.4.  On macOS,
`/bin/bash` is version 3.2 and the default shell is zsh, so install a
newer bash (for example with Homebrew) and note that zsh is not
supported.  The unsuffixed `chopper` filename works with
bash-completion, though versions 2.18 and newer prefer `chopper.bash`.

### Dev integration

1. Install chopper globally
2. Edit `package.json` scripts section


### DDev integration

To integrate this into a ddev environment and have it automatically
work for any user that runs the ddev environment the chopper wheel
needs to be available to `.ddev/config.yaml`.

1. Place the `chopper-X.X.X-py3-none-any.whl` file somewhere in your project.
2. In `.ddev/config.yaml`, add `pipx` to `webimage_extra_packages`.
3. Add an `exec:` to `hooks: post-start` in `config.yaml`
4. `pipx install path/to/chopper-X.X.X-py3-none-any.whl`

In `package.json` add the chopper line to the scripts section.  This
will run the chopper watch script in parallel with npm's watch.

``` json
"scripts": {
  "chopper": "bash path/to/chopper-watch.bash watch & npm run watch"
}
```

`ddev npm run chopper`


### Development

``` bash
# Show help
uv run chopper -h

# Run with warn mode (check without overwriting)
uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/ --warn

# use pudb for breakpoint()
export PYTHONBREAKPOINT="pudb.set_trace"
uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/

# Install dependencies
make sync

# Format, lint, type check, and test
make fmt
make lint
make type
make test

# Run every check without changing files
make check

# Type checking
uv run mypy --strict src/

# Code formatting
uv run ruff format

# Linting
uv run ruff check
```

### Testing

``` bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_reverse_sync.py

# Run specific test class or method
uv run pytest tests/test_reverse_sync.py::TestBasicUpdateFlow
uv run pytest tests/test_reverse_sync.py::TestBasicUpdateFlow::test_basic_update_flow_css

# Run tests with coverage (if coverage is installed)
uv run pytest --cov=src/chopper tests/
```

The test suite includes tests for:
- **Core functionality**: File parsing, content extraction, directory handling
- **Reverse sync**: `--warn --update` interactive functionality
- **Security**: Path traversal protection, malicious input handling
- **Error handling**: Permissions, missing files, malformed HTML
- **CLI validation**: Flag combinations, argument validation
- **Base CLI options**: Help, config discovery, and bash completion generation
- **Edge cases**: Empty files, special characters, large files, unbalanced tags

### Build

To make available globally, install the package using `uv tool`.

``` bash
# install editable
make install

# install standalone
uv build
uv tool install dist/chopper-X.X.X-py3-none-any.whl
```
