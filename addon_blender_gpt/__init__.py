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
import requests

# Debug sys.path
print("Initial Python sys.path:")
for p in sys.path:
    print(f"  {p}")

# Add user site-packages path
site_packages_path = os.path.expanduser("~/.local/lib/python3.11/site-packages")
if os.path.exists(site_packages_path) and site_packages_path not in sys.path:
    sys.path.append(site_packages_path)
    print(f"Added to sys.path: {site_packages_path}")

# Add addon directory to path
addon_dir = os.path.dirname(os.path.realpath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)
    print(f"Added addon directory to sys.path: {addon_dir}")

# Verify required packages
required_packages = {'openai': 'openai', 'requests': 'requests'}
for package, import_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"Successfully imported {package}")
    except ImportError as e:
        raise ImportError(f"{package} not found. Install with: /Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install {package}")

import openai

# Load API key
def load_api_key():
    global api_key
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    for config_path in [os.path.join(os.path.dirname(addon_dir), "config.json"), os.path.join(addon_dir, "config.json")]:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as config_file:
                    config = json.load(config_file)
                    api_key = config.get("openai_api_key", "").strip()
                    if api_key:
                        print(f"Loaded API key from {config_path}")
                        return api_key
            except Exception as e:
                print(f"Error loading API key from {config_path}: {e}")
    print("No valid config.json found")
    return None

def save_api_key(api_key: str):
    try:
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        with open(config_path, 'w') as config_file:
            json.dump({"openai_api_key": api_key}, config_file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving API key: {e}")
        return False

# Initialize API key
api_key = load_api_key()

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
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderGPT",
    "description": "Generate and execute Blender commands using GPT with iterative enhancements",
    "category": "3D View",
}

# Message class for chat history
class Message(bpy.types.PropertyGroup):
    role: bpy.props.StringProperty(name="Role", default="USER")
    msg_content: bpy.props.StringProperty(name="Message Content", default="")

    def from_json(self, data):
        self.role = data.get("role", "USER")
        self.msg_content = data.get("msg_content", "")

