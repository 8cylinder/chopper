#!/usr/bin/env bash

project_root=/var/www/html
script_base=resources/js/
style_base=resources/css/
html_base=resources/views/
watch_dir=resources/chopper/
chopper=resouces/scripts/chopper.py

cd $project_root || exit

cmd='python3 $chopper
             --comments
             --script-dir $script_base
             --style-dir $style_base
             --html-dir $html_base'

# On first run, generate all, and if any files are different, stop,
# since that means that someone edited a destination file and that
# needs investigation.
if ! $cmd --warn $watch_dir; then
    echo 'chopper-watch: files are different, exiting.'
    exit
fi

if [[ $1 == 'watch' ]]; then
    inotifywait -mrq -e close_write,moved_to,create,modify $watch_dir |
        while read -r dir events name; do
            echo
            $cmd $dir$name
        done
else
    echo "Add command 'watch' to watch for changes."
fi
