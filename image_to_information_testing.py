import re
import json
from pathlib import Path

# Configuration (Sync with main script)
MD_INPUT_FILE = "extracted_data/documentname_mapped.md"

def get_chapter_contexts(lines):
    """
    IDENTICAL TO MAIN SCRIPT:
    Extracts the pure text content for each chapter (heading).
    Image links are removed to avoid noise in the context.
    """
    contexts = {}
    current_h = "General"
    current_text = []

    for line in lines:
        # Check for heading (H1 to H3)
        heading_match = re.match(r"^#{1,3}\s+(.*)$", line)
        if heading_match:
            # Save old context
            contexts[current_h] = "\n".join(current_text).strip()
            # New chapter name
            current_h = heading_match.group(1).strip()
            current_text = []
        else:
            # Remove image links from the context text
            clean_line = re.sub(r"!\[.*?\]\(.*?\)", "", line).strip()
            if clean_line:
                current_text.append(clean_line)
    
    # Save last chapter
    contexts[current_h] = "\n".join(current_text).strip()
    return contexts

def generate_openai_prompts(md_file_path):
    if not Path(md_file_path).exists():
        return f"Error: File {md_file_path} not found."

    with open(md_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # PHASE 1: Pre-calculate chapter contexts (identical to main script)
    chapter_contexts = get_chapter_contexts(lines)
    
    current_heading = "General"
    prompts_to_review = []
    
    # PHASE 2: Go through document and build payload preview
    for i, line in enumerate(lines):
        # Update the current heading
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue
            
        # Search for image references
        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        if img_match:
            img_rel_path = img_match.group(1)
            
            # Get the clean chapter text
            context_text = chapter_contexts.get(current_heading, "")
            
            # The identical generalized prompt
            prompt = (
                f"You are a technical documentation expert.\n"
                f"Chapter: {current_heading}\n"
                f"Context of the chapter: {context_text}\n\n"
                "Task: Analyze the screenshot and create an EXTREMELY SHORT, bulleted summary of the CURRENT state.\n\n"
                "Rules:\n"
                "1. Identify the window title and the active tab.\n"
                "2. Describe ONLY filled fields and activated checkboxes.\n"
                "3. Ignore standard elements (OK, Cancel, Help).\n"
                "4. Do not use introductory sentences.\n"
                "5. Capture exact paths and file names.\n\n"
                "Format:\n"
                "Window: [Title] ([Tab])\n"
                "Values: [Field name]: [Value], [Option]: [On/Off]"
            )

            prompts_to_review.append({
                "image_file": img_rel_path,
                "context_heading": current_heading,
                "debug_context_used": context_text, # Here you can see the filtered chapter text in the JSON
                "api_payload_preview": {
                    "model": "gpt-5-nano-2025-08-07",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,...(IMAGE-DATA)..."}
                                }
                            ]
                        }
                    ]
                }
            })

    # Save results
    output_path = Path("openai_prompts_preview.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts_to_review, f, indent=4, ensure_ascii=False)
    
    return output_path

if __name__ == "__main__":
    preview_file = generate_openai_prompts(MD_INPUT_FILE)
    print(f"--- Synchronized preview was created: {preview_file} ---")
    print("In the JSON, especially check the 'debug_context_used' field for cleanliness.")