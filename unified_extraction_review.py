import time
import re
import shutil
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.document import PictureItem

def run_unified_ingestor_with_review(pdf_filename):
    start_time = time.time()
    pdf_path = Path(pdf_filename)
    output_dir = Path("extracted_data")
    
    # 1. Here we get the PDF name (e.g. "softwarename" from "softwarename.pdf")
    software_name = pdf_path.stem 
    
    temp_image_dir = output_dir / "temp_review"
    
    # 2. We append the name to the image path
    final_image_dir = output_dir / "images" / software_name
    
    # Clean/create folder (mkdir ensures that 'images' is also created)
    if temp_image_dir.exists(): shutil.rmtree(temp_image_dir)
    temp_image_dir.mkdir(parents=True, exist_ok=True)
    
    # If the specific software folder exists, we delete it for a clean run
    if final_image_dir.exists(): shutil.rmtree(final_image_dir)
    final_image_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean/create folder
    for d in [temp_image_dir, final_image_dir]:
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # 1. Conversion (DocLing)
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = True 
    pipeline_options.images_scale = 2.0 

    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )

    print(f"--- Analysis running: {pdf_filename} ---")
    result = converter.convert(pdf_path)
    md_content = result.document.export_to_markdown()

    # 2. Extract all images for review
    all_images = []
    for item, _ in result.document.iterate_items():
        if isinstance(item, PictureItem):
            visual_crop = item.get_image(result.document)
            if visual_crop:
                all_images.append(visual_crop)

    if not all_images:
        print("No images found in the document.")
        return

    # Save images temporarily so the user can view them
    for i, img in enumerate(all_images, 1):
        img.save(temp_image_dir / f"image_{i}.png")

    print(f"\n--- REVIEW REQUIRED ---")
    print(f"I have extracted {len(all_images)} images.")
    print(f"Please open the folder: {temp_image_dir.absolute()}")
    print("Look at the images (image_1.png, image_2.png, etc.).")
    
    exclude_input = input("\nWhich image numbers should be REMOVED? (e.g. '1, 4, 7' or Enter to keep all): ")
    
    # Process input
    exclude_indices = []
    if exclude_input.strip():
        exclude_indices = [int(x.strip()) for x in exclude_input.split(",") if x.strip().isdigit()]

    # 3. Move final images and prepare mapping
    final_mapping = {}
    current_final_id = 1
    
    for i in range(1, len(all_images) + 1):
        if i in exclude_indices:
            final_mapping[i] = None
        else:
            new_name = f"diagram_{current_final_id}.png"
            shutil.move(temp_image_dir / f"image_{i}.png", final_image_dir / new_name)
            
            # HERE: We write the subfolder into the path for the Markdown
            final_mapping[i] = f"images/{software_name}/{new_name}"
            current_final_id += 1

    # 4. Adjust Markdown
    # We use a counter to know which tag we are at
    tag_counter = {"count": 0}

    def replace_logic(match):
        tag_counter["count"] += 1
        idx = tag_counter["count"]
        
        path = final_mapping.get(idx)
        if path:
            return f"![Extracted image]({path})"
        else:
            return "" # Remove tag completely if image was junk

    final_md = re.sub(r"<!-- image -->", replace_logic, md_content)

    # 5. Conclusion
    output_file = output_dir / f"{pdf_path.stem}_mapped.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_md)
    
    # Clean up temp folder
    shutil.rmtree(temp_image_dir)
    
    print(f"\n--- Done! ---")
    print(f"Images saved in: {final_image_dir}")
    print(f"Markdown created: {output_file}")

if __name__ == "__main__":
    run_unified_ingestor_with_review("documentname.pdf")