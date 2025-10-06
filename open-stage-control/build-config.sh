#!/bin/bash

script_path=$(dirname $(realpath "$0"))
project_path=$(dirname "$script_path")
cd $script_path

echo "Building new config script for open stage control"
contents="$(cat $project_path/open-stage-control/server-template.config)"
output=$contents
output="${output//\/ProjectPath/$project_path}"
rm $project_path/open-stage-control/server.config
echo "$output" >> $project_path/open-stage-control/server.config
