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
from .dreamer import Dreamer
from pathlib import Path
from typing import Dict
from io import StringIO
import math
import requests  # For better HTTP error handling

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
    'openai': 'openai',
    'requests': 'requests'  # Added for better HTTP handling
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
    print(f"Addon directory: {addon_dir}")
    
    # Check for config.json in the parent directory
    parent_dir = os.path.dirname(addon_dir)
    config_path_parent = os.path.join(parent_dir, "config.json")
    print(f"Looking for config.json in parent directory: {config_path_parent}")
    
    if os.path.exists(config_path_parent):
        try:
            with open(config_path_parent, 'r') as config_file:
                config = json.load(config_file)
                print(f"Config contents from parent directory: {config}")
                api_key = config.get("openai_api_key", "").strip()
                if api_key:
                    print("Successfully loaded API key from config.json in parent directory")
                    return api_key
                else:
                    print("No API key found in config.json in parent directory")
        except Exception as e:
            print(f"Error loading API key from config.json in parent directory: {e}")
    else:
        print("No config.json found in parent directory")
    
    # If not found in parent directory, check inside the addon directory
    config_path_addon = os.path.join(addon_dir, "config.json")
    print(f"Looking for config.json in addon directory: {config_path_addon}")
    
    if os.path.exists(config_path_addon):
        try:
            with open(config_path_addon, 'r') as config_file:
                config = json.load(config_file)
                print(f"Config contents from addon directory: {config}")
                api_key = config.get("openai_api_key", "").strip()
                if api_key:
                    print("Successfully loaded API key from config.json in addon directory")
                    return api_key
                else:
                    print("No API key found in config.json in addon directory")
        except Exception as e:
            print(f"Error loading API key from config.json in addon directory: {e}")
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
    def __init__(self, max_requests=120, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.last_cleanup = time.time()

    def can_make_request(self):
        current_time = time.time()
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
            text_box = box.box()
            text_box.scale_y = 3.0
            col = text_box.column()
            col.scale_y = 0.6
            col.prop(scene, "blender_gpt_generated_code", text="", icon='TEXT')
            
            row = box.row(align=True)
            row.operator("blendergpt.copy_commands", text="Copy", icon='COPYDOWN')
            row.operator("blendergpt.clear_commands", text="Clear", icon='X')
        else:
            box.label(text="No commands generated yet")

        # Execution Result
        box = layout.box()
        box.label(text="Result:", icon='INFO')
        if scene.blender_gpt_execution_result:
            box.label(text=scene.blender_gpt_execution_result)
            row = box.row(align=True)
            row.operator("blendergpt.copy_results", text="Copy Results", icon='COPYDOWN')
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

            msg_content = msg.msg_content
            words = msg_content.split()
            lines = []
            current_line = []

            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 50:
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

        # Mode Toggle
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

# Command System (Unused in current script-based workflow, but kept for potential future use)
class BlenderGPTCommands:
    @staticmethod
    def delete_object(name):
        try:
            print(f"\nAttempting to delete object: {name}")
            if name.lower() == "everything":
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
        try:
            print(f"Creating object: type={obj_type}, name={name}, location={location}, color={color}")
            
            if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            
            obj_type = obj_type.upper()
            if obj_type not in ['CUBE', 'SPHERE', 'CONE', 'CYLINDER', 'PLANE']:
                return {"status": "error",
                        "message": f"Unknown object type: {obj_type}. Use CUBE, SPHERE, CONE, CYLINDER, or PLANE."}

            primitive_ops = {
                'CUBE': lambda: bpy.ops.mesh.primitive_cube_add(size=2, location=location),
                'SPHERE': lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=location),
                'CONE': lambda: bpy.ops.mesh.primitive_cone_add(radius1=1, depth=2, location=location),
                'CYLINDER': lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2, location=location),
                'PLANE': lambda: bpy.ops.mesh.primitive_plane_add(size=2, location=location)
            }

            print(f"Executing operator for type: {obj_type}")
            primitive_ops[obj_type]()
            
            obj = bpy.context.active_object
            if not obj:
                return {"status": "error", "message": "Failed to create object - no active object"}

            print(f"Created object: {obj.name}")

            if name:
                obj.name = name
                if obj.name != name:
                    print(f"Warning: Requested name '{name}' was modified to '{obj.name}' to ensure uniqueness")
            
            obj.rotation_euler = rotation
            obj.scale = scale
            
            print(f"Object configured: name={obj.name}, rotation={obj.rotation_euler}, scale={obj.scale}")

            mat = bpy.data.materials.new(name=f"{obj.name}_material")
            mat.use_nodes = True
            
            principled = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if principled:
                if color and len(color) == 3:
                    principled.inputs["Base Color"].default_value = (*color, 1.0)
                else:
                    principled.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
                principled.inputs["Metallic"].default_value = 0.0
                principled.inputs["Roughness"].default_value = 0.5
            
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            print(f"Applied material to {obj.name} with color: {color if color else 'default'}")

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
        try:
            obj_type = obj_type.upper()
            if obj_type not in COMPOSITE_OBJECTS:
                return {"status": "error", "message": f"Unknown composite object type: {obj_type}"}
            
            base_name = name or f"{obj_type}_{random.randint(0,999)}"
            created_objects = []
            
            obj_def = COMPOSITE_OBJECTS[obj_type]
            
            variation_scales = variations or obj_def.get("variations", {})
            
            for comp in obj_def["components"]:
                count = 1
                if "count" in comp:
                    count = random.randint(comp["count"][0], comp["count"][1])
                
                for i in range(count):
                    pos_var = comp.get("position_variance", (0, 0, 0))
                    base_pos = comp.get("position", (0, 0, 0))
                    comp_loc = (
                        location[0] + base_pos[0] + random.uniform(-pos_var[0], pos_var[0]),
                        location[1] + base_pos[1] + random.uniform(-pos_var[1], pos_var[1]),
                        location[2] + base_pos[2] + random.uniform(-pos_var[2], pos_var[2])
                    )
                    
                    base_scale = comp["base_scale"]
                    scale_var = variation_scales.get(f"{comp['name']}_scale", 0.2)
                    comp_scale = tuple(
                        s * random.uniform(1 - scale_var, 1 + scale_var) 
                        for s in base_scale
                    )
                    
                    obj_result = BlenderGPTCommands.create_object(
                        comp["type"],
                        f"{base_name}_{comp['name']}_{i}",
                        comp_loc,
                        scale=comp_scale
                    )
                    
                    if obj_result["status"] == "success":
                        created_objects.append(obj_result)
                        
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


