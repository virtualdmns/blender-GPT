import bpy
import json
import re
import sys
import traceback
import ast
import os
import random
import time
import glob
from pathlib import Path
from typing import Dict

# Debug sys.path before any changes
print("Initial Python sys.path:")
for p in sys.path:
    print(f"  {p}")

# Add user site-packages path where openai is installed
site_packages_path = os.path.expanduser("~/.local/lib/python3.11/site-packages")
if os.path.exists(site_packages_path):
    if site_packages_path not in sys.path:
        sys.path.append(site_packages_path)
        print(f"Added to sys.path: {site_packages_path}")
    else:
        print(f"Path already in sys.path: {site_packages_path}")
else:
    print(f"Warning: Site-packages path not found: {site_packages_path}")

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.realpath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)
    print(f"Added addon directory to sys.path: {addon_dir}")

# Print current Python path for debugging
print("\nCurrent Python sys.path:")
for p in sys.path:
    print(f"  {p}")

# Verify required packages
required_packages = {
    'openai': 'openai'
}

for package, import_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"Successfully imported {package}")
    except ImportError as e:
        print(f"Failed to import {package}: {e}")
        raise ImportError(
            f"{package} not found. Install it with: /Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install {package}")

# Now import openai after path setup
import openai

# Load API key
def load_api_key():
    global api_key
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(addon_dir, "config.json")
    print(f"Looking for config.json at: {config_path}")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                api_key = config.get("openai_api_key", "").strip()
                if api_key:
                    print("Successfully loaded API key from config.json")
                    return api_key
                else:
                    print("No API key found in config.json")
        except Exception as e:
            print(f"Error loading API key from config.json: {e}")
            api_key = None
    else:
        print("No config.json found in addon directory")
    return api_key

def save_api_key(api_key: str):
    """Save the API key to config file."""
    try:
        addon_dir = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(addon_dir, "config.json")
        config = {"openai_api_key": api_key}
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving API key: {e}")
        return False

def check_config_during_install():
    """Check for config.json during addon installation"""
    global api_key
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(addon_dir, "config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                api_key = config.get("openai_api_key", "").strip()
                if api_key:
                    print("Successfully loaded API key from config.json during installation")
                    return True
        except Exception as e:
            print(f"Error loading config.json during installation: {e}")
    return False

# Initialize api_key as None
api_key = None

# Load API key on startup
api_key = load_api_key()

# Check for config during installation
check_config_during_install()

# Rate limiting
class RateLimiter:
    def __init__(self, max_requests=120, time_window=60):  # Increased to 120 requests per minute
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.last_cleanup = time.time()

    def can_make_request(self):
        current_time = time.time()
        
        # Only clean up old requests every 5 seconds to avoid constant cleanup
        if current_time - self.last_cleanup > 5:
            self.requests = [t for t in self.requests if current_time - t < self.time_window]
            self.last_cleanup = current_time
            
        return len(self.requests) < self.max_requests

    def add_request(self):
        self.requests.append(time.time())


rate_limiter = RateLimiter()

bl_info = {
    "name": "BlenderGPT",
    "author": "virtualdmns",
    "version": (1, 1, 8),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderGPT",
    "description": "Generate and execute Blender commands using GPT",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}


# Message class for chat history
class Message(bpy.types.PropertyGroup):
    """Property group for storing chat messages"""
    role: bpy.props.StringProperty(
        name="Role",
        description="The role of the message sender",
        default="USER"
    )
    msg_content: bpy.props.StringProperty(
        name="Message Content",
        description="The content of the message",
        default=""
    )

    def from_json(self, data):
        """Initialize from JSON data"""
        self.role = data.get("role", "USER")
        self.msg_content = data.get("msg_content", "")


# Chat properties
class BlenderGPTChatProps(bpy.types.PropertyGroup):
    """Property group for BlenderGPT chat interface"""
    chat_history: bpy.props.CollectionProperty(
        type=Message,
        name="Chat History",
        description="History of chat messages"
    )
    chat_input: bpy.props.StringProperty(
        name="Chat Input",
        description="Input field for chat messages",
        default=""
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Chat mode",
        items=[
            ('ASSISTANT', 'Assistant', 'Regular chat assistant mode'),
            ('DREAMER', 'Dreamer', 'Scene interpretation mode')
        ],
        default='ASSISTANT'
    )


# Panel class
class BLENDER_GPT_PT_Panel(bpy.types.Panel):
    bl_label = "BlenderGPT"
    bl_idname = "VIEW3D_PT_blender_gpt"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderGPT'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gpt_props = scene.blendergpt_props

        # API Key Status
        box = layout.box()
        box.label(text="API Key Status:", icon='CHECKMARK')
        if api_key:
            box.label(text="✓ API Key Configured", icon='CHECKMARK')
        else:
            box.label(text="⚠ No API Key Found", icon='ERROR')
            box.label(text="Using config.json in addon directory", icon='FILE_TEXT')
            box.operator("blendergpt.configure_api_key", text="Load API Key")

        # Prompt Section
        box = layout.box()
        box.label(text="Generate Scene:", icon='MESH_DATA')
        box.prop(scene, "blender_gpt_prompt", text="Prompt")
        row = box.row()
        row.operator("blender_gpt.generate_code", text="Generate")
        row.operator("blender_gpt.execute_code", text="Execute")

        # Generated Commands
        box = layout.box()
        box.label(text="Generated Commands:", icon='TEXT')
        if scene.blender_gpt_generated_code:
            try:
                cmd_data = json.loads(scene.blender_gpt_generated_code)
                if "explanation" in cmd_data:
                    box.label(text=cmd_data["explanation"])

                # Add text editor for commands with proper styling
                if "commands" in cmd_data and cmd_data["commands"]:
                    commands_text = json.dumps(cmd_data["commands"], indent=2)
                    text_box = box.box()
                    text_box.scale_y = 3.0  # Make the text area taller
                    col = text_box.column()
                    col.scale_y = 0.6  # Adjust text scaling
                    col.prop(scene, "blender_gpt_generated_code", text="", icon='TEXT')
                    
                    # Add Copy and Clear buttons in a row
                    row = box.row(align=True)
                    row.operator("blendergpt.copy_commands", text="Copy", icon='COPYDOWN')
                    row.operator("blendergpt.clear_commands", text="Clear", icon='X')
            except json.JSONDecodeError:
                box.label(text="Error parsing commands", icon='ERROR')
        else:
            box.label(text="No commands generated yet")

        # Execution Result
        box = layout.box()
        box.label(text="Result:", icon='INFO')
        if scene.blender_gpt_execution_result:
            try:
                result_data = json.loads(scene.blender_gpt_execution_result)
                if result_data["status"] == "success":
                    box.label(text="✓ Success!", icon='CHECKMARK')
                    if "details" in result_data:
                        for detail in result_data["details"]:
                            if detail["status"] == "success":
                                box.label(text=f"• {detail.get('name', 'Operation')} created", icon='DOT')
                            else:
                                box.label(text=f"⚠ {detail.get('message', 'Unknown error')}", icon='ERROR')
                else:
                    box.label(text=f"⚠ Error: {result_data.get('message', 'Unknown error')}", icon='ERROR')
                
                # Add Copy button for results
                row = box.row(align=True)
                row.operator("blendergpt.copy_results", text="Copy Results", icon='COPYDOWN')
            except json.JSONDecodeError:
                box.label(text=scene.blender_gpt_execution_result)
        else:
            box.label(text="No results yet")

        # Chat Section
        box = layout.box()
        box.label(text="Chat with BlenderGPT:", icon='TEXT')
        for msg in gpt_props.chat_history:
            msg_box = box.box()
            row = msg_box.row()
            col = row.column()
            display_role = msg.role if msg.role in ["DREAMER", "USER"] else "Assistant"
            col.label(text=f"{display_role}:", icon='USER' if msg.role == 'USER' else 'TEXT')

            # Split message content into multiple lines if needed
            msg_content = msg.msg_content
            words = msg_content.split()
            lines = []
            current_line = []

            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 50:  # Max 50 characters per line
                    lines.append(" ".join(current_line[:-1]))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))

            col = row.column()
            for line in lines:
                col.label(text=line)
        box.prop(gpt_props, "chat_input", text="Message")
        row = box.row()
        row.operator("blendergpt.send_message", text="Send")
        row.operator("blendergpt.clear_history", text="Clear")
        row.operator("blendergpt.copy_chat", text="Copy Chat", icon='COPYDOWN')

        # Mode Toggle (moved to bottom)
        box = layout.box()
        box.label(text="Mode:", icon='MODIFIER')
        box.prop(gpt_props, "mode", expand=True)


