import bpy
import json
import re
import sys
import traceback
import ast
import os
import random
import time
import openai

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

# Load API key
addon_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(addon_dir, "config.json")
print(f"Looking for config.json at: {config_path}")
api_key = None


def load_api_key():
    global api_key
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                api_key = config.get("openai_api_key", "").strip()
        except Exception as e:
            print(f"Error loading API key: {e}")
            api_key = None
    return api_key


def save_api_key(api_key: str):
    """Save the API key to config file."""
    try:
        config = {"openai_api_key": api_key}
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving API key: {e}")
        return False


# Load API key on startup
api_key = load_api_key()


# Rate limiting
class RateLimiter:
    def __init__(self, max_requests=60, time_window=60):  # 60 requests per minute
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    def can_make_request(self):
        current_time = time.time()
        # Remove old requests
        self.requests = [t for t in self.requests if current_time - t < self.time_window]
        return len(self.requests) < self.max_requests

    def add_request(self):
        self.requests.append(time.time())


rate_limiter = RateLimiter()

bl_info = {
    "name": "BlenderGPT",
    "author": "virtualdmns",
    "version": (1, 1, 6),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderGPT",
    "description": "Dynamic GPT integration with primitives for scene creation.",
    "category": "Interface",
}


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
    def create_object(obj_type, name=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        try:
            bpy.ops.object.select_all(action='DESELECT')
            if obj_type.upper() not in ['CUBE', 'SPHERE', 'CONE', 'CYLINDER', 'PLANE']:
                return {"status": "error",
                        "message": f"Unknown object type: {obj_type}. Use CUBE, SPHERE, CONE, CYLINDER, or PLANE."}

            # Ensure minimum spacing if location is [0,0,0]
            if location == (0, 0, 0):
                existing_locations = [obj["location"] for obj in get_scene_info()["objects"]]
                x, y = 0, 0
                for i in range(100):  # Try up to 100 times to find a non-overlapping spot
                    x = random.uniform(-10, 10)
                    y = random.uniform(-10, 10)
                    new_location = [x, y, 0]
                    too_close = any(
                        ((loc[0] - x) ** 2 + (loc[1] - y) ** 2) < 2 ** 2 for loc in existing_locations
                    )
                    if not too_close:
                        break
                location = (x, y, 0)

            # Map object types to their respective primitive add operators
            primitive_ops = {
                'CUBE': lambda: bpy.ops.mesh.primitive_cube_add(size=2, location=location),
                'SPHERE': lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=location),
                'CONE': lambda: bpy.ops.mesh.primitive_cone_add(radius1=1, depth=2, location=location),
                'CYLINDER': lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2, location=location),
                'PLANE': lambda: bpy.ops.mesh.primitive_plane_add(size=2, location=location)
            }

            # Execute the appropriate operator
            primitive_ops[obj_type.upper()]()
            obj = bpy.context.active_object

            if not obj:
                return {"status": "error", "message": "Failed to create object"}

            # Set name, rotation, and scale with randomization
            obj.name = name if name else f"{obj_type}_{random.randint(0, 999)}"
            obj.rotation_euler = rotation
            obj.scale = [s * random.uniform(0.5, 1.5) for s in scale]

            # Apply a default material if none specified
            if not obj.data.materials:
                mat = bpy.data.materials.new(name=f"{obj.name}_material")
                mat.use_nodes = True
                principled = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                principled.inputs["Base Color"].default_value = [0.5, 0.5, 0.5, 1.0]
                obj.data.materials.append(mat)

            return {"status": "success", "name": obj.name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

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


class CommandValidationError(Exception):
    """Custom exception for command validation errors."""
    pass


def validate_command(cmd: dict) -> bool:
    """Validate command structure and parameters."""
    if not isinstance(cmd, dict):
        raise CommandValidationError(f"Command must be a dictionary, got {type(cmd)}")

    if "command" in cmd:
        cmd_name = cmd["command"]
        cmd_params = {k: v for k, v in cmd.items() if k != "command"}
    elif len(cmd) == 1:
        cmd_name = list(cmd.keys())[0]
        cmd_params = cmd[cmd_name]
    else:
        raise CommandValidationError(f"Invalid command structure: {cmd}")

    if not isinstance(cmd_params, dict):
        raise CommandValidationError(f"Command parameters must be a dictionary, got {type(cmd_params)}")

    # Validate specific command types
    if cmd_name == "create_object":
        if "type" not in cmd_params:
            raise CommandValidationError("create_object requires a 'type' parameter")
        if cmd_params["type"].upper() not in ['CUBE', 'SPHERE', 'CONE', 'CYLINDER', 'PLANE']:
            raise CommandValidationError(f"Invalid object type: {cmd_params['type']}")

    elif cmd_name == "set_material":
        if "obj_name" not in cmd_params:
            raise CommandValidationError("set_material requires an 'obj_name' parameter")
        if "color" in cmd_params and len(cmd_params["color"]) != 3:
            raise CommandValidationError("color must be a list of 3 values [r,g,b]")

    elif cmd_name == "modify_object":
        if "name" not in cmd_params:
            raise CommandValidationError("modify_object requires a 'name' parameter")

    return True


# Command Generation
def generate_blender_commands(prompt: str, api_key: str, model: str, scene_info=None, last_result=None,
                              messages=None) -> dict:
    try:
        if not rate_limiter.can_make_request():
            return {"error": "Rate limit exceeded. Please wait before making more requests."}

        rate_limiter.add_request()

        api_key = api_key.strip()
        api_key = ''.join(char for char in api_key if ord(char) < 128 and char.isprintable())
        print(f"Using API key (first 8, last 4): {api_key[:8]}...{api_key[-4:]}")
        print(f"API key length: {len(api_key)}")

        if not api_key:
            raise ValueError("No API key provided. Please set it in config.json.")

        client = openai.Client(api_key=api_key)

        if messages is None:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are BlenderGPT, an AI assistant for Blender. Your task is to assist the user by generating commands to modify the scene or providing detailed explanations based on their prompt. "
                        "Available commands for scene modification:\n"
                        "- create_object(type, name=None, location=[x,y,z], rotation=[x,y,z], scale=[x,y,z]): Types include CUBE, SPHERE, CONE, CYLINDER, PLANE.\n"
                        "- set_material(obj_name, color=[r,g,b], metallic=0-1, roughness=0-1): Apply materials with realistic colors and properties.\n"
                        "- modify_object(name, location=[x,y,z], rotation=[x,y,z], scale=[x,y,z], visible=bool): Adjust existing objects.\n"
                        "Guidelines:\n"
                        "1. For scene modification prompts (e.g., 'create a forest', 'add a car'), generate commands:\n"
                        "   - Break down complex objects into multiple create_object calls (e.g., a 'tree' might use a CYLINDER for the trunk and a CONE for foliage).\n"
                        "   - Use appropriate primitives (e.g., SPHERE for balls, CUBE for buildings).\n"
                        "   - Ensure objects are spaced apart by at least 2 units in the X-Y plane, using varied locations (e.g., randomize X and Y between -10 and 10).\n"
                        "   - Add variation: Randomize scale (0.5-1.5), rotation (especially Z-axis), and colors for diverse results.\n"
                        "   - For natural objects like trees, apply realistic materials immediately after creation:\n"
                        "     * Tree trunks: Brown color [0.36, 0.20, 0.09], roughness=0.8, metallic=0.0\n"
                        "     * Foliage: Green color [0.13, 0.55, 0.13], roughness=0.9, metallic=0.0\n"
                        "     * Ground: Natural green [0.1, 0.4, 0.1], roughness=1.0, metallic=0.0\n"
                        "   - Position foliage above trunks proportionally (e.g., foliage_z = trunk_z + trunk_scale_z * 2)\n"
                        "   - Randomize rotation on all axes (X/Y between -0.1 and 0.1 radians, Z between 0 and 3.14)\n"
                        "   - Suggest reasonable defaults for missing details (e.g., location, scale).\n"
                        "   - Use meaningful names (e.g., 'TreeTrunk.001', 'TreeFoliage.001').\n"
                        "   - Output JSON: {'explanation': str, 'commands': list}, where each command is a dictionary.\n"
                        "2. For informational prompts (e.g., 'explain the scene'), analyze scene_info and provide details.\n"
                        "3. If the prompt is vague, ask for clarification in the 'explanation' field.\n"
                        "4. For natural scenes, consider adding ground planes and appropriate lighting.\n"
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
            messages=messages,
            max_tokens=8000,
            temperature=0.7,
        )
        raw_content = response.choices[0].message.content
        print(f"Raw response content: {raw_content}")

        # Parse the response as JSON
        try:
            parsed_response = json.loads(raw_content)
            if "explanation" not in parsed_response or "commands" not in parsed_response:
                # Not the format we want, but let's salvage it
                return {
                    "explanation": raw_content,
                    "commands": []
                }
            return parsed_response
        except json.JSONDecodeError:
            # If GPT returned something that's not JSON, just treat it as plain text
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
        bpy.ops.ed.undo_push(message="Before blender_gpt execution")
        result = {"status": "success", "details": [], "progress": 0}

        if "commands" not in commands:
            return {"status": "error", "message": "No 'commands' key found in the input."}

        total_commands = len(commands["commands"])
        for i, cmd in enumerate(commands["commands"], 1):
            try:
                print(f"Executing command {i}/{total_commands}: {cmd}")
                result["progress"] = (i / total_commands) * 100

                # Validate command before execution
                validate_command(cmd)

                if "command" in cmd:
                    cmd_name = cmd["command"]
                    cmd_params = {k: v for k, v in cmd.items() if k != "command"}
                    cmd = {cmd_name: cmd_params}
                elif len(cmd) == 1:
                    cmd_name = list(cmd.keys())[0]
                    cmd_params = cmd[cmd_name]
                else:
                    cmd_name = None
                    cmd_params = {}
                    if "create_object" in cmd and isinstance(cmd["create_object"], str):
                        cmd_name = "create_object"
                        cmd_params = {"type": cmd["create_object"]}
                        for key in cmd:
                            if key != "create_object":
                                cmd_params[key] = cmd[key]
                    elif "set_material" in cmd or "modify_object" in cmd:
                        cmd_name = "set_material" if "set_material" in cmd else "modify_object"
                        cmd_params = cmd
                    else:
                        result["details"].append({"status": "error", "message": f"Invalid command structure: {cmd}"})
                        continue

                # Execute command with progress tracking
                if cmd_name == "create_object":
                    if "type" in cmd_params:
                        cmd_params["obj_type"] = cmd_params.pop("type")
                    res = BlenderGPTCommands.create_object(**cmd_params)
                    result["details"].append(res)
                    if isinstance(res.get("name"), list):
                        for name in res["name"]:
                            print(f"Created composite object part: {name}")
                elif cmd_name == "set_material":
                    result["details"].append(BlenderGPTCommands.set_material(**cmd_params))
                elif cmd_name == "modify_object":
                    result["details"].append(BlenderGPTCommands.modify_object(**cmd_params))
                else:
                    result["details"].append({"status": "error", "message": f"Unknown command: {cmd_name}"})

            except CommandValidationError as e:
                result["details"].append({"status": "error", "message": str(e)})
            except Exception as e:
                result["details"].append({"status": "error", "message": f"Error executing command: {str(e)}"})

        bpy.context.view_layer.update()
        bpy.ops.ed.undo_push(message="After blender_gpt execution")
        result["progress"] = 100
        return result

    except Exception as e:
        return {"status": "error", "message": f"{str(e)}\n{traceback.format_exc()}"}


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
        layout.label(text="API Key in config.json in addon directory.")
        layout.prop(self, "gpt_model")


