#!/bin/bash

script_path=$(dirname $(realpath "$0"))
project_path=$(dirname "$script_path")

cd $script_path
../open-stage-control/build-config.sh
./uninstall.sh

declare -a services=("ca.parquette.lighting.openstagecontrol" "ca.parquette.lighting.server")

mkdir -p ~/Library/LaunchAgents

for service_name in "${services[@]}"
do
    # if [ -f ~/Library/LaunchAgents/$service_name.plist ]; then
    #     echo "Unload and delete old plist ~/Library/LaunchAgents/$service_name.plist"
    #     launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/$service_name.plist 2> /dev/null
    #     rm ~/Library/LaunchAgents/$service_name.plist
    # fi
    echo "Creating ~/Library/LaunchAgents/$service_name.plist"
    contents="$(cat $service_name.plist)"
    output=$contents
    output="${contents//\/Users\/user/$HOME}"
    output="${output//\/ProjectPath/$project_path}"
    echo "$output" >> ~/Library/LaunchAgents/$service_name.plist
done

read -p "Do you want to load and start services now? (y/n) " yn
case $yn in
    [Yy]* )
    	for service_name in "${services[@]}"
    	do
    		launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$service_name.plist
    		launchctl kickstart gui/$(id -u)/$service_name
    	done
esac
