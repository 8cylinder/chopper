
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
- **Type safe**: Full mypy --strict compliance
- **Well tested**: 70 comprehensive tests covering all functionality


## Installation

This is a python package that can be installed with pipx, and it's
only available by checking out the git repo.  The [UV packaging
tool](https://docs.astral.sh/uv/getting-started/installation) is used
to build the package.

To install it globally,

``` Bash
git clone <this repo>
uv build
uv tool install dist/chopper-X.X.X-py3-none-any.whl
```


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
CHOPPER_COMMENTS=true
CHOPPER_WARN=true
CHOPPER_WATCH=true
CHOPPER_INDENT="  "
```

Chopper will automatically search upward from the current directory for
configuration files in this order: `.chopper`, `chopper.conf`, `.env.chopper`,
`.env`

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

# Type checking
uv run mypy src/ --strict

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
- **Edge cases**: Empty files, special characters, large files, unbalanced tags
- **Type safety**: Full mypy --strict compliance

### Build

To make available globally, install the package using `uv tool`.

``` bash
# install editable
uv tool install --editable .

# install standalone
uv build
uv tool install dist/chopper-X.X.X-py3-none-any.whl
    ```
