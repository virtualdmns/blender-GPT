from typing import Dict, List
import random

class VisionSystem:
    """
    Handles high-level scene analysis and composition.
    Breaks down user requests into scene elements, atmosphere, and relationships.
    """
    
    def analyze_scene(self, prompt: str) -> Dict:
        """Analyze a scene request and break it down into components"""
        return {
            "atmosphere": self._analyze_atmosphere(prompt),
            "composition": self._analyze_composition(prompt),
            "objects": self._identify_objects(prompt),
            "relationships": self._analyze_relationships(prompt)
        }
    
    def _analyze_atmosphere(self, prompt: str) -> Dict:
        """Analyze atmospheric conditions from prompt"""
        # Dream-like variations
        time_variations = ["dawn", "dusk", "night", "eternal twilight", "timeless void"]
        mood_variations = ["serene", "mysterious", "ethereal", "otherworldly", "dreamy", "surreal"]
        lighting_variations = ["moonlight", "starlight", "aurora", "bioluminescence", "ethereal glow"]
        weather_variations = ["misty", "foggy", "crystal clear", "ethereal mist", "cosmic dust"]
        
        # Randomly select variations
        time_of_day = random.choice(time_variations)
        mood = random.choice(mood_variations)
        lighting = random.choice(lighting_variations)
        weather = random.choice(weather_variations)
        
        return {
            "time_of_day": time_of_day,
            "mood": mood,
            "lighting": {
                "primary": lighting,
                "intensity": random.uniform(0.3, 1.0),
                "color_temperature": random.randint(2000, 10000),  # Wide range for dream-like lighting
                "color_tint": [random.uniform(0.8, 1.0) for _ in range(3)]  # Slight color tinting
            },
            "weather": {
                "type": weather,
                "effects": [
                    "floating particles",
                    "ethereal mist",
                    "cosmic dust",
                    "aurora borealis"
                ][:random.randint(0, 2)]  # Random number of effects
            },
            "dream_quality": {
                "lucidity": random.uniform(0.5, 1.0),
                "surrealism": random.uniform(0.3, 0.9),
                "stability": random.uniform(0.7, 1.0)
            }
        }
    
    def _analyze_composition(self, prompt: str) -> Dict:
        """Analyze scene composition and layout"""
        # Dream-like layer variations
        layer_types = {
            "ground": {
                "height": random.uniform(-0.5, 0.5),
                "objects": [],
                "valid_types": ["rock", "mushroom", "grass", "crystal", "portal", "void"]
            },
            "mid": {
                "height_range": [random.uniform(0.5, 2.0), random.uniform(2.0, 4.0)],
                "objects": [],
                "valid_types": ["bush", "small_tree", "fallen_log", "floating_island", "energy_crystal"]
            },
            "canopy": {
                "height_range": [random.uniform(3.0, 6.0), random.uniform(6.0, 12.0)],
                "objects": [],
                "valid_types": ["tree_top", "hanging_vine", "floating_platform", "cloud", "aurora"]
            }
        }
        
        # Dream-like distribution patterns
        distribution_patterns = [
            "natural",
            "geometric",
            "spiral",
            "fractal",
            "random",
            "symmetrical"
        ]
        
        # Dream-like depth variations
        depth_variations = [
            "infinite",
            "layered",
            "foggy",
            "crystal clear",
            "ethereal"
        ]
        
        return {
            "layers": layer_types,
            "focal_points": [
                {
                    "type": random.choice(["portal", "crystal", "light_source", "void"]),
                    "position": [random.uniform(-5, 5), random.uniform(-5, 5), random.uniform(0, 5)],
                    "influence_radius": random.uniform(2, 8)
                }
            ][:random.randint(0, 2)],  # Random number of focal points
            "depth": random.choice(depth_variations),
            "distribution": {
                "pattern": random.choice(distribution_patterns),
                "density": random.choice(["sparse", "medium", "dense"]),
                "clustering": random.choice(["natural", "geometric", "random"]),
                "symmetry": random.choice(["none", "radial", "bilateral", "fractal"])
            },
            "dream_effects": {
                "gravity": random.choice(["normal", "reversed", "variable", "none"]),
                "time_flow": random.choice(["normal", "slow", "fast", "variable"]),
                "reality_distortion": random.uniform(0.0, 0.8)
            }
        }
    
    def _identify_objects(self, prompt: str) -> List[Dict]:
        """Identify objects in the scene"""
        # Dream-like object types and their variations
        dream_objects = {
            "natural": {
                "tree": ["normal", "crystal", "floating", "upside_down", "transparent"],
                "rock": ["normal", "floating", "crystalline", "hollow", "glowing"],
                "mushroom": ["normal", "giant", "glowing", "floating", "crystalline"],
                "grass": ["normal", "crystal", "glowing", "floating", "transparent"]
            },
            "surreal": {
                "portal": ["normal", "crystal", "void", "energy", "time"],
                "crystal": ["normal", "floating", "energy", "void", "time"],
                "void": ["normal", "crystal", "energy", "time", "portal"],
                "light_source": ["normal", "crystal", "void", "energy", "time"]
            },
            "floating": {
                "island": ["normal", "crystal", "void", "energy", "time"],
                "platform": ["normal", "crystal", "void", "energy", "time"],
                "cloud": ["normal", "crystal", "void", "energy", "time"],
                "aurora": ["normal", "crystal", "void", "energy", "time"]
            }
        }
        
        # Generate a random number of objects
        num_objects = random.randint(3, 8)
        objects = []
        
        for _ in range(num_objects):
            # Randomly select object category and type
            category = random.choice(list(dream_objects.keys()))
            obj_type = random.choice(list(dream_objects[category].keys()))
            variation = random.choice(dream_objects[category][obj_type])
            
            # Generate random position and scale
            position = [
                random.uniform(-5, 5),
                random.uniform(-5, 5),
                random.uniform(0, 5)
            ]
            scale = random.uniform(0.5, 2.0)
            
            # Generate random rotation
            rotation = [
                random.uniform(0, 360),
                random.uniform(0, 360),
                random.uniform(0, 360)
            ]
            
            # Generate random properties
            properties = {
                "glow_intensity": random.uniform(0, 1),
                "transparency": random.uniform(0, 1),
                "energy_level": random.uniform(0, 1),
                "stability": random.uniform(0, 1),
                "reality_distortion": random.uniform(0, 1)
            }
            
            objects.append({
                "type": obj_type,
                "category": category,
                "variation": variation,
                "position": position,
                "scale": scale,
                "rotation": rotation,
                "properties": properties
            })
        
        return objects
    
    def _analyze_relationships(self, prompt: str) -> List[Dict]:
        """Analyze spatial and logical relationships between objects"""
        return [
            {
                "type": "proximity",
                "objects": ["mushroom", "tree"],
                "rule": "near",
                "parameters": {"max_distance": 0.8}
            },
            {
                "type": "grouping",
                "objects": ["rock"],
                "rule": "cluster",
                "parameters": {
                    "min_count": 2,
                    "max_count": 5,
                    "spacing": 0.3
                }
            }
        ] 