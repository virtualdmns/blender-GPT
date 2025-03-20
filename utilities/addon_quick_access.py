import bpy
import addon_utils
import os
import subprocess
import shutil
from bpy.types import Panel, Operator, PropertyGroup, AddonPreferences
from bpy.props import StringProperty, IntProperty, PointerProperty

bl_info = {
    "name": "addon_quick_access",
    "author": "virtualdmns",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Properties > Scene > Add-ons",
    "description": "Quick access to manage selected Blender add-ons",
    "category": "System",
}

# PropertyGroup for addon items in both lists, with editable source path
class ADDONQUICK_AddonItem(bpy.types.PropertyGroup):
    name: StringProperty()
    source_path: StringProperty(
        name="Source Path",
        description="Path to the add-on's source file or folder for reinstalling",
        default="",
        subtype='FILE_PATH'
    )

# Properties for the addon
class ADDONQUICK_Properties(PropertyGroup):
    addon_path: StringProperty(
        name="Add-on Path",
        description="Path to the add-on folder or Python file",
        default="",
        subtype='FILE_PATH'
    )

# Operator to refresh the addons list
class ADDONQUICK_OT_RefreshAddons(Operator):
    bl_idname = "addonquick.refresh_addons"
    bl_label = "Refresh Add-ons"
    bl_description = "Refresh the list of add-ons"

    def execute(self, context):
        addon_utils.modules(refresh=True)
        self.report({'INFO'}, "Add-ons list refreshed")
        print("Add-ons list refreshed.")
        return {'FINISHED'}

# Operator to install addon from disk
class ADDONQUICK_OT_InstallAddon(Operator):
    bl_idname = "addonquick.install_addon"
    bl_label = "Install Add-on"
    bl_description = "Install an add-on from disk"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.window_manager.addonquick_props
        addon_path = props.addon_path

        if not addon_path or not os.path.exists(addon_path):
            self.report({'ERROR'}, "Please select a valid add-on file or folder")
            print(f"Installation failed: Invalid or missing add-on path: {addon_path}")
            return {'CANCELLED'}

        # Determine addon name and target path
        if os.path.isfile(addon_path):
            addon_name = os.path.splitext(os.path.basename(addon_path))[0]
            target_path = os.path.join(bpy.utils.user_resource('SCRIPTS', path="addons"), addon_name + ".py")
        else:
            addon_name = os.path.basename(addon_path)
            target_path = os.path.join(bpy.utils.user_resource('SCRIPTS', path="addons"), addon_name)

        # Copy the addon to the target path
        print(f"Installing add-on: {addon_name} from {addon_path} to {target_path}")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        if os.path.exists(target_path):
            if os.path.isfile(target_path):
                os.remove(target_path)
            else:
                shutil.rmtree(target_path)
            print(f"Overwriting existing add-on at: {target_path}")

        if os.path.isfile(addon_path):
            shutil.copy2(addon_path, target_path)
        else:
            shutil.copytree(addon_path, target_path)

        # Refresh addon list
        addon_utils.modules(refresh=True)
        print("Refreshed add-on list after installation.")

        # Enable the addon
        try:
            addon_utils.enable(addon_name, default_set=True)
            self.report({'INFO'}, f"Successfully installed and enabled add-on: {addon_name}")
            print(f"Successfully installed and enabled add-on: {addon_name}")
        except Exception as e:
            self.report({'WARNING'}, f"Add-on installed but couldn't be enabled: {str(e)}")
            print(f"Add-on installed but couldn't be enabled: {str(e)}")

        # Add to available addons (without setting source path automatically)
        preferences = context.preferences.addons["addon_quick_access"].preferences
        for item in preferences.available_addons:
            if item.name == addon_name:
                print(f"Add-on {addon_name} already in available list, skipping addition.")
                break
        else:
            item = preferences.available_addons.add()
            item.name = addon_name
            item.source_path = ""  # Source path will be set manually in preferences
            print(f"Added new add-on to available list: {addon_name}")

        return {'FINISHED'}

# Operator to run a bash script
class ADDONQUICK_OT_RunBashScript(Operator):
    bl_idname = "addonquick.run_bash_script"
    bl_label = "Run Bash Script"
    bl_description = "Execute a specified bash script"

    def execute(self, context):
        script_path = context.preferences.addons["addon_quick_access"].preferences.bash_script_path
        if not script_path or not os.path.isfile(script_path):
            self.report({'ERROR'}, "No valid bash script path set in preferences")
            print(f"No valid bash script path set: {script_path}")
            return {'CANCELLED'}
        try:
            subprocess.run(["bash", script_path], check=True)
            self.report({'INFO'}, "Bash script executed successfully")
            print("Bash script executed successfully.")
        except subprocess.CalledProcessError as e:
            self.report({'ERROR'}, f"Error executing script: {str(e)}")
            print(f"Error executing script: {str(e)}")
        return {'FINISHED'}

