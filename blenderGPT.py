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
from io import StringIO
import math
#import requests
from bpy.types import UILayout

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
    config_path = os.path.join(addon_dir, "config.json")
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

    # If no config.json or API key not found, try to load from preferences
    try:
        prefs = bpy.context.preferences.addons[__name__].preferences
        api_key = prefs.api_key.strip()
        if api_key:
            print("Loaded API key from preferences")
            # Save to config.json for consistency
            save_api_key(api_key)
            return api_key
    except Exception as e:
        print(f"Error loading API key from preferences: {e}")

    print("No valid API key found")
    return None

def save_api_key(api_key: str):
    try:
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        with open(config_path, 'w') as config_file:
            json.dump({"openai_api_key": api_key}, config_file, indent=2)
        print(f"Saved API key to {config_path}")
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
    "version": (2, 0, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > BlenderGPT",
    "description": "Generate and execute Blender commands using GPT with advanced features",
    "category": "3D View",
}

# Message class for chat history
class Message(bpy.types.PropertyGroup):
    role: bpy.props.StringProperty(name="Role", default="USER")
    msg_content: bpy.props.StringProperty(name="Message Content", default="")
    script: bpy.props.StringProperty(name="Script", default="")  # Store generated script

    def from_json(self, data):
        self.role = data.get("role", "USER")
        self.msg_content = data.get("msg_content", "")
        self.script = data.get("script", "")

