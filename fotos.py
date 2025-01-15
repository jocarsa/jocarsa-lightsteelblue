import os
import json
import threading
import exifread
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageTk, ImageOps, ImageEnhance

try:
    import numpy as np
except ImportError:
    np = None  # If NumPy is not available, we'll use PIL's ImageEnhance for exposure adjustments.

# ttkbootstrap imports
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap import Style

CONFIG_FILENAME = "config.json"

class EnhancedImageBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("jocarsa | lightsteelblue")

        # -------------------------
        # 1) Load or Create Config
        # -------------------------
        self.config = self.load_config()  # loads user hotkeys from config.json
        # Example structure of self.config:
        # {
        #   "next_photo": "Right",
        #   "prev_photo": "Left",
        #   "save_photo": "z",
        #   "increase_exposure": "KP_Add",
        #   "decrease_exposure": "KP_Subtract"
        # }

        # Variables
        self.folder_path = ""
        self.seleccion_folder = ""
        self.image_list = []
        self.seleccion_list = []
        self.current_index = 0
        self.original_image_pil = None  # Store the original full PIL image
        self.display_image_tk = None    # Store the currently displayed (resized) image as ImageTk
        self.exposure_factor = 1.0      # Default exposure factor
        self.selection_coords = None    # (x1, y1, x2, y2) in image's coordinate space
        self.canvas_rect_id = None      # ID of the rectangle drawn on the canvas

        # For storing thumbnail ImageTk references so they don't get garbage-collected
        self.thumb_images_left = {}
        self.thumb_images_right = {}

        # UI setup
        self.create_widgets()
        self.setup_layout()
        # We will do key-binding AFTER widgets are created
        self.bind_events()

    # -------------------------
    # Load / Save Config
    # -------------------------
    def load_config(self):
        """
        Loads the config from a JSON file, or creates it if not found.
        Returns a dictionary with the hotkeys.
        """
        default_config = {
            "next_photo": "Right",
            "prev_photo": "Left",
            "save_photo": "z",
            "increase_exposure": "KP_Add",
            "decrease_exposure": "KP_Subtract"
        }
        if os.path.exists(CONFIG_FILENAME):
            try:
                with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                # Ensure any missing keys from default are populated
                for k, v in default_config.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
            except Exception as e:
                print(f"Failed to load config.json; using defaults. Error: {e}")
                return default_config
        else:
            # Create a new config file with default values
            self.save_config(default_config)
            return default_config

    def save_config(self, config_dict=None):
        """
        Saves config to config.json. If config_dict is None,
        saves 'self.config' to disk. Otherwise saves config_dict.
        """
        if config_dict is None:
            config_dict = self.config
        try:
            with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving config.json: {e}")

    # -------------------------
    # UI Construction
    # -------------------------
    def create_widgets(self):
        # -- Header (top) with progress bar
        self.header_frame = ttkb.Frame(self.root)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.progress_label = ttkb.Label(self.header_frame, text="Progress:")
        self.progress_label.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttkb.Progressbar(
            self.header_frame,
            variable=self.progress_var,
            maximum=100,
            bootstyle=SUCCESS
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # -- Main container (3 columns)
        self.main_frame = ttkb.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # -- Left column: Treeview for folder images
        self.left_frame = ttkb.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Configure row height so that 64px-high thumbnails are visible
        style = ttkb.Style()
        style.configure("Treeview", rowheight=72)

        self.folder_tree = ttkb.Treeview(self.left_frame, show="tree")
        self.folder_tree.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        self.folder_scroll = ttkb.Scrollbar(self.left_frame, orient="vertical", command=self.folder_tree.yview)
        self.folder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_tree.configure(yscrollcommand=self.folder_scroll.set)

        # -- Center column: Canvas for image display
        self.center_frame = ttkb.Frame(self.main_frame)
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # We'll use a Canvas to display the image and also to draw a selection rectangle
        self.image_canvas = tk.Canvas(self.center_frame, bg="black", highlightthickness=0)
        self.image_canvas.pack(fill=tk.BOTH, expand=True)

        # -- Right column: Treeview for 'seleccion' folder images
        self.right_frame = ttkb.Frame(self.main_frame)
        self.right_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.seleccion_tree = ttkb.Treeview(self.right_frame, show="tree")
        self.seleccion_tree.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        self.seleccion_scroll = ttkb.Scrollbar(self.right_frame, orient="vertical", command=self.seleccion_tree.yview)
        self.seleccion_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.seleccion_tree.configure(yscrollcommand=self.seleccion_scroll.set)

        # -- Bottom status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Welcome to Enhanced Image Browser!")
        self.status_bar = ttkb.Label(self.root, textvariable=self.status_var, anchor=tk.W, bootstyle="dark")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # -- Toolbar (top) for selecting folder, copying images, etc.
        self.toolbar_frame = ttkb.Frame(self.root)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.select_folder_button = ttkb.Button(
            self.toolbar_frame,
            text="Seleccionar carpeta",
            command=self.select_folder,
            bootstyle=INFO
        )
        self.select_folder_button.pack(side=tk.LEFT, padx=5)

        self.copy_image_button = ttkb.Button(
            self.toolbar_frame,
            text="Copiar imagen",
            command=self.copy_image,
            bootstyle=SUCCESS
        )
        self.copy_image_button.pack(side=tk.LEFT, padx=5)

        # Config button
        self.config_button = ttkb.Button(
            self.toolbar_frame,
            text="Config",
            command=self.open_config_window,
            bootstyle=SECONDARY
        )
        self.config_button.pack(side=tk.LEFT, padx=5)

        # -- Footer toolbar (for rename button)
        self.footer_toolbar_frame = ttkb.Frame(self.root)
        self.footer_toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.rename_files_button = ttkb.Button(
            self.footer_toolbar_frame,
            text="Renombrar (EXIF)",
            command=self.rename_all_jpg_by_exif,
            bootstyle=WARNING
        )
        self.rename_files_button.pack(side=tk.LEFT, padx=10)

    def setup_layout(self):
        """ Additional geometry or layout configurations if needed """
        self.root.geometry("1200x700")  # Initial window size

    def bind_events(self):
        """ Bind keyboard and mouse events based on config. """
        # We use the config keys for next/prev/save/increase/decrease
        # but we also need to handle other keys (like ignoring unrecognized).
        self.update_bindings()

        # Capture all other key presses to avoid freezing on unrecognized keys
        self.root.bind("<Key>", self.on_any_key, add="+")  # add="+" so we don't remove other bindings

        # Mouse events for selection rectangle on the canvas
        self.image_canvas.bind("<ButtonPress-1>", self.on_left_button_press)
        self.image_canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.image_canvas.bind("<ButtonRelease-1>", self.on_left_button_release)

        # Treeview selection events
        self.folder_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.seleccion_tree.bind("<<TreeviewSelect>>", self.on_tree_select_seleccion)

        # Handle window resize to update displayed image
        self.center_frame.bind("<Configure>", self.on_center_frame_resize)

    def update_bindings(self):
        """ Unbind old keys, bind new ones according to self.config. """
        # Unbind everything that might have been previously bound:
        for key in ["<Left>", "<Right>", "<Up>", "<Down>",
                    "<KP_Add>", "<KP_Subtract>", "<z>",
                    # Also unbind any current config keys
                    f"<{self.config['next_photo']}>",
                    f"<{self.config['prev_photo']}>",
                    f"<{self.config['save_photo']}>",
                    f"<{self.config['increase_exposure']}>",
                    f"<{self.config['decrease_exposure']}>"]:
            try:
                self.root.unbind(key)
            except:
                pass

        # Now bind the newly configured hotkeys
        self.root.bind(f"<{self.config['prev_photo']}>", self.show_previous_image)
        self.root.bind(f"<{self.config['next_photo']}>", self.show_next_image)
        self.root.bind(f"<{self.config['save_photo']}>", self.copy_image)
        self.root.bind(f"<{self.config['increase_exposure']}>", self.increase_exposure)
        self.root.bind(f"<{self.config['decrease_exposure']}>", self.decrease_exposure)

    # -------------------------
    # Config Window (Modal)
    # -------------------------
    def open_config_window(self):
        """
        Opens a modal (Toplevel) window that allows the user
        to change hotkeys for next/prev/save/increase/decrease.
        """
        config_window = ttkb.Toplevel(self.root)
        config_window.title("Configurar Hotkeys")
        config_window.resizable(False, False)

        # Make it modal
        config_window.grab_set()

        # Current keys from self.config
        row = 0
        # Labels & entry fields
        ttkb.Label(config_window, text="Previous Photo key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        prev_var = tk.StringVar(value=self.config["prev_photo"])
        prev_entry = ttkb.Entry(config_window, textvariable=prev_var)
        prev_entry.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttkb.Label(config_window, text="Next Photo key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        next_var = tk.StringVar(value=self.config["next_photo"])
        next_entry = ttkb.Entry(config_window, textvariable=next_var)
        next_entry.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttkb.Label(config_window, text="Save Photo key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        save_var = tk.StringVar(value=self.config["save_photo"])
        save_entry = ttkb.Entry(config_window, textvariable=save_var)
        save_entry.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttkb.Label(config_window, text="Increase Exposure key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        inc_var = tk.StringVar(value=self.config["increase_exposure"])
        inc_entry = ttkb.Entry(config_window, textvariable=inc_var)
        inc_entry.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttkb.Label(config_window, text="Decrease Exposure key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        dec_var = tk.StringVar(value=self.config["decrease_exposure"])
        dec_entry = ttkb.Entry(config_window, textvariable=dec_var)
        dec_entry.grid(row=row, column=1, padx=5, pady=5)

        # Save/Cancel buttons
        def save_changes():
            """Save the changes to config, update bindings, close window."""
            self.config["prev_photo"] = prev_var.get() or "Left"
            self.config["next_photo"] = next_var.get() or "Right"
            self.config["save_photo"] = save_var.get() or "z"
            self.config["increase_exposure"] = inc_var.get() or "KP_Add"
            self.config["decrease_exposure"] = dec_var.get() or "KP_Subtract"

            self.save_config()  # updates config.json
            self.update_bindings()
            config_window.destroy()

        def cancel():
            config_window.destroy()

        row += 1
        button_frame = ttkb.Frame(config_window)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttkb.Button(button_frame, text="Save", command=save_changes, bootstyle=SUCCESS).pack(side=tk.LEFT, padx=5)
        ttkb.Button(button_frame, text="Cancel", command=cancel, bootstyle=DANGER).pack(side=tk.LEFT, padx=5)

    # -------------------------
    # Generic Key Event Handler
    # -------------------------
    def on_any_key(self, event):
        """
        Prevents the program from hanging if the user presses
        a key that does not have a specific binding.
        """
        recognized_keys = {
            self.config["prev_photo"],
            self.config["next_photo"],
            self.config["save_photo"],
            self.config["increase_exposure"],
            self.config["decrease_exposure"]
        }
        if event.keysym not in recognized_keys:
            self.update_status(f"Ignored unrecognized key: {event.keysym}")

    # -------------------------
    # Folder and File Operations
    # -------------------------
    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path = folder_selected
            self.seleccion_folder = os.path.join(self.folder_path, "seleccion")
            os.makedirs(self.seleccion_folder, exist_ok=True)
            self.load_images()
            self.populate_folder_tree()
            self.populate_seleccion_tree()

            # Start threads to generate thumbnails in background
            self.start_thumbnail_generation(
                folder_path=self.folder_path,
                image_list=self.image_list,
                thumb_dict=self.thumb_images_left,
                tree=self.folder_tree,
                subfolder_name="miniaturas"
            )
            self.start_thumbnail_generation(
                folder_path=self.seleccion_folder,
                image_list=self.seleccion_list,
                thumb_dict=self.thumb_images_right,
                tree=self.seleccion_tree,
                subfolder_name="miniaturas"
            )

            if self.image_list:
                self.current_index = 0
                self.display_image(self.current_index)
                self.update_status(f"Loaded {len(self.image_list)} images from '{self.folder_path}'.")
            else:
                self.update_status("No JPG images found in the selected folder.")
                messagebox.showinfo("No Images", "No JPG images found in the selected folder.")

    def load_images(self):
        """ Load JPG/JPEG files from the selected folder """
        supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG')
        self.image_list = [f for f in os.listdir(self.folder_path) if f.lower().endswith(supported_extensions)]
        self.image_list.sort()

    def populate_folder_tree(self):
        """ Populate the left treeview with the image_list """
        self.folder_tree.delete(*self.folder_tree.get_children())
        for idx, fname in enumerate(self.image_list):
            self.folder_tree.insert("", "end", iid=str(idx), text=fname)

    def populate_seleccion_tree(self):
        """
        Populate the right treeview with files in the seleccion folder.
        We also assign iid=str(idx) so we can directly match items
        in generate_thumbnails via `if str(idx) in tree.get_children():`
        """
        self.seleccion_tree.delete(*self.seleccion_tree.get_children())
        supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG')
        if os.path.exists(self.seleccion_folder):
            self.seleccion_list = sorted(
                [f for f in os.listdir(self.seleccion_folder) if f.lower().endswith(supported_extensions)]
            )
        else:
            self.seleccion_list = []

        for idx, fname in enumerate(self.seleccion_list):
            self.seleccion_tree.insert("", "end", iid=str(idx), text=fname)

    def on_tree_select(self, event):
        """
        Called when the user selects a file in the left treeview.
        We must ensure not to re-display the same index to avoid infinite loops.
        """
        item_id = self.folder_tree.focus()
        if item_id.isdigit():
            selected_index = int(item_id)
            # Only display if it's a different index
            if selected_index != self.current_index:
                self.current_index = selected_index
                self.display_image(self.current_index)

    def on_tree_select_seleccion(self, event):
        """ Handle selection in the 'seleccion' treeview on the right (optional) """
        item_id = self.seleccion_tree.focus()
        if item_id:
            fname = self.seleccion_tree.item(item_id, "text")
            self.update_status(f"'seleccion' folder item selected: {fname}")

    # -------------------------
    # Thumbnails Generation (Background Thread)
    # -------------------------
    def start_thumbnail_generation(self, folder_path, image_list, thumb_dict, tree, subfolder_name="miniaturas"):
        """
        Starts a background thread to generate thumbnails in a subfolder of `folder_path`.
        Once a thumbnail is created, updates the TreeView item with the image.
        """
        thread = threading.Thread(
            target=self.generate_thumbnails,
            args=(folder_path, image_list, thumb_dict, tree, subfolder_name),
            daemon=True
        )
        thread.start()

    def generate_thumbnails(self, folder_path, image_list, thumb_dict, tree, subfolder_name):
        """
        Generates thumbnail images in `folder_path/subfolder_name`.
        Then updates the TreeView items with the thumbnail images.
        """
        if not folder_path:
            return

        thumbs_folder = os.path.join(folder_path, subfolder_name)
        os.makedirs(thumbs_folder, exist_ok=True)

        for idx, filename in enumerate(image_list):
            source_path = os.path.join(folder_path, filename)
            # Build destination path
            base, ext = os.path.splitext(filename)
            thumb_filename = base + "_thumb.jpg"
            thumb_path = os.path.join(thumbs_folder, thumb_filename)

            # If thumbnail does not exist, generate it
            if not os.path.exists(thumb_path):
                try:
                    with Image.open(source_path) as img:
                        img = ImageOps.exif_transpose(img)
                        img.thumbnail((64, 64))  # small thumbnail
                        img.save(thumb_path, format="JPEG", quality=70)
                except Exception as e:
                    print(f"Could not generate thumbnail for {source_path}: {e}")
                    continue

            # Now load the thumbnail into memory and update the dict
            try:
                with Image.open(thumb_path) as thumb_img:
                    tk_thumb = ImageTk.PhotoImage(thumb_img)
                    thumb_dict[filename] = tk_thumb

                # Attempt to update by iid=str(idx) first
                if str(idx) in tree.get_children():
                    tree.item(str(idx), image=tk_thumb)
                else:
                    # fallback: match by the 'text' if we can't find a matching iid
                    for item_id in tree.get_children():
                        if tree.item(item_id, "text") == filename:
                            tree.item(item_id, image=tk_thumb)
                            break
            except Exception as e:
                print(f"Could not load thumbnail image: {thumb_path} => {e}")

    # -------------------------
    # Image Display & Resizing
    # -------------------------
    def display_image(self, index):
        """ Load and display the image at the given index """
        if not self.image_list:
            return

        # Reset exposure factor for each new image
        self.exposure_factor = 1.0

        image_path = os.path.join(self.folder_path, self.image_list[index])
        try:
            # Open the image (store original)
            pil_img = Image.open(image_path)
            pil_img = self.apply_exif_orientation(pil_img)
            self.original_image_pil = pil_img

            # Apply current exposure (which is back to 1.0 for every new image)
            pil_img = self.apply_exposure(pil_img, self.exposure_factor)

            # Resize to fit the center frame's current size
            self.update_image_on_canvas(pil_img)

            # Update the window title and status
            self.root.title(f"jocarsa | lightsteelblue - {self.image_list[self.current_index]}")
            self.update_status(f"Mostrando '{self.image_list[self.current_index]}'.")
            self.highlight_current_tree_item()

            # Update the progress bar to reflect current position (0% -> first, 100% -> last)
            self.update_progress_bar()
        except Exception as e:
            self.update_status(f"Failed to load image: {self.image_list[self.current_index]}")
            messagebox.showerror("Error", f"Failed to load image.\n{e}")

    def apply_exif_orientation(self, image):
        """ Adjust image orientation based on EXIF data """
        try:
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            self.update_status(f"Could not apply EXIF orientation: {e}")
        return image

    def apply_exposure(self, pil_img, factor):
        """
        Adjust brightness (exposure) of the image with a given factor.
        factor = 1.0 means no change, >1.0 brightens, <1.0 darkens.
        """
        if np is not None:
            # Example using NumPy.
            arr = np.array(pil_img, dtype=np.float32)
            arr *= factor
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            return Image.fromarray(arr)
        else:
            # Fallback to PIL's ImageEnhance
            enhancer = ImageEnhance.Brightness(pil_img)
            return enhancer.enhance(factor)

    def update_image_on_canvas(self, pil_img):
        """ Resize the image to fit the center frame, display on the canvas """
        if not pil_img:
            return

        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()

        if canvas_width < 10 or canvas_height < 10:
            # Canvas not yet properly sized
            return

        display_img = pil_img.copy()
        display_img.thumbnail((canvas_width, canvas_height), self.get_resample_filter())
        self.display_image_tk = ImageTk.PhotoImage(display_img)

        # Clear the canvas and redraw
        self.image_canvas.delete("all")
        self.image_canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image=self.display_image_tk,
            anchor=tk.CENTER
        )
        # Reset selection rectangle
        self.selection_coords = None
        self.canvas_rect_id = None

    def get_resample_filter(self):
        # For Pillow >=10.0.0
        try:
            return Image.Resampling.LANCZOS
        except AttributeError:
            # For older Pillow versions
            return Image.ANTIALIAS

    def on_center_frame_resize(self, event):
        """ Called whenever the center frame or canvas is resized. Redraw the current image. """
        if self.original_image_pil:
            pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)
            self.update_image_on_canvas(pil_img)

    # -------------------------
    # Navigation
    # -------------------------
    def show_previous_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index - 1) % len(self.image_list)
            self.display_image(self.current_index)

    def show_next_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index + 1) % len(self.image_list)
            self.display_image(self.current_index)

    def highlight_current_tree_item(self):
        """
        Highlight the current image in the left treeview without
        re-triggering the same selection.
        """
        for item_id in self.folder_tree.get_children():
            self.folder_tree.selection_remove(item_id)
        if str(self.current_index) not in self.folder_tree.selection():
            self.folder_tree.selection_set(str(self.current_index))
        self.folder_tree.see(str(self.current_index))

    # -------------------------
    # Exposure Adjustments
    # -------------------------
    def increase_exposure(self, event=None):
        if self.original_image_pil:
            self.exposure_factor += 0.1
            if self.exposure_factor > 5.0:
                self.exposure_factor = 5.0
            self.update_status(f"Exposure increased to {self.exposure_factor:.2f}")
            self.redisplay_with_exposure()

    def decrease_exposure(self, event=None):
        if self.original_image_pil:
            self.exposure_factor -= 0.1
            if self.exposure_factor < 0.1:
                self.exposure_factor = 0.1
            self.update_status(f"Exposure decreased to {self.exposure_factor:.2f}")
            self.redisplay_with_exposure()

    def redisplay_with_exposure(self):
        """ Re-apply exposure to the original PIL image and update the canvas """
        if self.original_image_pil:
            pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)
            self.update_image_on_canvas(pil_img)

    # -------------------------
    # Selection Rectangle
    # -------------------------
    def on_left_button_press(self, event):
        """ Capture the starting point for the selection rectangle """
        self.start_x = self.image_canvas.canvasx(event.x)
        self.start_y = self.image_canvas.canvasy(event.y)
        self.selection_coords = (self.start_x, self.start_y, self.start_x, self.start_y)

    def on_mouse_move(self, event):
        """ Update the selection rectangle as the mouse moves """
        if not self.selection_coords:
            return
        end_x = self.image_canvas.canvasx(event.x)
        end_y = self.image_canvas.canvasy(event.y)

        self.selection_coords = (self.start_x, self.start_y, end_x, end_y)

        if self.canvas_rect_id:
            self.image_canvas.delete(self.canvas_rect_id)
        self.canvas_rect_id = self.image_canvas.create_rectangle(
            self.start_x, self.start_y, end_x, end_y,
            outline="yellow", width=2
        )

    def on_left_button_release(self, event):
        """ Finalize the selection rectangle """
        if not self.selection_coords:
            return
        end_x = self.image_canvas.canvasx(event.x)
        end_y = self.image_canvas.canvasy(event.y)
        self.selection_coords = (self.start_x, self.start_y, end_x, end_y)

    # -------------------------
    # Copy / Save Image
    # -------------------------
    def copy_image(self, event=None):
        """
        If no selection rectangle is defined (or it's effectively zero-area),
        copy the full image with the current exposure factor.
        Otherwise, crop to the selection rectangle and save that portion.
        """
        if not self.image_list:
            self.update_status("No image to copy.")
            return

        source_image = os.path.join(self.folder_path, self.image_list[self.current_index])
        os.makedirs(self.seleccion_folder, exist_ok=True)

        # Extract EXIF datetime to build destination filename
        new_filename = self.build_destination_filename(source_image)
        destination_image = os.path.join(self.seleccion_folder, new_filename)

        base, ext = os.path.splitext(new_filename)
        counter = 1
        while os.path.exists(destination_image):
            destination_image = os.path.join(self.seleccion_folder, f"{base}_{counter}{ext}")
            counter += 1

        # Load the full original image, apply orientation, apply exposure
        try:
            full_img = Image.open(source_image)
            full_img = self.apply_exif_orientation(full_img)
            full_img = self.apply_exposure(full_img, self.exposure_factor)

            # Check if there's a selection
            cropped_img = self.maybe_crop(full_img)
            # Save final
            cropped_img.save(destination_image, quality=95)
            self.update_status(f"Image copied to '{destination_image}'.")
            self.populate_seleccion_tree()

            # Also generate a thumbnail in seleccion's miniaturas folder (in background)
            self.start_thumbnail_generation(
                folder_path=self.seleccion_folder,
                image_list=[os.path.basename(destination_image)],
                thumb_dict=self.thumb_images_right,
                tree=self.seleccion_tree,
                subfolder_name="miniaturas"
            )

        except Exception as e:
            self.update_status(f"Copy Error: {e}")
            messagebox.showerror("Copy Error", f"Failed to copy image.\n{e}")

    def build_destination_filename(self, source_image):
        """ Build a new filename based on EXIF date if available, else use original name """
        try:
            with open(source_image, 'rb') as img_file:
                tags = exifread.process_file(img_file, stop_tag="EXIF DateTimeOriginal", details=False)
                date_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                if date_tag:
                    date_str = str(date_tag)
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d-%H-%M-%S") + ".jpg"
        except Exception as e:
            self.update_status(f"EXIF Error: {e}. Using original filename.")
        return self.image_list[self.current_index]

    def maybe_crop(self, full_img):
        """
        If the user made a selection rectangle, crop to that rectangle.
        Otherwise, return the full image.
        We need to map the selection rectangle from the *canvas coords* back to the
        original image coords.
        """
        if not self.selection_coords:
            return full_img  # No selection made

        x1, y1, x2, y2 = self.selection_coords
        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()
        orig_width, orig_height = full_img.size

        # Determine scale factor used to fit the image into the canvas
        display_ratio = min(canvas_width / orig_width, canvas_height / orig_height)

        # The displayed image is center-aligned in the canvas
        new_disp_width = int(orig_width * display_ratio)
        new_disp_height = int(orig_height * display_ratio)
        offset_x = (canvas_width - new_disp_width) // 2
        offset_y = (canvas_height - new_disp_height) // 2

        sel_x1 = (x1 - offset_x) / display_ratio
        sel_y1 = (y1 - offset_y) / display_ratio
        sel_x2 = (x2 - offset_x) / display_ratio
        sel_y2 = (y2 - offset_y) / display_ratio

        left = min(sel_x1, sel_x2)
        right = max(sel_x1, sel_x2)
        top = min(sel_y1, sel_y2)
        bottom = max(sel_y1, sel_y2)

        # If selection is too small, return full image
        if (right - left) < 2 or (bottom - top) < 2:
            return full_img

        # Clip to the image boundaries
        left = max(0, left)
        top = max(0, top)
        right = min(orig_width, right)
        bottom = min(orig_height, bottom)

        return full_img.crop((left, top, right, bottom))

    # -------------------------
    # Progress Bar Update
    # -------------------------
    def update_progress_bar(self):
        """
        Maps current_index to a percentage of the list.
        First photo => 0%
        Last photo => 100%
        """
        if len(self.image_list) <= 1:
            progress = 0.0
        else:
            progress = (self.current_index / (len(self.image_list) - 1)) * 100.0
        self.progress_var.set(progress)

    # -------------------------
    # Rename All JPG by EXIF
    # -------------------------
    def rename_all_jpg_by_exif(self):
        """
        Renames all .jpg/.jpeg files in the source folder to 'YYYY-MM-DD-HH-MM-SS.jpg'
        based on EXIF 'DateTimeOriginal'. If no EXIF date is found, the file is skipped.
        After renaming, reload the image list and TreeView.
        """
        if not self.folder_path:
            self.update_status("No folder selected.")
            return

        supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG')
        all_files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(supported_extensions)]

        renamed_count = 0
        for old_name in all_files:
            old_path = os.path.join(self.folder_path, old_name)
            try:
                new_name = self.build_destination_filename_rename(old_path, old_name)
                if new_name != old_name:  # means we found an EXIF date
                    new_path = os.path.join(self.folder_path, new_name)
                    base, ext = os.path.splitext(new_name)
                    # If conflict, append counter
                    counter = 1
                    while os.path.exists(new_path):
                        new_path = os.path.join(self.folder_path, f"{base}_{counter}{ext}")
                        counter += 1

                    os.rename(old_path, new_path)
                    renamed_count += 1
            except Exception as e:
                print(f"Could not rename {old_name}: {e}")

        # Reload images
        self.load_images()
        self.populate_folder_tree()
        self.update_status(f"Renamed {renamed_count} file(s) based on EXIF in '{self.folder_path}'.")

        # Regenerate the left thumbnails in the background
        self.start_thumbnail_generation(
            folder_path=self.folder_path,
            image_list=self.image_list,
            thumb_dict=self.thumb_images_left,
            tree=self.folder_tree,
            subfolder_name="miniaturas"
        )

    def build_destination_filename_rename(self, source_path, original_name):
        """
        Build a new filename using EXIF date if available.
        If no EXIF date is found, return the original_name (skip rename).
        """
        try:
            with open(source_path, 'rb') as img_file:
                tags = exifread.process_file(img_file, stop_tag="EXIF DateTimeOriginal", details=False)
                date_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                if date_tag:
                    date_str = str(date_tag)
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d-%H-%M-%S") + ".jpg"
        except Exception as e:
            print(f"EXIF reading error for {original_name}: {e}")
        return original_name  # no rename if no EXIF date found

    # -------------------------
    # Utilities
    # -------------------------
    def update_status(self, message):
        """ Update the status bar with the given message """
        self.status_var.set(message)
        self.root.update_idletasks()

def main():
    # Instead of tk.Tk(), create a ttkbootstrap-themed window with a dark theme
    # Available dark themes: e.g. "darkly", "cyborg", "superhero", etc.
    app = ttkb.Window(themename="darkly")
    EnhancedImageBrowser(app)
    app.mainloop()

if __name__ == "__main__":
    main()