# Chat Interface
class Message(bpy.types.PropertyGroup):
    role: bpy.props.StringProperty()
    msg_content: bpy.props.StringProperty()

    def from_json(self, data):
        self.role = data["role"]
        self.msg_content = data["msg_content"]


class BlenderGPTChatProps(bpy.types.PropertyGroup):
    chat_history: bpy.props.CollectionProperty(type=Message)
    chat_input: bpy.props.StringProperty(default="")


# Combined Panel
class BLENDER_GPT_PT_Panel(bpy.types.Panel):
    bl_label = "BlenderGPT"
    bl_idname = "BLENDER_GPT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderGPT'

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
            box.operator("blendergpt.configure_api_key", text="Configure API Key")

        # Prompt Section
        box = layout.box()
        box.label(text="Generate Scene:", icon='MESH_DATA')
        box.prop(scene, "blender_gpt_prompt", text="Prompt")
        row = box.row()
        row.operator("blender_gpt.generate_code", text="Generate")
        row.operator("blender_gpt.execute_code", text="Execute")

        # Progress Section
        if hasattr(scene, "blender_gpt_progress"):
            box = layout.box()
            box.label(text=f"Progress: {int(scene.blender_gpt_progress)}%", icon='TIME')
            row = box.row()
            row.prop(scene, "blender_gpt_progress", text="")
            if scene.blender_gpt_progress == 100:
                row.label(text="Complete!", icon='CHECKMARK')
            elif scene.blender_gpt_progress > 0:
                row.label(text="Processing...", icon='SORTTIME')

        # Generated Commands
        box = layout.box()
        box.label(text="Generated Commands:", icon='TEXT')
        if scene.blender_gpt_generated_code:
            try:
                cmd_data = json.loads(scene.blender_gpt_generated_code)
                if "explanation" in cmd_data:
                    # Split long explanation into multiple lines
                    explanation = cmd_data["explanation"]
                    words = explanation.split()
                    lines = []
                    current_line = []

                    for word in words:
                        current_line.append(word)
                        if len(" ".join(current_line)) > 50:  # Max 50 characters per line
                            lines.append(" ".join(current_line[:-1]))
                            current_line = [word]
                    if current_line:
                        lines.append(" ".join(current_line))

                    for line in lines:
                        box.label(text=line)

                if "commands" in cmd_data and cmd_data["commands"]:
                    for cmd in cmd_data["commands"]:
                        if isinstance(cmd, dict):
                            if "command" in cmd:
                                cmd_str = f"• {cmd['command']}: " + ", ".join(
                                    f"{k}={v}" for k, v in cmd.items() if k != "command")
                            else:
                                cmd_name = next(iter(cmd))
                                cmd_value = cmd[cmd_name]
                                if isinstance(cmd_value, dict):
                                    cmd_str = f"• {cmd_name}: " + ", ".join(f"{k}={v}" for k, v in cmd_value.items())
                                else:
                                    cmd_str = f"• {cmd_name}: {cmd_value}"
                            box.label(text=cmd_str, icon='DOT')
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
            col.label(text=f"{msg.role}:", icon='USER' if msg.role == 'USER' else 'TEXT')

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


