import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def update_or_create_vector_index(md_file_path, index_path="faiss_index"):
    print(f"--- Verarbeite: {md_file_path} ---")
    
    # 1. Datei einlesen
    with open(md_file_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 2. Splitting (dein bewährter Workflow)
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = markdown_splitter.split_text(md_text)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, 
        chunk_overlap=200, # Etwas mehr Overlap, damit Bildpfade nicht am Rand "abgeschnitten" werden
        separators=["\n## ", "\n### ", "\n![", "\n\n", "\n"] 
    )
    splits = text_splitter.split_documents(md_header_splits)

    # 3. Embeddings initialisieren
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings = HuggingFaceEmbeddings(model_name=model_name)

    # 4. Logik: Erweitern oder Neu erstellen
    if os.path.exists(index_path):
        print(f"Bestehender Index gefunden. Füge {len(splits)} Chunks hinzu...")
        # Index laden
        # WICHTIG: allow_dangerous_deserialization=True ist bei lokalem FAISS Pflicht
        vector_db = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        # Neue Dokumente hinzufügen
        vector_db.add_documents(splits)
    else:
        print(f"Kein Index unter '{index_path}' gefunden. Erstelle neuen Index...")
        vector_db = FAISS.from_documents(splits, embeddings)

    # 5. Speichern (überschreibt jetzt den Ordner mit dem aktualisierten Stand)
    vector_db.save_local(index_path)
    print(f"--- Index erfolgreich aktualisiert unter '{index_path}' ---")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Update Vector Index with Markdown content")
    parser.add_argument("file", nargs="?", help="Path to the enriched Markdown file")
    
    args = parser.parse_args()
    
    if args.file:
        update_or_create_vector_index(args.file)
    else:
        print("Usage: python vector_transformer.py <path_to_markdown>")
        # Fallback debug if needed, or just exit cleanly
        # update_or_create_vector_index("extracted_data/charly_mapped_enriched.md")