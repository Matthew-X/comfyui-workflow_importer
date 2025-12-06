"""
Workflow Importer Extension for ComfyUI

This extension provides:
1. A backend node to extract workflow metadata from PNG images
2. A frontend UI button and dialog for drag-and-drop workflow import
3. An API endpoint for workflow extraction from uploaded images
"""

import os
import json
import logging
from PIL import Image
from aiohttp import web

import folder_paths
import server

# Point to the web directory for frontend assets
WEB_DIRECTORY = "web"


class ExtractWorkflowFromImage:
    """
    Extracts ComfyUI workflow metadata from PNG images.
    Supports multiple ComfyUI versions and metadata formats.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_path": ("STRING", {"default": "", "multiline": False}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("workflow_json", "prompt_json", "metadata_info")
    FUNCTION = "extract_workflow"
    CATEGORY = "utils"
    OUTPUT_NODE = True
    
    # Known metadata keys used by different ComfyUI versions
    WORKFLOW_KEYS = ["workflow", "Workflow", "comfyui_workflow", "ComfyUI_Workflow"]
    PROMPT_KEYS = ["prompt", "Prompt", "comfyui_prompt", "ComfyUI_Prompt"]
    
    def extract_workflow(self, image_path: str):
        """
        Extract workflow and prompt metadata from a PNG image.
        
        Args:
            image_path: Path to the image file (can be annotated filepath)
            
        Returns:
            Tuple of (workflow_json, prompt_json, metadata_info)
            - workflow_json: The workflow graph as JSON string, or empty string if not found
            - prompt_json: The prompt/API format as JSON string, or empty string if not found  
            - metadata_info: JSON string with extraction status and source info
        """
        result_info = {
            "success": False,
            "source": "unknown",
            "source_version": None,
            "has_workflow": False,
            "has_prompt": False,
            "error": None,
            "raw_keys": []
        }
        
        workflow_json = ""
        prompt_json = ""
        
        try:
            # Handle annotated filepath format
            resolved_path = folder_paths.get_annotated_filepath(image_path)
            if not resolved_path or not os.path.exists(resolved_path):
                # Try as direct path
                if os.path.exists(image_path):
                    resolved_path = image_path
                else:
                    result_info["error"] = f"Image file not found: {image_path}"
                    return ("", "", json.dumps(result_info))
            
            # Open image and extract text chunks
            with Image.open(resolved_path) as img:
                metadata = {}
                
                # Get PNG text chunks
                if hasattr(img, 'text'):
                    metadata = dict(img.text)
                    result_info["raw_keys"] = list(metadata.keys())
                
                # Also check info dict for other formats
                if hasattr(img, 'info'):
                    for key, value in img.info.items():
                        if isinstance(value, str) and key not in metadata:
                            metadata[key] = value
                            if key not in result_info["raw_keys"]:
                                result_info["raw_keys"].append(key)
                
                if not metadata:
                    result_info["error"] = "No metadata found in image"
                    return ("", "", json.dumps(result_info))
                
                # Extract workflow (the graph/nodes structure)
                workflow_data = None
                for key in self.WORKFLOW_KEYS:
                    if key in metadata:
                        try:
                            workflow_data = json.loads(metadata[key])
                            result_info["has_workflow"] = True
                            result_info["source"] = "comfyui"
                            logging.debug(f"Found workflow under key: {key}")
                            break
                        except json.JSONDecodeError:
                            logging.warning(f"Failed to parse workflow from key: {key}")
                            continue
                
                # Extract prompt (the API format / execution format)
                prompt_data = None
                for key in self.PROMPT_KEYS:
                    if key in metadata:
                        try:
                            prompt_data = json.loads(metadata[key])
                            result_info["has_prompt"] = True
                            result_info["source"] = "comfyui"
                            logging.debug(f"Found prompt under key: {key}")
                            break
                        except json.JSONDecodeError:
                            logging.warning(f"Failed to parse prompt from key: {key}")
                            continue
                
                # Try to extract version info from extra_pnginfo or workflow
                if workflow_data and isinstance(workflow_data, dict):
                    # Check for version in workflow
                    if "extra" in workflow_data and isinstance(workflow_data["extra"], dict):
                        version = workflow_data["extra"].get("comfyui_version")
                        if version:
                            result_info["source_version"] = version
                
                # Check for standalone version key
                for version_key in ["comfyui_version", "ComfyUI_version", "version"]:
                    if version_key in metadata and not result_info["source_version"]:
                        result_info["source_version"] = metadata[version_key]
                        break
                
                # Convert to JSON strings
                if workflow_data:
                    workflow_json = json.dumps(workflow_data)
                
                if prompt_data:
                    prompt_json = json.dumps(prompt_data)
                
                # Determine success
                if workflow_data or prompt_data:
                    result_info["success"] = True
                else:
                    # Check for other known formats (A1111, etc.)
                    if "parameters" in metadata or "Parameters" in metadata:
                        result_info["source"] = "automatic1111"
                        result_info["error"] = "Image contains Automatic1111 parameters, not ComfyUI workflow"
                    else:
                        result_info["error"] = "No ComfyUI workflow or prompt found in image metadata"
                
        except Exception as e:
            logging.error(f"Error extracting workflow from image: {e}")
            result_info["error"] = str(e)
        
        return (workflow_json, prompt_json, json.dumps(result_info))


class ExtractWorkflowFromUploadedImage:
    """
    Extracts ComfyUI workflow metadata from an uploaded image.
    Takes the upload response fields (name, subfolder, type) as input.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename": ("STRING", {"default": ""}),
                "subfolder": ("STRING", {"default": ""}),
                "type": ("STRING", {"default": "input"}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("workflow_json", "prompt_json", "metadata_info")
    FUNCTION = "extract_workflow"
    CATEGORY = "utils"
    OUTPUT_NODE = True
    
    def extract_workflow(self, filename: str, subfolder: str, type: str):
        """
        Extract workflow from an uploaded image using upload response fields.
        
        Args:
            filename: The filename from upload response
            subfolder: The subfolder from upload response
            type: The type from upload response (input, temp, output)
            
        Returns:
            Same as ExtractWorkflowFromImage
        """
        # Build the annotated filepath
        if subfolder:
            image_path = f"{subfolder}/{filename}"
        else:
            image_path = filename
            
        if type and type != "input":
            image_path = f"{image_path} [{type}]"
        
        # Delegate to the main extractor
        extractor = ExtractWorkflowFromImage()
        return extractor.extract_workflow(image_path)


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "ExtractWorkflowFromImage": ExtractWorkflowFromImage,
    "ExtractWorkflowFromUploadedImage": ExtractWorkflowFromUploadedImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ExtractWorkflowFromImage": "Extract Workflow From Image",
    "ExtractWorkflowFromUploadedImage": "Extract Workflow From Uploaded Image",
}