class BLENDERGPT_OT_ConfigureAPIKey(bpy.types.Operator):
    bl_idname = "blendergpt.configure_api_key"
    bl_label = "Configure API Key"
    bl_description = "Configure OpenAI API Key"

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Your OpenAI API Key",
        type='PASSWORD'
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.api_key:
            if save_api_key(self.api_key):
                self.report({'INFO'}, "API key saved successfully")
            else:
                self.report({'ERROR'}, "Failed to save API key")
        return {'FINISHED'}


class BLENDER_GPT_OT_GenerateCode(bpy.types.Operator):
    bl_idname = "blender_gpt.generate_code"
    bl_label = "Generate Code"
    bl_description = "Generate Blender commands from prompt"

    def execute(self, context):
        prefs = context.preferences.addons["addon_blender_gpt"].preferences
        model = prefs.gpt_model

        if not api_key:
            self.report({'ERROR'}, "No API key found. Please configure it first.")
            return {'CANCELLED'}

        prompt = context.scene.blender_gpt_prompt
        if not prompt.strip():
            self.report({'WARNING'}, "Please enter a prompt first")
            return {'CANCELLED'}

        scene_info = get_scene_info()
        commands = generate_blender_commands(prompt, api_key, model, scene_info)

        if "error" in commands:
            context.scene.blender_gpt_generated_code = json.dumps({"explanation": f"Error: {commands['error']}"})
            self.report({'ERROR'}, commands['error'])
            return {'CANCELLED'}

        context.scene.blender_gpt_generated_code = json.dumps(commands)
        context.scene.blender_gpt_execution_result = ""
        self.report({'INFO'}, "Commands generated successfully")
        return {'FINISHED'}


