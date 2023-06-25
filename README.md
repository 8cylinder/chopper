
# Chopper


### Overview

Write server side partials with all their parts in one file.  Js, css and html are extracted and written to seperate files so they can be then handled by whatever build tool you use such as webpack.

Given a file in `src/templates` called `headline.chopper.html`:

```
<style chopper:file="headline.scss">
  h1{
    color: grey;
    & .title{
      font-size: 3rem;
    }
  }
</style>

<script chopper:file="site.js">
  console.log('This is a log')
</script>

<chopper chopper:file="title.twig">
  <h1 class="title">{{title}}</h1>
</chopper>
```

This command will create three new files:

```
python3 chopper --script=src/js --style=src/scss --html=private/templates src/templates
```

It will walk through all the files in `src/templates` and process all the files that end in `.chopper.html`.  In this case these three files will be created:

1. `src/scss/headline.scss`
1. `src/js/site.js`
1. `private/templates/title.twig`


### Intergration

This can be intergrated with mix
