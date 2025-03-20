"""
The Dreamer module provides scene analysis and decomposition capabilities
for the BlenderGPT addon.
"""

import json
import re
import random
import math
from typing import Dict, List, Union

__all__ = ['Dreamer']

class Dreamer:
    """
    The Dreamer system breaks down scene requests into logical primitive components
    with proper spatial relationships and attachment points.
    """
    
    def __init__(self):
        self.debug = True  # Enable console output
        self._log("\n=== Initializing Dreamer System ===")
        
        # Sacred geometry constants
        self.PHI = (1 + math.sqrt(5)) / 2  # Golden ratio
        self.FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        
        # Initialize error handling
        self.errors = []
        self.warnings = []
        
        try:
            # Load reference decompositions (if any)
            self.reference_decompositions = self._load_reference_decompositions()
            if not self.reference_decompositions:
                self.warnings.append("No reference decompositions loaded")
            else:
                self._log(f"Loaded {len(self.reference_decompositions)} reference decompositions")
            
            self._log("Dreamer system initialized successfully")
            
        except Exception as e:
            self.errors.append(f"Initialization error: {str(e)}")
            self._log(f"Error during initialization: {str(e)}")

    def _log(self, message: str):
        """Debug logging to console"""
        if self.debug:
            print(f"[DREAMER] {message}")

    def process_request(self, prompt: str) -> Dict:
        """
        Process a user's scene request and break it down into a structured vision.
        Returns a dictionary with objects and relationships.
        """
        self._log(f"Processing request: {prompt}")
        
        try:
            prompt_lower = prompt.lower().strip()
            scene_vision = {
                "objects": [],
                "relationships": [],
                "atmosphere": self._analyze_atmosphere(prompt_lower),
                "composition": self._analyze_composition(prompt_lower)
            }
            
            # Extract count from prompt (e.g., "10 trees")
            count_match = re.search(r"(\d+)", prompt_lower)
            count = int(count_match.group()) if count_match else 1
            
            # Identify objects in the prompt
            objects = self._identify_objects(prompt_lower)
            if not objects:
                self._log("No objects identified in prompt, defaulting to cube")
                objects = [{"name": "cube", "count": count}]

            # Process each object
            for obj in objects:
                object_name = obj["name"]
                obj_count = obj.get("count", count)
                
                # Get properties (e.g., "tall" trees)
                properties = {}
                if "tall" in prompt_lower and "tree" in object_name:
                    object_name = "tall_tree"
                    properties["height"] = "tall"
                
                # Decompose the object into primitives
                base_decomp = self._decompose_object(object_name, context=scene_vision)
                scene_vision["objects"].append({
                    "type": object_name,
                    "count": obj_count,
                    "components": [
                        {
                            "primitive": base_decomp["primary_form"]["primitive"],
                            "name": base_decomp["primary_form"]["name"],
                            "dimensions": base_decomp["primary_form"]["dimensions"]
                        },
                        *[
                            {
                                "primitive": f["primitive"],
                                "name": f["name"],
                                "dimensions": f["dimensions"]
                            }
                            for f in base_decomp["secondary_forms"]
                        ]
                    ],
                    "properties": properties
                })
            
            # Analyze relationships between objects
            scene_vision["relationships"] = self._analyze_relationships(prompt_lower, objects)
            
            self._log("\n=== Scene Vision ===")
            self._log(json.dumps(scene_vision, indent=2))
            return scene_vision
        
        except Exception as e:
            self.errors.append(f"Error processing request: {str(e)}")
            self._log(f"Error during processing: {str(e)}")
            return {"objects": [], "relationships": [], "atmosphere": {}, "composition": {}}

    def _analyze_atmosphere(self, prompt: str) -> Dict:
        """Analyze atmospheric conditions from prompt."""
        atmosphere = {
            "time_of_day": "day",
            "mood": "neutral",
            "lighting": {"primary": "sun", "intensity": 1.0}
        }
        if "night" in prompt:
            atmosphere["time_of_day"] = "night"
            atmosphere["lighting"]["primary"] = "moon"
            atmosphere["lighting"]["intensity"] = 0.5
        elif "dark" in prompt:
            atmosphere["mood"] = "mysterious"
            atmosphere["lighting"]["intensity"] = 0.3
        return atmosphere

    def _analyze_composition(self, prompt: str) -> Dict:
        """Analyze scene composition and layout."""
        return {
            "layers": {
                "ground": {"height": 0, "objects": []},
                "mid": {"height_range": [1, 3], "objects": []},
                "canopy": {"height_range": [3, 10], "objects": []}
            },
            "focal_points": [],
            "depth": "medium"
        }

    def _identify_objects(self, prompt: str) -> List[Dict]:
        """Identify objects mentioned in the prompt."""
        objects = []
        base_decompositions = self._get_base_decomposition("")
        
        # Split prompt into words and look for matches
        prompt_words = prompt.lower().split()
        for word in prompt_words:
            for obj_name in base_decompositions.keys():
                obj_parts = obj_name.split('_')
                if any(part in word for part in obj_parts) or word in obj_name:
                    # Check for a count specific to this object (e.g., "5 trees")
                    count_match = re.search(r"(\d+)\s+" + word, prompt)
                    count = int(count_match.group(1)) if count_match else 1
                    objects.append({"name": obj_name, "count": count})
                    break
            # Handle basic shapes explicitly
            if "sphere" in word:
                objects.append({"name": "sphere", "count": 1})
            elif "cylinder" in word:
                objects.append({"name": "cylinder", "count": 1})
            elif "cube" in word:
                objects.append({"name": "cube", "count": 1})

        return objects

    def _analyze_relationships(self, prompt: str, objects: List[Dict]) -> List[Dict]:
        """Analyze spatial and logical relationships between objects."""
        relationships = []
        if "near" in prompt or "with" in prompt:
            if len(objects) >= 2:
                # Example: mushrooms near trees
                for i, obj1 in enumerate(objects):
                    for obj2 in objects[i+1:]:
                        if ("mushroom" in obj1["name"] and "tree" in obj2["name"]) or \
                           ("mushroom" in obj2["name"] and "tree" in obj1["name"]):
                            relationships.append({
                                "type": "proximity",
                                "objects": [obj1["name"], obj2["name"]],
                                "rule": "near",
                                "parameters": {"max_distance": 0.8}
                            })
        return relationships

    def _decompose_object(self, object_name: str, context: Dict) -> Dict:
        """
        Break down an object into its primary, secondary, and tertiary forms
        with proper attachment points and logical placement.
        """
        base_decomp = self._get_base_decomposition(object_name)
        if not base_decomp:
            base_decomp = self._get_default_decomposition(object_name)

        # Adjust decomposition based on context (e.g., atmosphere)
        if context["atmosphere"]["mood"] == "mysterious":
            if "tertiary_details" in base_decomp:
                base_decomp["tertiary_details"].append("glow")

        return base_decomp

    def _get_base_decomposition(self, object_name: str) -> Dict:
        """Define base decompositions for known objects."""
        base_decompositions = {
            "tall_tree": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.3, "height": 5.0},
                    "variation": 0.2,
                    "attachment_points": {
                        "top": {"position": [0, 0, 5], "normal": [0, 0, 1], "valid_attachments": ["foliage"]}
                    }
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "crown",
                        "attaches_to": "top",
                        "dimensions": {"radius": 2.0},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["bark_texture", "leaves", "branches"]
            },
            "tree": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.2, "height": 3.0},
                    "variation": 0.2,
                    "attachment_points": {
                        "top": {"position": [0, 0, 3], "normal": [0, 0, 1], "valid_attachments": ["foliage"]}
                    }
                },
                "secondary_forms": [
                    {
                        "primitive": "CONE",
                        "name": "foliage",
                        "attaches_to": "top",
                        "dimensions": {"radius": 1.5, "height": 2.0},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["bark_texture", "leaves"]
            },
            "mushroom": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "stem",
                    "dimensions": {"radius": 0.1, "height": 0.3},
                    "variation": 0.2,
                    "attachment_points": {
                        "top": {"position": [0, 0, 0.3], "normal": [0, 0, 1], "valid_attachments": ["cap"]}
                    }
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "cap",
                        "attaches_to": "top",
                        "dimensions": {"radius": 0.25},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["spots", "glow"]
            },
            "rock": {
                "primary_form": {
                    "primitive": "ICO_SPHERE",
                    "name": "base",
                    "dimensions": {"radius": 0.5},
                    "variation": 0.5
                },
                "secondary_forms": [],
                "tertiary_details": ["rock_texture", "displacement"]
            },
            "sphere": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "sphere",
                    "dimensions": {"radius": 1.0},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": ["smooth_texture"]
            },
            "cylinder": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "cylinder",
                    "dimensions": {"radius": 0.5, "height": 2.0},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": ["smooth_texture"]
            },
            "cube": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "cube",
                    "dimensions": {"size": 1.0},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": []
            }
        }
        return base_decompositions.get(object_name, {})

    def _get_default_decomposition(self, object_name: str) -> Dict:
        """Provide a default decomposition for unknown objects."""
        return {
            "primary_form": {
                "primitive": "CUBE",
                "name": object_name,
                "dimensions": {"size": 1.0},
                "variation": 0.2,
                "attachment_points": {}
            },
            "secondary_forms": [],
            "tertiary_details": ["basic_texture"]
        }

    def _load_reference_decompositions(self) -> Dict:
        """Load reference decompositions from unrefined.json (if available)."""
        try:
            import os
            addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
            json_path = os.path.join(addon_dir, "composite_objects", "reference", "unrefined.json")
            self._log(f"Loading reference decompositions from: {json_path}")
            with open(json_path, "r") as f:
                data = json.load(f)
                decompositions = {}
                for obj_name, obj_data in data.items():
                    decompositions[obj_name.lower()] = {
                        "primary_form": {
                            "primitive": obj_data["Primary"]["primitive"],
                            "name": "base",
                            "dimensions": self._get_default_dimensions(obj_data["Primary"]["primitive"]),
                            "variation": 0.3,
                            "attachment_points": {}
                        },
                        "secondary_forms": [
                            {
                                "primitive": form["primitive"],
                                "name": f"secondary_{i}",
                                "dimensions": self._get_default_dimensions(form["primitive"]),
                                "variation": 0.3
                            }
                            for i, form in enumerate(obj_data["Secondary"])
                        ],
                        "tertiary_details": obj_data["Tertiary"]
                    }
                return decompositions
        except Exception as e:
            self._log(f"Warning: Could not load reference decompositions: {e}")
            return {}

    def _get_default_dimensions(self, primitive: str) -> Dict:
        """Get default dimensions for a primitive type."""
        dimensions = {
            "SPHERE": {"radius": 1.0},
            "CUBE": {"width": 1.0, "height": 1.0, "depth": 1.0},
            "CYLINDER": {"radius": 0.5, "height": 1.0},
            "CONE": {"radius": 0.5, "height": 1.0},
            "TORUS": {"radius": 1.0, "thickness": 0.2},
            "PLANE": {"width": 1.0, "height": 1.0},
            "ICO_SPHERE": {"radius": 1.0},
            "PYRAMID": {"base": 1.0, "height": 1.0}
        }
        return dimensions.get(primitive.upper(), {"size": 1.0})

# For testing
if __name__ == "__main__":
    dreamer = Dreamer()
    vision = dreamer.process_request("Create a forest scene with 10 tall trees and mushrooms growing near their bases")