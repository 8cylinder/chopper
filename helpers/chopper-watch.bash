#!/usr/bin/env bash

# shellcheck disable=SC2034  # shellcheck disable=SC2034

project_root=/var/www/html
script_base=resources/js/
style_base=resources/css/
html_base=resources/views/
watch_dir=resources/chopper/
chopper=resources/scripts/chopper.py

initializeANSI()
{
    esc=""

    # blackf="${esc}[30m"
    redf="${esc}[31m"
    # greenf="${esc}[32m"
    yellowf="${esc}[33m"
    # bluef="${esc}[34m"
    # purplef="${esc}[35m"
    # cyanf="${esc}[36m"
    whitef="${esc}[37m"

    # blackb="${esc}[40m"
    redb="${esc}[41m"
    # greenb="${esc}[42m"
    # yellowb="${esc}[43m"
    # blueb="${esc}[44m"
    # purpleb="${esc}[45m"
    # cyanb="${esc}[46m"
    # whiteb="${esc}[47m"

    boldon="${esc}[1m"
    boldoff="${esc}[22m"
    # italicson="${esc}[3m"
    # italicsoff="${esc}[23m"
    # ulon="${esc}[4m"
    # uloff="${esc}[24m"
    # invon="${esc}[7m"
    # invoff="${esc}[27m"

    reset="${esc}[0m"
}
initializeANSI

cd $project_root || exit

cmd="python3 $chopper
             --comments
             --script-dir $script_base
             --style-dir $style_base
             --html-dir $html_base"

# On first run, generate all, and if any files are different, stop,
# since that means that someone edited a destination file and that
# needs investigation.
if ! $cmd --warn --dry-run $watch_dir; then
    echo "${redb}${whitef}${boldon}chopper-watch:${boldoff} files are different, exiting.${reset}"
    echo "${redf}Run this command if you want to overwrite the dest file:${reset}"
    single_line=$(echo $cmd | sed -e 's/ */ /' | tr -d '\n')
    echo "${yellowf}${single_line} ${watch_dir}CHOPPER-FILE${reset}"
    exit
fi

inotifywait -mrq -e close_write,moved_to,create,modify $watch_dir |
    while read -r dir _events name; do
        if [[ $name == *chopper.html ]]; then
            echo
            $cmd "$dir$name"
        fi
    done
