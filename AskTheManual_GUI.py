import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from pathlib import Path
import threading
import re
from PIL import Image, ImageTk
from unified_extraction_review import PdfProcessor

# Try import AI module
try:
    from image_to_information import enrich_file
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Try import Vector module
try:
    from vector_transformer import update_or_create_vector_index
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False

class ReviewApp(tb.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("AskTheManual")
        self.geometry("1400x900")
        
        self.processor = None
        self.temp_dir = None
        self.generated_md_path = None
        self.final_md_path = None
        self.image_count = 0
        self.current_image_index = 0
        self.deleted_indices = set()
        self.decided_indices = set()
        self.cached_images = {} # index -> ImageTk
        
        # Data for Step 2
        self.final_image_paths = [] # List of (relative_path, absolute_path) for Step 2
        self.manual_descriptions = {} # path -> description text
        self.current_step2_index = 0
        
        self.create_start_screen()

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    # --- SCREEN 1: START ---
    def create_start_screen(self):
        self.clear_window()
        
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        
        header = tb.Label(container, text="PDF Extraction + Review", font=("Helvetica", 24))
        header.pack(pady=20)
        
        # File config
        file_frame = tb.Frame(container)
        file_frame.pack(pady=20, fill=X)
        
        tb.Label(file_frame, text="Select PDF:", font=("Helvetica", 12)).pack(side=LEFT, padx=10)
        
        self.pdf_list = sorted([f.name for f in Path(".").glob("*.pdf")])
        self.file_combo = tb.Combobox(file_frame, values=self.pdf_list, state="readonly", width=40)
        if self.pdf_list:
            self.file_combo.current(0)
        self.file_combo.pack(side=LEFT, padx=10, fill=X, expand=YES)
        
        tb.Button(file_frame, text="Refresh", command=self.refresh_files, bootstyle="outline").pack(side=LEFT, padx=5)

        self.start_btn = tb.Button(container, text="Start Processing", command=self.start_processing, bootstyle="success", width=20)
        self.start_btn.pack(pady=40)
        
        # Progress
        self.progress_frame = tb.Frame(container)
        self.progress_label = tb.Label(self.progress_frame, text="Processing... This may take a minute.", font=("Helvetica", 10))
        self.progress_label.pack(pady=5)
        self.progress_bar = tb.Progressbar(self.progress_frame, mode='indeterminate', bootstyle="info", length=400)
        self.progress_bar.pack(pady=5)
        
        self.error_label = tb.Label(container, text="", bootstyle="danger")
        self.error_label.pack(pady=10)

    def refresh_files(self):
        self.pdf_list = sorted([f.name for f in Path(".").glob("*.pdf")])
        self.file_combo['values'] = self.pdf_list
        if self.pdf_list:
            self.file_combo.current(0)

    def start_processing(self):
        filename = self.file_combo.get()
        if not filename:
            self.error_label.config(text="Please select a file.")
            return
            
        self.start_btn.config(state="disabled")
        self.progress_frame.pack(pady=20)
        self.progress_bar.start(10)
        self.error_label.config(text="")
        
        threading.Thread(target=self.run_processing_thread, args=(filename,), daemon=True).start()

    def run_processing_thread(self, filename):
        try:
            self.processor = PdfProcessor(filename)
            self.temp_dir, self.image_count = self.processor.process_phase_1()
            
            # Reset state
            self.current_image_index = 1
            self.deleted_indices = set()
            self.decided_indices = set()
            self.cached_images = {}
            
            self.after(0, self.show_review_screen)
        except Exception as e:
            self.after(0, lambda: self.show_error(str(e)))

    def show_error(self, message):
        self.progress_bar.stop()
        self.progress_frame.pack_forget()
        self.start_btn.config(state="normal")
        self.error_label.config(text=f"Error: {message}")

    # --- SCREEN 2: REVIEW IMAGES (Carousel) ---
    def show_review_screen(self):
        self.clear_window()
        
        if self.image_count == 0:
            self.show_no_images_screen()
            return

        main_frame = tb.Frame(self, padding=20)
        main_frame.pack(fill=BOTH, expand=YES)
        
        # Top Bar
        top_bar = tb.Frame(main_frame)
        top_bar.pack(fill=X, pady=(0, 20))
        
        tb.Label(top_bar, text=f"Reviewing: {self.processor.pdf_filename}", font=("Helvetica", 14, "bold")).pack(side=LEFT)
        self.counter_label = tb.Label(top_bar, text=f"Image {self.current_image_index} of {self.image_count}", font=("Helvetica", 14))
        self.counter_label.pack(side=RIGHT)

        # Image Display
        self.image_container = tb.Frame(main_frame, bootstyle="secondary", padding=10)
        self.image_container.pack(fill=BOTH, expand=YES)
        
        self.image_label = tk.Label(self.image_container, bg='#444')
        self.image_label.pack(fill=BOTH, expand=YES)
        
        self.status_label = tb.Label(main_frame, text="", font=("Helvetica", 16, "bold"))
        self.status_label.pack(pady=10, before=self.image_container)

        # Controls
        bottom_bar = tb.Frame(main_frame, padding=(0, 20, 0, 0))
        bottom_bar.pack(fill=X, side=BOTTOM)
        
        btn_frame = tb.Frame(bottom_bar)
        btn_frame.pack(anchor=CENTER)
        
        tb.Button(btn_frame, text="◀ Previous", command=self.prev_image, bootstyle="outline").pack(side=LEFT, padx=10)
        
        self.btn_keep = tb.Button(btn_frame, text="Keep (K)", command=self.mark_keep, bootstyle="success", width=15)
        self.btn_keep.pack(side=LEFT, padx=20)
        
        self.btn_delete = tb.Button(btn_frame, text="Delete (D)", command=self.mark_delete, bootstyle="danger", width=15)
        self.btn_delete.pack(side=LEFT, padx=20)

        tb.Button(btn_frame, text="Next ▶", command=self.next_image, bootstyle="outline").pack(side=LEFT, padx=10)

        tb.Button(main_frame, text="Finish & Save", command=self.finish_process_step1, bootstyle="primary").pack(side=BOTTOM, pady=10)

        # Bindings
        self.unbind_all_keys()
        self.bind("<Left>", lambda e: self.prev_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("k", lambda e: self.mark_keep())
        self.bind("d", lambda e: self.mark_delete())

        self.update_image_display()

    def unbind_all_keys(self):
        # Unbind common keys to prevent conflict between screens
        for k in ["<Left>", "<Right>", "<Up>", "<Down>", "k", "d"]:
            self.unbind(k)

    def update_image_display(self):
        idx = self.current_image_index
        self.counter_label.config(text=f"Image {idx} of {self.image_count}")
        
        if idx in self.deleted_indices:
            self.status_label.config(text="MARKED FOR DELETION", bootstyle="inverse-danger")
            self.btn_delete.config(bootstyle="danger")
            self.btn_keep.config(bootstyle="outline-success")
        elif idx in self.decided_indices:
            self.status_label.config(text="KEEPING", bootstyle="inverse-success")
            self.btn_delete.config(bootstyle="outline-danger")
            self.btn_keep.config(bootstyle="success")
        else:
            self.status_label.config(text="")
            self.btn_delete.config(bootstyle="outline-danger")
            self.btn_keep.config(bootstyle="outline-success")

        if idx not in self.cached_images:
            try:
                img_path = self.temp_dir / f"bild_{idx}.png"
                pil_img = Image.open(img_path)
                display_width, display_height = 1000, 600
                ratio = min(display_width/pil_img.width, display_height/pil_img.height)
                new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                self.cached_images[idx] = ImageTk.PhotoImage(pil_img)
            except Exception as e:
                print(f"Error loading image {idx}: {e}")
                return

        self.image_label.config(image=self.cached_images[idx])

    def prev_image(self):
        if self.current_image_index > 1:
            self.current_image_index -= 1
            self.update_image_display()

    def next_image(self):
        if self.current_image_index < self.image_count:
            self.current_image_index += 1
            self.update_image_display()

    def mark_keep(self):
        if self.current_image_index in self.deleted_indices:
            self.deleted_indices.remove(self.current_image_index)
        self.decided_indices.add(self.current_image_index)
        self.next_image_auto()
        
    def mark_delete(self):
        self.deleted_indices.add(self.current_image_index)
        self.decided_indices.add(self.current_image_index)
        self.next_image_auto()

    def next_image_auto(self):
        if self.current_image_index < self.image_count:
            self.current_image_index += 1
            self.update_image_display()
        else:
            self.update_image_display()

    def finish_process_step1(self):
        # Run Phase 2 (Move files, create basic Markdown)
        loading = tb.Toplevel(self)
        loading.title("Saving...")
        loading.geometry("300x100")
        tb.Label(loading, text="Finalizing files...", padding=20).pack()
        loading.update()
        
        try:
            self.generated_md_path = self.processor.process_phase_2(list(self.deleted_indices))
            self.generated_md_path = Path(str(self.generated_md_path))
            self.final_md_path = self.generated_md_path # Default if no step 2
            loading.destroy()
            self.show_step2_selection_screen()
            
        except Exception as e:
            loading.destroy()
            messagebox.showerror("Error", str(e))

    # --- SCREEN 3: SELECT NEXT STEP ---
    def show_step2_selection_screen(self):
        self.clear_window()
        self.unbind_all_keys()
        
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        
        tb.Label(container, text="Extraction Complete", font=("Helvetica", 24), bootstyle="success").pack(pady=30)
        tb.Label(container, text=f"Basic markdown created at:\n{self.generated_md_path}", font=("Helvetica", 12)).pack(pady=10)
        
        tb.Label(container, text="Step 2: Enrichment (Optional)", font=("Helvetica", 16, "bold")).pack(pady=40)
        
        btn_frame = tb.Frame(container)
        btn_frame.pack()
        
        # Vision AI Button
        vision_btn = tb.Button(btn_frame, text="Send to Vision AI (Auto)", command=self.run_vision_ai, bootstyle="info", width=25)
        vision_btn.pack(pady=10)
        if not AI_AVAILABLE:
            vision_btn.config(state="disabled", text="Vision AI (Module missing)")
        
        # Human Description Button
        tb.Button(btn_frame, text="Human Description (Manual)", command=self.prep_human_review, bootstyle="warning", width=25).pack(pady=10)
        
        # Skip to Step 3
        tb.Button(container, text="Skip to Step 3 (Indexing)", command=self.show_step3_screen, bootstyle="secondary").pack(pady=40)

    # --- VISION AI FLOW ---
    def run_vision_ai(self):
        self.clear_window()
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        
        tb.Label(container, text="Running Vision AI...", font=("Helvetica", 24)).pack(pady=50)
        
        log_text = tk.Text(container, height=15, width=80)
        log_text.pack(pady=20)
        log_text.insert(END, "Starting AI enrichment process...\nPlease wait, this can take a while depending on file size.\n")
        
        def update_log(current, total, message):
            def _update():
                log_text.insert(END, f"[{current}/{total}] {message}\n")
                log_text.see(END)
            self.after(0, _update)
        
        def run_ai_thread():
            try:
                # We assume a valid API key is in the script or ENV
                new_file = enrich_file(self.generated_md_path, progress_callback=update_log)
                self.final_md_path = Path(new_file)
                
                self.after(0, lambda: messagebox.showinfo("Done", f"Enrichment Complete!\nSaved to: {new_file}"))
                self.after(0, self.show_step3_screen)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, self.show_step2_selection_screen)

        threading.Thread(target=run_ai_thread, daemon=True).start()

    # --- HUMAN REVIEW FLOW ---
    def prep_human_review(self):
        # Scan markdown for images
        self.final_image_paths = []
        md_path = self.generated_md_path
        
        if not md_path.exists():
            messagebox.showerror("Error", "Markdown file not found.")
            return

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        base_dir = md_path.parent
        matches = re.findall(r"!\[.*?\]\((.*?)\)", content)
        
        for rel_path in matches:
            abs_path = base_dir / rel_path
            if abs_path.exists():
                self.final_image_paths.append((rel_path, abs_path))
        
        if not self.final_image_paths:
            messagebox.showinfo("Info", "No images found in markdown to describe.")
            self.show_step3_screen()
            return
            
        self.current_step2_index = 0
        self.manual_descriptions = {}
        self.show_human_review_screen()

    def show_human_review_screen(self):
        self.clear_window()
        
        total = len(self.final_image_paths)
        if self.current_step2_index >= total:
            self.finish_human_review()
            return

        rel_path, abs_path = self.final_image_paths[self.current_step2_index]

        main_frame = tb.Frame(self, padding=20)
        main_frame.pack(fill=BOTH, expand=YES)
        
        header = tb.Frame(main_frame)
        header.pack(fill=X, pady=(0, 10))
        tb.Label(header, text=f"Describe Image {self.current_step2_index + 1} of {total}", font=("Helvetica", 16, "bold")).pack(side=LEFT)
        tb.Button(header, text="Skip/Next", command=self.next_human_step, bootstyle="outline").pack(side=RIGHT)

        paned = tb.Panedwindow(main_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=YES)
        
        left_frame = tb.Frame(paned, padding=10)
        paned.add(left_frame, weight=1)
        
        try:
            pil_img = Image.open(abs_path)
            display_w, display_h = 600, 600
            ratio = min(display_w/pil_img.width, display_h/pil_img.height)
            new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(pil_img)
            
            lbl = tb.Label(left_frame, image=tk_img)
            lbl.image = tk_img
            lbl.pack(expand=YES)
        except Exception as e:
            tb.Label(left_frame, text=f"Error loading image: {e}").pack()

        right_frame = tb.Frame(paned, padding=10)
        paned.add(right_frame, weight=1)
        
        tb.Label(right_frame, text="Description:", font=("Helvetica", 12)).pack(anchor=W)
        self.desc_text = tk.Text(right_frame, height=20, width=40, font=("Helvetica", 11), wrap=WORD)
        self.desc_text.pack(fill=BOTH, expand=YES, pady=10)
        
        controls = tb.Frame(right_frame)
        controls.pack(fill=X, pady=10)
        
        tb.Button(controls, text="Save & Next", command=self.save_and_next_human, bootstyle="success").pack(fill=X)

    def save_and_next_human(self):
        text = self.desc_text.get("1.0", END).strip()
        rel_path, _ = self.final_image_paths[self.current_step2_index]
        if text:
            self.manual_descriptions[rel_path] = text
        
        self.next_human_step()

    def next_human_step(self):
        self.current_step2_index += 1
        self.show_human_review_screen()
        
    def finish_human_review(self):
        try:
            md_path = self.generated_md_path
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            for line in lines:
                new_lines.append(line)
                match = re.search(r"!\[.*?\]\((.*?)\)", line)
                if match:
                    rel_path = match.group(1)
                    if rel_path in self.manual_descriptions:
                        desc = self.manual_descriptions[rel_path]
                        new_lines.append(f"> Image description: {desc}\n\n")

            # Save as enriched file to match Vision AI behavior
            new_filename = md_path.stem.replace("_mapped", "") + "_mapped_enriched.md"
            output_path = md_path.parent / new_filename
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            
            self.final_md_path = output_path
            messagebox.showinfo("Success", f"Descriptions saved to:\n{output_path.name}")
            self.show_step3_screen()
            
        except Exception as e:
            messagebox.showerror("Error Saving Descriptions", str(e))
            self.show_step3_screen()

    def show_no_images_screen(self):
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        tb.Label(container, text="No images found to extract.", font=("Helvetica", 18)).pack(pady=50)
        tb.Button(container, text="Back", command=self.create_start_screen).pack()

    # --- SCREEN 4: VECTOR INDEXING ---
    def show_step3_screen(self):
        self.clear_window()
        
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        
        tb.Label(container, text="Step 3: Vector Indexing", font=("Helvetica", 24), bootstyle="info").pack(pady=30)
        
        if self.final_md_path:
            msg = f"Ready to update vector index with:\n{self.final_md_path.name}"
        else:
            msg = "Ready to update vector index."
            
        tb.Label(container, text=msg, font=("Helvetica", 14)).pack(pady=20)
        
        if not VECTOR_AVAILABLE:
            tb.Label(container, text="Vector module missing or failed to load.", bootstyle="danger").pack(pady=10)
            
        btn_frame = tb.Frame(container)
        btn_frame.pack(pady=40)
        
        idx_btn = tb.Button(btn_frame, text="Update Vector Index", command=self.run_indexing, bootstyle="primary", width=25)
        idx_btn.pack(pady=10)
        if not VECTOR_AVAILABLE:
            idx_btn.config(state="disabled")
            
        tb.Button(container, text="Exit / New File", command=self.create_start_screen, bootstyle="secondary").pack(pady=20)

    def run_indexing(self):
        self.clear_window()
        container = tb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)
        
        tb.Label(container, text="Updating Index...", font=("Helvetica", 24)).pack(pady=50)
        
        pb = tb.Progressbar(container, mode='indeterminate', bootstyle="primary", length=400)
        pb.pack(pady=20)
        pb.start(10)
        
        def index_thread():
            try:
                # We use default index path for now as requested
                # Ensure we pass string path
                target_file = str(self.final_md_path) if self.final_md_path else str(self.generated_md_path)
                update_or_create_vector_index(target_file)
                
                self.after(0, lambda: messagebox.showinfo("Success", "Vector Index Updated Successfully!"))
                self.after(0, self.create_start_screen)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, self.create_start_screen)
                
        threading.Thread(target=index_thread, daemon=True).start()

if __name__ == "__main__":
    app = ReviewApp()
    app.mainloop()
