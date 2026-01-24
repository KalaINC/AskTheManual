import os
import re
import base64
import requests
import json
from pathlib import Path

# Configuration
OPENAI_API_KEY = "Your_KEY"
MD_INPUT_FILE = "extracted_data/documentname_mapped.md"
IMAGE_BASE_DIR = "extracted_data"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_chapter_contexts(lines):
    """
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

def get_vision_description(image_path, heading, context_text):
    base64_image = encode_image(image_path)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    prompt = (
        f"You are a technical documentation expert.\n"
        f"Chapter: {heading}\n"
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

    payload = {
        "model": "gpt-5-nano-2025-08-07", # Recommendation for stable vision results
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    }
                ]
            }
        ]
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return response.json()['choices'][0]['message']['content']

def enrich_markdown():
    with open(MD_INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Step 1: Pre-calculate entire chapter context
    chapter_contexts = get_chapter_contexts(lines)
    
    enriched_content = []
    current_heading = "General"
    
    # Step 2: Process document and analyze images
    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
        
        enriched_content.append(line)
        
        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        if img_match:
            img_rel_path = img_match.group(1)
            full_img_path = Path(IMAGE_BASE_DIR) / img_rel_path
            
            if full_img_path.exists():
                print(f"Analyzing {img_rel_path} in '{current_heading}'...")
                
                # Get the clean text for this chapter
                context = chapter_contexts.get(current_heading, "")
                
                try:
                    description = get_vision_description(full_img_path, current_heading, context)
                    enriched_content.append(f"\n> [AI-ANALYSIS: {description.strip()}]\n\n")
                except Exception as e:
                    print(f"Error with {img_rel_path}: {e}")
                    enriched_content.append("\n> [AI-ANALYSIS failed]\n\n")

    output_path = Path(MD_INPUT_FILE).parent / f"{Path(MD_INPUT_FILE).stem}_enriched.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(enriched_content)
    
    print(f"--- Enrichment complete: {output_path} ---")

if __name__ == "__main__":
    enrich_markdown()