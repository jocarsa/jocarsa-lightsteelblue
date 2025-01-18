import os
import json
import threading
import exifread
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageTk, ImageOps, ImageEnhance

# Attempt NumPy import
try:
    import numpy as np
except ImportError:
    np = None  # fallback if not available

# Attempt OpenCV import
try:
    import cv2
except ImportError:
    cv2 = None  # fallback if not available

import colorsys

# Import denoise from external file
import denoise  # Make sure denoise.py is in the same directory

# ttkbootstrap imports
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap import Style

CONFIG_FILENAME = "config.json"
SETTINGS_FILENAME = "settings.json"

class EnhancedImageBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("jocarsa | lightsteelblue")

        # 1) Load or Create Config
        self.config = self.load_config()

        # 2) Load or Create Settings
        self.settings = self.load_settings()

        # Variables
        self.folder_path = ""
        self.seleccion_folder = ""
        self.image_list = []
        self.seleccion_list = []
        self.current_index = 0
        self.original_image_pil = None  
        self.display_image_tk = None    
        self.exposure_factor = 1.0      
        self.selection_coords = None    
        self.canvas_rect_id = None      

        # Store thumbnail references
        self.thumb_images_left = {}
        self.thumb_images_right = {}

        # Denoise parameters
        self.enable_denoise_var = tk.BooleanVar(value=False)
        self.denoise_radius_var = tk.IntVar(value=2)
        self.denoise_tol_var = tk.IntVar(value=10)
        self.denoise_mix_var = tk.DoubleVar(value=1.0)

        # Zoom/pan states
        self.zoom_scale = 1.0   # Current zoom factor
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.dragging = False
        self.auto_fit = True  # Flag to control auto-fitting

        # Create UI
        self.create_widgets()
        self.setup_layout()
        self.bind_events()

        # Show floating welcome window **after** widgets are created
        self.show_welcome_window()

    # -------------------------
    # Welcome Window
    # -------------------------
    def show_welcome_window(self):
        """Create and display the centered welcome window with logo and application name."""
        welcome = tk.Toplevel(self.root)
        welcome.title("Bienvenido")
        
        # Define window size
        width = 600
        height = 400

        # Prevent window from being resizable
        welcome.resizable(False, False)
        
        # Center the window on the screen
        welcome.update_idletasks()  # Ensure the window dimensions are calculated
        screen_width = welcome.winfo_screenwidth()
        screen_height = welcome.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        welcome.geometry(f"{width}x{height}+{x}+{y}")
        
        # Ensure the welcome window stays on top
        welcome.attributes("-topmost", True)
        
        # Create a frame to hold the content
        content_frame = ttkb.Frame(welcome)
        content_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        # Load and display the logo image
        try:
            logo_path = "lightsteelbue.png"
            if not os.path.exists(logo_path):
                raise FileNotFoundError(f"Logo image '{logo_path}' not found.")
            
            logo_img = Image.open(logo_path)
            # Resize the logo to fit within the window (e.g., 150x150 pixels)
            logo_img = logo_img.resize((300, 300), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            
            logo_label = ttkb.Label(content_frame, image=self.logo_photo)
            logo_label.pack(pady=(0, 10))
        except Exception as e:
            self.update_status(f"Could not load logo image: {e}")
            # If the image fails to load, skip displaying it
            self.logo_photo = None
        
        # Display the application name
        app_name_label = ttkb.Label(
            content_frame, 
            text="jocarsa | lightsteelblue", 
            font=("Helvetica", 16, "bold")
        )
        app_name_label.pack(pady=(0, 20))
        
        # Add an "Aceptar" button to close the welcome window
        accept_button = ttkb.Button(
            content_frame, 
            text="Aceptar", 
            command=welcome.destroy,
            bootstyle=SUCCESS
        )
        accept_button.pack()

    # -------------------------
    # Load / Save Config
    # -------------------------
    def load_config(self):
        default_config = {
            "next_photo": "Right",
            "prev_photo": "Left",
            "save_photo": "z",
            "increase_exposure": "KP_Add",
            "decrease_exposure": "KP_Subtract",
            "delete_photo": "q"  # Added default delete shortcut
        }
        if os.path.exists(CONFIG_FILENAME):
            try:
                with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                for k, v in default_config.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
            except Exception as e:
                print(f"Failed to load config.json; using defaults. Error: {e}")
                return default_config
        else:
            self.save_config(default_config)
            return default_config

    def save_config(self, config_dict=None):
        if config_dict is None:
            config_dict = self.config
        try:
            with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving config.json: {e}")

    # -------------------------
    # Load / Save Settings
    # -------------------------
    def load_settings(self):
        default_settings = {
            "last_folder": ""
        }
        if os.path.exists(SETTINGS_FILENAME):
            try:
                with open(SETTINGS_FILENAME, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                for k, v in default_settings.items():
                    if k not in settings:
                        settings[k] = v
                return settings
            except Exception as e:
                print(f"Failed to load settings.json; using defaults. Error: {e}")
                return default_settings
        else:
            self.save_settings(default_settings)
            return default_settings

    def save_settings(self, settings_dict=None):
        if settings_dict is None:
            settings_dict = self.settings
        try:
            with open(SETTINGS_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving settings.json: {e}")

    # -------------------------
    # UI Construction
    # -------------------------
    def create_widgets(self):
        # Create Menu
        self.create_menu()

        # Header (top) with progress bar
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

        # Main container (3 columns)
        self.main_frame = ttkb.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column: Treeview for folder images
        self.left_frame = ttkb.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        style = ttkb.Style()
        style.configure("Treeview", rowheight=72)

        self.folder_tree = ttkb.Treeview(self.left_frame, show="tree")
        self.folder_tree.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        self.folder_scroll = ttkb.Scrollbar(self.left_frame, orient="vertical", command=self.folder_tree.yview)
        self.folder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_tree.configure(yscrollcommand=self.folder_scroll.set)

        # Center column: Canvas for image display
        self.center_frame = ttkb.Frame(self.main_frame)
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image_canvas = tk.Canvas(self.center_frame, bg="black", highlightthickness=0)
        self.image_canvas.pack(fill=tk.BOTH, expand=True)

        # Right column: Treeview for 'seleccion' images
        self.right_frame = ttkb.Frame(self.main_frame)
        self.right_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.seleccion_tree = ttkb.Treeview(self.right_frame, show="tree")
        self.seleccion_tree.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        self.seleccion_scroll = ttkb.Scrollbar(self.right_frame, orient="vertical", command=self.seleccion_tree.yview)
        self.seleccion_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.seleccion_tree.configure(yscrollcommand=self.seleccion_scroll.set)

        # Bottom status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Welcome to Enhanced Image Browser!")
        self.status_bar = ttkb.Label(self.root, textvariable=self.status_var, anchor=tk.W, bootstyle="dark")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Remove existing toolbar and footer buttons
        # These have been removed as per the new menu structure

    def create_menu(self):
        self.menubar = tk.Menu(self.root)

        # Archivo Menu
        archivo_menu = tk.Menu(self.menubar, tearoff=0)
        archivo_menu.add_command(label="Seleccionar carpeta", command=self.select_folder)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.root.quit)
        self.menubar.add_cascade(label="Archivo", menu=archivo_menu)

        # Editar Menu
        editar_menu = tk.Menu(self.menubar, tearoff=0)
        editar_menu.add_command(label="Renombrar archivos (EXIF)", command=self.rename_all_jpg_by_exif)
        self.menubar.add_cascade(label="Editar", menu=editar_menu)

        # Efectos Menu
        efectos_menu = tk.Menu(self.menubar, tearoff=0)
        efectos_menu.add_command(label="Reducción de ruido", command=self.open_denoise_window)
        # Future effects can be added here
        self.menubar.add_cascade(label="Efectos", menu=efectos_menu)

        # Ayuda Menu
        ayuda_menu = tk.Menu(self.menubar, tearoff=0)
        ayuda_menu.add_command(label="Información", command=self.show_info)
        ayuda_menu.add_command(label="Configuración", command=self.open_config_window)
        self.menubar.add_cascade(label="Ayuda", menu=ayuda_menu)

        self.root.config(menu=self.menubar)

    # -------------------------
    # Floating Denoise Window
    # -------------------------
    def open_denoise_window(self):
        denoise_window = ttkb.Toplevel(self.root)
        denoise_window.title("Reducción de ruido")
        denoise_window.geometry("400x300")
        denoise_window.grab_set()
        denoise_window.attributes("-topmost", True)

        ttkb.Label(denoise_window, text="Parámetros de reducción de ruido", font=("Helvetica", 12)).pack(pady=10)

        # Radius
        radius_frame = ttkb.Frame(denoise_window)
        radius_frame.pack(pady=5, padx=10, fill=tk.X)
        ttkb.Label(radius_frame, text="Radio:").pack(side=tk.LEFT, padx=5)
        radius_var = tk.IntVar(value=self.denoise_radius_var.get())
        radius_entry = ttkb.Spinbox(radius_frame, from_=0, to=10, textvariable=radius_var)
        radius_entry.pack(side=tk.LEFT, padx=5)

        # Tolerance
        tol_frame = ttkb.Frame(denoise_window)
        tol_frame.pack(pady=5, padx=10, fill=tk.X)
        ttkb.Label(tol_frame, text="Tolerancia:").pack(side=tk.LEFT, padx=5)
        tol_var = tk.IntVar(value=self.denoise_tol_var.get())
        tol_entry = ttkb.Spinbox(tol_frame, from_=0, to=100, textvariable=tol_var)
        tol_entry.pack(side=tk.LEFT, padx=5)

        # Mix
        mix_frame = ttkb.Frame(denoise_window)
        mix_frame.pack(pady=5, padx=10, fill=tk.X)
        ttkb.Label(mix_frame, text="Mezcla:").pack(side=tk.LEFT, padx=5)
        mix_var = tk.DoubleVar(value=self.denoise_mix_var.get())
        mix_entry = ttkb.Spinbox(mix_frame, from_=0.0, to=1.0, increment=0.1, textvariable=mix_var)
        mix_entry.pack(side=tk.LEFT, padx=5)

        # Buttons: Preview and Apply & Close
        button_frame = ttkb.Frame(denoise_window)
        button_frame.pack(pady=20)

        preview_button = ttkb.Button(button_frame, text="Previsualizar", command=lambda: self.preview_denoise(
            radius_var.get(),
            tol_var.get(),
            mix_var.get()
        ), bootstyle=INFO)
        preview_button.pack(side=tk.LEFT, padx=10)

        apply_button = ttkb.Button(button_frame, text="Aplicar y Cerrar", command=lambda: self.apply_denoise_and_close(
            radius_var.get(),
            tol_var.get(),
            mix_var.get(),
            denoise_window
        ), bootstyle=SUCCESS)
        apply_button.pack(side=tk.LEFT, padx=10)

    def preview_denoise(self, radius, tolerance, mix):
        if not self.original_image_pil:
            messagebox.showwarning("Advertencia", "No hay imagen cargada para previsualizar.")
            return

        def denoise_thread():
            try:
                # Apply denoise without modifying the original image
                pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)
                denoised_img = denoise.denoise_image(
                    pil_img,
                    radius=radius,
                    tolerance=tolerance,
                    mix=mix
                )
                # Schedule the UI update in the main thread
                self.root.after(0, lambda: self.update_image_on_canvas(denoised_img))
                self.update_status("Previsualización de reducción de ruido aplicada.")
            except Exception as e:
                self.update_status(f"Error en previsualización de denoising: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo previsualizar la reducción de ruido.\n{e}"))

        threading.Thread(target=denoise_thread, daemon=True).start()

    def apply_denoise_and_close(self, radius, tolerance, mix, window):
        if not self.original_image_pil:
            messagebox.showwarning("Advertencia", "No hay imagen cargada para aplicar.")
            return

        def denoise_thread():
            try:
                # Apply denoise and update the original image
                pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)
                denoised_img = denoise.denoise_image(
                    pil_img,
                    radius=radius,
                    tolerance=tolerance,
                    mix=mix
                )
                self.original_image_pil = denoised_img
                # Schedule the UI update in the main thread
                self.root.after(0, lambda: self.update_image_on_canvas(denoised_img))
                self.update_status("Reducción de ruido aplicada.")
            except Exception as e:
                self.update_status(f"Error al aplicar denoising: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo aplicar la reducción de ruido.\n{e}"))

        threading.Thread(target=denoise_thread, daemon=True).start()
        window.destroy()

    # -------------------------
    # Info Window
    # -------------------------
    def show_info(self):
        info = "Enhanced Image Browser\nVersión 1.0\nDesarrollado por Jocarsa."
        messagebox.showinfo("Información", info)

    # -------------------------
    # Setup Layout
    # -------------------------
    def setup_layout(self):
        self.root.geometry("1200x700")

    def bind_events(self):
        """ Bind keyboard and mouse events. """
        self.update_bindings()
        self.root.bind("<Key>", self.on_any_key, add="+")
        # Mouse events on canvas
        self.image_canvas.bind("<ButtonPress-1>", self.on_left_button_press)
        self.image_canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.image_canvas.bind("<ButtonRelease-1>", self.on_left_button_release)

        # Middle-mouse or right-click for panning
        self.image_canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.image_canvas.bind("<B2-Motion>", self.on_pan_move)
        self.image_canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        self.image_canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.image_canvas.bind("<B3-Motion>", self.on_pan_move)
        self.image_canvas.bind("<ButtonRelease-3>", self.on_pan_end)

        # Mouse wheel zoom
        self.image_canvas.bind("<MouseWheel>", self.on_mouse_wheel)            # Windows
        self.image_canvas.bind("<Button-4>", self.on_mouse_wheel_linux)        # Linux scroll up
        self.image_canvas.bind("<Button-5>", self.on_mouse_wheel_linux)        # Linux scroll down

        # Treeview selection
        self.folder_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.seleccion_tree.bind("<<TreeviewSelect>>", self.on_tree_select_seleccion)

        # Handle window resize
        self.center_frame.bind("<Configure>", self.on_center_frame_resize)

    def update_bindings(self):
        """Update/unbind old keys and rebind with config values."""
        # Unbind known keys
        for key in ["<Left>", "<Right>", "<Up>", "<Down>",
                    "<KP_Add>", "<KP_Subtract>", "<z>", "<q>",
                    f"<{self.config['next_photo']}>",
                    f"<{self.config['prev_photo']}>",
                    f"<{self.config['save_photo']}>",
                    f"<{self.config['increase_exposure']}>",
                    f"<{self.config['decrease_exposure']}>",
                    f"<{self.config['delete_photo']}>"]:
            try:
                self.root.unbind(key)
            except:
                pass

        # Bind from config
        self.root.bind(f"<{self.config['prev_photo']}>", self.show_previous_image)
        self.root.bind(f"<{self.config['next_photo']}>", self.show_next_image)
        self.root.bind(f"<{self.config['save_photo']}>", self.copy_image)
        self.root.bind(f"<{self.config['increase_exposure']}>", self.increase_exposure)
        self.root.bind(f"<{self.config['decrease_exposure']}>", self.decrease_exposure)
        self.root.bind(f"<{self.config['delete_photo']}>", self.delete_image)

    # -------------------------
    # Config Window
    # -------------------------
    def open_config_window(self):
        config_window = ttkb.Toplevel(self.root)
        config_window.title("Configurar Hotkeys")
        config_window.resizable(False, False)
        config_window.grab_set()

        row = 0
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

        row += 1
        ttkb.Label(config_window, text="Delete Photo key:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.E)
        delete_var = tk.StringVar(value=self.config.get("delete_photo", "q"))
        delete_entry = ttkb.Entry(config_window, textvariable=delete_var)
        delete_entry.grid(row=row, column=1, padx=5, pady=5)

        def save_changes():
            self.config["prev_photo"] = prev_var.get() or "Left"
            self.config["next_photo"] = next_var.get() or "Right"
            self.config["save_photo"] = save_var.get() or "z"
            self.config["increase_exposure"] = inc_var.get() or "KP_Add"
            self.config["decrease_exposure"] = dec_var.get() or "KP_Subtract"
            self.config["delete_photo"] = delete_var.get() or "q"
            self.save_config()
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
    # Key Event Handler
    # -------------------------
    def on_any_key(self, event):
        recognized_keys = {
            self.config["prev_photo"],
            self.config["next_photo"],
            self.config["save_photo"],
            self.config["increase_exposure"],
            self.config["decrease_exposure"],
            self.config["delete_photo"]
        }
        if event.keysym not in recognized_keys:
            self.update_status(f"Ignored unrecognized key: {event.keysym}")

    # -------------------------
    # Folder / File Ops
    # -------------------------
    def select_folder(self):
        initial_dir = self.settings.get("last_folder", "")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~")  # Default to home directory

        folder_selected = filedialog.askdirectory(initialdir=initial_dir)
        if folder_selected:
            self.folder_path = folder_selected
            self.seleccion_folder = os.path.join(self.folder_path, "seleccion")
            os.makedirs(self.seleccion_folder, exist_ok=True)
            self.load_images()
            self.populate_folder_tree()
            self.populate_seleccion_tree()

            # Update settings.json with the last folder
            self.settings["last_folder"] = self.folder_path
            self.save_settings()

            # Generate thumbnails in background, but assign them in main thread
            self.start_thumbnail_generation(
                folder_path=self.folder_path,
                image_list=self.image_list,
                thumb_dict=self.thumb_images_left,
                tree=self.folder_tree
            )
            self.start_thumbnail_generation(
                folder_path=self.seleccion_folder,
                image_list=self.seleccion_list,
                thumb_dict=self.thumb_images_right,
                tree=self.seleccion_tree
            )

            if self.image_list:
                self.current_index = 0
                self.display_image(self.current_index, fit=True)
                self.update_status(f"Loaded {len(self.image_list)} images from '{self.folder_path}'.")
            else:
                self.update_status("No JPG images found in the selected folder.")
                messagebox.showinfo("No Images", "No JPG images found in the selected folder.")

    def load_images(self):
        supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG')
        self.image_list = [f for f in os.listdir(self.folder_path) if f.lower().endswith(supported_extensions)]
        self.image_list.sort()

    def populate_folder_tree(self):
        self.folder_tree.delete(*self.folder_tree.get_children())
        for idx, fname in enumerate(self.image_list):
            self.folder_tree.insert("", "end", iid=str(idx), text=fname)

    def populate_seleccion_tree(self):
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
        item_id = self.folder_tree.focus()
        if item_id.isdigit():
            selected_index = int(item_id)
            if selected_index != self.current_index:
                self.current_index = selected_index
                self.display_image(self.current_index, fit=True)

    def on_tree_select_seleccion(self, event):
        item_id = self.seleccion_tree.focus()
        if item_id:
            fname = self.seleccion_tree.item(item_id, "text")
            self.update_status(f"'seleccion' folder item selected: {fname}")

    # -------------------------
    # Thumbnails Generation
    # -------------------------
    def start_thumbnail_generation(self, folder_path, image_list, thumb_dict, tree, subfolder_name="miniaturas"):
        """Spawn a thread that will generate the thumbnail files, then schedule
        an update in the main thread to create PhotoImage and assign it."""
        thread = threading.Thread(
            target=self.generate_thumbnails_in_background,
            args=(folder_path, image_list, thumb_dict, tree, subfolder_name),
            daemon=True
        )
        thread.start()

    def generate_thumbnails_in_background(self, folder_path, image_list, thumb_dict, tree, subfolder_name):
        if not folder_path:
            return
        thumbs_folder = os.path.join(folder_path, subfolder_name)
        os.makedirs(thumbs_folder, exist_ok=True)

        # We'll store results (filename -> thumb_path) so we can update in main thread
        result_list = []
        for filename in image_list:
            source_path = os.path.join(folder_path, filename)
            base, ext = os.path.splitext(filename)
            thumb_filename = base + "_thumb.jpg"
            thumb_path = os.path.join(thumbs_folder, thumb_filename)

            if not os.path.exists(thumb_path):
                try:
                    with Image.open(source_path) as img:
                        img = ImageOps.exif_transpose(img)
                        img.thumbnail((64, 64))
                        img.save(thumb_path, format="JPEG", quality=70)
                except Exception as e:
                    print(f"Could not generate thumbnail for {source_path}: {e}")
                    continue

            result_list.append((filename, thumb_path))

        # Now schedule the creation of PhotoImage objects in the main thread
        def update_thumbs():
            for filename, thumb_path in result_list:
                try:
                    with Image.open(thumb_path) as thumb_img:
                        tk_thumb = ImageTk.PhotoImage(thumb_img)
                        thumb_dict[filename] = tk_thumb
                    # Try to find the item in the tree
                    for item_id in tree.get_children():
                        item_text = tree.item(item_id, "text")
                        if item_text == filename:
                            tree.item(item_id, image=tk_thumb)
                            break
                except Exception as e:
                    print(f"Could not load thumbnail image: {thumb_path} => {e}")

        self.root.after(50, update_thumbs)

    # -------------------------
    # Image Display
    # -------------------------
    def display_image(self, index, fit=False):
        if not self.image_list:
            return

        image_path = os.path.join(self.folder_path, self.image_list[index])
        try:
            pil_img = Image.open(image_path)
            pil_img = self.apply_exif_orientation(pil_img)
            self.original_image_pil = pil_img
            if fit:
                self.auto_fit = True
                self.fit_image_to_canvas()
            else:
                self.redisplay_with_exposure()
            self.root.title(f"jocarsa | lightsteelblue - {self.image_list[self.current_index]}")
            self.update_status(f"Mostrando '{self.image_list[self.current_index]}'.")
            self.highlight_current_tree_item()
            self.update_progress_bar()
        except Exception as e:
            self.update_status(f"Failed to load image: {self.image_list[self.current_index]}")
            messagebox.showerror("Error", f"Failed to load image.\n{e}")

    def apply_exif_orientation(self, image):
        try:
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            self.update_status(f"Could not apply EXIF orientation: {e}")
        return image

    def update_image_on_canvas(self, pil_img):
        """Scale the PIL image according to zoom_scale, then display with pan offsets."""
        if not pil_img:
            return
        cw = self.image_canvas.winfo_width()
        ch = self.image_canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        # Compute scaled size
        w, h = pil_img.size
        scaled_w = int(w * self.zoom_scale)
        scaled_h = int(h * self.zoom_scale)
        display_img = pil_img.resize((scaled_w, scaled_h), self.get_resample_filter())

        self.display_image_tk = ImageTk.PhotoImage(display_img)

        self.image_canvas.delete("all")
        # Calculate center position
        center_x = cw / 2 + self.pan_offset_x
        center_y = ch / 2 + self.pan_offset_y
        self.image_canvas.create_image(
            center_x,
            center_y,
            image=self.display_image_tk,
            anchor=tk.CENTER
        )

        # Redraw selection rectangle if we had one
        self.redraw_selection()

    def get_resample_filter(self):
        try:
            return Image.Resampling.LANCZOS
        except AttributeError:
            return Image.ANTIALIAS

    def on_center_frame_resize(self, event):
        # Redisplay with current exposure/denoise/zoom/pan
        if self.auto_fit:
            self.fit_image_to_canvas()
        else:
            self.update_image_on_canvas(self.original_image_pil)

    def fit_image_to_canvas(self):
        """Fit the image to the canvas while maintaining aspect ratio."""
        if not self.original_image_pil:
            return

        cw = self.image_canvas.winfo_width()
        ch = self.image_canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)

        # Calculate scale to fit
        img_w, img_h = pil_img.size
        scale_w = cw / img_w
        scale_h = ch / img_h
        self.zoom_scale = min(scale_w, scale_h, 1.0)  # Don't upscale beyond original size

        self.pan_offset_x = 0
        self.pan_offset_y = 0

        self.update_image_on_canvas(pil_img)

    # -------------------------
    # Navigation
    # -------------------------
    def show_previous_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index - 1) % len(self.image_list)
            self.display_image(self.current_index, fit=True)

    def show_next_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index + 1) % len(self.image_list)
            self.display_image(self.current_index, fit=True)

    def highlight_current_tree_item(self):
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
            self.auto_fit = False  # User is manually adjusting
            self.update_image_on_canvas(self.original_image_pil)

    def decrease_exposure(self, event=None):
        if self.original_image_pil:
            self.exposure_factor -= 0.1
            if self.exposure_factor < 0.1:
                self.exposure_factor = 0.1
            self.update_status(f"Exposure decreased to {self.exposure_factor:.2f}")
            self.auto_fit = False  # User is manually adjusting
            self.update_image_on_canvas(self.original_image_pil)

    def redisplay_with_exposure(self):
        """Apply exposure and optional denoising, then show."""
        if not self.original_image_pil:
            return
        pil_img = self.apply_exposure(self.original_image_pil, self.exposure_factor)
        if self.enable_denoise_var.get():
            # Apply denoise in a separate thread to avoid freezing the UI
            threading.Thread(
                target=self.apply_denoise_effect,
                args=(pil_img,),
                daemon=True
            ).start()
        else:
            self.update_image_on_canvas(pil_img)

    def apply_exposure(self, pil_img, factor):
        if np is not None:
            arr = np.array(pil_img, dtype=np.float32)
            arr *= factor
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            return Image.fromarray(arr)
        else:
            enhancer = ImageEnhance.Brightness(pil_img)
            return enhancer.enhance(factor)

    def apply_denoise_effect(self, pil_img):
        try:
            denoised_img = denoise.denoise_image(
                pil_img,
                radius=self.denoise_radius_var.get(),
                tolerance=self.denoise_tol_var.get(),
                mix=self.denoise_mix_var.get()
            )
            self.update_image_on_canvas(denoised_img)
            self.update_status("Reducción de ruido aplicada.")
        except Exception as e:
            self.update_status(f"Denoising Error: {e}")
            messagebox.showerror("Error", f"Failed to apply denoising.\n{e}")

    # -------------------------
    # Selection Rectangle
    # -------------------------
    def on_left_button_press(self, event):
        # Start drawing rectangle
        self.start_x = self.image_canvas.canvasx(event.x)
        self.start_y = self.image_canvas.canvasy(event.y)
        self.selection_coords = (self.start_x, self.start_y, self.start_x, self.start_y)

    def on_mouse_move(self, event):
        # Update selection rectangle if left mouse is pressed
        if event.state & 0x0100:  # left button bit
            end_x = self.image_canvas.canvasx(event.x)
            end_y = self.image_canvas.canvasy(event.y)
            self.selection_coords = (self.start_x, self.start_y, end_x, end_y)
            self.redraw_selection()

    def on_left_button_release(self, event):
        # Finalize selection
        if self.selection_coords:
            end_x = self.image_canvas.canvasx(event.x)
            end_y = self.image_canvas.canvasy(event.y)
            self.selection_coords = (self.start_x, self.start_y, end_x, end_y)

    def redraw_selection(self):
        self.image_canvas.delete("selection_rect")
        if self.selection_coords:
            x1, y1, x2, y2 = self.selection_coords
            self.image_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="yellow", width=2,
                tag="selection_rect"
            )

    # -------------------------
    # Panning & Zoom
    # -------------------------
    def on_pan_start(self, event):
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_pan_move(self, event):
        if self.dragging:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            # Move offsets
            self.pan_offset_x += dx
            self.pan_offset_y += dy
            self.update_image_on_canvas(self.original_image_pil)

    def on_pan_end(self, event):
        self.dragging = False

    def on_mouse_wheel(self, event):
        """Zoom on Windows (event.delta is usually 120 or -120)"""
        if event.delta > 0:
            self.zoom_scale *= 1.1
        else:
            self.zoom_scale /= 1.1
        if self.zoom_scale < 0.1:
            self.zoom_scale = 0.1
        self.auto_fit = False  # User is manually zooming
        self.update_image_on_canvas(self.original_image_pil)

    def on_mouse_wheel_linux(self, event):
        """Zoom on Linux: Button-4 => up, Button-5 => down"""
        if event.num == 4:
            self.zoom_scale *= 1.1
        elif event.num == 5:
            self.zoom_scale /= 1.1
        if self.zoom_scale < 0.1:
            self.zoom_scale = 0.1
        self.auto_fit = False  # User is manually zooming
        self.update_image_on_canvas(self.original_image_pil)

    # -------------------------
    # Copy / Save Image
    # -------------------------
    def copy_image(self, event=None):
        if not self.image_list:
            self.update_status("No image to copy.")
            return

        source_image = os.path.join(self.folder_path, self.image_list[self.current_index])
        os.makedirs(self.seleccion_folder, exist_ok=True)
        new_filename = self.build_destination_filename(source_image)
        destination_image = os.path.join(self.seleccion_folder, new_filename)

        base, ext = os.path.splitext(new_filename)
        counter = 1
        while os.path.exists(destination_image):
            destination_image = os.path.join(self.seleccion_folder, f"{base}_{counter}{ext}")
            counter += 1

        try:
            full_img = Image.open(source_image)
            full_img = self.apply_exif_orientation(full_img)
            full_img = self.apply_exposure(full_img, self.exposure_factor)
            # Crop if selection
            final_img = self.maybe_crop(full_img)

            # If denoise is enabled, apply it
            if self.enable_denoise_var.get():
                final_img = denoise.denoise_image(
                    final_img,
                    radius=self.denoise_radius_var.get(),
                    tolerance=self.denoise_tol_var.get(),
                    mix=self.denoise_mix_var.get()
                )

            final_img.save(destination_image, quality=95)
            self.update_status(f"Image copied to '{destination_image}'.")
            self.populate_seleccion_tree()

            # Generate a thumbnail (in background, main thread will attach to Treeview)
            self.start_thumbnail_generation(
                folder_path=self.seleccion_folder,
                image_list=[os.path.basename(destination_image)],
                thumb_dict=self.thumb_images_right,
                tree=self.seleccion_tree
            )
        except Exception as e:
            self.update_status(f"Copy Error: {e}")
            messagebox.showerror("Copy Error", f"Failed to copy image.\n{e}")

    def build_destination_filename(self, source_image):
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
        """Crop the full_img according to selection rectangle, if any."""
        if not self.selection_coords:
            return full_img

        x1, y1, x2, y2 = self.selection_coords

        # Since we are panning/zooming, we need to account for that
        # We'll invert the transform from canvas coords -> image coords
        # scaled image size
        orig_w, orig_h = full_img.size
        scaled_w = int(orig_w * self.zoom_scale)
        scaled_h = int(orig_h * self.zoom_scale)

        # The image center is at (pan_offset_x, pan_offset_y) in canvas coords
        # So the image top-left is (pan_offset_x - scaled_w/2, pan_offset_y - scaled_h/2).
        left_in_canvas = self.pan_offset_x - scaled_w / 2
        top_in_canvas = self.pan_offset_y - scaled_h / 2

        # The selection coords are in canvas space
        # so (x1 - left_in_canvas) / self.zoom_scale gives us the original image x
        sel_left = (x1 - left_in_canvas) / self.zoom_scale
        sel_top = (y1 - top_in_canvas) / self.zoom_scale
        sel_right = (x2 - left_in_canvas) / self.zoom_scale
        sel_bottom = (y2 - top_in_canvas) / self.zoom_scale

        # Clamp
        sel_left = max(0, min(sel_left, orig_w))
        sel_right = max(0, min(sel_right, orig_w))
        sel_top = max(0, min(sel_top, orig_h))
        sel_bottom = max(0, min(sel_bottom, orig_h))

        if (sel_right - sel_left) < 2 or (sel_bottom - sel_top) < 2:
            return full_img

        return full_img.crop((sel_left, sel_top, sel_right, sel_bottom))

    # -------------------------
    # Denoising
    # -------------------------
    def on_denoise_toggle(self):
        """Called when the checkbox is toggled."""
        self.redisplay_with_exposure()

    def on_denoise_param_change(self, event=None):
        """Called when any scale changes, if denoise is active, re-render."""
        if self.enable_denoise_var.get():
            self.redisplay_with_exposure()

    # -------------------------
    # Progress Bar
    # -------------------------
    def update_progress_bar(self):
        if len(self.image_list) <= 1:
            progress = 0.0
        else:
            progress = (self.current_index / (len(self.image_list) - 1)) * 100.0
        self.progress_var.set(progress)

    # -------------------------
    # Rename All by EXIF
    # -------------------------
    def rename_all_jpg_by_exif(self):
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
                if new_name != old_name:
                    new_path = os.path.join(self.folder_path, new_name)
                    base, ext = os.path.splitext(new_name)
                    counter = 1
                    while os.path.exists(new_path):
                        new_path = os.path.join(self.folder_path, f"{base}_{counter}{ext}")
                        counter += 1
                    os.rename(old_path, new_path)
                    renamed_count += 1
            except Exception as e:
                print(f"Could not rename {old_name}: {e}")

        self.load_images()
        self.populate_folder_tree()
        self.update_status(f"Renamed {renamed_count} file(s) based on EXIF in '{self.folder_path}'.")

        self.thumb_images_left.clear()  # Clear existing thumbnails
        self.populate_folder_tree()      # Repopulate tree with updated image_list
        self.start_thumbnail_generation(
            folder_path=self.folder_path,
            image_list=self.image_list,
            thumb_dict=self.thumb_images_left,
            tree=self.folder_tree
        )

    def build_destination_filename_rename(self, source_path, original_name):
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
        return original_name

    # -------------------------
    # Delete Image
    # -------------------------
    def delete_image(self, event=None):
        if not self.image_list:
            self.update_status("No image to delete.")
            return

        source_image = os.path.join(self.folder_path, self.image_list[self.current_index])
        eliminadas_folder = os.path.join(self.folder_path, "eliminadas")
        os.makedirs(eliminadas_folder, exist_ok=True)
        destination_image = os.path.join(eliminadas_folder, self.image_list[self.current_index])

        try:
            os.rename(source_image, destination_image)
            self.update_status(f"Image moved to 'eliminadas' folder: '{destination_image}'.")

            # Remove from image_list
            del self.image_list[self.current_index]

            # Refresh the folder_tree to update item IDs
            self.populate_folder_tree()

            # Re-populate the thumbnails
            self.thumb_images_left.clear()  # Clear existing thumbnails
            self.populate_folder_tree()      # Repopulate tree with updated image_list
            self.start_thumbnail_generation(
                folder_path=self.folder_path,
                image_list=self.image_list,
                thumb_dict=self.thumb_images_left,
                tree=self.folder_tree
            )

            # Update the selection and display
            if self.image_list:
                self.current_index = min(self.current_index, len(self.image_list) - 1)
                self.display_image(self.current_index, fit=True)
            else:
                self.image_canvas.delete("all")
                self.original_image_pil = None
                self.display_image_tk = None
                self.update_status("No images left in the folder.")
        except Exception as e:
            self.update_status(f"Failed to delete image: {e}")
            messagebox.showerror("Error", f"Failed to delete image.\n{e}")

    # -------------------------
    # Utilities
    # -------------------------
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

def main():
    app = ttkb.Window(themename="darkly")
    EnhancedImageBrowser(app)
    app.mainloop()

if __name__ == "__main__":
    main()
