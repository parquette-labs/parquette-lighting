#!/bin/bash

# Pass -y to skip the interactive "load and start services?" prompt — used
# by the deploy.py script for non-interactive remote installs.
ASSUME_YES=0
while getopts "y" opt; do
    case $opt in
        y) ASSUME_YES=1 ;;
        *) echo "Usage: $0 [-y]" >&2; exit 1 ;;
    esac
done

script_path=$(dirname $(realpath "$0"))
project_path=$(dirname "$script_path")

cd $script_path
../open-stage-control/build-config.sh

# Install custom Open Stage Control branding (disco-ball favicon, apple-touch
# icon, and web manifest) into the app bundle. OSC serves these from its own
# app directory rather than from the session, so they are copied in here on
# every install and are overwritten whenever Open Stage Control itself is
# updated — re-run this script after updating OSC to reapply.
osc_app="/Applications/open-stage-control.app/Contents/Resources/app"
osc_branding="$project_path/open-stage-control/branding"
if [ -d "$osc_app/assets" ]; then
    echo "Installing Open Stage Control branding (favicon, logo, manifest)"
    [ -f "$osc_branding/favicon.png" ] && cp "$osc_branding/favicon.png" "$osc_app/assets/favicon.png"
    [ -f "$osc_branding/logo.png" ] && cp "$osc_branding/logo.png" "$osc_app/assets/logo.png"
    [ -f "$osc_branding/manifest.webmanifest" ] && cp "$osc_branding/manifest.webmanifest" "$osc_app/assets/manifest.webmanifest"
    osc_index="$osc_app/client/index.html"
    if [ -f "$osc_index" ] && ! grep -q 'rel="manifest"' "$osc_index"; then
        echo "  linking manifest into client/index.html"
        perl -0pi -e 's{(<link rel="shortcut icon"[^>]*>)}{$1\n    <link rel="manifest" href="/__APP_DIR__/assets/manifest.webmanifest"/>}' "$osc_index"
    fi
else
    echo "Open Stage Control app not found at $osc_app; skipping branding install"
fi

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

if [ "$ASSUME_YES" -eq 1 ]; then
    yn="y"
else
    read -p "Do you want to load and start services now? (y/n) " yn
fi
case $yn in
    [Yy]* )
    	for service_name in "${services[@]}"
    	do
    		launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$service_name.plist
    		launchctl kickstart gui/$(id -u)/$service_name
    	done
esac
