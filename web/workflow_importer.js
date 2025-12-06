/**
 * Workflow Importer Extension for ComfyUI
 * 
 * Adds a toolbar button and dialog for importing workflows from images
 * with embedded ComfyUI metadata.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * Dialog for importing workflows from images
 */
class WorkflowImportDialog {
    constructor() {
        this.isOpen = false;
        this.isProcessing = false;
        this.overlay = null;
        this.dialog = null;
        this.statusEl = null;
        this.init();
    }

    init() {
        // Add styles first
        this.addStyles();
        
        // Create overlay (backdrop)
        this.overlay = document.createElement("div");
        this.overlay.id = "workflow-import-overlay";
        this.overlay.addEventListener("click", (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
        
        // Create dialog container
        this.dialog = document.createElement("div");
        this.dialog.id = "workflow-import-dialog";
        
        this.overlay.appendChild(this.dialog);
        document.body.appendChild(this.overlay);
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.show();
        }
    }

    close() {
        this.isOpen = false;
        this.overlay.style.display = "none";
        this.isProcessing = false;
    }

    show() {
        this.isOpen = true;
        this.isProcessing = false;
        
        // Build dialog content
        this.dialog.innerHTML = "";
        
        // Header
        const header = document.createElement("div");
        header.style.cssText = "display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;";
        
        const title = document.createElement("h3");
        title.textContent = "Import Workflow from Image";
        title.style.cssText = "margin: 0; color: #fff; fontSize: 18px;";
        
        const closeBtn = document.createElement("button");
        closeBtn.textContent = "✕";
        closeBtn.onclick = () => this.close();
        closeBtn.style.cssText = "background: none; border: none; font-size: 24px; cursor: pointer; color: #aaa; padding: 0; line-height: 1;";
        closeBtn.onmouseover = () => closeBtn.style.color = "#fff";
        closeBtn.onmouseout = () => closeBtn.style.color = "#aaa";
        
        header.appendChild(title);
        header.appendChild(closeBtn);
        
        // Drop zone
        const dropZone = this.createDropZone();
        
        // Status area
        this.statusEl = document.createElement("div");
        this.statusEl.id = "import-status";
        this.statusEl.style.cssText = "min-height: 40px; padding: 10px; background-color: #2a2a2a; border-radius: 4px; font-size: 13px; display: none; margin-top: 15px; color: #ccc;";
        
        // Instructions
        const instructions = document.createElement("div");
        instructions.style.cssText = "font-size: 12px; color: #888; text-align: center; margin-top: 15px;";
        instructions.innerHTML = `
            <p style="margin: 0 0 5px 0;">Drop PNG images containing ComfyUI workflow metadata.</p>
            <p style="margin: 0;">Each image will open in a new workflow tab.</p>
            <p style="margin: 10px 0 0 0; color: #666;">Keyboard shortcut: Ctrl+Shift+I</p>
        `;
        
        // Append all elements
        this.dialog.appendChild(header);
        this.dialog.appendChild(dropZone);
        this.dialog.appendChild(this.statusEl);
        this.dialog.appendChild(instructions);
        
        // Show the overlay
        this.overlay.style.display = "flex";
    }

    createDropZone() {
        const dropZone = document.createElement("div");
        dropZone.id = "drop-zone";
        dropZone.style.cssText = "border: 2px dashed #555; border-radius: 8px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all 0.2s ease; background-color: #2a2a2a;";
        
        const icon = document.createElement("div");
        icon.style.cssText = "font-size: 48px; margin-bottom: 10px;";
        icon.textContent = "📁";
        
        const mainText = document.createElement("div");
        mainText.textContent = "Drag & drop images here";
        mainText.style.cssText = "font-size: 16px; margin-bottom: 8px; color: #ddd;";
        
        const subText = document.createElement("div");
        subText.textContent = "or click to select files";
        subText.style.cssText = "font-size: 13px; color: #888;";
        
        const fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.accept = "image/png,image/webp,image/jpeg";
        fileInput.multiple = true;
        fileInput.style.display = "none";
        fileInput.addEventListener("change", (e) => this.handleFileSelect(e.target.files));
        
        dropZone.appendChild(icon);
        dropZone.appendChild(mainText);
        dropZone.appendChild(subText);
        dropZone.appendChild(fileInput);

        // Click to open file dialog
        dropZone.addEventListener("click", (e) => {
            if (e.target.tagName !== "INPUT") {
                fileInput.click();
            }
        });

        // Hover effects
        dropZone.addEventListener("mouseenter", () => {
            dropZone.style.borderColor = "#888";
            dropZone.style.backgroundColor = "#333";
        });
        dropZone.addEventListener("mouseleave", () => {
            dropZone.style.borderColor = "#555";
            dropZone.style.backgroundColor = "#2a2a2a";
        });

        // Drag and drop handlers
        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.style.borderColor = "#4a9eff";
            dropZone.style.backgroundColor = "#333";
        });