# Scene Inspection
def get_scene_info():
    scene_info = {"objects": [], "materials": [], "cameras": [], "lights": []}
    for obj in bpy.context.scene.objects:
        obj_info = {
            "name": obj.name, "type": obj.type, "location": list(obj.location),
            "rotation": [r for r in obj.rotation_euler], "scale": list(obj.scale),
            "visible": obj.visible_get()
        }
        scene_info["objects"].append(obj_info)
        if obj.type == 'CAMERA':
            scene_info["cameras"].append(
                {"name": obj.name, "lens": obj.data.lens, "sensor_width": obj.data.sensor_width})
        elif obj.type == 'LIGHT':
            scene_info["lights"].append({"name": obj.name, "type": obj.data.type, "energy": obj.data.energy,
                                         "color": [c for c in obj.data.color]})
    for mat in bpy.data.materials:
        mat_info = {"name": mat.name, "users": mat.users}
        if mat.use_nodes:
            principled = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if principled:
                mat_info.update({
                    "base_color": [c for c in principled.inputs["Base Color"].default_value],
                    "metallic": principled.inputs["Metallic"].default_value,
                    "roughness": principled.inputs["Roughness"].default_value
                })
        scene_info["materials"].append(mat_info)
    return scene_info


# Command System
class BlenderGPTCommands:
    @staticmethod
    def delete_object(name):
        """Delete an object from the scene."""
        try:
            print(f"\nAttempting to delete object: {name}")
            if name.lower() == "everything":
                # Delete all objects
                print("Deleting all objects in scene")
                count = len(bpy.data.objects)
                for obj in bpy.data.objects:
                    print(f"Removing object: {obj.name}")
                    bpy.data.objects.remove(obj, do_unlink=True)
                return {"status": "success", "message": f"All {count} objects deleted", "count": count}
            
            obj = bpy.data.objects.get(name)
            if not obj:
                error_msg = f"Object {name} not found"
                print(error_msg)
                return {"status": "error", "message": error_msg}
            
            print(f"Found object {name}, removing it")
            bpy.data.objects.remove(obj, do_unlink=True)
            return {"status": "success", "message": f"Deleted object: {name}", "count": 1}
        except Exception as e:
            error_msg = f"Error deleting object {name}: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

    @staticmethod
    def create_object(obj_type, name=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), color=None):
        """Create a basic 3D object in the scene."""
        try:
            print(f"Creating object: type={obj_type}, name={name}, location={location}, color={color}")
            
            # Ensure we're in object mode and nothing is selected
            if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            
            # Validate object type
            obj_type = obj_type.upper()
            if obj_type not in ['CUBE', 'SPHERE', 'CONE', 'CYLINDER', 'PLANE']:
                return {"status": "error",
                        "message": f"Unknown object type: {obj_type}. Use CUBE, SPHERE, CONE, CYLINDER, or PLANE."}

            # Map object types to their respective primitive add operators
            primitive_ops = {
                'CUBE': lambda: bpy.ops.mesh.primitive_cube_add(size=2, location=location),
                'SPHERE': lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=location),
                'CONE': lambda: bpy.ops.mesh.primitive_cone_add(radius1=1, depth=2, location=location),
                'CYLINDER': lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2, location=location),
                'PLANE': lambda: bpy.ops.mesh.primitive_plane_add(size=2, location=location)
            }

            # Execute the appropriate operator
            print(f"Executing operator for type: {obj_type}")
            primitive_ops[obj_type]()
            
            # Get the created object (it should be the active object)
            obj = bpy.context.active_object
            if not obj:
                return {"status": "error", "message": "Failed to create object - no active object"}

            print(f"Created object: {obj.name}")

            # Set object properties
            if name:
                # Ensure unique name
                obj.name = name
                if obj.name != name:  # Blender appends .001 etc. for duplicate names
                    print(f"Warning: Requested name '{name}' was modified to '{obj.name}' to ensure uniqueness")
            
            obj.rotation_euler = rotation
            obj.scale = scale
            
            print(f"Object configured: name={obj.name}, rotation={obj.rotation_euler}, scale={obj.scale}")

            # Create and apply material
            mat = bpy.data.materials.new(name=f"{obj.name}_material")
            mat.use_nodes = True
            
            # Get the principled BSDF node
            principled = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if principled:
                # Set material properties
                if color and len(color) == 3:
                    principled.inputs["Base Color"].default_value = (*color, 1.0)  # RGB + Alpha
                else:
                    principled.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
                principled.inputs["Metallic"].default_value = 0.0
                principled.inputs["Roughness"].default_value = 0.5
            
            # Assign material to object
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            print(f"Applied material to {obj.name} with color: {color if color else 'default'}")

            # Update the view layer to ensure the object is visible
            bpy.context.view_layer.update()
            
            return {"status": "success", "name": obj.name}
            
        except Exception as e:
            error_msg = f"Error creating object: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

    @staticmethod
    def set_material(obj_name, color=None, metallic=None, roughness=None):
        try:
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object {obj_name} not found"}
            mat = bpy.data.materials.new(name=f"{obj_name}_material")
            mat.use_nodes = True
            principled = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            if color and len(color) == 3:
                principled.inputs["Base Color"].default_value = [*color, 1.0]
            if metallic is not None:
                principled.inputs["Metallic"].default_value = metallic
            if roughness is not None:
                principled.inputs["Roughness"].default_value = roughness
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            return {"status": "success", "material_name": mat.name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def modify_object(name, location=None, rotation=None, scale=None, visible=None):
        try:
            obj = bpy.data.objects.get(name)
            if not obj:
                return {"status": "error", "message": f"Object {name} not found"}
            if location:
                obj.location = location
            if rotation:
                obj.rotation_euler = rotation
            if scale:
                obj.scale = scale
            if visible is not None:
                obj.hide_set(not visible)
            return {"status": "success", "name": name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def create_composite_object(obj_type, name=None, location=(0,0,0), variations=None):
        """
        Create complex composite objects using the COMPOSITE_OBJECTS dictionary
        """
        try:
            obj_type = obj_type.upper()
            if obj_type not in COMPOSITE_OBJECTS:
                return {"status": "error", "message": f"Unknown composite object type: {obj_type}"}
            
            # Generate base name if none provided
            base_name = name or f"{obj_type}_{random.randint(0,999)}"
            created_objects = []
            
            # Get object definition
            obj_def = COMPOSITE_OBJECTS[obj_type]
            
            # Apply global variations if provided
            variation_scales = variations or obj_def.get("variations", {})
            
            # Create each component
            for comp in obj_def["components"]:
                # Handle multiple instances of the same component
                count = 1
                if "count" in comp:
                    count = random.randint(comp["count"][0], comp["count"][1])
                
                for i in range(count):
                    # Calculate component position
                    pos_var = comp.get("position_variance", (0, 0, 0))
                    base_pos = comp.get("position", (0, 0, 0))
                    comp_loc = (
                        location[0] + base_pos[0] + random.uniform(-pos_var[0], pos_var[0]),
                        location[1] + base_pos[1] + random.uniform(-pos_var[1], pos_var[1]),
                        location[2] + base_pos[2] + random.uniform(-pos_var[2], pos_var[2])
                    )
                    
                    # Calculate scale with variations
                    base_scale = comp["base_scale"]
                    scale_var = variation_scales.get(f"{comp['name']}_scale", 0.2)
                    comp_scale = tuple(
                        s * random.uniform(1 - scale_var, 1 + scale_var) 
                        for s in base_scale
                    )
                    
                    # Create the component
                    obj_result = BlenderGPTCommands.create_object(
                        comp["type"],
                        f"{base_name}_{comp['name']}_{i}",
                        comp_loc,
                        scale=comp_scale
                    )
                    
                    if obj_result["status"] == "success":
                        created_objects.append(obj_result)
                        
                        # Apply material
                        mat_def = comp["material"]
                        if "color_options" in mat_def:
                            color = random.choice(mat_def["color_options"])
                        else:
                            color = mat_def["color"]
                        
                        BlenderGPTCommands.set_material(
                            obj_result["name"],
                            color=color,
                            roughness=mat_def.get("roughness", 0.8),
                            metallic=mat_def.get("metallic", 0.0)
                        )
            
            return {"status": "success", "objects": created_objects}
            
        except Exception as e:
            return {"status": "error", "message": f"Error creating {obj_type}: {str(e)}"}


class CommandValidationError(Exception):
    """Custom exception for command validation errors."""
    pass


def validate_command(cmd: dict) -> bool:
    """Validate command structure and parameters."""
    if not isinstance(cmd, dict):
        raise CommandValidationError(f"Command must be a dictionary, got {type(cmd)}")

    if "command" not in cmd:
        raise CommandValidationError(f"Missing 'command' key in command: {cmd}")
    
    cmd_name = cmd["command"]
    cmd_params = {k: v for k, v in cmd.items() if k != "command"}

    # Validate specific command types
    if cmd_name == "create_object":
        if "type" not in cmd_params:
            raise CommandValidationError("create_object requires a 'type' parameter")
        if cmd_params["type"].upper() not in ['CUBE', 'SPHERE', 'CONE', 'CYLINDER', 'PLANE']:
            raise CommandValidationError(f"Invalid object type: {cmd_params['type']}")
        if "color" in cmd_params:
            if not isinstance(cmd_params["color"], list):
                raise CommandValidationError("color must be a list of 3 values [r,g,b]")
            if len(cmd_params["color"]) != 3:
                raise CommandValidationError("color must be a list of 3 values [r,g,b]")
            if not all(isinstance(c, (int, float)) for c in cmd_params["color"]):
                raise CommandValidationError("color values must be numbers")

    elif cmd_name == "set_material":
        if "obj_name" not in cmd_params:
            raise CommandValidationError("set_material requires an 'obj_name' parameter")
        if "color" in cmd_params and len(cmd_params["color"]) != 3:
            raise CommandValidationError("color must be a list of 3 values [r,g,b]")

    elif cmd_name == "modify_object":
        if "name" not in cmd_params:
            raise CommandValidationError("modify_object requires a 'name' parameter")

    elif cmd_name == "delete_object":
        if "name" not in cmd_params:
            raise CommandValidationError("delete_object requires a 'name' parameter")

    return True


# Command Generation
def generate_blender_commands(prompt: str, api_key: str, model: str, scene_info=None, last_result=None,
                              messages=None) -> dict:
    try:
        print("\n=== Starting Command Generation ===")
        print(f"Prompt: {prompt}")
        print(f"Scene info: {json.dumps(scene_info, indent=2)}")

        # Special case for delete everything
        if prompt.lower().strip() in ["delete everything", "delete all", "clear scene", "remove everything", "remove all"]:
            print("Using special case for delete everything command")
            return {
                "explanation": "Deleting all objects from the scene",
                "commands": [
                    {"command": "delete_object", "name": "everything"}
                ]
            }

        if not rate_limiter.can_make_request():
            return {"error": "Rate limit exceeded. Please wait before making more requests."}

        rate_limiter.add_request()

        api_key = api_key.strip()
        api_key = ''.join(char for char in api_key if ord(char) < 128 and char.isprintable())

        if not api_key:
            raise ValueError("No API key provided. Please set it in config.json.")

        client = openai.Client(api_key=api_key)

        if messages is None:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are BlenderGPT, a command generation system for Blender. Your task is to generate precise commands based on user prompts.\n\n"
                        "IMPORTANT: You MUST generate valid commands for EVERY request. Do not explain or discuss - just generate the commands.\n\n"
                        "Available Commands:\n"
                        "1. Basic Commands:\n"
                        "- create_object: Creates a basic 3D object\n"
                        "  Required: 'type': 'CUBE'|'SPHERE'|'CONE'|'CYLINDER'|'PLANE'\n"
                        "  Optional: 'name': str, 'location': [x,y,z], 'rotation': [x,y,z], 'scale': [x,y,z], 'color': [r,g,b]\n"
                        "  Example: {'command': 'create_object', 'type': 'CUBE', 'name': 'RedCube', 'location': [0,0,0], 'color': [1,0,0]}\n\n"
                        "- delete_object: Deletes an object from the scene\n"
                        "  Required: 'name': str (name of object to delete)\n"
                        "  Example: {'command': 'delete_object', 'name': 'Cube'}\n\n"
                        "- set_material: Sets material properties for an object\n"
                        "  Required: 'obj_name': str\n"
                        "  Optional: 'color': [r,g,b], 'metallic': float, 'roughness': float\n"
                        "  Example: {'command': 'set_material', 'obj_name': 'RedCube', 'color': [1,0,0]}\n\n"
                        "Output format MUST be:\n"
                        "{\n"
                        "  'explanation': 'Brief description of what you're creating',\n"
                        "  'commands': [list of command dictionaries]\n"
                        "}\n\n"
                        "Example for 'delete everything':\n"
                        "{\n"
                        "  'explanation': 'Deleting all objects from the scene',\n"
                        "  'commands': [\n"
                        "    {'command': 'delete_object', 'name': 'Cube'},\n"
                        "    {'command': 'delete_object', 'name': 'Light'},\n"
                        "    {'command': 'delete_object', 'name': 'Camera'}\n"
                        "  ]\n"
                        "}\n\n"
                        "ALWAYS generate commands - no discussion or suggestions."
                    )
                }
            ]
            if scene_info:
                messages.append({"role": "system", "content": f"Current scene: {json.dumps(scene_info, indent=2)}"})
            if last_result:
                messages.append({"role": "system", "content": f"Last result: {json.dumps(last_result, indent=2)}"})
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            max_tokens=8000,
            temperature=0.7,
        )
        raw_content = response.choices[0].message.content

        # Parse the response as JSON
        try:
            print(f"Raw response content: {raw_content}")
            # First try to parse as regular JSON
            try:
                parsed_response = json.loads(raw_content)
            except json.JSONDecodeError:
                # If that fails, try to evaluate as Python literal (handles single quotes)
                try:
                    parsed_response = ast.literal_eval(raw_content)
                except (ValueError, SyntaxError) as e:
                    print(f"Failed to parse response as Python literal: {e}")
                    return {
                        "explanation": "Failed to parse response",
                        "commands": []
                    }
            
            # Validate the parsed response
            if not isinstance(parsed_response, dict):
                print(f"Response is not a dictionary: {parsed_response}")
                return {
                    "explanation": "Invalid response format",
                    "commands": []
                }
            
            if "explanation" not in parsed_response or "commands" not in parsed_response:
                print(f"Response missing required keys: {parsed_response}")
                return {
                    "explanation": raw_content,
                    "commands": []
                }
            
            # Ensure commands is a list
            if not isinstance(parsed_response["commands"], list):
                print(f"Commands is not a list: {parsed_response['commands']}")
                parsed_response["commands"] = []
            
            print(f"Successfully parsed response: {json.dumps(parsed_response, indent=2)}")
            return parsed_response
            
        except Exception as e:
            print(f"Error parsing response: {e}\n{traceback.format_exc()}")
            return {
                "explanation": raw_content,
                "commands": []
            }

    except openai.AuthenticationError as auth_error:
        print(f"Authentication Error: {auth_error}")
        return {"error": f"Authentication failed: {str(auth_error)}. Please check your API key."}

    except openai.APIError as api_error:
        print(f"API Error: {api_error}")
        return {"error": f"API error: {str(api_error)}"}

    except Exception as e:
        print(f"Error generating commands: {str(e)}")
        return {"error": f"Error generating commands: {str(e)}"}


