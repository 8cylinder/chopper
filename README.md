
# 🚁 Chopper


### Overview

Write server side partials with all their parts in one file.  Js, css
and html are extracted and written to seperate files so they can be
then handled by whatever build tool you use such as webpack.

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

<script chopper:file="theme/{NAME}.js">
  console.log('This is a log')
</script>

<chopper chopper:file="title.twig">
  <h1 class="title">{{title}}</h1>
</chopper>
```

This command will create three new files:

``` bash
python3 chopper --script=src/js --style=src/scss --html=private/templates src/chopper
```

It will walk through all the files in `src/chopper` and process all
the files that end in `.chopper.html`.  In this case these three files
will be created:

1. `src/scss/headline.scss`
1. `src/js/theme/headline.js`
1. `private/templates/title.twig`

If `{NAME}` is used in the `chopper:file` attribute, it will be
replaced with the source file's base name.  In this case it would be
`headline`.  The `.chopper.html` part of the file name is removed.

A single file can be passed as the source argument and in that case
the script won't walk the filesystem looking for chopper files.

``` bash
python3 chopper --script=src/js --style=src/scss --html=private/templates src/chopper/headline.chopper.html
```


### Intergration

`chopper-watch.bash`

``` bash
#!/usr/bin/env bash

watch_dir=resources/chopper/
cd /var/www/html || exit

cmd='python3 resources/scripts/chopper.py
             --comments
             --script-dir resources/js/
             --style-dir resources/css/
             --html-dir resources/views/'

$cmd --warn $watch_dir

if [[ $1 == 'watch' ]]; then
    inotifywait -mrq -e close_write,moved_to,create,modify $watch_dir |
        while read -r dir events name; do
            echo
            $cmd $dir$name
        done
else
    echo "Add command 'watch' to watch for changes."
fi
```

In `package.json` add the chopper line to the scripts section.  This
will run the chopper watch script in parallel with npm's watch.

``` json
"scripts": {
  "chopper": "bash chopper-watch.bash watch & npm run watch && fg"
}
```

`npm run chopper`