# ============================================================================
# API Routes for workflow extraction
# ============================================================================

@server.PromptServer.instance.routes.post("/workflow_importer/extract")
async def extract_workflow_from_image_api(request):
    """
    API endpoint to extract workflow metadata from an image.
    
    Request body (JSON):
        - image_path: Path to the image file (can be annotated filepath, or upload response fields)
        - OR upload response fields: filename, subfolder, type
        
    Returns JSON:
        - success: Boolean indicating if extraction succeeded
        - workflow: The workflow JSON object (or null)
        - prompt: The prompt JSON object (or null)
        - info: Additional metadata about the extraction
        - error: Error message if failed
    """
    try:
        data = await request.json()
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": f"Invalid JSON in request body: {str(e)}",
            "workflow": None,
            "prompt": None,
            "info": None
        }, status=400)
    
    # Determine which format was provided
    image_path = data.get("image_path")
    filename = data.get("filename")
    
    if image_path:
        # Direct path provided
        extractor = ExtractWorkflowFromImage()
        workflow_json, prompt_json, info_json = extractor.extract_workflow(image_path)
    elif filename:
        # Upload response fields provided
        subfolder = data.get("subfolder", "")
        file_type = data.get("type", "input")
        extractor = ExtractWorkflowFromUploadedImage()
        workflow_json, prompt_json, info_json = extractor.extract_workflow(filename, subfolder, file_type)
    else:
        return web.json_response({
            "success": False,
            "error": "Missing required parameter: 'image_path' or 'filename'",
            "workflow": None,
            "prompt": None,
            "info": None
        }, status=400)
    
    # Parse the results
    try:
        info = json.loads(info_json) if info_json else {}
    except json.JSONDecodeError:
        info = {"raw": info_json}
    
    workflow = None
    prompt = None
    
    if workflow_json:
        try:
            workflow = json.loads(workflow_json)
        except json.JSONDecodeError:
            pass
    
    if prompt_json:
        try:
            prompt = json.loads(prompt_json)
        except json.JSONDecodeError:
            pass
    
    success = info.get("success", False)
    error = info.get("error")
    
    return web.json_response({
        "success": success,
        "workflow": workflow,
        "prompt": prompt,
        "info": info,
        "error": error
    })