# Execution
def execute_generated_commands(commands: dict) -> dict:
    try:
        print("\n=== Starting Command Execution ===")
        print(f"Input commands: {json.dumps(commands, indent=2)}")
        
        # Push undo state
        bpy.ops.ed.undo_push(message="Before blender_gpt execution")
        result = {"status": "success", "details": []}

        if not isinstance(commands, dict):
            error_msg = f"Invalid commands format: expected dict, got {type(commands)}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

        if "commands" not in commands:
            error_msg = "No 'commands' key found in input"
            print(error_msg)
            return {"status": "error", "message": error_msg}

        if not isinstance(commands["commands"], list):
            error_msg = f"Invalid commands format: expected list, got {type(commands['commands'])}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

        total_commands = len(commands["commands"])
        print(f"Total commands to execute: {total_commands}")
        
        for i, cmd in enumerate(commands["commands"], 1):
            try:
                print(f"\n--- Executing command {i}/{total_commands} ---")
                print(f"Command data: {json.dumps(cmd, indent=2)}")

                # Validate command before execution
                print("Validating command...")
                validate_command(cmd)

                cmd_name = cmd["command"]
                cmd_params = {k: v for k, v in cmd.items() if k != "command"}
                print(f"Command name: {cmd_name}")
                print(f"Command parameters: {json.dumps(cmd_params, indent=2)}")

                # Execute command
                print(f"Executing {cmd_name}...")
                if cmd_name == "create_object":
                    if "type" in cmd_params:
                        cmd_params["obj_type"] = cmd_params.pop("type")
                    res = BlenderGPTCommands.create_object(**cmd_params)
                elif cmd_name == "set_material":
                    res = BlenderGPTCommands.set_material(**cmd_params)
                elif cmd_name == "modify_object":
                    res = BlenderGPTCommands.modify_object(**cmd_params)
                elif cmd_name == "delete_object":
                    res = BlenderGPTCommands.delete_object(**cmd_params)
                elif cmd_name == "create_composite_object":
                    res = BlenderGPTCommands.create_composite_object(**cmd_params)
                else:
                    error_msg = f"Unknown command: {cmd_name}"
                    print(error_msg)
                    res = {"status": "error", "message": error_msg}

                print(f"Command result: {json.dumps(res, indent=2)}")
                result["details"].append(res)

                # Update the view layer after each command
                bpy.context.view_layer.update()

            except CommandValidationError as e:
                error_msg = f"Command validation error: {str(e)}"
                print(error_msg)
                result["details"].append({"status": "error", "message": error_msg})
            except Exception as e:
                error_msg = f"Error executing command: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                result["details"].append({"status": "error", "message": error_msg})

        print("\nUpdating view layer and pushing undo state...")
        bpy.context.view_layer.update()
        bpy.ops.ed.undo_push(message="After blender_gpt execution")
        print("=== Command Execution Complete ===\n")
        return result

    except Exception as e:
        error_msg = f"Fatal error in execute_generated_commands: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


