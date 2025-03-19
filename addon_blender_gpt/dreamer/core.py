import json
import random
import math
import os
import traceback
import time
from typing import Dict, List, Union, Tuple

class Dreamer:
    """
    The Dreamer system breaks down scene requests into logical primitive components
    with proper spatial relationships and attachment points.
    """
    
    def __init__(self):
        self.debug = True
        print("\n=== Initializing Dreamer System ===")
        
        # Sacred geometry constants
        self.PHI = (1 + math.sqrt(5)) / 2  # Golden ratio
        self.FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        
        # Initialize error handling
        self.errors = []
        self.warnings = []
        
        try:
            # Load reference decompositions
            print("Loading reference decompositions...")
            self.reference_decompositions = self._load_reference_decompositions()
            if not self.reference_decompositions:
                self.warnings.append("No reference decompositions loaded")
            else:
                print(f"Loaded {len(self.reference_decompositions)} reference decompositions")
            
            print("Dreamer system initialized successfully")
            
        except Exception as e:
            self.errors.append(f"Initialization error: {str(e)}")
            print(f"Error during initialization: {str(e)}")
    
    def process_request(self, prompt: str) -> Dict:
        """Process a user's request into emotional and energetic insights"""
        if not prompt or not isinstance(prompt, str):
            return {
                "error": "Invalid prompt provided",
                "insights": None
            }
            
        try:
            # Generate emotional and energetic insights
            insights = {
                "emotional": {
                    "primary": random.choice(["joy", "melancholy", "rage", "serenity", "wonder", "dread", "love", "hate"]),
                    "secondary": random.choice(["nostalgia", "euphoria", "anxiety", "peace", "excitement", "despair", "hope", "fear"]),
                    "intensity": random.uniform(0.3, 1.0)
                },
                "energetic": {
                    "flow": random.choice(["chaotic", "serene", "turbulent", "gentle", "violent", "peaceful"]),
                    "frequency": random.choice(["high", "low", "medium", "variable", "pulsing", "constant"]),
                    "quality": random.choice(["pure", "corrupted", "balanced", "unstable", "harmonious", "discordant"])
                },
                "conceptual": {
                    "form": random.choice(["organic", "geometric", "fluid", "rigid", "amorphous", "crystalline"]),
                    "setting": random.choice(["void", "cosmos", "abyss", "heaven", "hell", "liminal"]),
                    "essence": random.choice(["light", "darkness", "chaos", "order", "creation", "destruction"])
                },
                "aesthetic": {
                    "beauty": random.choice(["sublime", "grotesque", "elegant", "crude", "ethereal", "mundane"]),
                    "color": random.choice(["vibrant", "muted", "monochrome", "rainbow", "dark", "bright"]),
                    "texture": random.choice(["smooth", "rough", "crystalline", "fuzzy", "metallic", "organic"])
                },
                "narrative": {
                    "tone": random.choice(["hopeful", "tragic", "mysterious", "whimsical", "dark", "light"]),
                    "pace": random.choice(["fast", "slow", "erratic", "steady", "pulsing", "still"]),
                    "mood": random.choice(["dreamy", "nightmarish", "peaceful", "chaotic", "serene", "turbulent"])
                }
            }
            
            # Add cosmic insights
            insights["cosmic"] = {
                "dimension": random.choice(["infinite", "finite", "bent", "folded", "torn", "mended"]),
                "reality": random.choice(["stable", "unstable", "fractured", "whole", "shifting", "fixed"]),
                "existence": random.choice(["eternal", "temporary", "cyclical", "linear", "spiral", "void"])
            }
            
            return {
                "insights": insights,
                "timestamp": time.time()
            }
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            print(error_msg)
            self.errors.append(error_msg)
            return {
                "error": error_msg,
                "insights": None
            }
    
    def _get_base_decomposition(self, object_name: str) -> Dict:
        """Get base decomposition for known objects"""
        base_decompositions = {
            "tall_tree": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.3, "height": 5.0},
                    "variation": 0.2
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "crown",
                        "dimensions": {"radius": 2.0},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["bark_texture", "leaves", "branches"]
            },
            "small_tree": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.2, "height": 2.5},
                    "variation": 0.2
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "foliage",
                        "dimensions": {"radius": 1.2},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["bark_texture", "leaf_particles"]
            },
            "bush": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "foliage",
                    "dimensions": {"radius": 0.8},
                    "variation": 0.4
                },
                "secondary_forms": [],
                "tertiary_details": ["leaf_texture"]
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
            "grass": {
                "primary_form": {
                    "primitive": "PLANE",
                    "name": "blade",
                    "dimensions": {"size": 0.1, "height": 0.3},
                    "variation": 0.6
                },
                "secondary_forms": [],
                "tertiary_details": ["transparency", "wind_motion"]
            },
            "mushroom": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "stem",
                    "dimensions": {"radius": 0.1, "height": 0.3},
                    "variation": 0.2
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "cap",
                        "dimensions": {"radius": 0.25},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["spots", "glow"]
            },
            "building": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "main",
                    "dimensions": {"width": 2.0, "height": 4.0, "depth": 2.0},
                    "variation": 0.1
                },
                "secondary_forms": [
                    {
                        "primitive": "CUBE",
                        "name": "windows",
                        "dimensions": {"width": 0.2, "height": 0.2, "depth": 0.1},
                        "variation": 0.2
                    }
                ],
                "tertiary_details": ["glass", "reflection"]
            },
            "car": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "body",
                    "dimensions": {"width": 1.5, "height": 0.5, "depth": 0.8},
                    "variation": 0.2
                },
                "secondary_forms": [
                    {
                        "primitive": "CYLINDER",
                        "name": "wheel",
                        "dimensions": {"radius": 0.2, "height": 0.1},
                        "variation": 0.1
                    }
                ],
                "tertiary_details": ["metal", "glass"]
            },
            "person": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "body",
                    "dimensions": {"radius": 0.2, "height": 1.7},
                    "variation": 0.1
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "head",
                        "dimensions": {"radius": 0.15},
                        "variation": 0.1
                    }
                ],
                "tertiary_details": ["clothing", "face"]
            },
            "lamp_post": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "pole",
                    "dimensions": {"radius": 0.1, "height": 3.0},
                    "variation": 0.1
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "lamp",
                        "dimensions": {"radius": 0.3},
                        "variation": 0.2
                    }
                ],
                "tertiary_details": ["glow", "metal"]
            },
            "bench": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "seat",
                    "dimensions": {"width": 1.5, "height": 0.2, "depth": 0.4},
                    "variation": 0.1
                },
                "secondary_forms": [
                    {
                        "primitive": "CYLINDER",
                        "name": "leg",
                        "dimensions": {"radius": 0.05, "height": 0.4},
                        "variation": 0.1
                    }
                ],
                "tertiary_details": ["wood", "metal"]
            },
            "crib": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "frame",
                    "dimensions": {"width": 1.0, "height": 0.8, "depth": 0.6},
                    "variation": 0.1
                },
                "secondary_forms": [
                    {
                        "primitive": "CYLINDER",
                        "name": "bar",
                        "dimensions": {"radius": 0.02, "height": 0.6},
                        "variation": 0.1
                    }
                ],
                "tertiary_details": ["wood", "fabric"]
            },
            "teddy_bear": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "body",
                    "dimensions": {"radius": 0.3},
                    "variation": 0.2
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "head",
                        "dimensions": {"radius": 0.2},
                        "variation": 0.2
                    }
                ],
                "tertiary_details": ["fur", "face"]
            },
            "psychedelic_plant": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "stem",
                    "dimensions": {"radius": 0.1, "height": 1.0},
                    "variation": 0.3
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "flower",
                        "dimensions": {"radius": 0.3},
                        "variation": 0.4
                    }
                ],
                "tertiary_details": ["neon_glow", "fractal_pattern"]
            },
            "crystal": {
                "primary_form": {
                    "primitive": "ICO_SPHERE",
                    "name": "base",
                    "dimensions": {"radius": 0.3},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": ["refraction", "rainbow"]
            },
            "fractal": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "base",
                    "dimensions": {"size": 1.0},
                    "variation": 0.5
                },
                "secondary_forms": [],
                "tertiary_details": ["recursive", "neon"]
            },
            "nebula": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "cloud",
                    "dimensions": {"radius": 2.0},
                    "variation": 0.8
                },
                "secondary_forms": [],
                "tertiary_details": ["gas", "stars"]
            },
            "portal": {
                "primary_form": {
                    "primitive": "TORUS",
                    "name": "ring",
                    "dimensions": {"radius": 1.0, "thickness": 0.1},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": ["energy", "distortion"]
            },
            "wave": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "base",
                    "dimensions": {"width": 3.0, "height": 0.5, "depth": 1.0},
                    "variation": 0.4
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "crest",
                        "dimensions": {"radius": 0.3},
                        "variation": 0.5
                    }
                ],
                "tertiary_details": ["water", "foam", "transparency"]
            },
            "sand": {
                "primary_form": {
                    "primitive": "PLANE",
                    "name": "ground",
                    "dimensions": {"width": 10.0, "height": 10.0},
                    "variation": 0.3
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "dune",
                        "dimensions": {"radius": 0.5},
                        "variation": 0.4
                    }
                ],
                "tertiary_details": ["texture", "displacement"]
            },
            "shell": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "base",
                    "dimensions": {"radius": 0.2},
                    "variation": 0.3
                },
                "secondary_forms": [
                    {
                        "primitive": "CUBE",
                        "name": "spiral",
                        "dimensions": {"size": 0.1},
                        "variation": 0.4
                    }
                ],
                "tertiary_details": ["iridescence", "pattern"]
            },
            "palm": {
                "primary_form": {
                    "primitive": "CYLINDER",
                    "name": "trunk",
                    "dimensions": {"radius": 0.2, "height": 3.0},
                    "variation": 0.3
                },
                "secondary_forms": [
                    {
                        "primitive": "SPHERE",
                        "name": "frond",
                        "dimensions": {"radius": 0.8},
                        "variation": 0.4
                    }
                ],
                "tertiary_details": ["texture", "wind_motion"]
            },
            "coral": {
                "primary_form": {
                    "primitive": "ICO_SPHERE",
                    "name": "base",
                    "dimensions": {"radius": 0.3},
                    "variation": 0.5
                },
                "secondary_forms": [
                    {
                        "primitive": "CUBE",
                        "name": "branch",
                        "dimensions": {"size": 0.1},
                        "variation": 0.6
                    }
                ],
                "tertiary_details": ["color", "texture"]
            },
            "empty_crib": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "frame",
                    "dimensions": {"width": 1.0, "height": 0.8, "depth": 0.6},
                    "variation": 0.3
                },
                "secondary_forms": [
                    {
                        "primitive": "CYLINDER",
                        "name": "bar",
                        "dimensions": {"radius": 0.02, "height": 0.6},
                        "variation": 0.3
                    }
                ],
                "tertiary_details": ["broken_wood", "dust", "cobwebs"]
            },
            "broken_toy": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "body",
                    "dimensions": {"radius": 0.2},
                    "variation": 0.5
                },
                "secondary_forms": [
                    {
                        "primitive": "CUBE",
                        "name": "fragment",
                        "dimensions": {"size": 0.1},
                        "variation": 0.6
                    }
                ],
                "tertiary_details": ["cracked", "dirty", "faded"]
            },
            "doll": {
                "primary_form": {
                    "primitive": "SPHERE",
                    "name": "head",
                    "dimensions": {"radius": 0.15},
                    "variation": 0.4
                },
                "secondary_forms": [
                    {
                        "primitive": "CYLINDER",
                        "name": "body",
                        "dimensions": {"radius": 0.1, "height": 0.3},
                        "variation": 0.4
                    }
                ],
                "tertiary_details": ["cracked_face", "torn_clothes", "dirty"]
            },
            "shadow": {
                "primary_form": {
                    "primitive": "PLANE",
                    "name": "base",
                    "dimensions": {"width": 2.0, "height": 2.0},
                    "variation": 0.8
                },
                "secondary_forms": [],
                "tertiary_details": ["dark", "transparent", "blurred"]
            },
            "mirror": {
                "primary_form": {
                    "primitive": "CUBE",
                    "name": "frame",
                    "dimensions": {"width": 0.8, "height": 1.2, "depth": 0.1},
                    "variation": 0.2
                },
                "secondary_forms": [],
                "tertiary_details": ["cracked", "foggy", "reflection"]
            }
        }
        return base_decompositions.get(object_name, self._get_default_decomposition(object_name))
    
    def _get_default_decomposition(self, object_name: str) -> Dict:
        """Provide a default decomposition for unknown objects"""
        return {
            "primary_form": {
                "primitive": "CUBE",
                "name": object_name,
                "dimensions": {"size": 1.0},
                "variation": 0.2
            },
            "secondary_forms": [],
            "tertiary_details": ["basic_texture"]
        }
    
    def _load_reference_decompositions(self) -> Dict:
        """Load and parse the reference decompositions from unrefined.json"""
        try:
            with open("addon_blender_gpt/composite_objects/reference/unrefined.json", "r") as f:
                data = json.load(f)
                # Convert the reference format to our internal format
                decompositions = {}
                for obj_name, obj_data in data.items():
                    decompositions[obj_name.lower()] = {
                        "primary_form": {
                            "primitive": obj_data["Primary"]["primitive"],
                            "name": "base",
                            "dimensions": self._get_default_dimensions(obj_data["Primary"]["primitive"]),
                            "variation": 0.3
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
            print(f"Warning: Could not load reference decompositions: {e}")
            return {}

    def _get_default_dimensions(self, primitive: str) -> Dict:
        """Get default dimensions for a primitive type"""
        dimensions = {
            "Sphere": {"radius": 1.0},
            "Cube": {"width": 1.0, "height": 1.0, "depth": 1.0},
            "Cylinder": {"radius": 0.5, "height": 1.0},
            "Cone": {"radius": 0.5, "height": 1.0},
            "Torus": {"radius": 1.0, "thickness": 0.2},
            "Plane": {"width": 1.0, "height": 1.0},
            "Icosphere": {"radius": 1.0},
            "Pyramid": {"base": 1.0, "height": 1.0}
        }
        return dimensions.get(primitive, {"size": 1.0}) 