def generate_blender_commands(prompt: str, api_key: str, model: str, scene_info: Dict, chat_history=None) -> Dict:
    """Generate a Blender script via OpenAI API."""
    if not api_key:
        raise ValueError("No API key configured")

    chat_history_str = "\n".join([f"{msg.role}: {msg.msg_content}" for msg in chat_history]) if chat_history else ""

    system_prompt = (
        "You are a Blender Python API expert. Generate a safe, efficient Python script using bpy based on the user's prompt.\n"
        "Use randomization for realism (e.g., positions, scales). Avoid dangerous commands like os.system or eval.\n"
        f"Current scene: {json.dumps(scene_info, indent=2)}\n"
        f"Chat history: {chat_history_str}\n"
        "Return in JSON: {\"script\": \"<script>\", \"description\": \"<desc>\", \"follow_up\": \"<question>\"}\n"
        "No markdown wrappers."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        client = openai.Client(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
            timeout=15
        )

        response_content = response.choices[0].message.content.strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:-3].strip()

        result = json.loads(response_content)
        if not all(key in result for key in ["script", "description", "follow_up"]):
            raise ValueError("Missing required fields in API response")
        return result

    except Exception as e:
        return {
            "script": "",
            "description": f"Error: {str(e)}\nRaw response: {response_content if 'response_content' in locals() else 'N/A'}",
            "follow_up": "Something went wrong. Try rephrasing your prompt or check your API key."
        }
