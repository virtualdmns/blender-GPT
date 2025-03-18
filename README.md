# Blender GPT

A Blender addon that integrates GPT to generate and execute Python code for automating tasks in Blender. This addon allows you to describe what you want to do in natural language (e.g., "Create three spheres at different locations and make each a different color (red, green, blue)"), and it will generate and execute the corresponding Blender Python code.

## Features
- **Natural Language Input**: Describe your Blender task in plain English, and the addon will generate the Python code to accomplish it.
- **Code Execution with Undo Support**: Generated code is executed in Blender with undo support, so you can easily revert changes.
- **Customizable GPT Model**: Choose between GPT-4, GPT-3.5 Turbo, or GPT-4o Mini (default) in the addon preferences.
- **Safe API Key Storage**: Stores your OpenAI API key in a `config.json` file in the addon directory, avoiding Blender's preferences system.

## Requirements
- **Blender Version**: 3.0.0 or higher (tested on Blender 4.3).
- **Python Libraries**:
  - `openai`: Required for GPT integration. Install via Blender's Python environment.
- **OpenAI API Key**: You need an API key from [OpenAI](https://platform.openai.com/account/api-keys).

## Installation
1. **Download the Addon**:
   - Clone or download this repository to your local machine.

2. **Install Required Python Library**:
   - Open a terminal and navigate to Blender's Python executable directory:
     - On macOS: `/Applications/Blender.app/Contents/Resources/4.3/python/bin/`
     - On Windows: `C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\`
     - On Linux: `/path/to/blender/4.3/python/bin/`
   - Install the `openai` library:
     ```bash
     ./python3.11 -m pip install openai