        dropZone.addEventListener("dragleave", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.style.borderColor = "#555";
            dropZone.style.backgroundColor = "#2a2a2a";
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.style.borderColor = "#555";
            dropZone.style.backgroundColor = "#2a2a2a";
            
            const files = e.dataTransfer.files;
            this.handleFileSelect(files);
        });

        return dropZone;
    }

    async handleFileSelect(files) {
        if (!files || files.length === 0) return;
        if (this.isProcessing) {
            this.showStatus("Please wait for current import to complete...", "warning");
            return;
        }

        const imageFiles = Array.from(files).filter(f => 
            f.type.startsWith("image/")
        );

        if (imageFiles.length === 0) {
            this.showStatus("No valid image files selected.", "error");
            return;
        }

        this.isProcessing = true;
        this.showStatus(`Processing ${imageFiles.length} image(s)...`, "info");

        let successCount = 0;
        let failCount = 0;
        const errors = [];

        for (const file of imageFiles) {
            try {
                this.showStatus(`Processing: ${file.name}...`, "info");
                const result = await this.processImageFile(file);
                
                if (result.success) {
                    successCount++;
                } else {
                    failCount++;
                    errors.push(`${file.name}: ${result.error}`);
                }
            } catch (err) {
                failCount++;
                errors.push(`${file.name}: ${err.message}`);
                console.error("Error processing file:", file.name, err);
            }
        }

        this.isProcessing = false;

        // Show final status
        if (successCount > 0 && failCount === 0) {
            this.showStatus(`✓ Successfully imported ${successCount} workflow(s)!`, "success");
            // Auto-close after success
            setTimeout(() => this.close(), 1500);
        } else if (successCount > 0 && failCount > 0) {
            this.showStatus(
                `Imported ${successCount} workflow(s), ${failCount} failed:\n${errors.join("\n")}`,
                "warning"
            );
        } else {
            this.showStatus(
                `Failed to import workflows:\n${errors.join("\n")}`,
                "error"
            );
        }
    }

    async processImageFile(file) {
        // Extract workflow directly from image data (no upload needed)
        const extractResult = await this.extractWorkflowFromData(file);

        if (!extractResult.success) {
            return { success: false, error: extractResult.error };
        }

        // Load the workflow into a new tab
        const loadResult = await this.loadWorkflow(
            extractResult.workflow,
            extractResult.prompt,
            file.name
        );

        return loadResult;
    }

    /**
     * Extract workflow directly from image file data without uploading
     */
    async extractWorkflowFromData(file) {
        try {
            const formData = new FormData();
            formData.append("image", file);

            // Call our extraction API endpoint that accepts image data directly
            const response = await api.fetchApi("/workflow_importer/extract_from_data", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Extraction failed: ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                return { 
                    success: false, 
                    error: result.error || "No workflow found in image" 
                };
            }

            return {
                success: true,
                workflow: result.workflow,
                prompt: result.prompt,
                info: result.info
            };
        } catch (err) {
            return { success: false, error: `Extraction failed: ${err.message}` };
        }
    }

    async loadWorkflow(workflowJson, promptJson, filename) {
        try {
            let graphData = null;

            // Prefer workflow over prompt as it contains the full graph
            if (workflowJson) {
                graphData = typeof workflowJson === "string" 
                    ? JSON.parse(workflowJson) 
                    : workflowJson;
            } else if (promptJson) {
                // Prompt format is API format, may need conversion
                graphData = typeof promptJson === "string"
                    ? JSON.parse(promptJson)
                    : promptJson;
            }

            if (!graphData) {
                return { success: false, error: "No valid workflow data found" };
            }

            // Generate a clean name for the tab
            const tabName = filename.replace(/\.[^/.]+$/, "") || "Imported Workflow";

            // Load the graph into ComfyUI
            // This uses the app's built-in graph loading functionality
            await app.loadGraphData(graphData, true, true, tabName);

            return { success: true };
        } catch (err) {
            return { success: false, error: `Failed to load workflow: ${err.message}` };
        }
    }

    showStatus(message, type = "info") {
        if (!this.statusEl) return;

        this.statusEl.style.display = "block";
        this.statusEl.textContent = message;
        this.statusEl.style.whiteSpace = "pre-wrap";

        // Color based on type
        const colors = {
            info: "#ccc",
            success: "#4CAF50",
            warning: "#FF9800",
            error: "#F44336"
        };
        this.statusEl.style.color = colors[type] || colors.info;
    }

    addStyles() {
        if (document.getElementById("workflow-importer-styles")) return;

        const style = document.createElement("style");
        style.id = "workflow-importer-styles";
        style.textContent = `
            #workflow-import-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.6);
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 10000;
            }
            
            #workflow-import-dialog {
                background: #1e1e1e;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                padding: 20px;
                width: 500px;
                max-width: 90vw;
                border: 1px solid #444;
            }

            #drop-zone:hover {
                border-color: #888 !important;
            }
        `;
        document.head.appendChild(style);
    }
}