# Chat properties
class BlenderGPTChatProps(bpy.types.PropertyGroup):
    chat_history: bpy.props.CollectionProperty(type=Message)
    chat_input: bpy.props.StringProperty(name="Chat Input", default="")
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[('ASSISTANT', 'Assistant', ''), ('DREAMER', 'Dreamer', '')],
        default='ASSISTANT'
    )
    iterations: bpy.props.IntProperty(name="Iterations", default=0, min=0, max=10)
    iteration_progress: bpy.props.FloatProperty(name="Iteration Progress", default=0.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    current_iteration: bpy.props.IntProperty(name="Current Iteration", default=0, min=0)
    total_iterations: bpy.props.IntProperty(name="Total Iterations", default=0, min=0)

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
        box.label(text="✓ API Key Configured" if api_key else "⚠ No API Key Found", icon='CHECKMARK' if api_key else 'ERROR')
        if not api_key:
            box.operator("blendergpt.configure_api_key", text="Load API Key")

        # Prompt Section
        box = layout.box()
        box.label(text="Generate Scene:", icon='MESH_DATA')
        box.prop(scene, "blender_gpt_prompt", text="Prompt")
        box.label(text="Additional Iterations:")
        box.prop(gpt_props, "iterations", text="")
        if gpt_props.total_iterations > 0:
            box.label(text=f"Iteration {gpt_props.current_iteration}/{gpt_props.total_iterations}")
            box.prop(gpt_props, "iteration_progress", text="", slider=True)
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
            col.prop(scene, "blender_gpt_generated_code", text="")
            row = box.row()
            row.operator("blendergpt.copy_commands", text="Copy")
            row.operator("blendergpt.clear_commands", text="Clear")
        else:
            box.label(text="No commands generated yet")

        # Execution Result
        box = layout.box()
        box.label(text="Result:", icon='INFO')
        if scene.blender_gpt_execution_result:
            box.label(text=scene.blender_gpt_execution_result)
            box.operator("blendergpt.copy_results", text="Copy Results")

        # Chat Section
        box = layout.box()
        box.label(text="Chat with BlenderGPT:", icon='TEXT')
        for msg in gpt_props.chat_history:
            msg_box = box.box()
            row = msg_box.row()
            col = row.column()
            display_role = msg.role if msg.role in ["DREAMER", "USER"] else "Assistant"
            col.label(text=f"{display_role}:", icon='USER' if msg.role == 'USER' else 'TEXT')
            col = row.column()
            for line in [msg.msg_content[i:i+50] for i in range(0, len(msg.msg_content), 50)]:
                col.label(text=line)
        box.prop(gpt_props, "chat_input", text="Message")
        row = box.row()
        row.operator("blendergpt.send_message", text="Send")
        row.operator("blendergpt.clear_history", text="Clear")

        # Mode Toggle
        box = layout.box()
        box.label(text="Mode:", icon='MODIFIER')
        box.prop(gpt_props, "mode", expand=True)

# Modal Operator for Iterative Generation
class BLENDERGPT_OT_IterativeGeneration(bpy.types.Operator):
    bl_idname = "blendergpt.iterative_generation"
    bl_label = "Iterative Scene Generation"

    initial_prompt: bpy.props.StringProperty()
    api_key: bpy.props.StringProperty()
    model: bpy.props.StringProperty()
    iterations: bpy.props.IntProperty()
    _timer = None
    current_iteration = 0

    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            context.scene.blender_gpt_execution_result = "Iterative generation cancelled by user."
            return {'CANCELLED'}

        if event.type == 'TIMER' and self.current_iteration < self.iterations:
            try:
                # Get current scene info
                scene_info = get_scene_info()
                existing_objects = [obj["type"] for obj in scene_info.get("objects", [])]
                object_counts = {}
                for obj in existing_objects:
                    object_counts[obj] = object_counts.get(obj, 0) + 1
                scene_description = "The scene currently contains: " + ", ".join(f"{count} {obj_type}(s)" for obj_type, count in object_counts.items()) + "."
                print(f"\n=== Iteration {self.current_iteration + 1}/{self.iterations} ===")
                print(f"Scene Analysis: {scene_description}")

                # Dynamic prompt
                new_prompt = (
                    f"Based on the initial request: {self.initial_prompt}\n"
                    f"Current scene: {scene_description}\n"
                    "Suggest and add a new element that complements the existing scene, properly spaced in the 3D environment to avoid clutter."
                )
                print(f"Generated Prompt: {new_prompt}")

                # Generate and execute commands
                gpt_props = context.scene.blendergpt_props
                result = generate_blender_commands(new_prompt, self.api_key, self.model, scene_info, gpt_props.chat_history)
                if result["script"]:
                    exec_result = execute_blender_code(result["script"])
                    if exec_result["status"] == "success":
                        print(f"Action Taken: {result['description']}")
                        print(f"Script Executed:\n{result['script']}")
                        context.scene.blender_gpt_execution_result = f"Iteration {self.current_iteration + 1}/{self.iterations}: {result['description']}"
                    else:
                        print(f"Error: {exec_result['message']}")
                        context.scene.blender_gpt_execution_result = f"Iteration {self.current_iteration + 1}/{self.iterations} failed: {exec_result['message']}"
                else:
                    print(f"Error: {result['description']}")
                    context.scene.blender_gpt_execution_result = f"Iteration {self.current_iteration + 1}/{self.iterations} failed: {result['description']}"

            except Exception as e:
                print(f"Error during iteration {self.current_iteration + 1}: {str(e)}")
                context.scene.blender_gpt_execution_result = f"Error during iteration {self.current_iteration + 1}: {str(e)}"
                self.cancel(context)
                return {'CANCELLED'}

            # Update progress
            self.current_iteration += 1
            gpt_props = context.scene.blendergpt_props
            gpt_props.current_iteration = self.current_iteration
            gpt_props.iteration_progress = (self.current_iteration / self.iterations) * 100.0
            context.area.tag_redraw()

            if self.current_iteration >= self.iterations:
                self.cancel(context)
                context.scene.blender_gpt_execution_result = f"Completed {self.iterations} iterations successfully."
                print("=== Iterative Scene Generation Complete ===\n")
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        gpt_props.total_iterations = self.iterations
        gpt_props.current_iteration = 0
        gpt_props.iteration_progress = 0.0
        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        gpt_props = context.scene.blendergpt_props
        gpt_props.current_iteration = 0
        gpt_props.total_iterations = 0
        gpt_props.iteration_progress = 0.0
        context.area.tag_redraw()

# Scene Inspection
def get_scene_info():
    scene_info = {"objects": [], "materials": [], "cameras": [], "lights": []}
    for obj in bpy.context.scene.objects:
        obj_info = {"name": obj.name, "type": obj.type, "location": list(obj.location), "rotation": list(obj.rotation_euler), "scale": list(obj.scale), "visible": obj.visible_get()}
        scene_info["objects"].append(obj_info)
        if obj.type == 'CAMERA':
            scene_info["cameras"].append({"name": obj.name, "lens": obj.data.lens})
        elif obj.type == 'LIGHT':
            scene_info["lights"].append({"name": obj.name, "type": obj.data.type, "energy": obj.data.energy})
    for mat in bpy.data.materials:
        mat_info = {"name": mat.name, "users": mat.users}
        if mat.use_nodes and (principled := next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)):
            mat_info.update({"base_color": list(principled.inputs["Base Color"].default_value), "metallic": principled.inputs["Metallic"].default_value, "roughness": principled.inputs["Roughness"].default_value})
        scene_info["materials"].append(mat_info)
    return scene_info

