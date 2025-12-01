
# Chopper 🚁
*Get to the choppa!* <br><br>


Split a single file into separate files.  This is designed mostly for
writing partials for server side CMSs.

Write server side partials with all their parts in one file.  Js, css
and html are extracted and written to separate files so they can be
then handled by whatever build tool you use, such as webpack.

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
python3 chopper --script=src/js --style=src/scss --html=private/templates src/chopper/headline.chopper.html
```

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
```

### Installation

This is a python package that can be installed with pipx, and it's
only available by checking out the git repo.  The [UV packaging
tool](https://docs.astral.sh/uv/getting-started/installation) is used
to build the package.

To install it globally,

``` Bash
git clone <this repo>
uv build
pipx install dist/chopper-X.X.X-py3-none-any.whl
```


### Integration

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
  "chopper": "bash path/to/chopper-watch.bash watch & npm run watch && fg"
}
```

`ddev npm run chopper`


### Development

``` bash
uv run chopper -h

uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/ --dry-run

# use pudb for breakpoint()
export PYTHONBREAKPOINT="pudb.set_trace"; uv run chopper public/chopper/ -s public/js/ -c public/css/ -m public/views/
```

### Testing

Run the test suite to ensure functionality works correctly:

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

The test suite includes comprehensive tests for:
- Core chopper functionality
- Reverse sync (`--warn --update`) functionality
- Error handling and edge cases
- CLI flag validation

### Build

To make available globally, install the package using `uv tool`.

``` bash
# install editable
uv tool install --editable .

# install standalone
uv build
uv tool install dist/chopper-X.X.X-py3-none-any.whl
    ```