# Preferences
class BlenderGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "addon_blender_gpt"
    gpt_model: bpy.props.EnumProperty(
        name="GPT Model",
        items=[("gpt-4", "GPT-4", ""), ("gpt-3.5-turbo", "GPT-3.5 Turbo", ""),
               ("gpt-4o-mini-2024-07-18", "GPT-4o Mini", "")],
        default="gpt-4o-mini-2024-07-18"
    )

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gpt_props = scene.blendergpt_props

        # API Key Section
        box = layout.box()
        box.label(text="API Key Status:", icon='CHECKMARK')
        if api_key:
            box.label(text="✓ API Key Configured", icon='CHECKMARK')
        else:
            box.label(text="⚠ No API Key Found", icon='ERROR')
            box.label(text="Using config.json in addon directory", icon='FILE_TEXT')
            box.operator("blendergpt.configure_api_key", text="Load API Key")

        # Prompt Section
        box = layout.box()
        box.label(text="Generate Scene:", icon='MESH_DATA')
        box.prop(scene, "blender_gpt_prompt", text="Prompt")
        row = box.row()
        row.operator("blender_gpt.generate_code", text="Generate")
        row.operator("blender_gpt.execute_code", text="Execute")

        # Generated Commands
        box = layout.box()
        box.label(text="Generated Commands:", icon='TEXT')
        if scene.blender_gpt_generated_code:
            try:
                cmd_data = json.loads(scene.blender_gpt_generated_code)
                if "explanation" in cmd_data:
                    box.label(text=cmd_data["explanation"])

                # Add text editor for commands with proper styling
                if "commands" in cmd_data and cmd_data["commands"]:
                    commands_text = json.dumps(cmd_data["commands"], indent=2)
                    text_box = box.box()
                    text_box.scale_y = 3.0  # Make the text area taller
                    col = text_box.column()
                    col.scale_y = 0.6  # Adjust text scaling
                    col.prop(scene, "blender_gpt_generated_code", text="", icon='TEXT')
                    
                    # Add Copy and Clear buttons in a row
                    row = box.row(align=True)
                    row.operator("blendergpt.copy_commands", text="Copy", icon='COPYDOWN')
                    row.operator("blendergpt.clear_commands", text="Clear", icon='X')
            except json.JSONDecodeError:
                box.label(text="Error parsing commands", icon='ERROR')
        else:
            box.label(text="No commands generated yet")

        # Execution Result
        box = layout.box()
        box.label(text="Result:", icon='INFO')
        if scene.blender_gpt_execution_result:
            try:
                result_data = json.loads(scene.blender_gpt_execution_result)
                if result_data["status"] == "success":
                    box.label(text="✓ Success!", icon='CHECKMARK')
                    if "details" in result_data:
                        for detail in result_data["details"]:
                            if detail["status"] == "success":
                                box.label(text=f"• {detail.get('name', 'Operation')} created", icon='DOT')
                            else:
                                box.label(text=f"⚠ {detail.get('message', 'Unknown error')}", icon='ERROR')
                else:
                    box.label(text=f"⚠ Error: {result_data.get('message', 'Unknown error')}", icon='ERROR')
                
                # Add Copy button for results
                row = box.row(align=True)
                row.operator("blendergpt.copy_results", text="Copy Results", icon='COPYDOWN')
            except json.JSONDecodeError:
                box.label(text=scene.blender_gpt_execution_result)
        else:
            box.label(text="No results yet")

        # Chat Section
        box = layout.box()
        box.label(text="Chat with BlenderGPT:", icon='TEXT')
        for msg in gpt_props.chat_history:
            msg_box = box.box()
            row = msg_box.row()
            col = row.column()
            display_role = msg.role if msg.role in ["DREAMER", "USER"] else "Assistant"
            col.label(text=f"{display_role}:", icon='USER' if msg.role == 'USER' else 'TEXT')

            # Split message content into multiple lines if needed
            msg_content = msg.msg_content
            words = msg_content.split()
            lines = []
            current_line = []

            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 50:  # Max 50 characters per line
                    lines.append(" ".join(current_line[:-1]))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))

            col = row.column()
            for line in lines:
                col.label(text=line)
        box.prop(gpt_props, "chat_input", text="Message")
        row = box.row()
        row.operator("blendergpt.send_message", text="Send")
        row.operator("blendergpt.clear_history", text="Clear")
        row.operator("blendergpt.copy_chat", text="Copy Chat", icon='COPYDOWN')

        # Mode Toggle (moved to bottom)
        box = layout.box()
        box.label(text="Mode:", icon='MODIFIER')
        box.prop(gpt_props, "mode", expand=True)