# Generate Blender Commands
def generate_blender_commands(prompt: str, api_key: str, model: str, scene_info: Dict, chat_history=None) -> Dict:
    if not api_key:
        return {"script": "", "description": "No API key configured", "follow_up": "Please configure your API key."}

    chat_history_str = "\n".join(f"{msg.role}: {msg.msg_content}" for msg in chat_history) if chat_history else ""
    system_prompt = (
        "You are a Blender Python API expert. Generate a safe, efficient Python script using bpy based on the user's prompt.\n"
        "Use randomization for realism (e.g., positions, scales).\n"
        "Avoid dangerous commands like os.system, eval, exec, sys, subprocess, shutil, or file operations like open().\n"
        "Do not use sys for any purpose, including sys.stdout or sys.path.\n"
        "Focus on using bpy, random, and math modules only to create and manipulate Blender objects, materials, and scenes.\n"
        f"Current scene: {json.dumps(scene_info, indent=2)}\n"
        f"Chat history: {chat_history_str}\n"
        "Return in JSON: {\"script\": \"<script>\", \"description\": \"<desc>\", \"follow_up\": \"<question>\"}\n"
        "No markdown wrappers."
    )

    try:
        client = openai.Client(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            max_tokens=7000,  # Increased to 7000
            temperature=0.7,
            timeout=15
        )
        response_content = response.choices[0].message.content.strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:-3].strip()
        # Check for incomplete JSON
        if not response_content.startswith("{") or not response_content.endswith("}"):
            return {"script": "", "description": "Error: Incomplete response from API, possibly due to token limit", "follow_up": "Try simplifying your prompt or reducing iterations."}
        result = json.loads(response_content)
        if not all(key in result for key in ["script", "description", "follow_up"]):
            raise ValueError("Missing required fields in API response")
        print(f"Generated Script:\n{result['script']}")
        return result
    except json.JSONDecodeError as e:
        return {"script": "", "description": f"Error: Failed to parse API response as JSON: {str(e)}", "follow_up": "Try simplifying your prompt or reducing iterations."}
    except Exception as e:
        return {"script": "", "description": f"Error: {str(e)}", "follow_up": "Try rephrasing your prompt or check your API key."}