def execute_blender_code(script):
    """
    Safely execute a Blender Python script.
    Returns a dictionary with the result or error message.
    """
    if not script:
        return {"status": "error", "message": "No script provided."}

    dangerous_keywords = ["__import__", "eval", "exec", "os.", "sys.", "subprocess", "shutil", "open("]
    for keyword in dangerous_keywords:
        if keyword in script:
            return {"status": "error", "message": f"Script contains unsafe keyword: {keyword}"}

    start_time = time.time()
    timeout = 10

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = sys.stderr = output = StringIO()

    try:
        exec(script, {"bpy": bpy, "random": random, "math": math})
        if time.time() - start_time > timeout:
            return {"status": "error", "message": "Script execution timed out."}
        return {"status": "success", "message": "Code executed successfully.", "output": output.getvalue()}
    except Exception as e:
        error_msg = f"Error executing script: {str(e)}\n{traceback.format_exc()}"
        return {"status": "error", "message": error_msg, "output": output.getvalue()}
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        output.close()

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
        layout.prop(self, "gpt_model")

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
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
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

    def execute(self, context):
        """Generate a Blender Python script based on the user's prompt."""
        print("\n=== Starting Command Generation ===")
        prompt = context.scene.blender_gpt_prompt.strip()
        if not prompt:
            print("No prompt provided")
            self.report({'WARNING'}, "Please enter a prompt.")
            return {'CANCELLED'}

        scene = context.scene
        gpt_props = scene.blendergpt_props
        scene_info = get_scene_info()  # Assumes this function exists to get current scene data

        try:
            print(f"Generating commands for prompt: '{prompt}'")
            # Call the helper function to generate commands via API
            result = generate_blender_commands(
                prompt,
                api_key,  # Assumes api_key is defined globally or passed appropriately
                context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                scene_info,
                gpt_props.chat_history
            )
            print(f"Generation result: {result}")

            if result["script"]:
                # Store the generated script and update UI
                context.scene.blender_gpt_generated_code = result["script"]
                context.scene.blender_gpt_execution_result = "Commands generated successfully. Click 'Execute' to run the script."
                self.report({'INFO'}, "Commands generated successfully")
            else:
                # Handle case where no script is generated
                context.scene.blender_gpt_generated_code = ""
                context.scene.blender_gpt_execution_result = result["description"]
                self.report({'WARNING'}, "Failed to generate commands")

        except Exception as e:
            error_msg = f"Error generating commands: {str(e)}\n{traceback.format_exc()}"
            print(f"Generation error: {error_msg}")
            context.scene.blender_gpt_execution_result = f"Error: {str(e)}"
            self.report({'ERROR'}, "Failed to generate commands")

        print("=== Command Generation Complete ===\n")
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

        scene = context.scene
        gpt_props = scene.blendergpt_props

        try:
            print(f"Executing script:\n{code}")
            exec_result = execute_blender_code(code)
            print(f"Execution result: {exec_result}")

            if exec_result["status"] == "success":
                # Store the script in the chat history for future modifications
                gpt_props.chat_history.add().from_json({
                    "role": "assistant",
                    "msg_content": "Script executed successfully."
                })
                # Store the script in a scene property for follow-up modifications
                context.scene.blender_gpt_last_script = code
                context.scene.blender_gpt_execution_result = "Code executed successfully."
                self.report({'INFO'}, "Script executed successfully")
            else:
                error_msg = exec_result["message"]
                if "name 'math' is not defined" in error_msg:
                    fixed_script = "import math\n" + code
                    exec_result = execute_blender_code(fixed_script)
                    if exec_result["status"] == "success":
                        gpt_props.chat_history.add().from_json({
                            "role": "assistant",
                            "msg_content": "Fixed an error (missing math import) and executed the script."
                        })
                        context.scene.blender_gpt_last_script = fixed_script
                        context.scene.blender_gpt_execution_result = "Code executed successfully after fixing."
                        self.report({'INFO'}, "Script executed successfully after fixing an error")
                    else:
                        gpt_props.chat_history.add().from_json({
                            "role": "assistant",
                            "msg_content": f"Failed to execute script even after fixing: {exec_result['message']}\nOutput: {exec_result['output']}"
                        })
                        context.scene.blender_gpt_execution_result = f"Error: {exec_result['message']}"
                        self.report({'ERROR'}, "Failed to execute script even after fixing")
                else:
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": f"Failed to execute script: {error_msg}\nOutput: {exec_result['output']}"
                    })
                    context.scene.blender_gpt_execution_result = f"Error: {error_msg}"
                    self.report({'ERROR'}, "Failed to execute script")

        except Exception as e:
            error_msg = f"Error executing script: {str(e)}\n{traceback.format_exc()}"
            print(f"Execution error: {error_msg}")
            gpt_props.chat_history.add().from_json({
                "role": "assistant",
                "msg_content": error_msg
            })
            context.scene.blender_gpt_execution_result = f"Error: {error_msg}"
            self.report({'ERROR'}, "Failed to execute script")

        print("=== Command Execution Complete ===\n")
        return {'FINISHED'}