class BLENDER_GPT_OT_ConfigureAPIKey(bpy.types.Operator):
    bl_idname = "blendergpt.configure_api_key"
    bl_label = "Configure API Key"
    bl_description = "Load API Key from config.json or file"
    
    filepath: bpy.props.StringProperty(
        name="API Key File",
        description="Select a text file containing your OpenAI API key",
        subtype='FILE_PATH'
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.txt;*.json",
        options={'HIDDEN'}
    )

    def invoke(self, context, event):
        # First try to load from config.json
        addon_dir = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(addon_dir, "config.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    key = config.get("openai_api_key", "").strip()
                    if key:
                        global api_key
                        api_key = key
                        self.report({'INFO'}, "API key loaded from config.json")
                        return {'FINISHED'}
            except Exception as e:
                self.report({'WARNING'}, f"Could not load config.json: {str(e)}")
        
        # If config.json doesn't exist or is invalid, use file selector
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # This is only called when using file selector
        try:
            with open(self.filepath, 'r') as f:
                if self.filepath.endswith('.json'):
                    config = json.load(f)
                    key = config.get("openai_api_key", "").strip()
                else:
                    key = f.read().strip()
                
                if key:
                    if save_api_key(key):
                        global api_key
                        api_key = key
                        self.report({'INFO'}, "API key loaded and saved successfully")
                    else:
                        self.report({'ERROR'}, "Failed to save API key")
                else:
                    self.report({'ERROR'}, "No API key found in file")
        except Exception as e:
            self.report({'ERROR'}, f"Error reading API key file: {str(e)}")
        return {'FINISHED'}


class BLENDER_GPT_OT_GenerateCode(bpy.types.Operator):
    bl_idname = "blender_gpt.generate_code"
    bl_label = "Generate Code"
    bl_description = "Generate Blender commands from prompt"

    def execute(self, context):
        print("\n=== Starting Command Generation ===")
        prefs = context.preferences.addons["addon_blender_gpt"].preferences
        model = prefs.gpt_model
        print(f"Using model: {model}")

        if not api_key:
            self.report({'ERROR'}, "No API key found. Please configure it first.")
            return {'CANCELLED'}

        prompt = context.scene.blender_gpt_prompt
        if not prompt.strip():
            self.report({'WARNING'}, "Please enter a prompt first")
            return {'CANCELLED'}

        print(f"Generating commands for prompt: {prompt}")
        scene_info = get_scene_info()
        print(f"Current scene info: {json.dumps(scene_info, indent=2)}")
        
        commands = generate_blender_commands(prompt, api_key, model, scene_info)
        print(f"Generated commands: {json.dumps(commands, indent=2)}")

        if "error" in commands:
            print(f"Error in command generation: {commands['error']}")
            context.scene.blender_gpt_generated_code = json.dumps({"explanation": f"Error: {commands['error']}"})
            self.report({'ERROR'}, commands['error'])
            return {'CANCELLED'}

        context.scene.blender_gpt_generated_code = json.dumps(commands)
        context.scene.blender_gpt_execution_result = ""
        print("=== Command Generation Complete ===\n")
        self.report({'INFO'}, "Commands generated successfully")
        return {'FINISHED'}


class BLENDER_GPT_OT_ExecuteCode(bpy.types.Operator):
    bl_idname = "blender_gpt.execute_code"
    bl_label = "Execute Code"

    def execute(self, context):
        print("\n=== Starting Command Execution ===")
        code = context.scene.blender_gpt_generated_code
        if not code.strip():
            print("No commands to execute")
            self.report({'WARNING'}, "No commands to execute.")
            return {'CANCELLED'}

        try:
            print(f"Parsing commands from: {code}")
            commands = json.loads(code)
            print(f"Parsed commands structure: {json.dumps(commands, indent=2)}")
            
            result = execute_generated_commands(commands)
            print(f"Execution result: {json.dumps(result, indent=2)}")

            context.scene.blender_gpt_execution_result = json.dumps(result)
            if result["status"] == "error":
                print(f"Execution error: {result['message']}")
                self.report({'ERROR'}, result["message"])
            else:
                print("Execution completed successfully")
                # Check if any objects were affected
                if result.get("details"):
                    success_count = sum(1 for detail in result["details"] if detail.get("status") == "success")
                    if success_count > 0:
                        # Check if this was a deletion operation
                        is_deletion = any(cmd.get("command") == "delete_object" for cmd in commands.get("commands", []))
                        if is_deletion:
                            self.report({'INFO'}, f"Successfully deleted {success_count} objects.")
                        else:
                            self.report({'INFO'}, f"Successfully created {success_count} objects.")
                    else:
                        self.report({'WARNING'}, "Commands executed but no objects were affected.")
                else:
                    self.report({'WARNING'}, "Commands executed but no results were returned.")
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse commands: {str(e)}"
            print(error_msg)
            context.scene.blender_gpt_execution_result = json.dumps(
                {"status": "error", "message": error_msg})
            self.report({'ERROR'}, error_msg)
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            context.scene.blender_gpt_execution_result = json.dumps(
                {"status": "error", "message": error_msg})
            self.report({'ERROR'}, f"Execution failed: {str(e)}")
        
        print("=== Command Execution Complete ===\n")
        return {'FINISHED'}


def technical_distill(insights: Dict, prompt: str) -> str:
    """Translate dream insights into technical scene elements"""
    # Extract key elements from prompt
    prompt_words = prompt.lower().split()
    
    # Map emotional qualities to technical parameters
    emotional_map = {
        "wonder": {"scale": 1.2, "brightness": 1.1},
        "euphoria": {"color_intensity": 1.3, "glow_strength": 1.2}, 
        "serenity": {"smoothness": 0.8, "transparency": 0.2},
        "turbulent": {"roughness": 0.7, "displacement": 0.5},
        "passion": { "vibrance": 1.4,   "pulse_strength": 0.7}  # Adds sexy horniness
    }
    
    # Map conceptual forms to technical shapes
    form_map = {
        "crystalline": "ICO_SPHERE",
        "organic": "SPHERE",
        "geometric": "CUBE",
        "fluid": "SPHERE",
        "rigid": "CUBE",
        "amorphous": "SPHERE"
    }
    
    # Map aesthetic qualities to material properties
    aesthetic_map = {
        "smooth": {"roughness": 0.2, "metallic": 0.1},
        "rough": {"roughness": 0.8, "metallic": 0.0},
        "crystalline": {"roughness": 0.3, "metallic": 0.2, "transparency": 0.5},
        "metallic": {"roughness": 0.4, "metallic": 0.8}
    }
    
    # Generate technical response
    technical_response = "🎬 Technical Scene Breakdown:\n\n"
    
    # Main object based on prompt
    main_object = prompt_words[0] if prompt_words else "object"
    technical_response += f"Primary Object: {main_object}\n"
    
    # Form and structure
    form = insights["conceptual"]["form"]
    technical_response += f"Base Form: {form_map.get(form, 'SPHERE')}\n"
    
    # Material properties
    texture = insights["aesthetic"]["texture"]
    material_props = aesthetic_map.get(texture, {"roughness": 0.5, "metallic": 0.0})
    technical_response += f"Material Properties:\n"
    technical_response += f"• Roughness: {material_props['roughness']:.2f}\n"
    technical_response += f"• Metallic: {material_props['metallic']:.2f}\n"
    
    # Lighting setup
    lighting = insights["energetic"]["flow"]
    technical_response += f"Lighting: {lighting.title()}\n"
    
    # Special effects based on cosmic insights
    if insights["cosmic"]["reality"] == "fractured":
        technical_response += "Effects: Fractured Reality (Displacement + Transparency)\n"
    
    # Camera and composition
    technical_response += f"Camera: {insights['narrative']['pace'].title()} Movement\n"
    
    return technical_response


class BLENDERGPT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blendergpt.send_message"
    bl_label = "Send Message"

    def execute(self, context):
        scene = context.scene
        gpt_props = scene.blendergpt_props
        prompt = gpt_props.chat_input
        scene_info = get_scene_info()

        # Add user's message to chat history
        gpt_props.chat_history.add().from_json({"role": "USER", "msg_content": prompt})

        try:
            if gpt_props.mode == 'DREAMER':
                # Use Dreamer mode
                try:
                    # Import Dreamer from local module
                    from .dreamer.core import Dreamer
                    dreamer_instance = Dreamer()
                    result = dreamer_instance.process_request(prompt)
                    
                    # Format the response nicely for display
                    display_response = "✨ Dream Insights ✨\n\n"
                    
                    # Emotional insights
                    display_response += f"💫 Emotional Essence:\n"
                    display_response += f"• Primary: {result['insights']['emotional']['primary']}\n"
                    display_response += f"• Secondary: {result['insights']['emotional']['secondary']}\n"
                    display_response += f"• Intensity: {result['insights']['emotional']['intensity']:.2f}\n\n"
                    
                    # Energetic insights
                    display_response += f"⚡ Energetic Flow:\n"
                    display_response += f"• Flow: {result['insights']['energetic']['flow']}\n"
                    display_response += f"• Frequency: {result['insights']['energetic']['frequency']}\n"
                    display_response += f"• Quality: {result['insights']['energetic']['quality']}\n\n"
                    
                    # Conceptual insights
                    display_response += f"🌌 Conceptual Realm:\n"
                    display_response += f"• Form: {result['insights']['conceptual']['form']}\n"
                    display_response += f"• Setting: {result['insights']['conceptual']['setting']}\n"
                    display_response += f"• Essence: {result['insights']['conceptual']['essence']}\n\n"
                    
                    # Aesthetic insights
                    display_response += f"🎨 Aesthetic Vision:\n"
                    display_response += f"• Beauty: {result['insights']['aesthetic']['beauty']}\n"
                    display_response += f"• Color: {result['insights']['aesthetic']['color']}\n"
                    display_response += f"• Texture: {result['insights']['aesthetic']['texture']}\n\n"
                    
                    # Narrative insights
                    display_response += f"📖 Narrative Thread:\n"
                    display_response += f"• Tone: {result['insights']['narrative']['tone']}\n"
                    display_response += f"• Pace: {result['insights']['narrative']['pace']}\n"
                    display_response += f"• Mood: {result['insights']['narrative']['mood']}\n\n"
                    
                    # Cosmic insights
                    display_response += f"🌠 Cosmic Perspective:\n"
                    display_response += f"• Dimension: {result['insights']['cosmic']['dimension']}\n"
                    display_response += f"• Reality: {result['insights']['cosmic']['reality']}\n"
                    display_response += f"• Existence: {result['insights']['cosmic']['existence']}\n"
                    
                    # Add formatted response to chat history with DREAMER role
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": display_response
                    })
                    
                    # Generate technical breakdown
                    technical_response = technical_distill(result['insights'], prompt)
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": technical_response
                    })
                    
                    # Create AI system prompt with Dreamer's insights
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a dream interpreter and scene creator. Your role is to:\n\n"
                                "1. Understand the emotional and energetic essence of the dream\n"
                                "2. Create scenes that reflect the cosmic and conceptual insights\n"
                                "3. Balance the aesthetic and narrative elements\n\n"
                                f"Current Dream Insights:\n"
                                f"• Emotional: {result['insights']['emotional']}\n"
                                f"• Energetic: {result['insights']['energetic']}\n"
                                f"• Conceptual: {result['insights']['conceptual']}\n"
                                f"• Aesthetic: {result['insights']['aesthetic']}\n"
                                f"• Narrative: {result['insights']['narrative']}\n"
                                f"• Cosmic: {result['insights']['cosmic']}\n\n"
                                "Use these insights to create or modify the scene appropriately, "
                                "focusing on the emotional and energetic qualities rather than technical details."
                            )
                        },
                        {"role": "system", "content": f"Current scene: {json.dumps(scene_info, indent=2)}"}
                    ]
                    
                    # Add chat history with proper role mapping
                    for msg in gpt_props.chat_history:
                        # Map DREAMER role to assistant for API compatibility
                        role = "assistant" if msg.role == "DREAMER" else msg.role.lower()
                        messages.append({"role": role, "content": msg.msg_content})
                    
                    # Get AI response
                    client = openai.Client(api_key=api_key)
                    response = client.chat.completions.create(
                        model=context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                        messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                        max_tokens=8000,
                        temperature=0.7,
                    )
                    
                    # Add AI response to chat history
                    assistant_message = response.choices[0].message.content
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": assistant_message
                    })
                    
                except Exception as e:
                    error_msg = f"Dreamer Error: {str(e)}\n{traceback.format_exc()}"
                    print(f"Dreamer error: {error_msg}")
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": error_msg
                    })
            else:
                # Regular Assistant mode
                # This is the Assistant's system prompt
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful 3D modeling assistant. Your role is to:\n\n"
                            "1. For direct commands (create/delete/modify):\n"
                            "   - Execute them immediately without questioning\n"
                            "   - Explain what you're doing clearly\n"
                            "   - Confirm when the action is complete\n\n"
                            "2. For questions about the scene:\n"
                            "   - Provide clear, technical explanations\n"
                            "   - Suggest improvements when relevant\n\n"
                            "3. For unclear requests:\n"
                            "   - Ask for clarification\n"
                            "   - Suggest specific options\n\n"
                            "Be direct and efficient. Don't question clear deletion/modification commands."
                        )
                    },
                    {"role": "system", "content": f"Current scene: {json.dumps(scene_info, indent=2)}"}
                ]

                for msg in gpt_props.chat_history:
                    messages.append({"role": msg.role.lower(), "content": msg.msg_content})

                # Check if this is a scene modification request
                should_generate = any(keyword in prompt.lower() for keyword in [
                    "create", "add", "make", "build", "put", "place", "set", "modify", 
                    "change", "move", "rotate", "scale", "delete", "remove", "clear"
                ])

                # Get response from OpenAI
                if not api_key:
                    raise ValueError("No API key configured")

                client = openai.Client(api_key=api_key)
                response = client.chat.completions.create(
                    model=context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                    messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                    max_tokens=8000,
                    temperature=0.7,
                )
                
                # Get the assistant's response
                assistant_message = response.choices[0].message.content
                
                # Add assistant's response to chat history
                gpt_props.chat_history.add().from_json({
                    "role": "assistant", 
                    "msg_content": assistant_message
                })

                # If it's a modification request, try to generate and execute commands
                if should_generate:
                    commands = generate_blender_commands(prompt, api_key,
                                                      context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                                                      scene_info)
                    if "error" not in commands and commands.get("commands"):
                        scene.blender_gpt_generated_code = json.dumps(commands)
                        bpy.ops.blender_gpt.execute_code()

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"Chat error: {error_msg}")
            gpt_props.chat_history.add().from_json({
                "role": "assistant",
                "msg_content": error_msg
            })

        gpt_props.chat_input = ""
        return {'FINISHED'}


