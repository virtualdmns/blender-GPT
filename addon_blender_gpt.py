import bpy
import json
import re
import subprocess
import sys
import traceback
import openai
import ast
import os

# Add local site-packages path if needed
site_packages_path = os.path.expanduser("~/.local/lib/python3.11/site-packages")
if site_packages_path not in sys.path:
    sys.path.append(site_packages_path)

print(f"Loading module: {__name__}")  # Debug: Confirm module load

# Load API key from config.json in the addon directory
addon_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(addon_dir, "config.json")
print(f"Looking for config.json at: {config_path}")  # Debug: Confirm path
api_key = None
if os.path.exists(config_path):
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
        api_key = config.get("openai_api_key", "").strip()

bl_info = {
    "name": "blender_gpt",
    "author": "virtualdmns",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > blender_gpt",
    "description": "Embed GPT chat to generate and execute Python code in Blender.",
    "category": "Interface",
}

# -------------------------------------------------------------------
# Addon Preferences (Simplified, no API key field)
# -------------------------------------------------------------------
class BlenderGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "addon_blender_gpt"

    gpt_model: bpy.props.EnumProperty(
        name="GPT Model",
        description="Select the GPT model to use",
        items=[
            ("gpt-4", "GPT-4", "Use GPT-4 (requires API access)"),
            ("gpt-3.5-turbo", "GPT-3.5 Turbo", "Use GPT-3.5 Turbo (more accessible)"),
            ("gpt-4o-mini-2024-07-18", "GPT-4o Mini", "Use GPT-4o Mini (optimized for smaller tasks)"),
        ],
        default="gpt-4o-mini-2024-07-18"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="API Key is stored in config.json in the addon directory.")
        layout.prop(self, "gpt_model")
        layout.label(text="To set the API key, edit config.json with: {\"openai_api_key\": \"your-key-here\"}")


# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
def remove_code_fence(code: str) -> str:
    code = re.sub(r"^```(?:python)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code, flags=re.IGNORECASE)
    return code.strip()


def check_scene_for_object(object_name: str) -> bool:
    return bool(bpy.data.objects.get(object_name))


def validate_code_syntax(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax Error: {str(e)}"


def generate_blender_code(prompt: str, api_key: str, model: str) -> str:
    """
    Use GPT to generate Blender Python code based on the user's prompt.
    Updated for OpenAI API version >= 1.0.0 using openai.Client.
    Returns only the code.
    """
    try:
        # Sanitize the API key
        api_key = api_key.strip()
        api_key = ''.join(char for char in api_key if ord(char) < 128 and char.isprintable())
        print(f"Using API key (first 8, last 4): {api_key[:8]}...{api_key[-4:]}")
        print(f"API key length: {len(api_key)}")

        if not api_key:
            raise ValueError("No API key provided. Please set it in config.json.")

        client = openai.Client(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Blender Python assistant. Generate code to accomplish the user's request. "
                        "Follow these rules:\n"
                        "1. Do not assume an active object exists. Always look up objects using bpy.data.objects.get('ObjectName').\n"
                        "2. If creating an object, check if it exists first with bpy.data.objects.get() to avoid duplicates.\n"
                        "3. If modifying an object (e.g., applying a material), ensure the object exists first.\n"
                        "4. When applying materials, assign to the first material slot (obj.data.materials[0] = mat) and clear existing materials if needed.\n"
                        "5. After making changes (e.g., creating objects, applying materials), force a viewport update with bpy.context.view_layer.update().\n"
                        "6. Return only the code, with no explanations or comments."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        code = response.choices[0].message.content.strip()
        code = remove_code_fence(code)
        return code
    except Exception as e:
        return f"# Error generating code: {str(e)}"


def execute_generated_code(code: str) -> str:
    try:
        is_valid, error_msg = validate_code_syntax(code)
        if not is_valid:
            return error_msg

        bpy.ops.ed.undo_push(message="Before blender_gpt execution")

        local_ns = {"bpy": bpy}
        exec(code, local_ns)

        bpy.context.view_layer.update()

        bpy.ops.ed.undo_push(message="After blender_gpt execution")

        return "Code executed successfully."
    except Exception as e:
        return f"Execution Error: {str(e)}\n{traceback.format_exc()}"


# -------------------------------------------------------------------
# UI Panel and Operators
# -------------------------------------------------------------------
class BLENDER_GPT_PT_Panel(bpy.types.Panel):
    bl_label = "blender_gpt"
    bl_idname = "BLENDER_GPT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'blender_gpt'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "blender_gpt_prompt", text="Prompt")

        row = layout.row()
        row.operator("blender_gpt.generate_code", text="Generate Code")
        row.operator("blender_gpt.execute_code", text="Execute Code")

        layout.label(text="Generated Code:")
        layout.prop(scene, "blender_gpt_generated_code", text="", expand=True)

        if scene.blender_gpt_execution_result:
            layout.label(text="Result:")
            box = layout.box()
            for line in scene.blender_gpt_execution_result.split('\n'):
                box.label(text=line)


class BLENDER_GPT_OT_GenerateCode(bpy.types.Operator):
    bl_idname = "blender_gpt.generate_code"
    bl_label = "Generate Code"

    def execute(self, context):
        prefs = context.preferences.addons["addon_blender_gpt"].preferences
        model = prefs.gpt_model
        global api_key
        if not api_key:
            self.report({'ERROR'}, "No API key found. Please set it in config.json in the addon directory.")
            return {'CANCELLED'}
        prompt = context.scene.blender_gpt_prompt
        code = generate_blender_code(prompt, api_key, model)
        context.scene.blender_gpt_generated_code = code
        context.scene.blender_gpt_execution_result = ""
        self.report({'INFO'}, "Code generated.")
        return {'FINISHED'}


class BLENDER_GPT_OT_ExecuteCode(bpy.types.Operator):
    bl_idname = "blender_gpt.execute_code"
    bl_label = "Execute Code"

    def execute(self, context):
        code = context.scene.blender_gpt_generated_code
        if not code.strip():
            self.report({'WARNING'}, "No code to execute.")
            return {'CANCELLED'}
        result = execute_generated_code(code)
        context.scene.blender_gpt_execution_result = result
        if "Error" in result:
            self.report({'ERROR'}, result)
        else:
            self.report({'INFO'}, result)
        return {'FINISHED'}


# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------
classes = [
    BlenderGPTAddonPreferences,
    BLENDER_GPT_PT_Panel,
    BLENDER_GPT_OT_GenerateCode,
    BLENDER_GPT_OT_ExecuteCode,
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
    bpy.types.Scene.blender_gpt_prompt = bpy.props.StringProperty(
        name="GPT Prompt", default="Make the cube red"
    )
    bpy.types.Scene.blender_gpt_generated_code = bpy.props.StringProperty(
        name="Generated Code", default="", options={'TEXTEDIT_UPDATE'}
    )
    bpy.types.Scene.blender_gpt_execution_result = bpy.props.StringProperty(
        name="Execution Result", default=""
    )
    print("blender_gpt Addon registered successfully.")

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
    print("blender_gpt Addon unregistered successfully.")

if __name__ == "__main__":
    register()