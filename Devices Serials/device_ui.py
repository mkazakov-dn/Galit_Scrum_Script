#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import threading
from queue import Queue

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DeviceData:
    """Data model for a device and its components"""
    serial: str
    status: str
    system_output: Optional[str] = None
    interfaces: Dict[str, str] = None
    fabric_interfaces: Dict[str, str] = None
    backplane_output: Optional[str] = None
    power_output: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceData':
        return cls(
            serial=data.get('serial'),
            status=data.get('status'),
            system_output=data.get('system_output'),
            interfaces=data.get('interfaces', {}),
            fabric_interfaces=data.get('fabric_interfaces', {}),
            backplane_output=data.get('backplane_output'),
            power_output=data.get('power_output'),
            error_message=data.get('error_message')
        )

class DeviceModel:
    """Model layer - handles data loading and management"""
    def __init__(self):
        self._devices: Dict[str, DeviceData] = {}
        self._loading = False
        self._executor = ThreadPoolExecutor(max_workers=1)
        logger.debug("DeviceModel initialized")

    def is_loading(self) -> bool:
        return self._loading

    def load_data(self, json_path: str, callback: callable) -> None:
        """Load device data from JSON file in a thread"""
        def _load():
            try:
                logger.debug(f"Starting to load data from {json_path}")
                self._loading = True
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"JSON loaded successfully, found {len(data)} devices")
                
                self._devices = {
                    device['serial']: DeviceData.from_dict(device)
                    for device in data
                }
                logger.debug(f"Processed {len(self._devices)} devices")
                callback(None)  # Success
            except Exception as e:
                logger.error(f"Error loading data: {e}")
                callback(e)
            finally:
                self._loading = False

        self._executor.submit(_load)

    def get_device(self, serial: str) -> Optional[DeviceData]:
        device = self._devices.get(serial)
        logger.debug(f"Retrieved device {serial}: {'Found' if device else 'Not found'}")
        return device

    def get_all_serials(self) -> List[str]:
        serials = list(self._devices.keys())
        logger.debug(f"Retrieved all serials: {serials}")
        return serials

class DeviceTreeBuilder:
    """Controller layer - manages tree construction and updates"""
    def __init__(self, tree: ttk.Treeview, model: DeviceModel):
        self.tree = tree
        self.model = model
        self._setup_tree()

    def _setup_tree(self) -> None:
        """Configure the treeview columns and bindings"""
        # Configure style for larger rows
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)  # Slightly reduced height since we don't need double-click area
        style.configure("Treeview", font=('TkDefaultFont', 10))
        style.configure("Treeview", padding=5)
        
        # Configure selection colors for better visibility
        style.map("Treeview",
            foreground=[("selected", "#000000")],
            background=[("selected", "#CCE8FF")]  # Lighter blue for selection
        )

        # Configure columns
        self.tree["columns"] = ("status",)
        self.tree.column("#0", width=400, minwidth=200)  # Made wider
        self.tree.column("status", width=100, minwidth=100)
        
        # Configure headings with padding
        self.tree.heading("#0", text="Device/Command", anchor=tk.W)
        self.tree.heading("status", text="Status", anchor=tk.W)
        
        # Configure tags for different item types
        self.tree.tag_configure("device", font=('TkDefaultFont', 11, 'bold'))
        self.tree.tag_configure("command", font=('TkDefaultFont', 10))
        self.tree.tag_configure("interface", font=('TkDefaultFont', 10))

    def build_device_node(self, serial: str) -> None:
        """Build a top-level device node"""
        device = self.model.get_device(serial)
        if not device:
            logger.warning(f"Device {serial} not found in model")
            return

        # Create device node with tag for styling
        node_id = self.tree.insert(
            "", "end",
            text=serial,
            values=(f"✔ done" if device.status == "success" else f"✖ error: {device.error_message}",),
            tags=("device",)  # Apply device styling
        )

        if device.status == "success":
            # Add placeholder for lazy loading
            self.tree.insert(node_id, "end", text="Loading...")

    def expand_device_node(self, node_id: str) -> None:
        """Lazily load device node contents when expanded"""
        # Get the device serial from the node text
        serial = self.tree.item(node_id)["text"]
        device = self.model.get_device(serial)
        if not device or device.status != "success":
            return

        # Remove placeholder
        for child in self.tree.get_children(node_id):
            self.tree.delete(child)

        # Add command nodes
        self._add_command_node(node_id, "show system")
        
        # Add transceiver nodes with tag
        transceiver_node = self.tree.insert(node_id, "end", 
                                          text="interface transceiver",
                                          tags=("command",))
        
        # Add interface nodes with tag
        for interface in device.interfaces.keys():
            self.tree.insert(transceiver_node, "end", 
                           text=interface,
                           tags=("interface",))

        # Add fabric transceiver nodes
        fabric_node = self.tree.insert(node_id, "end", 
                                     text="interfaces fabric transceiver",
                                     tags=("command",))
        
        # Add fabric interface nodes with tag
        for interface in device.fabric_interfaces.keys():
            self.tree.insert(fabric_node, "end", 
                           text=interface,
                           tags=("interface",))

        # Add other command nodes
        self._add_command_node(node_id, "show system backplane")
        self._add_command_node(node_id, "show system hardware power")

    def _add_command_node(self, parent_id: str, command: str) -> None:
        """Add a command node to the tree"""
        self.tree.insert(parent_id, "end", 
                        text=command,
                        tags=("command",))  # Apply command styling