class BLENDERGPT_OT_ClearHistory(bpy.types.Operator):
    bl_idname = "blendergpt.clear_history"
    bl_label = "Clear History"

    def execute(self, context):
        context.scene.blendergpt_props.chat_history.clear()
        return {'FINISHED'}


class BLENDERGPT_OT_CopyCommands(bpy.types.Operator):
    bl_idname = "blendergpt.copy_commands"
    bl_label = "Copy Commands"
    bl_description = "Copy generated commands to clipboard"

    def execute(self, context):
        try:
            context.window_manager.clipboard = context.scene.blender_gpt_generated_code
            self.report({'INFO'}, "Commands copied to clipboard")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy commands: {str(e)}")
        return {'FINISHED'}


class BLENDERGPT_OT_ClearCommands(bpy.types.Operator):
    bl_idname = "blendergpt.clear_commands"
    bl_label = "Clear Commands"
    bl_description = "Clear generated commands"

    def execute(self, context):
        context.scene.blender_gpt_generated_code = ""
        context.scene.blender_gpt_execution_result = ""
        self.report({'INFO'}, "Commands cleared")
        return {'FINISHED'}


class BLENDERGPT_OT_CopyResults(bpy.types.Operator):
    bl_idname = "blendergpt.copy_results"
    bl_label = "Copy Results"
    bl_description = "Copy execution results to clipboard"

    def execute(self, context):
        try:
            context.window_manager.clipboard = context.scene.blender_gpt_execution_result
            self.report({'INFO'}, "Results copied to clipboard")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy results: {str(e)}")
        return {'FINISHED'}