/**
 * Main extension registration
 */
app.registerExtension({
    name: "Comfy.WorkflowImporter",
    
    async setup() {
        // Create the import dialog instance
        const importDialog = new WorkflowImportDialog();

        // Wait for menu to be ready and add button
        await this.addMenuButton(importDialog);
        
        // Also add keyboard shortcut (Ctrl/Cmd + Shift + I)
        document.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "I") {
                e.preventDefault();
                importDialog.toggle();
            }
        });

        console.log("[Workflow Importer] Extension loaded");
    },

    async addMenuButton(importDialog) {
        // Try new-style menu first (ComfyUI 0.2.0+)
        try {
            const { ComfyButtonGroup } = await import("../../scripts/ui/components/buttonGroup.js");
            const { ComfyButton } = await import("../../scripts/ui/components/button.js");

            // Wait for app.menu to be available
            const waitForMenu = () => {
                return new Promise((resolve) => {
                    const check = () => {
                        if (app.menu?.settingsGroup) {
                            resolve();
                        } else {
                            setTimeout(check, 100);
                        }
                    };
                    check();
                });
            };

            await waitForMenu();

            // Create import button for new-style menu
            const importButton = new ComfyButton({
                icon: "file-import",
                action: () => importDialog.toggle(),
                tooltip: "Import Workflow from Image (Ctrl+Shift+I)",
                content: "Import"
            });

            // Add to menu before settings
            const importGroup = new ComfyButtonGroup(importButton);
            app.menu.settingsGroup.element.before(importGroup.element);
            
            console.log("[Workflow Importer] Added to new-style menu");
            
        } catch (err) {
            console.log("[Workflow Importer] New-style menu not available, using legacy menu");
            this.addLegacyMenuButton(importDialog);
        }
    },

    addLegacyMenuButton(importDialog) {
        // Find the legacy menu container
        const menuContainer = document.querySelector(".comfy-menu");
        if (!menuContainer) {
            // Try again after a short delay
            setTimeout(() => this.addLegacyMenuButton(importDialog), 500);
            return;
        }

        // Check if button already exists
        if (document.getElementById("workflow-import-button")) return;

        // Create the button
        const importButton = document.createElement("button");
        importButton.id = "workflow-import-button";
        importButton.textContent = "Import";
        importButton.title = "Import Workflow from Image (Ctrl+Shift+I)";
        importButton.onclick = () => importDialog.toggle();
        
        // Style to match other buttons
        importButton.style.cssText = `
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 4px 8px;
            cursor: pointer;
            border-radius: 4px;
        `;

        // Find Manager button and insert after it, or append to menu
        const managerButton = Array.from(menuContainer.querySelectorAll("button"))
            .find(b => b.textContent.includes("Manager"));
        
        if (managerButton) {
            managerButton.after(importButton);
        } else {
            menuContainer.appendChild(importButton);
        }
    }
});
