
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
python3 chopper --script=src/js --style=src/scss --html=private/templates src/templates
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
python3 chopper --script=src/js --style=src/scss --html=private/templates src/templates/headline.chopper.html
```

<!--
### Intergration

This can be intergrated with mix to be part of the build process.  Add
this to `webpack.mix.js` somewhere before mix is executed.

``` js

const {spawn} = require('child_process');

const python = spawn('python3', ['chopper.py']);
python.stdout.on('data', function (data) {
  console.log('Pipe data from python script ...');
  dataToSend = data.toString();
  console.log('A', dataToSend)
});
python.stderr.on('data', function(data){
  console.log('START CHOPPER ERROR -----------------------------------------------------')
  console.log()
  console.log(data.toString())
  console.log('END CHOPPER ERROR -------------------------------------------------------')
  console.log()
  throw Error('Chopper error')
})
python.on('close', (code) => {
 console.log(`child process close all stdio with code ${code}`);
  // send data to browser
  // res.send(dataToSend)
  console.log('B', dataToSend)
});

```
-->
