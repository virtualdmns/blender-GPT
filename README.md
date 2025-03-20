![GPT's Forest](forest.png)
# BlenderGPT

BlenderGPT is a Blender addon that leverages AI to generate and execute Python scripts for creating 3D scenes based on natural language prompts. It supports iterative scene enhancement, allowing the AI to analyze and improve the scene over multiple passes, with features like real-time progress tracking, cancellation, and detailed logging.

## Features

- **Natural Language Scene Generation**: Describe your scene in plain English (e.g., "Create a model of the solar system with the Sun and planets as spheres"), and BlenderGPT will generate and execute the corresponding Blender Python script.
- **Iterative Scene Enhancement**: Automatically refine your scene over multiple iterations by analyzing the current state and adding complementary elements (e.g., adding moons to planets in a solar system model). Each iteration includes a 1-second pause for visual feedback, and you can cancel at any time by pressing the Esc key.
- **Dual Panel Access**: Access BlenderGPT in either the Sidebar (View3D > Sidebar > BlenderGPT) or the Properties panel (Properties > Scene > BlenderGPT).
- **Progress Tracking**: A progress bar displays the current iteration and percentage completion during iterative generation.
- **Detailed Logging**: View detailed logs in the Blender console, including scene analysis, generated prompts, and executed scripts for each iteration.
- **Chat Interface**: Interact with BlenderGPT in Assistant mode for script generation or Dreamer mode for creative scene interpretation.
- **Safe Script Execution**: Scripts are validated to prevent unsafe commands, ensuring a secure workflow.
- **Customizable Settings**: Choose your preferred GPT model (e.g., GPT-4o Mini) in the addon preferences.

## Installation

1. **Download the Addon**:
   - Clone or download this repository from `https://github.com/virtualdmns/blender-gpt`.

2. **Install in Blender**:
   - Open Blender and go to `Edit > Preferences > Add-ons`.
   - Click `Install`, then select the downloaded `addon_blender_gpt.zip` file.
   - Enable the addon by checking the box next to "BlenderGPT".

3. **Configure API Key**:
   - Create a `config.json` file in the addon directory with your OpenAI API key in the format:
     ```json
     {
       "openai_api_key": "your-api-key-here"
     }
     ```
   - Alternatively, use the "Load API Key" button in the BlenderGPT panel to select a file containing your API key.

4. **Install Dependencies**:
   - Ensure the `openai` and `requests` Python packages are installed for Blender's Python environment:
     ```bash
     /Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install openai requests
     ```
   - On Windows, the path might be:
     ```bash
     "C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe" -m pip install openai requests
     ```

## Usage

1. **Access the Panel**:
   - Open the BlenderGPT panel in either:
     - **Sidebar**: `View3D > Sidebar > BlenderGPT`
     - **Properties Panel**: `Properties > Scene > BlenderGPT`

2. **Generate a Scene**:
   - Enter a prompt in the "Prompt" field (e.g., "Create a model of the solar system with the Sun and planets as spheres, with circle curves for orbits").
   - Set the number of iterations to enhance the scene (e.g., 2 iterations to add moons or an asteroid belt).
   - Click "Generate" to create the script.
   - Review the generated script in the "Generated Commands" section.
   - Click "Execute" to apply the script to your scene.
   - Watch the scene evolve with a 1-second pause between iterations, and press Esc to cancel if needed.

3. **Monitor Progress**:
   - During iterative generation, a progress bar will display the current iteration and percentage completion.
   - Check the Blender console for detailed logs of each iteration, including scene analysis and executed scripts.

4. **Interact via Chat**:
   - Use the chat interface to refine your scene or ask questions.
   - Switch between "Assistant" mode for script generation and "Dreamer" mode for creative insights.

## Example Prompt

- **Prompt**: "Create a model of the solar system with the Sun and all 8 planets (Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune) as spheres. The Sun should be at the center with a bright yellow material, and each planet should have a unique color and size, positioned at increasing distances from the Sun. Use circle curves to represent the orbits."
- **Iterations**: 3
- **Result**: The addon will create the solar system model, then iteratively add elements like moons, an asteroid belt, or a starry background, with a 1-second pause between each iteration.

## Requirements

- Blender 4.0 or later
- OpenAI API key
- Python packages: `openai`, `requests`

## Notes

- Ensure your API key is correctly configured to avoid errors.
- The addon includes safety checks to prevent execution of dangerous scripts.
- Iterations can be resource-intensive depending on the complexity of the scene and the number of iterations.

## Contributing

Contributions are welcome! Please submit issues or pull requests to the GitHub repository: `https://github.com/virtualdmns/blender-gpt`.

## License

This project is licensed under the MIT License. See the LICENSE file for details.