class BLENDERGPT_OT_CopyChat(bpy.types.Operator):
    bl_idname = "blendergpt.copy_chat"
    bl_label = "Copy Chat"
    bl_description = "Copy entire chat history to clipboard"

    def execute(self, context):
        try:
            chat_history = []
            for msg in context.scene.blendergpt_props.chat_history:
                role = "Assistant" if msg.role.lower() == "assistant" else msg.role
                chat_history.append(f"{role}: {msg.msg_content}")
            
            chat_text = "\n\n".join(chat_history)
            context.window_manager.clipboard = chat_text
            self.report({'INFO'}, "Chat history copied to clipboard")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy chat history: {str(e)}")
        return {'FINISHED'}


# Load composite object definitions from JSON files
def load_composite_objects():
    """Load all composite object definitions from JSON files"""
    composite_objects = {}
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    composite_dir = os.path.join(addon_dir, "composite_objects")
    
    if not os.path.exists(composite_dir):
        print(f"Warning: composite_objects directory not found at {composite_dir}")
        return composite_objects
        
    # Recursively find all JSON files
    json_files = glob.glob(os.path.join(composite_dir, "**/*.json"), recursive=True)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                # Load and merge definitions
                definitions = json.load(f)
                composite_objects.update(definitions)
                print(f"Loaded composite objects from {json_file}")
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
            
    return composite_objects