@server.PromptServer.instance.routes.post("/workflow_importer/extract_from_data")
async def extract_workflow_from_image_data_api(request):
    """
    API endpoint to extract workflow metadata from image data sent in request.
    This allows extracting from images without uploading them first.
    
    Request: multipart/form-data with 'image' field containing the image file
        
    Returns JSON:
        - success: Boolean indicating if extraction succeeded
        - workflow: The workflow JSON object (or null)
        - prompt: The prompt JSON object (or null)
        - info: Additional metadata about the extraction
        - error: Error message if failed
    """
    import tempfile
    import io
    
    result_info = {
        "success": False,
        "source": "unknown",
        "source_version": None,
        "has_workflow": False,
        "has_prompt": False,
        "error": None,
        "raw_keys": []
    }
    
    try:
        reader = await request.multipart()
        field = await reader.next()
        
        if field is None or field.name != 'image':
            return web.json_response({
                "success": False,
                "error": "No 'image' field in multipart request",
                "workflow": None,
                "prompt": None,
                "info": result_info
            }, status=400)
        
        # Read the image data
        image_data = await field.read()
        
        # Extract metadata directly from the image data
        with Image.open(io.BytesIO(image_data)) as img:
            metadata = {}
            
            # Get PNG text chunks
            if hasattr(img, 'text'):
                metadata = dict(img.text)
                result_info["raw_keys"] = list(metadata.keys())
            
            # Also check info dict for other formats
            if hasattr(img, 'info'):
                for key, value in img.info.items():
                    if isinstance(value, str) and key not in metadata:
                        metadata[key] = value
                        if key not in result_info["raw_keys"]:
                            result_info["raw_keys"].append(key)
            
            if not metadata:
                result_info["error"] = "No metadata found in image"
                return web.json_response({
                    "success": False,
                    "error": result_info["error"],
                    "workflow": None,
                    "prompt": None,
                    "info": result_info
                })
            
            # Extract workflow
            workflow = None
            for key in ExtractWorkflowFromImage.WORKFLOW_KEYS:
                if key in metadata:
                    try:
                        workflow = json.loads(metadata[key])
                        result_info["has_workflow"] = True
                        result_info["source"] = "comfyui"
                        break
                    except json.JSONDecodeError:
                        continue
            
            # Extract prompt
            prompt = None
            for key in ExtractWorkflowFromImage.PROMPT_KEYS:
                if key in metadata:
                    try:
                        prompt = json.loads(metadata[key])
                        result_info["has_prompt"] = True
                        result_info["source"] = "comfyui"
                        break
                    except json.JSONDecodeError:
                        continue
            
            # Extract version info
            if workflow and isinstance(workflow, dict):
                if "extra" in workflow and isinstance(workflow["extra"], dict):
                    version = workflow["extra"].get("comfyui_version")
                    if version:
                        result_info["source_version"] = version
            
            for version_key in ["comfyui_version", "ComfyUI_version", "version"]:
                if version_key in metadata and not result_info["source_version"]:
                    result_info["source_version"] = metadata[version_key]
                    break
            
            if workflow or prompt:
                result_info["success"] = True
            else:
                if "parameters" in metadata or "Parameters" in metadata:
                    result_info["source"] = "automatic1111"
                    result_info["error"] = "Image contains Automatic1111 parameters, not ComfyUI workflow"
                else:
                    result_info["error"] = "No ComfyUI workflow or prompt found in image metadata"
            
            return web.json_response({
                "success": result_info["success"],
                "workflow": workflow,
                "prompt": prompt,
                "info": result_info,
                "error": result_info.get("error")
            })
            
    except Exception as e:
        logging.error(f"Error extracting workflow from image data: {e}")
        result_info["error"] = str(e)
        return web.json_response({
            "success": False,
            "error": str(e),
            "workflow": None,
            "prompt": None,
            "info": result_info
        }, status=500)


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
