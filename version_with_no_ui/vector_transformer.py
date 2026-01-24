import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def update_or_create_vector_index(md_file_path, index_path="faiss_index"):
    print(f"--- Processing: {md_file_path} ---")
    
    # 1. Read file
    with open(md_file_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 2. Splitting (your proven workflow)
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = markdown_splitter.split_text(md_text)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, 
        chunk_overlap=200, # A little more overlap so that image paths are not "cut off" at the edge
        separators=["\n## ", "\n### ", "\n![", "\n\n", "\n"] 
    )
    splits = text_splitter.split_documents(md_header_splits)

    # 3. Initialize embeddings
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings = HuggingFaceEmbeddings(model_name=model_name)

    # 4. Logic: Extend or create new
    if os.path.exists(index_path):
        print(f"Existing index found. Adding {len(splits)} chunks...")
        # Load index
        # IMPORTANT: allow_dangerous_deserialization=True is mandatory for local FAISS
        vector_db = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        # Add new documents
        vector_db.add_documents(splits)
    else:
        print(f"No index found under '{index_path}'. Creating new index...")
        vector_db = FAISS.from_documents(splits, embeddings)

    # 5. Save (now overwrites the folder with the updated state)
    vector_db.save_local(index_path)
    print(f"--- Index successfully updated under '{index_path}' ---")

if __name__ == "__main__":
    # You can now run different files one after the other
    update_or_create_vector_index("extracted_data/documentname_mapped_enriched.md")
    #update_or_create_vector_index("extracted_data/all_others_enriched.md")