class BLENDER_GPT_OT_ExecuteCode(bpy.types.Operator):
    bl_idname = "blender_gpt.execute_code"
    bl_label = "Execute Code"

    def execute(self, context):
        code = context.scene.blender_gpt_generated_code
        if not code.strip():
            self.report({'WARNING'}, "No commands to execute.")
            return {'CANCELLED'}
        try:
            commands = json.loads(code)
            result = execute_generated_commands(commands)

            # Update progress in the scene
            if "progress" in result:
                context.scene.blender_gpt_progress = result["progress"]

            context.scene.blender_gpt_execution_result = json.dumps(result)
            if result["status"] == "error":
                self.report({'ERROR'}, result["message"])
            else:
                self.report({'INFO'}, "Objects spawned successfully.")
        except Exception as e:
            context.scene.blender_gpt_execution_result = json.dumps(
                {"status": "error", "message": f"Execution failed: {str(e)}\n{traceback.format_exc()}"})
            self.report({'ERROR'}, f"Execution failed: {str(e)}")
        return {'FINISHED'}


class BLENDERGPT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blendergpt.send_message"
    bl_label = "Send Message"

    def execute(self, context):
        scene = context.scene
        gpt_props = scene.blendergpt_props
        prompt = gpt_props.chat_input
        scene_info = get_scene_info()

        messages = [
            {
                "role": "system",
                "content": (
                    "You are BlenderGPT, an AI assistant for Blender. Generate commands for any prompt and provide detailed explanations. "
                    "Analyze scene_info to inform your decisions. For questions, describe the scene with object details. "
                    "For vague prompts, ask for clarification or make a best guess. Suggest possible adjustments after actions."
                )
            },
            {"role": "system", "content": f"Current scene: {json.dumps(scene_info, indent=2)}"}
        ]

        for msg in gpt_props.chat_history:
            messages.append({"role": msg.role.lower(), "content": msg.msg_content})
        messages.append({"role": "user", "content": prompt})

        commands = generate_blender_commands(prompt, api_key,
                                             context.preferences.addons["addon_blender_gpt"].preferences.gpt_model,
                                             scene_info, messages=messages)

        gpt_props.chat_history.add().from_json({"role": "USER", "msg_content": prompt})
        if "error" in commands:
            gpt_props.chat_history.add().from_json({"role": "BlenderGPT", "msg_content": f"Error: {commands['error']}"})
        else:
            explanation = commands.get("explanation", "Commands generated successfully.")
            gpt_props.chat_history.add().from_json({"role": "BlenderGPT", "msg_content": explanation})
            if any(keyword in prompt.lower() for keyword in ["create", "add", "modify", "delete"]) and commands.get(
                    "commands"):
                bpy.ops.blender_gpt.execute_code()

        gpt_props.chat_input = ""
        return {'FINISHED'}


