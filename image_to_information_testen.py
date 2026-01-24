import re
import json
from pathlib import Path

# Konfiguration (Sync mit Hauptskript)
MD_INPUT_FILE = "extracted_data/documentname_mapped.md"

def get_chapter_contexts(lines):
    """
    IDENTISCH ZUM HAUPTSKRIPT:
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

def generate_openai_prompts(md_file_path):
    if not Path(md_file_path).exists():
        return f"Fehler: Datei {md_file_path} nicht gefunden."

    with open(md_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # PHASE 1: Kapitel-Kontexte vorab berechnen (identisch zum Hauptskript)
    chapter_contexts = get_chapter_contexts(lines)
    
    current_heading = "Allgemein"
    prompts_to_review = []
    
    # PHASE 2: Dokument durchlaufen und Payload-Vorschau bauen
    for i, line in enumerate(lines):
        # Update die aktuelle Überschrift
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue
            
        # Suche nach Bild-Referenzen
        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        if img_match:
            img_rel_path = img_match.group(1)
            
            # Hol den sauberen Kapitel-Text
            context_text = chapter_contexts.get(current_heading, "")
            
            # Der identische generalisierte Prompt
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

            prompts_to_review.append({
                "image_file": img_rel_path,
                "context_heading": current_heading,
                "debug_context_used": context_text, # Hier siehst du im JSON den gefilterten Kapiteltext
                "api_payload_preview": {
                    "model": "gpt-5-nano-2025-08-07",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,...(BILD-DATEN)..."}
                                }
                            ]
                        }
                    ]
                }
            })

    # Ergebnisse speichern
    output_path = Path("openai_prompts_preview.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts_to_review, f, indent=4, ensure_ascii=False)
    
    return output_path

if __name__ == "__main__":
    preview_file = generate_openai_prompts(MD_INPUT_FILE)
    print(f"--- Synchronisierte Vorschau wurde erstellt: {preview_file} ---")
    print("Prüfe in der JSON besonders das Feld 'debug_context_used' auf Sauberkeit.")