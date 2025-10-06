#!/bin/bash

declare -a services=("ca.parquette.lighting.openstagecontrol" "ca.parquette.lighting.server")

for service_name in "${services[@]}"
do
    if [ -f ~/Library/LaunchAgents/$service_name.plist ]; then
        echo "Unload and delete old plist ~/Library/LaunchAgents/$service_name.plist"
        launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/$service_name.plist 2> /dev/null
        rm ~/Library/LaunchAgents/$service_name.plist
    fi
done