# Execute Blender Code
def execute_blender_code(script):
    if not script:
        return {"status": "error", "message": "No script provided."}

    # Log the script before checking for dangerous keywords
    print(f"Executing Script:\n{script}")

    dangerous_keywords = ["__import__", "eval", "exec", "os.", "sys.", "subprocess", "shutil", "open("]
    for keyword in dangerous_keywords:
        if keyword in script:
            return {"status": "error", "message": f"Script contains unsafe keyword: {keyword}"}

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = output = StringIO()
    try:
        exec(script, {"bpy": bpy, "random": random, "math": math})
        return {"status": "success", "message": "Code executed successfully.", "output": output.getvalue()}
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}\n{traceback.format_exc()}", "output": output.getvalue()}
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        output.close()

# Operators
class BLENDER_GPT_OT_GenerateCode(bpy.types.Operator):
    bl_idname = "blender_gpt.generate_code"
    bl_label = "Generate Code"

    def execute(self, context):
        prompt = context.scene.blender_gpt_prompt.strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt.")
            return {'CANCELLED'}

        gpt_props = context.scene.blendergpt_props
        gpt_props.current_iteration = 0
        gpt_props.total_iterations = 0
        gpt_props.iteration_progress = 0.0
        context.area.tag_redraw()

        scene_info = get_scene_info()
        result = generate_blender_commands(prompt, api_key, context.preferences.addons["addon_blender_gpt"].preferences.gpt_model, scene_info, gpt_props.chat_history)

        if result["script"]:
            context.scene.blender_gpt_generated_code = result["script"]
            exec_result = execute_blender_code(result["script"])
            if exec_result["status"] == "success":
                context.scene.blender_gpt_execution_result = "Initial script executed successfully."
                if gpt_props.iterations > 0:
                    context.scene.blender_gpt_execution_result = "Starting iterative generation..."
                    bpy.ops.blendergpt.iterative_generation(initial_prompt=prompt, api_key=api_key, model=context.preferences.addons["addon_blender_gpt"].preferences.gpt_model, iterations=gpt_props.iterations)
                self.report({'INFO'}, "Initial commands generated and executed")
            else:
                context.scene.blender_gpt_execution_result = f"Failed to execute initial script: {exec_result['message']}"
                self.report({'WARNING'}, "Failed to execute initial script")
        else:
            context.scene.blender_gpt_generated_code = ""
            context.scene.blender_gpt_execution_result = result["description"]
            self.report({'WARNING'}, "Failed to generate commands")

        return {'FINISHED'}

class BLENDER_GPT_OT_ExecuteCode(bpy.types.Operator):
    bl_idname = "blender_gpt.execute_code"
    bl_label = "Execute Code"

    def execute(self, context):
        code = context.scene.blender_gpt_generated_code.strip()
        if not code:
            self.report({'WARNING'}, "No commands to execute.")
            return {'CANCELLED'}

        exec_result = execute_blender_code(code)
        context.scene.blender_gpt_execution_result = "Code executed successfully." if exec_result["status"] == "success" else f"Error: {exec_result['message']}"
        self.report({'INFO' if exec_result["status"] == "success" else 'ERROR'}, context.scene.blender_gpt_execution_result)
        return {'FINISHED'}

class BLENDERGPT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blendergpt.send_message"
    bl_label = "Send Message"

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        prompt = gpt_props.chat_input.strip()
        gpt_props.chat_history.add().from_json({"role": "USER", "msg_content": prompt})
        scene_info = get_scene_info()

        if gpt_props.mode == 'DREAMER':
            dreamer = Dreamer()
            scene_vision = dreamer.process_request(prompt or context.scene.blender_gpt_prompt)
            insights = {"emotional": {"tone": random.choice(["serene", "mysterious"])}, "conceptual": {"form": random.choice(["organic", "geometric"])}}
            response = f"✨ Dreamer: Emotional Tone: {insights['emotional']['tone']}, Form: {insights['conceptual']['form']}\nScene: {json.dumps(scene_vision, indent=2)}"
            gpt_props.chat_history.add().from_json({"role": "DREAMER", "msg_content": response})
        else:
            result = generate_blender_commands(prompt, api_key, context.preferences.addons["addon_blender_gpt"].preferences.gpt_model, scene_info, gpt_props.chat_history)
            gpt_props.chat_history.add().from_json({"role": "assistant", "msg_content": result["description"]})

        gpt_props.chat_input = ""
        return {'FINISHED'}