# Operator to fully reinstall selected addons
class ADDONQUICK_OT_ManageSelectedAddons(Operator):
    bl_idname = "addonquick.manage_selected_addons"
    bl_label = "Reinstall"
    bl_description = "Fully remove, reinstall, and activate selected add-ons"

    def execute(self, context):
        preferences = context.preferences.addons["addon_quick_access"].preferences
        selected_addons = [(item.name, item.source_path) for item in preferences.selected_addons if item.name != "addon_quick_access"]

        if not selected_addons:
            self.report({'WARNING'}, "No add-ons selected to reinstall")
            print("No add-ons selected to reinstall.")
            return {'CANCELLED'}

        addons_dir = bpy.utils.user_resource('SCRIPTS', path="addons")

        for addon_name, source_path in selected_addons:
            print(f"Starting reinstall process for add-on: {addon_name}")

            # Step 1: Validate source path
            if not source_path or not os.path.exists(source_path):
                self.report({'ERROR'}, f"Source path for {addon_name} not set or invalid: {source_path}")
                print(f"Source path for {addon_name} not set or invalid: {source_path}")
                continue

            # Step 2: Disable the addon
            try:
                if addon_name in [mod.__name__ for mod in addon_utils.modules(refresh=False)]:
                    addon_utils.disable(addon_name, default_set=True)
                    print(f"Disabled add-on: {addon_name}")
                else:
                    print(f"Add-on {addon_name} not found in loaded modules, proceeding to file removal.")
            except Exception as e:
                self.report({'ERROR'}, f"Error disabling {addon_name}: {str(e)}")
                print(f"Error disabling {addon_name}: {str(e)}")
                continue

            # Step 3: Locate and remove the addon file
            addon_file = os.path.join(addons_dir, f"{addon_name}.py")
            addon_dir = os.path.join(addons_dir, addon_name)

            if os.path.isfile(addon_file):
                print(f"Found single-file add-on at: {addon_file}")
                try:
                    os.remove(addon_file)
                    print(f"Removed add-on file: {addon_file}")
                except Exception as e:
                    self.report({'ERROR'}, f"Error removing {addon_name} file: {str(e)}")
                    print(f"Error removing {addon_name} file: {str(e)}")
                    continue
            elif os.path.isdir(addon_dir):
                print(f"Found directory-based add-on at: {addon_dir}")
                try:
                    shutil.rmtree(addon_dir)
                    print(f"Removed add-on directory: {addon_dir}")
                except Exception as e:
                    self.report({'ERROR'}, f"Error removing {addon_name} directory: {str(e)}")
                    print(f"Error removing {addon_name} directory: {str(e)}")
                    continue
            else:
                self.report({'ERROR'}, f"Add-on {addon_name} not found in addons directory")
                print(f"Add-on {addon_name} not found in addons directory: {addons_dir}")
                continue

            # Step 4: Refresh addon list to ensure it's unregistered
            addon_utils.modules(refresh=True)
            print("Refreshed addon list after removal.")

            # Step 5: Reinstall the addon from its source path
            print(f"Reinstalling add-on {addon_name} from source: {source_path}")
            if os.path.isfile(source_path):
                target_path = os.path.join(addons_dir, f"{addon_name}.py")
                try:
                    shutil.copy2(source_path, target_path)
                    print(f"Reinstalled add-on file from {source_path} to {target_path}")
                except Exception as e:
                    self.report({'ERROR'}, f"Error reinstalling {addon_name} file: {str(e)}")
                    print(f"Error reinstalling {addon_name} file: {str(e)}")
                    continue
            else:
                target_path = os.path.join(addons_dir, addon_name)
                try:
                    if os.path.exists(target_path):
                        shutil.rmtree(target_path)
                    shutil.copytree(source_path, target_path)
                    print(f"Reinstalled add-on directory from {source_path} to {target_path}")
                except Exception as e:
                    self.report({'ERROR'}, f"Error reinstalling {addon_name} directory: {str(e)}")
                    print(f"Error reinstalling {addon_name} directory: {str(e)}")
                    continue

            # Step 6: Refresh addon list again
            addon_utils.modules(refresh=True)
            print("Refreshed addon list after reinstall.")

            # Step 7: Activate the addon
            try:
                addon_utils.enable(addon_name, default_set=True)
                self.report({'INFO'}, f"Successfully reinstalled and activated add-on: {addon_name}")
                print(f"Successfully reinstalled and activated add-on: {addon_name}")
            except Exception as e:
                self.report({'ERROR'}, f"Error activating {addon_name}: {str(e)}")
                print(f"Error activating {addon_name}: {str(e)}")

        return {'FINISHED'}

# Operator to move addon from available to selected
class ADDONQUICK_OT_AddAddon(Operator):
    bl_idname = "addonquick.add_addon"
    bl_label = "Add Add-on"
    bl_description = "Move an add-on to the selected list"

    def execute(self, context):
        preferences = context.preferences.addons["addon_quick_access"].preferences
        index = preferences.available_addon_index
        if 0 <= index < len(preferences.available_addons):
            addon_item = preferences.available_addons[index]
            item = preferences.selected_addons.add()
            item.name = addon_item.name
            item.source_path = addon_item.source_path  # Carry over the source path
            preferences.available_addons.remove(index)
            print(f"Moved add-on to selected list: {item.name} (Source: {item.source_path})")
        return {'FINISHED'}

