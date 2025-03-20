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

# Create temp directory for zip
TEMP_DIR="/tmp/blendergpt_temp"
mkdir -p "$TEMP_DIR"

# Create zip file
echo "Creating addon zip file..."
cd "$PARENT_DIR"
ZIP_FILE="$TEMP_DIR/addon_blender_gpt.zip"
rm -f "$ZIP_FILE"
zip -r "$ZIP_FILE" addon_blender_gpt/

# Remove existing BlenderGPT addon if it exists
echo "Removing existing BlenderGPT addon..."
rm -rf "$BLENDER_ADDONS_DIR/addon_blender_gpt"
sleep 2  # Wait for filesystem operations to complete

# Start Blender in background mode to install addon
echo "Installing BlenderGPT addon..."
/Applications/Blender.app/Contents/MacOS/Blender --background --python-expr "import bpy; bpy.ops.preferences.addon_install(filepath='$ZIP_FILE'); bpy.ops.preferences.addon_enable(module='addon_blender_gpt'); bpy.ops.wm.save_userpref()"

# Wait for addon installation to complete
echo "Waiting for addon installation to complete..."
sleep 3

# Clean up temp files
echo "Cleaning up..."
rm -rf "$TEMP_DIR"

# Wait before starting Blender
echo "Preparing to start Blender..."
sleep 2

# Start Blender normally
echo "Starting Blender..."
open -a "Blender"

echo "Done! Blender should now be running with the updated BlenderGPT addon." 