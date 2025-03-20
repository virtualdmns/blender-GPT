#!/usr/bin/env python3
import os
import shutil
import zipfile
from pathlib import Path

def package_addon():
    # Get the script's directory
    script_dir = Path(__file__).parent.absolute()
    addon_dir = script_dir / "addon_blender_gpt"
    
    # Create a clean build directory
    build_dir = script_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    
    # Create addon directory in build
    build_addon_dir = build_dir / "addon_blender_gpt"
    build_addon_dir.mkdir()
    
    # Copy all Python files and directories
    for item in addon_dir.glob("**/*"):
        if item.is_file():
            # Skip __pycache__ and .pyc files
            if "__pycache__" not in str(item) and not str(item).endswith(".pyc"):
                # Create the directory structure in build
                relative_path = item.relative_to(addon_dir)
                target_path = build_addon_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_path)
                print(f"Copied: {relative_path}")
    
    # Create zip file
    version = "1.1.8"  # Update this based on your version
    zip_name = f"blender_gpt_v{version}.zip"
    zip_path = script_dir / zip_name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add the package directory
        for item in build_addon_dir.rglob("*"):
            if item.is_file():
                arcname = f"addon_blender_gpt/{item.relative_to(build_addon_dir)}"
                zipf.write(item, arcname)
                print(f"Added to zip: {arcname}")
    
    print(f"\nPackage created successfully: {zip_name}")
    print(f"Size: {os.path.getsize(zip_path) / 1024:.1f} KB")
    
    # Clean up build directory
    shutil.rmtree(build_dir)

if __name__ == "__main__":
    package_addon() 