# Operator to move addon from selected to available
class ADDONQUICK_OT_RemoveAddon(Operator):
    bl_idname = "addonquick.remove_addon"
    bl_label = "Remove Add-on"
    bl_description = "Move an add-on back to the available list"

    def execute(self, context):
        preferences = context.preferences.addons["addon_quick_access"].preferences
        index = preferences.selected_addon_index
        if 0 <= index < len(preferences.selected_addons):
            addon_item = preferences.selected_addons[index]
            item = preferences.available_addons.add()
            item.name = addon_item.name
            item.source_path = addon_item.source_path  # Carry over the source path
            preferences.selected_addons.remove(index)
            print(f"Moved add-on to available list: {item.name} (Source: {item.source_path})")
        return {'FINISHED'}

# Panel in Scene tab
class ADDONQUICK_PT_AddonPanel(Panel):
    bl_label = "Add-ons Quick Access"
    bl_idname = "ADDONQUICK_PT_AddonPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.window_manager.addonquick_props
        preferences = context.preferences.addons["addon_quick_access"].preferences

        # Bash script button
        layout.operator("addonquick.run_bash_script", text=preferences.button_label, icon='CONSOLE')

        # Main box
        box = layout.box()

        # Refresh button
        box.operator("addonquick.refresh_addons", icon='FILE_REFRESH')

        # Install new addon section
        install_box = box.box()
        install_box.label(text="Install New Add-on", icon='PLUGIN')
        install_box.prop(props, "addon_path", text="Add-on File/Folder")
        install_box.operator("addonquick.install_addon", icon='IMPORT')

        # Selected addons section
        addon_box = box.box()
        addon_box.label(text="Selected Add-ons", icon='PLUGIN')
        selected_addons = [item.name for item in preferences.selected_addons if item.name != "addon_quick_access"]

        if not selected_addons:
            addon_box.label(text="No add-ons selected in preferences.", icon='INFO')
        else:
            for addon_name in selected_addons:
                row = addon_box.row()
                row.label(text=addon_name, icon='PLUGIN')

        # Single reinstall button
        box.operator("addonquick.manage_selected_addons", text="Reinstall")

# Addon preferences with dual-list UI and source path editing
class ADDONQUICK_AP_AddonPreferences(AddonPreferences):
    bl_idname = "addon_quick_access"

    bash_script_path: StringProperty(
        name="Bash Script Path",
        description="Path to the bash script to execute",
        subtype='FILE_PATH',
    )
    button_label: StringProperty(
        name="Button Label",
        description="Label for the Run Bash Script button",
        default="Run Script"
    )
    available_addons: bpy.props.CollectionProperty(type=ADDONQUICK_AddonItem)
    selected_addons: bpy.props.CollectionProperty(type=ADDONQUICK_AddonItem)
    available_addon_index: IntProperty()
    selected_addon_index: IntProperty()

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bash_script_path")
        layout.prop(self, "button_label")

        # Dual-list UI for addon selection
        layout.label(text="Select Add-ons to Manage:")
        row = layout.row()

        # Available addons (left column)
        col = row.column()
        col.label(text="Available Add-ons:")
        col.template_list("UI_UL_list", "available_addons", self, "available_addons", self, "available_addon_index")

        # Middle column with move buttons
        col = row.column(align=True)
        col.operator("addonquick.add_addon", text=">", icon='FORWARD')
        col.operator("addonquick.remove_addon", text="<", icon='BACK')

        # Selected addons (right column) with source path
        col = row.column()
        col.label(text="Selected Add-ons:")
        col.template_list("UI_UL_list", "selected_addons", self, "selected_addons", self, "selected_addon_index")

        # Show source path for the selected addon
        if 0 <= self.selected_addon_index < len(self.selected_addons):
            selected_item = self.selected_addons[self.selected_addon_index]
            col.label(text=f"Source Path for {selected_item.name}:")
            col.prop(selected_item, "source_path", text="")

# Registration
classes = (
    ADDONQUICK_AddonItem,
    ADDONQUICK_Properties,
    ADDONQUICK_OT_RefreshAddons,
    ADDONQUICK_OT_InstallAddon,
    ADDONQUICK_OT_RunBashScript,
    ADDONQUICK_OT_ManageSelectedAddons,
    ADDONQUICK_OT_AddAddon,
    ADDONQUICK_OT_RemoveAddon,
    ADDONQUICK_PT_AddonPanel,
    ADDONQUICK_AP_AddonPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.addonquick_props = PointerProperty(type=ADDONQUICK_Properties)

    # Populate available addons on registration
    preferences = bpy.context.preferences.addons["addon_quick_access"].preferences
    preferences.available_addons.clear()
    preferences.selected_addons.clear()
    for mod in addon_utils.modules(refresh=True):
        addon_name = mod.__name__
        if addon_name != "addon_quick_access":
            item = preferences.available_addons.add()
            item.name = addon_name
            item.source_path = ""  # Source path will be set manually
            print(f"Added add-on to available list: {addon_name}")

def unregister():
    del bpy.types.WindowManager.addonquick_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()