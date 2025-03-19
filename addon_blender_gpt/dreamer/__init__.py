"""
The Dreamer module provides scene analysis and decomposition capabilities
for the BlenderGPT addon.
"""

from .core import Dreamer

__all__ = ['Dreamer']

import json
import bpy
from typing import Dict, List, Union

class Dreamer:
    """
    The Dreamer system breaks down scene requests into logical primitive components
    with proper spatial relationships and attachment points.
    """
    
    def __init__(self):
        self.debug = True  # Enable console output
        
    def _log(self, message: str):
        """Debug logging to console"""
        if self.debug:
            print(f"[DREAMER] {message}")

    def process_request(self, prompt: str) -> Dict:
        """
        Process a user's scene request and break it down into a structured vision
        """
        self._log(f"Processing request: {prompt}")
        
        # First pass: Scene-level understanding
        scene_vision = {
            "atmosphere": self._analyze_atmosphere(prompt),
            "composition": self._analyze_composition(prompt),
            "objects": self._identify_objects(prompt),
            "relationships": self._analyze_relationships(prompt)
        }
        
        # Second pass: Break down each object into primitives
        object_breakdowns = {}
        for obj in scene_vision["objects"]:
            object_breakdowns[obj] = self._decompose_object(
                obj, 
                context=scene_vision
            )
            
        scene_vision["object_breakdowns"] = object_breakdowns
        
        # Output the vision to console in a readable format
        self._log("\n=== Scene Vision ===")
        self._log(json.dumps(scene_vision, indent=2))
        
        return scene_vision
    
    def _analyze_atmosphere(self, prompt: str) -> Dict:
        """Analyze atmospheric conditions from prompt"""
        # For now, just basic time of day and mood
        # TODO: Integrate with GPT for more sophisticated analysis
        return {
            "time_of_day": "day",  # Default
            "mood": "neutral",
            "lighting": {
                "primary": "sun",
                "intensity": 1.0
            }
        }
    
    def _analyze_composition(self, prompt: str) -> Dict:
        """Analyze scene composition and layout"""
        return {
            "layers": {
                "ground": {"height": 0, "objects": []},
                "mid": {"height_range": [1, 3], "objects": []},
                "canopy": {"height_range": [3, 10], "objects": []}
            },
            "focal_points": [],
            "depth": "medium"
        }
    
    def _identify_objects(self, prompt: str) -> List[str]:
        """Identify required objects from prompt"""
        # TODO: Use GPT to properly parse objects from prompt
        # For now, return test objects
        return ["tree", "rock", "mushroom"]
    
    def _analyze_relationships(self, prompt: str) -> List[Dict]:
        """Analyze spatial and logical relationships between objects"""
        return [
            {
                "type": "proximity",
                "objects": ["mushroom", "tree"],
                "rule": "near",
                "parameters": {"max_distance": 0.8}
            }
        ]
    
    def _decompose_object(self, object_name: str, context: Dict) -> Dict:
        """
        Break down an object into its primary, secondary, and tertiary forms
        with proper attachment points and logical placement.
        """
        # Example decomposition for a tree
        if object_name == "tree":
            return {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.3, "height": 3.0},
                    "attachment_points": {
                        "branch_points": {
                            "positions": [[0, 0, 1], [0, 0, 2]],
                            "normals": [[1, 0, 0.2], [-1, 0, 0.2]],
                            "valid_attachments": ["branch"]
                        },
                        "top": {
                            "position": [0, 0, 3],
                            "normal": [0, 0, 1],
                            "valid_attachments": ["foliage"]
                        }
                    }
                },
                "secondary_forms": [
                    {
                        "primitive": "CONE",
                        "name": "foliage",
                        "attaches_to": "top",
                        "dimensions": {"radius": 1.5, "height": 2.0},
                        "attachment_logic": {
                            "rule": "biological",
                            "justification": "Tree foliage grows from top of trunk"
                        }
                    }
                ],
                "tertiary_details": [
                    {
                        "type": "texture",
                        "affects": "primary",
                        "description": "Bark texture",
                        "parameters": {
                            "noise_scale": 0.1,
                            "roughness": 0.8
                        }
                    }
                ]
            }
            
        # Add more object types as needed
        return {}

# For testing
if __name__ == "__main__":
    dreamer = Dreamer()
    vision = dreamer.process_request("Create a forest scene with tall trees and mushrooms growing near their bases") 