# Chat properties
class BlenderGPTChatProps(bpy.types.PropertyGroup):
    chat_history: bpy.props.CollectionProperty(type=Message)
    chat_input: bpy.props.StringProperty(name="Chat Input", default="")
    iterations: bpy.props.IntProperty(name="Iterations", default=0, min=0, max=10, description="Number of additional iterations for scene generation")
    iteration_progress: bpy.props.FloatProperty(name="Iteration Progress", default=0.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    current_iteration: bpy.props.IntProperty(name="Current Iteration", default=0, min=0)
    total_iterations: bpy.props.IntProperty(name="Total Iterations", default=0, min=0)
    show_api_status: bpy.props.BoolProperty(name="Show API Status", default=True)
    show_generate_scene: bpy.props.BoolProperty(name="Show Generate Scene", default=True)
    show_generated_commands: bpy.props.BoolProperty(name="Show Generated Commands", default=True)
    show_chat: bpy.props.BoolProperty(name="Show Chat", default=True)
    show_quick_actions: bpy.props.BoolProperty(name="Show Quick Actions", default=True)
    show_settings: bpy.props.BoolProperty(name="Show Settings", default=True)
    status_message: bpy.props.StringProperty(name="Status Message", default="Ready")
    last_script: bpy.props.StringProperty(name="Last Script", default="")
    low_detail_mode: bpy.props.BoolProperty(name="Low Detail Mode", default=False, description="Reduce scene info detail to improve API response time")
    chat_height: bpy.props.IntProperty(name="Chat Height", default=10, min=5, max=20, description="Number of visible rows in the chat history")

# Helper function for word-wrapping text
def wrap_text(text, max_chars):
    """Wrap text by words, ensuring lines don't exceed max_chars."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        if current_length + word_length + len(current_line) <= max_chars:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    return lines

# Operator to show the full chat message in a popup with a copy button
class BLENDERGPT_OT_ShowFullMessage(bpy.types.Operator):
    bl_idname = "blendergpt.show_full_message"
    bl_label = "Show Full Message"
    bl_description = "Show the full chat message in a popup"

    message_index: bpy.props.IntProperty(name="Message Index", default=-1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        gpt_props = context.scene.blendergpt_props
        if 0 <= self.message_index < len(gpt_props.chat_history):
            msg = gpt_props.chat_history[self.message_index]
            role = "Assistant" if msg.role != "USER" else "USER"
            layout.label(text=f"{role}:", icon='USER' if msg.role == 'USER' else 'TEXT')
            col = layout.column(align=True)
            # Wrap the text for display in the popup
            panel_width = 500  # Approximate width of the popup
            chars_per_line = max(30, int(panel_width / 7))
            wrapped_lines = wrap_text(msg.msg_content, chars_per_line)
            for line in wrapped_lines:
                col.label(text=line)
            # Add a Copy button
            layout.operator("blendergpt.copy_message", text="Copy Message", icon='COPYDOWN').message_index = self.message_index

    def execute(self, context):
        return {'FINISHED'}

# Operator to copy an individual chat message
class BLENDERGPT_OT_CopyMessage(bpy.types.Operator):
    bl_idname = "blendergpt.copy_message"
    bl_label = "Copy Message"
    bl_description = "Copy the selected chat message to the clipboard"

    message_index: bpy.props.IntProperty(name="Message Index", default=-1)

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        if 0 <= self.message_index < len(gpt_props.chat_history):
            msg = gpt_props.chat_history[self.message_index]
            # Copy only the message content, without the role prefix
            message_text = msg.msg_content
            context.window_manager.clipboard = message_text
            gpt_props.status_message = "Message copied to clipboard."
            self.report({'INFO'}, "Message copied")
        else:
            self.report({'WARNING'}, "Invalid message index.")
        return {'FINISHED'}

# Operator to execute a script from a chat message
class BLENDERGPT_OT_ExecuteChatScript(bpy.types.Operator):
    bl_idname = "blendergpt.execute_chat_script"
    bl_label = "Execute Script"
    bl_description = "Execute the script from the selected chat message"

    message_index: bpy.props.IntProperty(name="Message Index", default=-1)

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        if 0 <= self.message_index < len(gpt_props.chat_history):
            msg = gpt_props.chat_history[self.message_index]
            if msg.script:
                gpt_props.status_message = "Executing script from chat..."
                context.area.tag_redraw()
                exec_result = execute_blender_code(msg.script)
                context.scene.blender_gpt_execution_result = exec_result["message"]
                gpt_props.status_message = "Script executed successfully." if exec_result["status"] == "success" else f"Error: {exec_result['message']}"
                gpt_props.last_script = msg.script
                self.report({'INFO' if exec_result["status"] == "success" else 'ERROR'}, gpt_props.status_message)
                context.area.tag_redraw()
            else:
                self.report({'WARNING'}, "No script available in this message.")
        else:
            self.report({'WARNING'}, "Invalid message index.")
        return {'FINISHED'}

# Main Panel (BlenderGPT Tab)
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

        # Status Section
        box = layout.box()
        row = box.row()
        row.label(text="Status:", icon='INFO')
        row.label(text=gpt_props.status_message)

        # API Key Status
        row = layout.row()
        row.prop(gpt_props, "show_api_status", text="API Key Status", icon='KEYINGSET', emboss=False)
        if gpt_props.show_api_status:
            box = layout.box()
            box.label(text="✓ API Key Configured" if api_key else "⚠ No API Key Found", icon='CHECKMARK' if api_key else 'ERROR')
            if not api_key:
                box.operator("blendergpt.configure_api_key", text="Load API Key", icon='FILE')

        # Quick Actions
        row = layout.row()
        row.prop(gpt_props, "show_quick_actions", text="Quick Actions", icon='PRESET', emboss=False)
        if gpt_props.show_quick_actions:
            box = layout.box()
            box.label(text="Quick Actions:", icon='PRESET')
            row = box.row()
            row.operator("blendergpt.quick_add_cube", text="Add Cube", icon='MESH_CUBE')
            row.operator("blendergpt.quick_add_light", text="Add Light", icon='LIGHT_SUN')
            row = box.row()
            row.operator("blendergpt.quick_add_camera", text="Add Camera", icon='CAMERA_DATA')
            row.operator("blendergpt.quick_clear_scene", text="Clear Scene", icon='TRASH')

        # Generate Scene
        row = layout.row()
        row.prop(gpt_props, "show_generate_scene", text="Generate Scene", icon='MESH_DATA', emboss=False)
        if gpt_props.show_generate_scene:
            box = layout.box()
            box.label(text="Generate Scene:", icon='MESH_DATA')
            box.prop(scene, "blender_gpt_prompt", text="Prompt", icon='TEXT')
            box.label(text="Additional Iterations:", icon='FILE_REFRESH')
            box.prop(gpt_props, "iterations", text="")
            if gpt_props.total_iterations > 0:
                total_runs = gpt_props.total_iterations + 1
                current_run = gpt_props.current_iteration + 1
                box.label(text=f"Run {current_run}/{total_runs}")
                box.prop(gpt_props, "iteration_progress", text="", slider=True)
            row = box.row()
            row.operator("blender_gpt.generate_code", text="Generate", icon='PLAY')
            row.operator("blender_gpt.execute_code", text="Execute", icon='CHECKMARK')
            row.operator("blendergpt.edit_script", text="", icon='TEXT')
            row.operator("blendergpt.preview_script", text="", icon='HIDE_OFF')

        # Generated Commands
        row = layout.row()
        row.prop(gpt_props, "show_generated_commands", text="Generated Commands", icon='TEXT', emboss=False)
        if gpt_props.show_generated_commands:
            box = layout.box()
            box.label(text="Generated Commands:", icon='TEXT')
            if scene.blender_gpt_generated_code:
                col = box.column(align=True)
                col.scale_y = 0.8
                panel_width = context.region.width if context.region else 300
                chars_per_line = max(40, int(panel_width / 6))
                for line in [scene.blender_gpt_generated_code[i:i+chars_per_line] for i in range(0, len(scene.blender_gpt_generated_code), chars_per_line)]:
                    col.label(text=line)
                row = box.row()
                row.operator("blendergpt.copy_commands", text="Copy", icon='COPYDOWN')
                row.operator("blendergpt.clear_commands", text="Clear", icon='TRASH')
            else:
                box.label(text="No commands generated yet")

        # Result Section
        box = layout.box()
        box.label(text="Result:", icon='INFO')
        if scene.blender_gpt_execution_result:
            col = box.column(align=True)
            col.scale_y = 0.8
            panel_width = context.region.width if context.region else 300
            chars_per_line = max(40, int(panel_width / 6))
            for line in [scene.blender_gpt_execution_result[i:i+chars_per_line] for i in range(0, len(scene.blender_gpt_execution_result), chars_per_line)]:
                col.label(text=line)
            box.operator("blendergpt.copy_results", text="Copy Results", icon='COPYDOWN')
        else:
            box.label(text="No results yet")

        # Chat Section
        row = layout.row()
        row.prop(gpt_props, "show_chat", text="Chat with BlenderGPT", icon='TEXT', emboss=False)
        if gpt_props.show_chat:
            box = layout.box()
            box.label(text="Chat with BlenderGPT:", icon='TEXT')
            # Scrollable chat history
            scroll_box = box.box()
            scroll_box.scale_y = 0.8
            for idx, msg in enumerate(gpt_props.chat_history):
                msg_box = scroll_box.box()
                row = msg_box.row(align=True)
                # Role label
                col = row.column(align=True)
                col.scale_x = 0.3  # Reduce width of the role label
                display_role = "Assistant" if msg.role != "USER" else "USER"
                col.label(text=f"{display_role}:", icon='USER' if msg.role == 'USER' else 'TEXT')
                # Message content (clickable to show full message)
                col = row.column(align=True)
                col.scale_x = 1.0  # Ensure the message content takes up the remaining space
                panel_width = context.region.width if context.region else 300
                effective_width = max(100, panel_width - 60)
                chars_per_line = max(30, int(effective_width / 7))
                wrapped_lines = wrap_text(msg.msg_content, chars_per_line)
                for i, line in enumerate(wrapped_lines):
                    # Make all lines clickable to show the full message
                    op = col.operator("blendergpt.show_full_message", text=line, emboss=False)
                    op.message_index = idx
                # If the message has a script, display it and add an Execute Script button
                if msg.script:
                    col = msg_box.column(align=True)
                    col.label(text="Generated Script:", icon='TEXT')
                    script_lines = msg.script.split('\n')
                    wrapped_script_lines = []
                    for line in script_lines:
                        wrapped_script_lines.extend(wrap_text(line, chars_per_line))
                    for line in wrapped_script_lines:
                        col.label(text=line)
                    row = msg_box.row(align=True)
                    row.operator("blendergpt.execute_chat_script", text="Execute Script", icon='PLAY').message_index = idx
            # Chat input and buttons
            box.prop(gpt_props, "chat_input", text="Message")
            row = box.row(align=True)
            row.operator("blendergpt.send_message", text="Send", icon='RIGHTARROW')
            row.operator("blendergpt.clear_history", text="Clear", icon='TRASH')
            row = box.row(align=True)
            row.operator("blendergpt.copy_chat", text="Copy Chat", icon='COPYDOWN')

        # Settings Section
        row = layout.row()
        row.prop(gpt_props, "show_settings", text="Settings", icon='SETTINGS', emboss=False)
        if gpt_props.show_settings:
            box = layout.box()
            box.label(text="Settings:", icon='SETTINGS')
            box.prop(gpt_props, "low_detail_mode", text="Low Detail Mode")
            box.prop(gpt_props, "chat_height", text="Chat Height")

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
            context.scene.blendergpt_props.status_message = "Iterative generation cancelled by user."
            return {'CANCELLED'}

        if event.type == 'TIMER' and self.current_iteration < self.iterations:
            try:
                scene_info = get_scene_info(low_detail=context.scene.blendergpt_props.low_detail_mode)
                existing_objects = [obj["type"] for obj in scene_info.get("objects", [])]
                object_counts = {}
                for obj in existing_objects:
                    object_counts[obj] = object_counts.get(obj, 0) + 1
                scene_description = "The scene currently contains: " + ", ".join(f"{count} {obj_type}(s)" for obj_type, count in object_counts.items()) + "."
                print(f"\n=== Iteration {self.current_iteration + 1}/{self.iterations} ===")
                print(f"Scene Analysis: {scene_description}")

                new_prompt = (
                    f"Based on the initial request: {self.initial_prompt}\n"
                    f"Current scene: {scene_description}\n"
                    "Suggest and add a new element that complements the existing scene, properly spaced in the 3D environment to avoid clutter."
                )
                print(f"Generated Prompt: {new_prompt}")

                gpt_props = context.scene.blendergpt_props
                gpt_props.status_message = f"Generating iteration {self.current_iteration + 1}/{self.iterations}..."
                context.area.tag_redraw()

                result = generate_blender_commands(new_prompt, self.api_key, self.model, scene_info, gpt_props.chat_history)
                if result["script"]:
                    exec_result = execute_blender_code(result["script"])
                    if exec_result["status"] == "success":
                        print(f"Action Taken: {result['description']}")
                        print(f"Script Executed:\n{result['script']}")
                        gpt_props.status_message = f"Iteration {self.current_iteration + 1}/{self.iterations}: {result['description']}"
                        gpt_props.last_script = result["script"]
                    else:
                        print(f"Error: {exec_result['message']}")
                        gpt_props.status_message = f"Iteration {self.current_iteration + 1}/{self.iterations} failed: {exec_result['message']}"
                else:
                    print(f"Error: {result['description']}")
                    gpt_props.status_message = f"Iteration {self.current_iteration + 1}/{self.iterations} failed: {result['description']}"

            except Exception as e:
                print(f"Error during iteration {self.current_iteration + 1}: {str(e)}")
                gpt_props.status_message = f"Error during iteration {self.current_iteration + 1}: {str(e)}"
                self.cancel(context)
                return {'CANCELLED'}

            self.current_iteration += 1
            gpt_props = context.scene.blendergpt_props
            gpt_props.current_iteration = self.current_iteration
            gpt_props.iteration_progress = (self.current_iteration / self.iterations) * 100.0 if self.iterations > 0 else 100.0
            context.area.tag_redraw()

            if self.current_iteration >= self.iterations:
                self.cancel(context)
                gpt_props.status_message = f"Completed {self.iterations} additional iterations successfully."
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
def get_scene_info(low_detail=False):
    scene_info = {"objects": [], "materials": [], "cameras": [], "lights": []}
    for obj in bpy.context.scene.objects:
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location)
        }
        if not low_detail:
            obj_info.update({
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
                "visible": obj.visible_get()
            })
        scene_info["objects"].append(obj_info)
        if obj.type == 'CAMERA':
            scene_info["cameras"].append({"name": obj.name, "lens": obj.data.lens})
        elif obj.type == 'LIGHT':
            scene_info["lights"].append({"name": obj.name, "type": obj.data.type, "energy": obj.data.energy})
    if not low_detail:
        for mat in bpy.data.materials:
            mat_info = {"name": mat.name, "users": mat.users}
            if mat.use_nodes and (principled := next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)):
                mat_info.update({
                    "base_color": list(principled.inputs["Base Color"].default_value),
                    "metallic": principled.inputs["Metallic"].default_value,
                    "roughness": principled.inputs["Roughness"].default_value
                })
            scene_info["materials"].append(mat_info)
    return scene_info

# Generate Blender Commands
def generate_blender_commands(prompt: str, api_key: str, model: str, scene_info: Dict, chat_history=None) -> Dict:
    if not api_key:
        return {"script": "", "description": "No API key configured", "follow_up": "Please configure your API key in the addon preferences."}

    messages = []
    chat_history_str = ""
    if chat_history:
        for msg in chat_history:
            role = "user" if msg.role == "USER" else "assistant"
            messages.append({"role": role, "content": msg.msg_content})
            chat_history_str += f"{msg.role}: {msg.msg_content}\n"

    system_prompt = (
        "You are a Blender Python API expert. Your task is to assist the user by generating safe, efficient Python scripts using bpy, or by providing helpful responses based on their prompts.\n"
        "When generating scripts:\n"
        "- Use randomization for realism (e.g., positions, scales).\n"
        "- Avoid dangerous commands like os.system, eval, exec, sys, subprocess, shutil, or file operations like open().\n"
        "- Do not use sys for any purpose, including sys.stdout or sys.path.\n"
        "- Focus on using bpy, random, and math modules only to create and manipulate Blender objects, materials, and scenes.\n"
        "- When creating new objects, always use bpy.ops to create the object and its data, or specify the object_data parameter in bpy.data.objects.new(). For example:\n"
        "  # Example: Create a cylinder\n"
        "  bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=5, location=(0, 0, 2.5))\n"
        "  cylinder_obj = bpy.context.object\n"
        "  cylinder_obj.name = 'TreeTrunk'\n"
        "  # Or, if using bpy.data.objects.new():\n"
        "  mesh_data = bpy.data.meshes.new('TreeTrunkMesh')\n"
        "  cylinder_obj = bpy.data.objects.new(name='TreeTrunk', object_data=mesh_data)\n"
        "  bpy.context.collection.objects.link(cylinder_obj)\n"
        "If the user asks a question about the scene or Blender, provide a detailed and helpful response without generating a script unless explicitly requested.\n"
        "If the user explicitly requests a script (e.g., by saying 'write a script', 'generate a script', 'I need the script', or similar phrases), you MUST generate a script and include it in the 'script' field of the JSON response. Do not just describe the script—provide the actual Python code.\n"
        f"Current scene: {json.dumps(scene_info, indent=2)}\n"
        f"Chat history:\n{chat_history_str}\n"
        "Return in JSON: {\"script\": \"<script>\", \"description\": \"<desc>\", \"follow_up\": \"<question>\"}\n"
        "If no script is generated (e.g., for a question), set \"script\" to an empty string.\n"
        "No markdown wrappers."
    )

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            client = openai.Client(api_key=api_key)
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=7000,
                temperature=0.7,
                timeout=30
            )
            response_content = response.choices[0].message.content.strip()
            if response_content.startswith("```json"):
                response_content = response_content[7:-3].strip()
            if not response_content.startswith("{") or not response_content.endswith("}"):
                if attempt < max_retries:
                    prompt = f"The following response was not valid JSON:\n{response_content}\nPlease correct the JSON formatting and return a valid JSON object with the fields \"script\", \"description\", and \"follow_up\"."
                    continue
                return {"script": "", "description": "Error: Incomplete response from API, possibly due to token limit", "follow_up": "Try simplifying your prompt or enabling Low Detail mode."}
            
            result = json.loads(response_content)
            if not all(key in result for key in ["script", "description", "follow_up"]):
                raise ValueError("Missing required fields in API response")
            print(f"Generated Script:\n{result['script']}")
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                prompt = f"The following response was not valid JSON:\n{response_content}\nError: {str(e)}\nPlease correct the JSON formatting and return a valid JSON object with the fields \"script\", \"description\", and \"follow_up\"."
                continue
            return {"script": "", "description": f"Error: Failed to parse API response as JSON: {str(e)}", "follow_up": "Try simplifying your prompt or enabling Low Detail mode."}
        except Exception as e:
            if "timeout" in str(e).lower() and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {"script": "", "description": f"Error: {str(e)}", "follow_up": "Try rephrasing your prompt, enabling Low Detail mode, or checking your API key."}

# Execute Blender Code
def execute_blender_code(script):
    if not script:
        return {"status": "error", "message": "No script provided."}

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
    bl_description = "Generate a Blender script based on the prompt"

    def execute(self, context):
        prompt = context.scene.blender_gpt_prompt.strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt.")
            return {'CANCELLED'}

        gpt_props = context.scene.blendergpt_props
        gpt_props.current_iteration = 0
        gpt_props.total_iterations = 0
        gpt_props.iteration_progress = 0.0
        gpt_props.status_message = "Generating initial script..."
        context.area.tag_redraw()

        scene_info = get_scene_info(low_detail=gpt_props.low_detail_mode)
        result = generate_blender_commands(prompt, api_key, context.preferences.addons[__name__].preferences.gpt_model, scene_info, gpt_props.chat_history)

        if result["script"]:
            context.scene.blender_gpt_generated_code = result["script"]
            exec_result = execute_blender_code(result["script"])
            if exec_result["status"] == "success":
                gpt_props.status_message = "Initial script executed successfully."
                gpt_props.last_script = result["script"]
                if gpt_props.iterations > 0:
                    gpt_props.status_message = "Starting iterative generation..."
                    bpy.ops.blendergpt.iterative_generation(
                        initial_prompt=prompt,
                        api_key=api_key,
                        model=context.preferences.addons[__name__].preferences.gpt_model,
                        iterations=gpt_props.iterations
                    )
                self.report({'INFO'}, "Initial commands generated and executed")
            else:
                gpt_props.status_message = f"Failed to execute initial script: {exec_result['message']}"
                self.report({'WARNING'}, "Failed to execute initial script")
        else:
            context.scene.blender_gpt_generated_code = ""
            gpt_props.status_message = result["description"]
            self.report({'WARNING'}, "Failed to generate commands")

        context.area.tag_redraw()
        return {'FINISHED'}

class BLENDER_GPT_OT_ExecuteCode(bpy.types.Operator):
    bl_idname = "blender_gpt.execute_code"
    bl_label = "Execute Code"
    bl_description = "Execute the generated script"

    def execute(self, context):
        code = context.scene.blender_gpt_generated_code.strip()
        if not code:
            self.report({'WARNING'}, "No commands to execute.")
            return {'CANCELLED'}

        gpt_props = context.scene.blendergpt_props
        gpt_props.status_message = "Executing script..."
        context.area.tag_redraw()

        exec_result = execute_blender_code(code)
        context.scene.blender_gpt_execution_result = exec_result["message"]
        gpt_props.status_message = "Code executed successfully." if exec_result["status"] == "success" else f"Error: {exec_result['message']}"
        gpt_props.last_script = code
        self.report({'INFO' if exec_result["status"] == "success" else 'ERROR'}, gpt_props.status_message)
        context.area.tag_redraw()
        return {'FINISHED'}

class BLENDERGPT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blendergpt.send_message"
    bl_label = "Send Message"
    bl_description = "Send a message to BlenderGPT"

    def execute(self, context):
        print("Send Message operator called")
        gpt_props = context.scene.blendergpt_props
        prompt = gpt_props.chat_input.strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a message.")
            print("No message entered")
            return {'CANCELLED'}

        # Add user message to chat history
        msg = gpt_props.chat_history.add()
        msg.from_json({"role": "USER", "msg_content": prompt})
        gpt_props.status_message = "Generating response..."
        print(f"User message added: {prompt}")
        context.area.tag_redraw()

        # Generate response
        scene_info = get_scene_info(low_detail=gpt_props.low_detail_mode)
        result = generate_blender_commands(prompt, api_key, context.preferences.addons[__name__].preferences.gpt_model, scene_info, gpt_props.chat_history)
        msg = gpt_props.chat_history.add()
        msg.from_json({"role": "assistant", "msg_content": result["description"], "script": result["script"]})
        print(f"Assistant response: {result['description']}")
        if result["script"]:
            print(f"Generated Script:\n{result['script']}")

        # Clear input and update status
        gpt_props.chat_input = ""
        gpt_props.status_message = "Response generated."
        context.area.tag_redraw()
        print("Message sent and UI updated")
        return {'FINISHED'}

class BLENDERGPT_OT_ClearHistory(bpy.types.Operator):
    bl_idname = "blendergpt.clear_history"
    bl_label = "Clear History"
    bl_description = "Clear the chat history"

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        gpt_props.chat_history.clear()
        gpt_props.status_message = "Chat history cleared."
        context.area.tag_redraw()
        return {'FINISHED'}

class BLENDERGPT_OT_CopyChat(bpy.types.Operator):
    bl_idname = "blendergpt.copy_chat"
    bl_label = "Copy Chat"
    bl_description = "Copy the chat history to the clipboard"

    def execute(self, context):
        gpt_props = context.scene.blendergpt_props
        chat_text = ""
        for msg in gpt_props.chat_history:
            role = "Assistant" if msg.role != "USER" else "USER"
            chat_text += f"{role}: {msg.msg_content}\n"
            if msg.script:
                chat_text += f"Generated Script:\n{msg.script}\n"
        context.window_manager.clipboard = chat_text.strip()
        gpt_props.status_message = "Chat history copied to clipboard."
        self.report({'INFO'}, "Chat history copied")
        context.area.tag_redraw()
        return {'FINISHED'}

class BLENDER_GPT_OT_ConfigureAPIKey(bpy.types.Operator):
    bl_idname = "blendergpt.configure_api_key"
    bl_label = "Configure API Key"
    bl_description = "Load an API key from a file"
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
                # Update preferences
                prefs = context.preferences.addons[__name__].preferences
                prefs.api_key = api_key
                self.report({'INFO'}, "API key loaded and saved")
                context.scene.blendergpt_props.status_message = "API key loaded and saved."
            else:
                self.report({'ERROR'}, "Invalid API key")
                context.scene.blendergpt_props.status_message = "Invalid API key."
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            context.scene.blendergpt_props.status_message = f"Error loading API key: {str(e)}"
        return {'FINISHED'}

class BLENDERGPT_OT_CopyCommands(bpy.types.Operator):
    bl_idname = "blendergpt.copy_commands"
    bl_label = "Copy Commands"
    bl_description = "Copy the generated commands to the clipboard"

    def execute(self, context):
        context.window_manager.clipboard = context.scene.blender_gpt_generated_code
        context.scene.blendergpt_props.status_message = "Commands copied to clipboard."
        self.report({'INFO'}, "Commands copied")
        return {'FINISHED'}

class BLENDERGPT_OT_ClearCommands(bpy.types.Operator):
    bl_idname = "blendergpt.clear_commands"
    bl_label = "Clear Commands"
    bl_description = "Clear the generated commands and results"

    def execute(self, context):
        context.scene.blender_gpt_generated_code = ""
        context.scene.blender_gpt_execution_result = ""
        context.scene.blendergpt_props.status_message = "Commands cleared."
        self.report({'INFO'}, "Commands cleared")
        return {'FINISHED'}

class BLENDERGPT_OT_CopyResults(bpy.types.Operator):
    bl_idname = "blendergpt.copy_results"
    bl_label = "Copy Results"
    bl_description = "Copy the execution results to the clipboard"

    def execute(self, context):
        context.window_manager.clipboard = context.scene.blender_gpt_execution_result
        context.scene.blendergpt_props.status_message = "Results copied to clipboard."
        self.report({'INFO'}, "Results copied")
        return {'FINISHED'}

class BLENDERGPT_OT_PreviewScript(bpy.types.Operator):
    bl_idname = "blendergpt.preview_script"
    bl_label = "Preview Script"
    bl_description = "Preview the generated script in a popup"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Generated Script Preview:", icon='TEXT')
        col = layout.column(align=True)
        for line in context.scene.blender_gpt_generated_code.split('\n'):
            col.label(text=line)

    def execute(self, context):
        return {'FINISHED'}

# class BLENDERGPT_OT_EditScript(bpy.types.Operator):
#     bl_idname = "blendergpt.edit_script"
#     bl_label = "Edit Script"
#     bl_description = "Edit the generated script before execution"

#     def invoke(self, context, event):
#         return context.window_manager.invoke_props_dialog(self, width=500)

#     def draw(self, context):
#         layout = self.layout
#         layout.label(text="Edit Generated Script:", icon='TEXT')
#         # Use a multiline text box by splitting the script into lines and using a column
#         col = layout.column(align=True)
#         # Display the script as a multiline text area
#         script_lines = context.scene.blender_gpt_generated_code.split('\n')
#         row = col.row(align=True)
#         row.label(text="")  # Spacer
#         # Create a temporary property to hold the edited script
#         if not hasattr(context.scene, "blender_gpt_temp_script"):
#             context.scene.blender_gpt_temp_script = bpy.props.StringProperty(name="Temp Script", default=context.scene.blender_gpt_generated_code)
#         # Use a multiline text area (simulated with a single string property that preserves newlines)
#         col.prop(context.scene, "blender_gpt_temp_script", text="", emboss=True, expand=True)

#     def execute(self, context):
#         # Update the generated code with the edited script
#         context.scene.blender_gpt_generated_code = context.scene.blender_gpt_temp_script
#         # Clean up the temporary property
#         if hasattr(context.scene, "blender_gpt_temp_script"):
#             del context.scene.blender_gpt_temp_script
#         context.scene.blendergpt_props.status_message = "Script edited."
#         return {'FINISHED'}
#         # End of Selection

# Quick Action Operators
class BLENDERGPT_OT_QuickAddCube(bpy.types.Operator):
    bl_idname = "blendergpt.quick_add_cube"
    bl_label = "Add Cube"
    bl_description = "Quickly add a cube to the scene"

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=2, location=(random.uniform(-5, 5), random.uniform(-5, 5), 1))
        context.scene.blendergpt_props.status_message = "Cube added to the scene."
        self.report({'INFO'}, "Cube added")
        return {'FINISHED'}

class BLENDERGPT_OT_QuickAddLight(bpy.types.Operator):
    bl_idname = "blendergpt.quick_add_light"
    bl_label = "Add Light"
    bl_description = "Quickly add a light to the scene"

    def execute(self, context):
        bpy.ops.object.light_add(type='SUN', location=(random.uniform(-5, 5), random.uniform(-5, 5), 10))
        context.scene.blendergpt_props.status_message = "Light added to the scene."
        self.report({'INFO'}, "Light added")
        return {'FINISHED'}

class BLENDERGPT_OT_QuickAddCamera(bpy.types.Operator):
    bl_idname = "blendergpt.quick_add_camera"
    bl_label = "Add Camera"
    bl_description = "Quickly add a camera to the scene"

    def execute(self, context):
        bpy.ops.object.camera_add(location=(random.uniform(-5, 5), random.uniform(-5, 5), 5))
        context.scene.blendergpt_props.status_message = "Camera added to the scene."
        self.report({'INFO'}, "Camera added")
        return {'FINISHED'}

class BLENDERGPT_OT_QuickClearScene(bpy.types.Operator):
    bl_idname = "blendergpt.quick_clear_scene"
    bl_label = "Clear Scene"
    bl_description = "Clear all objects from the scene"

    def execute(self, context):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        context.scene.blendergpt_props.status_message = "Scene cleared."
        self.report({'INFO'}, "Scene cleared")
        return {'FINISHED'}

# Preferences
class BlenderGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "BlenderGPT"

    api_key: bpy.props.StringProperty(
        name="OpenAI API Key",
        description="Enter your OpenAI API key",
        default="",
        update=lambda self, context: save_api_key(self.api_key)
    )

    gpt_model: bpy.props.EnumProperty(
        name="GPT Model",
        items=[
            ("gpt-4", "GPT-4", ""),
            ("gpt-3.5-turbo", "GPT-3.5 Turbo", ""),
            ("gpt-4o-mini-2024-07-18", "GPT-4o Mini", ""),
            ("custom", "Custom", "")
        ],
        default="gpt-4o-mini-2024-07-18"
    )

    custom_gpt_model: bpy.props.StringProperty(
        name="Custom Model",
        description="Enter a custom model name"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="BlenderGPT Preferences", icon='SETTINGS')
        layout.prop(self, "api_key")
        layout.prop(self, "gpt_model")
        if self.gpt_model == "custom":
            layout.prop(self, "custom_gpt_model")

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
    BLENDERGPT_OT_CopyChat,
    BLENDER_GPT_OT_ConfigureAPIKey,
    BLENDERGPT_OT_CopyCommands,
    BLENDERGPT_OT_ClearCommands,
    BLENDERGPT_OT_CopyResults,
    BLENDERGPT_OT_PreviewScript,
    #BLENDERGPT_OT_EditScript,
    BLENDERGPT_OT_IterativeGeneration,
    BLENDERGPT_OT_QuickAddCube,
    BLENDERGPT_OT_QuickAddLight,
    BLENDERGPT_OT_QuickAddCamera,
    BLENDERGPT_OT_QuickClearScene,
    BLENDERGPT_OT_ShowFullMessage,
    BLENDERGPT_OT_CopyMessage,
    BLENDERGPT_OT_ExecuteChatScript  # Added new operator
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blender_gpt_prompt = bpy.props.StringProperty(name="Prompt", default="")
    bpy.types.Scene.blender_gpt_generated_code = bpy.props.StringProperty(name="Generated Commands", default="")
    bpy.types.Scene.blender_gpt_execution_result = bpy.props.StringProperty(name="Execution Result", default="")
    bpy.types.Scene.blendergpt_props = bpy.props.PointerProperty(type=BlenderGPTChatProps)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blender_gpt_prompt
    del bpy.types.Scene.blender_gpt_generated_code
    del bpy.types.Scene.blender_gpt_execution_result
    del bpy.types.Scene.blendergpt_props

if __name__ == "__main__":
    register()