#!/bin/bash

# Kill any running Blender processes
echo "Killing existing Blender processes..."
pkill -f "Blender.app"

# Wait longer for processes to fully terminate
echo "Waiting for Blender to fully close..."
sleep 3

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get the parent directory of the script
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Path to Blender's addons directory
BLENDER_ADDONS_DIR="$HOME/Library/Application Support/Blender/4.3/scripts/addons"

# Ensure addons directory exists
mkdir -p "$BLENDER_ADDONS_DIR"

# Remove existing BlenderGPT addon if it exists
echo "Removing existing BlenderGPT addon..."
rm -f "$BLENDER_ADDONS_DIR/BlenderGPT.py"
sleep 1  # Brief pause for filesystem

# Copy BlenderGPT.py directly into addons directory
echo "Installing BlenderGPT addon..."
cp "$PARENT_DIR/BlenderGPT.py" "$BLENDER_ADDONS_DIR/"

# Start Blender in background mode to enable the addon
echo "Enabling BlenderGPT addon..."
/Applications/Blender.app/Contents/MacOS/Blender --background --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='BlenderGPT'); bpy.ops.wm.save_userpref()"

# Wait briefly for operation to finish
sleep 2

# Start Blender normally
echo "Starting Blender..."
open -a "Blender"

echo "Done! Blender should now be running with the updated BlenderGPT addon."