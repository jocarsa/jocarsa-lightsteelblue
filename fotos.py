import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, __version__ as PILLOW_VERSION
import exifread
from datetime import datetime

class ImageBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Browser")

        # Initialize variables
        self.image_list = []
        self.current_index = 0
        self.current_image = None
        self.image_label = None
        self.folder_path = ""

        # Create UI elements
        self.create_widgets()

        # Bind keys
        self.root.bind("<Left>", self.show_previous_image)
        self.root.bind("<Right>", self.show_next_image)
        self.root.bind("<z>", self.copy_image)

    def create_widgets(self):
        # Frame for the button
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        # Select Folder Button
        select_button = tk.Button(button_frame, text="Select Folder", command=self.select_folder)
        select_button.pack()

        # Label to display images
        self.image_label = tk.Label(self.root)
        self.image_label.pack()

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Welcome to Image Browser!")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, ipady=2)

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path = folder_selected
            self.load_images()
            if self.image_list:
                self.current_index = 0
                self.display_image()
                self.update_status(f"Loaded {len(self.image_list)} images from '{self.folder_path}'.")
            else:
                self.update_status("No JPG images found in the selected folder.")
                messagebox.showinfo("No Images", "No JPG images found in the selected folder.")

    def load_images(self):
        # Get list of jpg and jpeg files
        supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG')
        self.image_list = [file for file in os.listdir(self.folder_path) if file.endswith(supported_extensions)]
        self.image_list.sort()  # Sort the list for consistent ordering

    def display_image(self):
        image_path = os.path.join(self.folder_path, self.image_list[self.current_index])
        try:
            image = Image.open(image_path)

            # Apply EXIF-based rotation if necessary
            image = self.apply_exif_orientation(image, image_path)

            # Resize image to fit the window while maintaining aspect ratio
            max_size = (800, 600)

            # Determine the resampling filter based on Pillow version
            resample_filter = self.get_resample_filter()

            image.thumbnail(max_size, resample_filter)
            self.current_image = ImageTk.PhotoImage(image)
            self.image_label.config(image=self.current_image)
            self.root.title(f"Image Browser - {self.image_list[self.current_index]}")
            self.update_status(f"Displaying '{self.image_list[self.current_index]}'.")
        except Exception as e:
            self.update_status(f"Failed to load image: {self.image_list[self.current_index]}")
            messagebox.showerror("Error", f"Failed to load image.\n{e}")

    def get_resample_filter(self):
        # For Pillow >=10.0.0
        try:
            return Image.Resampling.LANCZOS
        except AttributeError:
            # For older Pillow versions
            return Image.ANTIALIAS

    def apply_exif_orientation(self, image, image_path):
        """
        Adjust image orientation based on EXIF data.
        """
        try:
            # Use Pillow's built-in method to handle EXIF orientation
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            self.update_status(f"Could not apply EXIF orientation: {e}")
        return image

    def show_previous_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index - 1) % len(self.image_list)
            self.display_image()

    def show_next_image(self, event=None):
        if self.image_list:
            self.current_index = (self.current_index + 1) % len(self.image_list)
            self.display_image()

    def copy_image(self, event=None):
        if not self.image_list:
            self.update_status("No image to copy.")
            return

        source_image = os.path.join(self.folder_path, self.image_list[self.current_index])

        # Create 'seleccion' folder if it doesn't exist
        seleccion_folder = os.path.join(self.folder_path, "seleccion")
        os.makedirs(seleccion_folder, exist_ok=True)

        # Extract EXIF data for datetime
        try:
            with open(source_image, 'rb') as img_file:
                tags = exifread.process_file(img_file, stop_tag="EXIF DateTimeOriginal", details=False)
                date_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                if date_tag:
                    date_str = str(date_tag)
                    # Parse date and time
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    new_filename = dt.strftime("%Y-%m-%d-%H-%M-%S") + ".jpg"
                else:
                    # Fallback to original filename if EXIF data is missing
                    new_filename = self.image_list[self.current_index]
        except Exception as e:
            self.update_status(f"EXIF Error: {e}. Using original filename.")
            new_filename = self.image_list[self.current_index]

        destination_image = os.path.join(seleccion_folder, new_filename)

        # Handle duplicate filenames
        if os.path.exists(destination_image):
            base, ext = os.path.splitext(new_filename)
            counter = 1
            while os.path.exists(destination_image):
                destination_image = os.path.join(seleccion_folder, f"{base}_{counter}{ext}")
                counter += 1

        try:
            shutil.copy2(source_image, destination_image)
            self.update_status(f"Image copied to '{destination_image}'.")
        except Exception as e:
            self.update_status(f"Copy Error: {e}")
            messagebox.showerror("Copy Error", f"Failed to copy image.\n{e}")

    def update_status(self, message):
        """
        Update the status bar with the given message.
        """
        self.status_var.set(message)

def main():
    root = tk.Tk()
    app = ImageBrowser(root)
    root.geometry("850x650")  # Set initial window size
    root.mainloop()

if __name__ == "__main__":
    main()
