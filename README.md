
# Chopper 🚁
*Get to the choppa!* <br><br>


Split a single file into seperate files.  This is designed mostly for
writing partials for server side CMSs.

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

<script chopper:file="theme/headline.js">
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

A single file can be passed as the source argument and in that case
the script won't walk the filesystem looking for chopper files.

``` bash
python3 chopper --script=src/js --style=src/scss --html=private/templates src/chopper/headline.chopper.html
```


### Intergration

Intergration with ddev and laravel mix.

In `.ddev/config.yaml`, add `inotify-tools` to `webimage_extra_packages`.

DDev needs to be able to access chopper-watch.bash and chopper.py from inside the container.  Create a dir somewhere in your project and copy `chopper-watch.bash` and `chopper.py` to it.

Edit the variables in the top of `chopper-watch.bash` to point to the various locations that it needs.

In `package.json` add the chopper line to the scripts section.  This
will run the chopper watch script in parallel with npm's watch.

``` json
"scripts": {
  "chopper": "bash path/to/chopper-watch.bash watch & npm run watch && fg"
}
```

`ddev npm run chopper`