class BLENDERGPT_OT_ClearHistory(bpy.types.Operator):
    bl_idname = "blendergpt.clear_history"
    bl_label = "Clear History"

    def execute(self, context):
        context.scene.blendergpt_props.chat_history.clear()
        return {'FINISHED'}


# Registration
classes = [
    BlenderGPTAddonPreferences,
    BLENDER_GPT_PT_Panel,
    BLENDER_GPT_OT_GenerateCode,
    BLENDER_GPT_OT_ExecuteCode,
    Message,
    BlenderGPTChatProps,
    BLENDERGPT_OT_SendMessage,
    BLENDERGPT_OT_ClearHistory,
    BLENDERGPT_OT_ConfigureAPIKey,
]


def register():
    print(f"Registering addon: {__name__}")
    for cls in classes:
        print(f"Registering class: {cls.__name__}")
        bpy.utils.register_class(cls)
    if hasattr(bpy.types.Scene, "blender_gpt_prompt"):
        del bpy.types.Scene.blender_gpt_prompt
    if hasattr(bpy.types.Scene, "blender_gpt_generated_code"):
        del bpy.types.Scene.blender_gpt_generated_code
    if hasattr(bpy.types.Scene, "blender_gpt_execution_result"):
        del bpy.types.Scene.blender_gpt_execution_result
    if hasattr(bpy.types.Scene, "blendergpt_props"):
        del bpy.types.Scene.blendergpt_props
    if hasattr(bpy.types.Scene, "blender_gpt_progress"):
        del bpy.types.Scene.blender_gpt_progress

    bpy.types.Scene.blender_gpt_prompt = bpy.props.StringProperty(
        default="",
        description="Enter your prompt here"
    )
    bpy.types.Scene.blender_gpt_generated_code = bpy.props.StringProperty(
        options={'TEXTEDIT_UPDATE'},
        description="Generated commands"
    )
    bpy.types.Scene.blender_gpt_execution_result = bpy.props.StringProperty(
        description="Execution results"
    )
    bpy.types.Scene.blendergpt_props = bpy.props.PointerProperty(
        type=BlenderGPTChatProps
    )
    bpy.types.Scene.blender_gpt_progress = bpy.props.FloatProperty(
        default=0.0,
        min=0.0,
        max=100.0,
        description="Operation progress"
    )
    print("BlenderGPT Addon registered successfully.")


def unregister():
    print(f"Unregistering addon: {__name__}")
    for cls in reversed(classes):
        print(f"Unregistering class: {cls.__name__}")
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "blender_gpt_prompt"):
        del bpy.types.Scene.blender_gpt_prompt
    if hasattr(bpy.types.Scene, "blender_gpt_generated_code"):
        del bpy.types.Scene.blender_gpt_generated_code
    if hasattr(bpy.types.Scene, "blender_gpt_execution_result"):
        del bpy.types.Scene.blender_gpt_execution_result
    if hasattr(bpy.types.Scene, "blendergpt_props"):
        del bpy.types.Scene.blendergpt_props
    if hasattr(bpy.types.Scene, "blender_gpt_progress"):
        del bpy.types.Scene.blender_gpt_progress
    print("BlenderGPT Addon unregistered successfully.")


if __name__ == "__main__":
    register()