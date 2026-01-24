import time
import re
import shutil
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import PictureItem

class PdfProcessor:
    def __init__(self, pdf_filename):
        self.pdf_filename = pdf_filename
        self.pdf_path = Path(pdf_filename)
        self.output_dir = Path("extracted_data")
        self.software_name = self.pdf_path.stem
        self.temp_image_dir = self.output_dir / "temp_review"
        self.final_image_dir = self.output_dir / "images" / self.software_name
        self.md_content = ""
        self.all_images = [] # Temporarily holds PILLOW image objects if kept in memory, 
                             # but for GUI we might just reload from disk or keep references.
                             # Actually, for step 2 we re-read or rely on indices. 
                             # Let's just track the count.
        self.image_count = 0

    def prepare_directories(self):
        # Ordner bereinigen/erstellen
        if self.temp_image_dir.exists(): shutil.rmtree(self.temp_image_dir)
        self.temp_image_dir.mkdir(parents=True, exist_ok=True)
        
        # Falls der spezifische Software-Ordner existiert, löschen wir ihn für einen sauberen Run
        if self.final_image_dir.exists(): shutil.rmtree(self.final_image_dir)
        self.final_image_dir.mkdir(parents=True, exist_ok=True)

    def process_phase_1(self):
        """
        Runs the conversion and extracts images to temp dir.
        Returns the path to the temp directory and the number of images found.
        """
        self.prepare_directories()

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = True
        pipeline_options.generate_page_images = True
        pipeline_options.images_scale = 2.0

        converter = DocumentConverter(
            format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
        )

        print(f"--- Analyse läuft: {self.pdf_filename} ---")
        result = converter.convert(self.pdf_path)
        self.md_content = result.document.export_to_markdown()

        # Bilder extrahieren
        images = []
        for item, _ in result.document.iterate_items():
            if isinstance(item, PictureItem):
                visual_crop = item.get_image(result.document)
                if visual_crop:
                    images.append(visual_crop)
        
        self.image_count = len(images)
        self.all_images = images # store references if needed later, though we save them now

        if not images:
            return self.temp_image_dir, 0

        # Bilder temporär speichern
        for i, img in enumerate(images, 1):
            img.save(self.temp_image_dir / f"bild_{i}.png")
            
        return self.temp_image_dir, self.image_count

    def process_phase_2(self, exclude_indices):
        """
        Moves kept images to final location and writes the Markdown file.
        exclude_indices: list of integers (1-based) to remove.
        """
        final_mapping = {}
        current_final_id = 1
        
        for i in range(1, self.image_count + 1):
            if i in exclude_indices:
                final_mapping[i] = None
            else:
                new_name = f"diagramm_{current_final_id}.png"
                src = self.temp_image_dir / f"bild_{i}.png"
                dst = self.final_image_dir / new_name
                
                if src.exists():
                    shutil.move(src, dst)
                    final_mapping[i] = f"images/{self.software_name}/{new_name}"
                    current_final_id += 1
                else:
                    # Should not happen if flow is correct
                    final_mapping[i] = None

        # Markdown anpassen
        tag_counter = {"count": 0}

        def replace_logic(match):
            tag_counter["count"] += 1
            idx = tag_counter["count"]
            
            path = final_mapping.get(idx)
            if path:
                return f"![Extrahiertes Bild]({path})"
            else:
                return "" 

        final_md = re.sub(r"<!-- image -->", replace_logic, self.md_content)

        output_file = self.output_dir / f"{self.pdf_path.stem}_mapped.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_md)
        
        # Temp-Ordner aufräumen
        if self.temp_image_dir.exists():
            shutil.rmtree(self.temp_image_dir)
            
        return output_file

def run_cli():
    pdf_filename = input("Filename (e.g. pas.pdf): ") or "pas.pdf"
    processor = PdfProcessor(pdf_filename)
    
    # Phase 1
    temp_dir, count = processor.process_phase_1()
    if count == 0:
        print("Keine Bilder gefunden.")
        return

    print(f"\n--- REVIEW BENÖTIGT ---")
    print(f"Ich habe {count} Bilder extrahiert.")
    print(f"Bitte öffne den Ordner: {temp_dir.absolute()}")
    
    exclude_input = input("\nWelche Bild-Nummern sollen ENTFERNT werden? (z.B. '1, 4, 7'): ")
    
    exclude_indices = []
    if exclude_input.strip():
        exclude_indices = [int(x.strip()) for x in exclude_input.split(",") if x.strip().isdigit()]

    # Phase 2
    output_file = processor.process_phase_2(exclude_indices)
    print(f"Fertig! Markdown: {output_file}")

if __name__ == "__main__":
    # We allow running it directly still
    run_cli()