class BLENDERGPT_OT_ClearHistory(bpy.types.Operator):
    bl_idname = "blendergpt.clear_history"
    bl_label = "Clear History"

    def execute(self, context):
        context.scene.blendergpt_props.chat_history.clear()
        return {'FINISHED'}

class BLENDER_GPT_OT_ConfigureAPIKey(bpy.types.Operator):
    bl_idname = "blendergpt.configure_api_key"
    bl_label = "Configure API Key"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.txt;*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global api_key
        try:
            with open(self.filepath, 'r') as f:
                api_key = json.load(f).get("openai_api_key", f.read().strip()) if self.filepath.endswith('.json') else f.read().strip()
            if api_key and save_api_key(api_key):
                self.report({'INFO'}, "API key loaded and saved")
            else:
                self.report({'ERROR'}, "Invalid API key")
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
        return {'FINISHED'}

class BLENDERGPT_OT_CopyCommands(bpy.types.Operator):
    bl_idname = "blendergpt.copy_commands"
    bl_label = "Copy Commands"

    def execute(self, context):
        context.window_manager.clipboard = context.scene.blender_gpt_generated_code
        self.report({'INFO'}, "Commands copied")
        return {'FINISHED'}

class BLENDERGPT_OT_ClearCommands(bpy.types.Operator):
    bl_idname = "blendergpt.clear_commands"
    bl_label = "Clear Commands"

    def execute(self, context):
        context.scene.blender_gpt_generated_code = ""
        context.scene.blender_gpt_execution_result = ""
        self.report({'INFO'}, "Commands cleared")
        return {'FINISHED'}

class BLENDERGPT_OT_CopyResults(bpy.types.Operator):
    bl_idname = "blendergpt.copy_results"
    bl_label = "Copy Results"

    def execute(self, context):
        context.window_manager.clipboard = context.scene.blender_gpt_execution_result
        self.report({'INFO'}, "Results copied")
        return {'FINISHED'}

# Preferences
class BlenderGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "addon_blender_gpt"
    gpt_model: bpy.props.EnumProperty(
        name="GPT Model",
        items=[("gpt-4", "GPT-4", ""), ("gpt-3.5-turbo", "GPT-3.5 Turbo", ""), ("gpt-4o-mini-2024-07-18", "GPT-4o Mini", ""), ("custom", "Custom", "")],
        default="gpt-4o-mini-2024-07-18"
    )
    custom_gpt_model: bpy.props.StringProperty(
        name="Custom Model",
        description="Enter a custom model name"
    )

    def draw(self, context):
        self.layout.prop(self, "gpt_model")
        self.layout.prop(self, "custom_gpt_model")

# Registration
classes = [
    Message, BlenderGPTChatProps, BlenderGPTAddonPreferences, BLENDER_GPT_PT_Panel, BLENDER_GPT_OT_GenerateCode,
    BLENDER_GPT_OT_ExecuteCode, BLENDERGPT_OT_SendMessage, BLENDERGPT_OT_ClearHistory, BLENDER_GPT_OT_ConfigureAPIKey,
    BLENDERGPT_OT_CopyCommands, BLENDERGPT_OT_ClearCommands, BLENDERGPT_OT_CopyResults, BLENDERGPT_OT_IterativeGeneration
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blender_gpt_prompt = bpy.props.StringProperty(name="Prompt", default="")
    bpy.types.Scene.blender_gpt_generated_code = bpy.props.StringProperty(name="Generated Commands", default="")
    bpy.types.Scene.blender_gpt_execution_result = bpy.props.StringProperty(name="Execution Result", default="")
    bpy.types.Scene.blender_gpt_last_script = bpy.props.StringProperty(name="Last Generated Script", default="")
    bpy.types.Scene.blendergpt_props = bpy.props.PointerProperty(type=BlenderGPTChatProps)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blender_gpt_prompt
    del bpy.types.Scene.blender_gpt_generated_code
    del bpy.types.Scene.blender_gpt_execution_result
    del bpy.types.Scene.blender_gpt_last_script
    del bpy.types.Scene.blendergpt_props

if __name__ == "__main__":
    register()