class OutputWindow:
    """View layer - handles output display windows"""
    def __init__(self, parent: tk.Tk, title: str, content: str):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        
        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Set minimum size
        self.window.minsize(400, 300)
        
        self._setup_window(content)

    def _setup_window(self, content: str) -> None:
        """Set up the output window with text and scrollbar"""
        # Create frame for better layout
        frame = ttk.Frame(self.window)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create text widget with better styling
        text = tk.Text(frame, wrap=tk.WORD, font=('TkDefaultFont', 10))
        text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=scrollbar.set)
        
        # Insert content
        text.insert("1.0", content)
        text.configure(state="disabled")
        
        # Add close button
        close_button = ttk.Button(self.window, text="Close", command=self.window.destroy)
        close_button.pack(pady=5)
        
        # Bind Escape key to close
        self.window.bind('<Escape>', lambda e: self.window.destroy())

class DeviceViewer(tk.Tk):
    """Main application window"""
    def __init__(self, json_path: Optional[str] = None):
        super().__init__()
        self.title("Device Viewer")
        self.geometry("900x600")  # Made wider to accommodate button
        logger.debug("DeviceViewer initialized")

        # Create main frame with padding
        self.main_frame = ttk.Frame(self, padding="5")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create left frame for tree
        tree_frame = ttk.Frame(self.main_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create right frame for buttons
        button_frame = ttk.Frame(self.main_frame, padding="5")
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Initialize components
        self.model = DeviceModel()
        self.tree = ttk.Treeview(tree_frame)
        
        # Add scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout for tree and scrollbars
        self.tree.grid(column=0, row=0, sticky='nsew')
        vsb.grid(column=1, row=0, sticky='ns')
        hsb.grid(column=0, row=1, sticky='ew')
        
        # Configure grid weights
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        self.builder = DeviceTreeBuilder(self.tree, self.model)

        # Add Expand button
        style = ttk.Style()
        style.configure("Action.TButton", padding=5)
        
        self.expand_button = ttk.Button(
            button_frame,
            text="Expand",
            command=self._handle_expand,
            style="Action.TButton",
            width=15  # Make button wider
        )
        self.expand_button.pack(pady=5)

        # Set up event bindings
        self._setup_bindings()

        # Load data if path provided
        if json_path:
            self.load_data(json_path)

    def _setup_bindings(self) -> None:
        """Set up tree event bindings"""
        # Single click for selection
        self.tree.bind("<Button-1>", self._on_single_click)
        
        # Tree open/close events
        self.tree.bind("<<TreeviewOpen>>", self._on_node_open)
        
        # Selection changed event
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        
        logger.debug("All event bindings set up")

    def _on_selection_changed(self, event: tk.Event) -> None:
        """Handle tree selection changes"""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            item = self.tree.item(item_id)
            parent_id = self.tree.parent(item_id)
            
            # Only enable expand button for items with potential content
            if parent_id and item["text"] not in ["interface transceiver", "interfaces fabric transceiver"]:
                self.expand_button.configure(state="normal")
            else:
                self.expand_button.configure(state="disabled")
        else:
            self.expand_button.configure(state="disabled")

    def _handle_expand(self) -> None:
        """Handle Expand button click"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item_id = selection[0]
        try:
            logger.debug(f"Expand button clicked for item: {item_id}")
            self._handle_item_open(item_id)
        except Exception as e:
            logger.error(f"Error handling expand: {e}")
            self._show_error("Error", f"Could not expand item: {e}")

    def _on_single_click(self, event: tk.Event) -> None:
        """Handle single click for selection"""
        try:
            item_id = self.tree.identify_row(event.y)
            logger.debug(f"Single click on item: {item_id}")
            
            if item_id:
                # Clear previous selection and select new item
                self.tree.selection_set(item_id)
                
                # Get item info for logging
                item_text = self.tree.item(item_id)["text"]
                logger.debug(f"Selected item: {item_text}")
        except Exception as e:
            logger.error(f"Error in single click handler: {e}")

    def _on_node_open(self, event: tk.Event) -> None:
        """Handle node expansion"""
        try:
            selection = self.tree.selection()
            if selection:
                node_id = selection[0]
                # Only expand if this is a device node
                if not self.tree.parent(node_id):
                    self.builder.expand_device_node(node_id)
        except Exception as e:
            logger.error(f"Error expanding node: {e}")
            self._show_error("Error expanding node", str(e))

    def _get_command_output(self, device_serial: str, command_text: str) -> Optional[str]:
        """Get the output for a specific command from the loaded data"""
        logger.debug(f"Getting command output for {device_serial}: {command_text}")
        
        device = self.model.get_device(device_serial)
        if not device:
            logger.debug(f"Device {device_serial} not found")
            return None
        
        if device.status != "success":
            logger.debug(f"Device {device_serial} status is not success: {device.status}")
            return None

        output = None
        if command_text == "show system":
            output = device.system_output
        elif command_text == "show system backplane":
            output = device.backplane_output
        elif command_text == "show system hardware power":
            output = device.power_output
        elif command_text == "interface transceiver":
            logger.debug("Parent node selected, no output")
            return None
        elif command_text == "interfaces fabric transceiver":
            logger.debug("Parent node selected, no output")
            return None
        else:
            # Check if it's an interface
            if command_text in device.interfaces:
                output = device.interfaces[command_text]
            elif command_text in device.fabric_interfaces:
                output = device.fabric_interfaces[command_text]

        logger.debug(f"Output found: {'Yes' if output else 'No'}")
        return output

    def _show_error(self, title: str, message: str) -> None:
        """Show an error dialog"""
        messagebox.showerror(title, message)

    def load_data(self, json_path: str) -> None:
        """Initialize data loading"""
        try:
            logger.debug(f"Starting data load from {json_path}")
            # Show loading message
            loading_id = self.tree.insert("", "end", text="Loading data...", values=("Please wait",))
            self.update()

            def on_load_complete(error):
                logger.debug("Data load completed")
                # Remove loading message
                self.tree.delete(loading_id)
                if error:
                    logger.error(f"Load error: {error}")
                    self._show_error("Loading Error", str(error))
                else:
                    logger.debug("Building initial tree")
                    self._build_initial_tree()

            # Start loading data
            self.model.load_data(json_path, on_load_complete)
        except Exception as e:
            logger.error(f"Error starting data load: {e}")
            self._show_error("Error", str(e))

    def _build_initial_tree(self) -> None:
        """Build the initial tree with device nodes"""
        try:
            for serial in self.model.get_all_serials():
                self.builder.build_device_node(serial)
        except Exception as e:
            logger.error(f"Error building tree: {e}")
            self._show_error("Error", str(e))

    def _handle_item_open(self, item_id: str) -> None:
        """Handle opening an item (shared between button and other triggers)"""
        try:
            logger.debug(f"Handling open for item: {item_id}")
            # Get item details
            item_text = self.tree.item(item_id)["text"]
            parent_id = self.tree.parent(item_id)
            logger.debug(f"Item text: {item_text}, Parent: {parent_id}")
            if not parent_id:
                logger.debug("No parent found - ignoring")
                return
            # Get device ID (might be parent or grandparent)
            device_id = parent_id
            if self.tree.parent(parent_id):
                device_id = self.tree.parent(parent_id)
                logger.debug(f"Using grandparent as device_id: {device_id}")
            device_serial = self.tree.item(device_id)["text"]
            logger.debug(f"Found device serial: {device_serial}")
            # Skip if this is a category node
            if item_text in ["interface transceiver", "interfaces fabric transceiver"]:
                logger.debug("Category node - ignoring")
                return
            # Get content
            content = self._get_command_output(device_serial, item_text)
            if content:
                logger.debug(f"Opening window with content (length: {len(content)})")
                try:
                    window = OutputWindow(self, f"{device_serial} - {item_text}", content)
                    window.window.focus_force()
                    x = self.winfo_x() + 50
                    y = self.winfo_y() + 50
                    window.window.geometry(f"+{x}+{y}")
                    logger.debug("Window created and positioned successfully")
                except Exception as e:
                    logger.error(f"Error creating window: {e}")
                    self._show_error("Error", f"Could not create window: {e}")
            else:
                logger.debug("No content found for item")
        except Exception as e:
            logger.error(f"Error handling item open: {e}")
            self._show_error("Error", f"Could not open item: {e}")

def build_tree(json_path: str) -> ttk.Treeview:
    """Create and return a populated treeview for testing"""
    root = tk.Tk()
    model = DeviceModel()
    tree = ttk.Treeview(root)
    builder = DeviceTreeBuilder(tree, model)
    
    # Load data synchronously for testing
    with open(json_path, 'r') as f:
        data = json.load(f)
        for device in data:
            model._devices[device['serial']] = DeviceData.from_dict(device)
    
    # Build tree
    for serial in model.get_all_serials():
        builder.build_device_node(serial)
    
    return tree

def main():
    app = DeviceViewer()
    app.load_data("devices_data.json")
    app.mainloop()

if __name__ == "__main__":
    main() 