class BLENDERGPT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blendergpt.send_message"
    bl_label = "Send Message"

    def execute(self, context):
        """Process chat input based on mode (Assistant or Dreamer)."""
        scene = context.scene
        gpt_props = scene.blendergpt_props
        prompt = gpt_props.chat_input.strip()
        scene_info = get_scene_info()  # Assumes this exists

        # Add user's message to chat history
        gpt_props.chat_history.add().from_json({"role": "USER", "msg_content": prompt})

        try:
            if gpt_props.mode == 'DREAMER':
                # Dreamer mode: Creative scene generation
                dreamer_instance = Dreamer()
                last_prompt = context.scene.blender_gpt_prompt if context.scene.blender_gpt_prompt else prompt
                scene_vision = dreamer_instance.process_request(last_prompt)

                print(f"Dreamer scene vision: {json.dumps(scene_vision, indent=2)}")

                # Generate creative insights
                insights = {
                    "emotional": {"tone": random.choice(["serene", "euphoric", "mysterious", "chaotic"])},
                    "energetic": {"flow": random.choice(["steady", "turbulent", "pulsing"])},
                    "conceptual": {"form": random.choice(["organic", "geometric", "fluid"])},
                    "aesthetic": {"texture": random.choice(["smooth", "rough", "crystalline"])},
                    "narrative": {"pace": random.choice(["slow", "fast", "erratic"])},
                    "cosmic": {"reality": random.choice(["whole", "fractured", "ethereal"])}
                }

                # Format the response
                display_response = "✨ Dreamer Scene Interpretation ✨\n\n"
                display_response += f"Emotional Tone: {insights['emotional']['tone'].title()}\n"
                display_response += f"Energetic Flow: {insights['energetic']['flow'].title()}\n"
                display_response += f"Conceptual Form: {insights['conceptual']['form'].title()}\n"
                display_response += f"Aesthetic Texture: {insights['aesthetic']['texture'].title()}\n"
                display_response += f"Narrative Pace: {insights['narrative']['pace'].title()}\n"
                display_response += f"Cosmic Reality: {insights['cosmic']['reality'].title()}\n\n"
                display_response += "Scene Breakdown:\n"
                for obj in scene_vision["objects"]:
                    display_response += f"Object: {obj['type']} (Count: {obj['count']})\n"
                    for comp in obj["components"]:
                        display_response += f"  - Component: {comp['name']} ({comp['primitive']}, Dimensions: {comp['dimensions']})\n"
                    if obj["properties"]:
                        display_response += f"  Properties: {obj['properties']}\n"
                for rel in scene_vision["relationships"]:
                    display_response += f"Relationship: {rel['type']} between {rel['objects']} (Max Distance: {rel['max_distance']})\n"
                gpt_props.chat_history.add().from_json({
                    "role": "DREAMER",
                    "msg_content": display_response
                })

                # Generate and execute a script based on the vision
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a Blender Python API expert. Generate a Python script using bpy to create a scene based on the Dreamer's vision and insights.\n"
                            "The script must be safe and use randomization for realism (e.g., positions, scales).\n"
                            f"Dreamer Scene Vision:\n{json.dumps(scene_vision, indent=2)}\n"
                            f"Dreamer Insights:\n{json.dumps(insights, indent=2)}\n"
                            f"Current Scene Info:\n{json.dumps(scene_info, indent=2)}\n"
                            "Return in JSON: {\"script\": \"<script>\", \"description\": \"<desc>\", \"follow_up\": \"<question>\"}\n"
                            "No markdown wrappers like ```json."
                        )
                    }
                ]

                for msg in gpt_props.chat_history:
                    role = "assistant" if msg.role == "DREAMER" else msg.role.lower()
                    messages.append({"role": role, "content": msg.msg_content})

                client = openai.Client(api_key=api_key)
                response = client.chat.completions.create(
                    model=context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                    messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                    max_tokens=8000,
                    temperature=0.7,
                    timeout=15
                )

                response_content = response.choices[0].message.content.strip()
                if response_content.startswith("```json"):
                    response_content = response_content[7:-3].strip()

                result = json.loads(response_content)
                if result["script"]:
                    exec_result = execute_blender_code(result["script"])
                    if exec_result["status"] == "success":
                        gpt_props.chat_history.add().from_json({
                            "role": "DREAMER",
                            "msg_content": f"{result['description']}\nCode executed successfully."
                        })
                    else:
                        gpt_props.chat_history.add().from_json({
                            "role": "DREAMER",
                            "msg_content": f"Failed to execute script: {exec_result['message']}\nOutput: {exec_result['output']}"
                        })
                    gpt_props.chat_history.add().from_json({
                        "role": "DREAMER",
                        "msg_content": result["follow_up"]
                    })

            else:
                # Assistant mode: Generate scripts for action prompts only
                action_keywords = ["make", "generate", "add", "create", "modify", "scale", "material"]
                should_generate = any(keyword in prompt.lower() for keyword in action_keywords)

                if should_generate:
                    result = generate_blender_commands(
                        prompt,
                        api_key,
                        context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                        scene_info,
                        gpt_props.chat_history
                    )

                    if result["script"]:
                        try:
                            exec_result = execute_blender_code(result["script"])
                            if exec_result["status"] == "success":
                                gpt_props.chat_history.add().from_json({
                                    "role": "assistant",
                                    "msg_content": f"{result['description']}\n{exec_result['message']}"
                                })
                                context.scene.blender_gpt_last_script = result["script"]
                            else:
                                gpt_props.chat_history.add().from_json({
                                    "role": "assistant",
                                    "msg_content": f"Failed to execute script: {exec_result['message']}\nOutput: {exec_result['output']}"
                                })
                            gpt_props.chat_history.add().from_json({
                                "role": "assistant",
                                "msg_content": result["follow_up"]
                            })
                        except Exception as e:
                            error_msg = f"Failed to execute script: {str(e)}\n{traceback.format_exc()}"
                            gpt_props.chat_history.add().from_json({
                                "role": "assistant",
                                "msg_content": error_msg
                            })
                    else:
                        gpt_props.chat_history.add().from_json({
                            "role": "assistant",
                            "msg_content": result["description"]
                        })
                        gpt_props.chat_history.add().from_json({
                            "role": "assistant",
                            "msg_content": result["follow_up"]
                        })
                else:
                    # Conversational response for non-action prompts
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a Blender scene assistant. Describe the scene or answer questions without generating scripts unless asked.\n"
                                f"Current scene: {json.dumps(scene_info, indent=2)}\n"
                                "Respond conversationally."
                            )
                        }
                    ]
                    for msg in gpt_props.chat_history:
                        messages.append({"role": msg.role.lower(), "content": msg.msg_content})

                    client = openai.Client(api_key=api_key)
                    response = client.chat.completions.create(
                        model=context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                        messages=messages,
                        max_tokens=500,
                        temperature=0.7,
                        timeout=15
                    )

                    assistant_message = response.choices[0].message.content
                    gpt_props.chat_history.add().from_json({
                        "role": "assistant",
                        "msg_content": assistant_message
                    })

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            print(f"Chat error: {error_msg}")
            gpt_props.chat_history.add().from_json({
                "role": "assistant",
                "msg_content": error_msg
            })

        gpt_props.chat_input = ""  # Clear input field
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
        
    json_files = glob.glob(os.path.join(composite_dir, "**/*.json"), recursive=True)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
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
    Message,
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
    BLENDERGPT_OT_CopyChat,
]

def register():
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    composite_dir = os.path.join(addon_dir, "composite_objects")
    if not os.path.exists(composite_dir):
        os.makedirs(composite_dir, exist_ok=True)
        print(f"Created composite_objects directory at {composite_dir}")

    for cls in classes:
        bpy.utils.register_class(cls)

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
    bpy.types.Scene.blender_gpt_last_script = bpy.props.StringProperty(
        name="Last Generated Script",
        description="The last script that was generated and executed",
        default=""
    )
    bpy.types.Scene.blendergpt_props = bpy.props.PointerProperty(type=BlenderGPTChatProps)

def unregister():
    del bpy.types.Scene.blender_gpt_prompt
    del bpy.types.Scene.blender_gpt_generated_code
    del bpy.types.Scene.blender_gpt_execution_result
    del bpy.types.Scene.blender_gpt_last_script
    del bpy.types.Scene.blendergpt_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()