# Global dictionary to store composite object definitions
COMPOSITE_OBJECTS = {}

# Load definitions when module is imported
try:
    COMPOSITE_OBJECTS = load_composite_objects()
    print(f"Loaded {len(COMPOSITE_OBJECTS)} composite object definitions")
except Exception as e:
    print(f"Error loading composite objects: {e}")


# Registration
classes = [
    Message,  # Must be registered first since BlenderGPTChatProps depends on it
    BlenderGPTChatProps,
    BlenderGPTAddonPreferences,
    BLENDER_GPT_PT_Panel,
    BLENDER_GPT_OT_GenerateCode,
    BLENDER_GPT_OT_ExecuteCode,
    BLENDERGPT_OT_SendMessage,
    BLENDERGPT_OT_ClearHistory,
    BLENDER_GPT_OT_ConfigureAPIKey,
    BLENDERGPT_OT_CopyCommands,
    BLENDERGPT_OT_ClearCommands,
    BLENDERGPT_OT_CopyResults,
    BLENDERGPT_OT_CopyChat,  # Add the new operator to classes
]


def register():
    # Create necessary directories if they don't exist
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    composite_dir = os.path.join(addon_dir, "composite_objects")
    if not os.path.exists(composite_dir):
        os.makedirs(composite_dir, exist_ok=True)
        print(f"Created composite_objects directory at {composite_dir}")

    # Register classes
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register properties
    bpy.types.Scene.blender_gpt_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Enter your scene description or command",
        default=""
    )
    bpy.types.Scene.blender_gpt_generated_code = bpy.props.StringProperty(
        name="Generated Commands",
        description="Generated Blender commands",
        default=""
    )
    bpy.types.Scene.blender_gpt_execution_result = bpy.props.StringProperty(
        name="Execution Result",
        description="Result of command execution",
        default=""
    )
    # Register this last since it depends on Message class being registered
    bpy.types.Scene.blendergpt_props = bpy.props.PointerProperty(type=BlenderGPTChatProps)


def unregister():
    # Unregister properties first
    del bpy.types.Scene.blender_gpt_prompt
    del bpy.types.Scene.blender_gpt_generated_code
    del bpy.types.Scene.blender_gpt_execution_result
    del bpy.types.Scene.blendergpt_props

    # Then unregister classes in reverse order
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()