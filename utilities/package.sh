#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Run the packaging script
python3 package_addon.py

# Make the zip file executable
chmod +x blender_gpt_*.zip

mv blender_gpt_*.zip ../

echo "Packaging complete!" 