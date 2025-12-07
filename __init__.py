"""
Workflow Importer Extension for ComfyUI

This extension provides a frontend UI button and dialog for drag-and-drop
workflow import from images containing ComfyUI metadata.
"""

# Point to the web directory for frontend assets
WEB_DIRECTORY = "web"


# Required by ComfyUI even for UI-only extensions
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["WEB_DIRECTORY", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
