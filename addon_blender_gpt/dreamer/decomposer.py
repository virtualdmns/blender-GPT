from typing import Dict, List, Union

class ObjectDecomposer:
    """
    Handles the breakdown of objects into their primitive components,
    following logical attachment and composition rules.
    """
    
    def decompose_object(self, object_name: str, context: Dict) -> Dict:
        """
        Break down an object into primary, secondary, and tertiary forms
        with proper attachment points and logical placement.
        """
        # Get the appropriate decomposition method
        method_name = f"_decompose_{object_name}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(context)
        return self._decompose_generic(object_name, context)
    
    def _decompose_tree(self, context: Dict) -> Dict:
        """Decompose a tree into its components"""
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
    
    def _decompose_mushroom(self, context: Dict) -> Dict:
        """Decompose a mushroom into its components"""
        return {
            "primary_form": {
                "primitive": "CYLINDER",
                "name": "stem",
                "dimensions": {"radius": 0.05, "height": 0.3},
                "attachment_points": {
                    "top": {
                        "position": [0, 0, 0.3],
                        "normal": [0, 0, 1],
                        "valid_attachments": ["cap"]
                    }
                }
            },
            "secondary_forms": [
                {
                    "primitive": "SPHERE",
                    "name": "cap",
                    "attaches_to": "top",
                    "dimensions": {"radius": 0.2},
                    "modifiers": [
                        {
                            "type": "scale",
                            "parameters": {"z": 0.5}
                        }
                    ],
                    "attachment_logic": {
                        "rule": "biological",
                        "justification": "Mushroom cap grows from top of stem"
                    }
                }
            ],
            "tertiary_details": [
                {
                    "type": "spots",
                    "affects": "secondary.cap",
                    "description": "Mushroom spots",
                    "parameters": {
                        "count": [3, 7],
                        "size_range": [0.02, 0.04],
                        "color": [1, 1, 1]
                    }
                }
            ]
        }
    
    def _decompose_rock(self, context: Dict) -> Dict:
        """Decompose a rock into its components"""
        return {
            "primary_form": {
                "primitive": "ICO_SPHERE",
                "name": "base",
                "dimensions": {"radius": 0.5},
                "modifiers": [
                    {
                        "type": "random_vertices",
                        "parameters": {
                            "strength": 0.2,
                            "seed": "random"
                        }
                    }
                ]
            },
            "secondary_forms": [],  # Rocks are primarily modified primary forms
            "tertiary_details": [
                {
                    "type": "texture",
                    "affects": "primary",
                    "description": "Rock texture",
                    "parameters": {
                        "noise_scale": 0.2,
                        "roughness": 0.7,
                        "color_variation": 0.1
                    }
                }
            ]
        }
    
    def _decompose_generic(self, object_name: str, context: Dict) -> Dict:
        """Generic decomposition for unknown objects"""
        return {
            "primary_form": {
                "primitive": "CUBE",  # Default to cube
                "name": object_name,
                "dimensions": {"size": 1.0}
            },
            "secondary_forms": [],
            "tertiary_details": []
        } 