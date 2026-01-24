import os
import re
import base64
import requests
import json
from pathlib import Path

# Konfiguration
OPENAI_API_KEY = "Your_API_KEY"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_chapter_contexts(lines):
    """
    Extrahiert den reinen Textinhalt für jedes Kapitel (Überschrift).
    Bilder-Links werden entfernt, um Rauschen im Kontext zu vermeiden.
    """
    contexts = {}
    current_h = "Allgemein"
    current_text = []

    for line in lines:
        # Prüfung auf Überschrift (H1 bis H3)
        heading_match = re.match(r"^#{1,3}\s+(.*)$", line)
        if heading_match:
            # Speichere alten Kontext ab
            contexts[current_h] = "\n".join(current_text).strip()
            # Neuer Kapitel-Name
            current_h = heading_match.group(1).strip()
            current_text = []
        else:
            # Entferne Bild-Links aus dem Kontext-Text
            clean_line = re.sub(r"!\[.*?\]\(.*?\)", "", line).strip()
            if clean_line:
                current_text.append(clean_line)
    
    # Letztes Kapitel sichern
    contexts[current_h] = "\n".join(current_text).strip()
    return contexts

def get_vision_description(image_path, heading, context_text, api_key=None):
    key_to_use = api_key if api_key else OPENAI_API_KEY
    if not key_to_use or key_to_use == "Your_API_KEY":
        raise ValueError("Missing OpenAI API Key")

    base64_image = encode_image(image_path)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key_to_use}"
    }

    prompt = (
        f"Du bist ein Senior Technical Author für Software-Handbücher.\n"
        f"Kapitel: {heading}\n"
        f"Kontext (Handlungsanweisung): {context_text}\n\n"
        "Aufgabe: Extrahiere die ZIEL-Konfiguration (Soll-Zustand) unter Synthese von Textanweisung und Screenshot.\n\n"
        "Analyse-Logik:\n"
        "1. Intent-Präzedenz: Die Textanweisungen im 'Kontext' haben absolute Priorität vor dem visuellen Zustand. Sagt der Text 'Aktivieren Sie X', dokumentiere 'X: An', auch wenn der Screenshot 'Aus' zeigt.\n"
        "2. Kontext-Mapping: Suche im Text nach spezifischen Werten (Pfade, IP-Adressen, Checkbox-Status) und ordne sie den UI-Elementen im Bild zu.\n"
        "3. Visueller Fallback: Dokumentiere den visuellen IST-Zustand aus dem Screenshot NUR dann, wenn der Text keine widersprüchlichen oder ergänzenden Anweisungen für dieses Element enthält.\n"
        "4. Annotationen als Workflow: Behandle visuelle Marker (Zahlen, Pfeile) als chronologische Schritte zum Erreichen des Soll-Zustands.\n"
        "5. Diskrepanz-Check: Falls Bild und Text massiv widersprüchlich sind (z.B. Text beschreibt ein Feld, das im Bild fehlt), markiere dies als [DOKU-FEHLER].\n\n"
        "Format:\n"
        "Fenster: [Pfad/Hierarchie]\n"
        "Workflow: [Schritt] > [Element] > [Ziel-Aktion laut Text/Bild]\n"
        "Soll-Konfiguration: [Feldname]: [Wert] (Priorität: Text-Anweisung)"
    )

    payload = {
        "model": "gpt-5-nano-2025-08-07", # Updated to a widely available vision model
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
    if response.status_code != 200:
         raise Exception(f"API Error: {response.text}")
         
    return response.json()['choices'][0]['message']['content']

def enrich_file(md_path, api_key=None, progress_callback=None):
    """
    Reads the markdown file, analyzes images, and appends the analysis.
    Returns the path to the new file.
    progress_callback: function(current, total, message)
    """
    input_path = Path(md_path)
    if not input_path.exists():
        raise FileNotFoundError(f"{md_path} not found")

    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Schritt 1: Gesamten Kapitel-Kontext vorab berechnen
    chapter_contexts = get_chapter_contexts(lines)
    
    enriched_content = []
    current_heading = "Allgemein"
    image_base_dir = input_path.parent 
    
    # Pre-count images for progress
    total_images = sum(1 for line in lines if re.search(r"!\[.*?\]\((.*?)\)", line))
    processed_images = 0
    
    # Schritt 2: Dokument verarbeiten und Bilder analysieren
    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
        
        enriched_content.append(line)
        
        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        if img_match:
            processed_images += 1
            img_rel_path = img_match.group(1)
            full_img_path = image_base_dir / img_rel_path
            
            if full_img_path.exists():
                msg = f"Analyzing {processed_images}/{total_images}: {img_rel_path}..."
                print(msg)
                if progress_callback:
                    progress_callback(processed_images, total_images, msg)
                
                # Hol den sauberen Text für dieses Kapitel
                context = chapter_contexts.get(current_heading, "")
                
                try:
                    description = get_vision_description(full_img_path, current_heading, context, api_key)
                    enriched_content.append(f"\n> [KI-ANALYSE: {description.strip()}]\n\n")
                except Exception as e:
                    print(f"Fehler bei {img_rel_path}: {e}")
                    enriched_content.append(f"\n> [KI-ANALYSE fehlgeschlagen: {str(e)}]\n\n")
            else:
               if progress_callback:
                    progress_callback(processed_images, total_images, f"Skipping missing: {img_rel_path}")

    output_path = input_path.parent / f"{input_path.stem}_enriched.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(enriched_content)
    
    print(f"--- Enrichment abgeschlossen: {output_path} ---")
    return str(output_path)

if __name__ == "__main__":
    # Test run
    # enrich_file("extracted_data/test.md")
    pass