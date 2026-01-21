import streamlit as st
import os
import re
import requests
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# --- CONFIGURATION ---
SERVER_IP = "127.0.0.1" 
OLLAMA_URL = f"http://{SERVER_IP}:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"
INDEX_PATH = "faiss_index"
IMAGE_BASE_DIR = Path("extracted_data") # Base folder of your data

# --- UI SETUP ---
st.set_page_config(page_title="Manual AI Chatbot", page_icon="🤖", layout="wide")

# CSS for nicer images and chat layout
st.markdown("""
    <style>
    .stImage { border: 2px solid #444; border-radius: 8px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3); }
    .source-box { background-color: #1e1e1e; padding: 10px; border-radius: 5px; border-left: 3px solid #00ff00; margin-bottom: 10px; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 Manual Chatbot")

# --- LOAD RESOURCES ---
@st.cache_resource
def load_resources():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_db = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    return vector_db

vector_db = load_resources()

# --- LOGIC FUNCTION ---
def ask_local_professor(query):
    docs = vector_db.similarity_search(query, k=5)
    
    context = ""
    source_chunks = []
    for doc in docs:
        header = doc.metadata.get('Header 2') or doc.metadata.get('Header 1') or "General"
        context += f"\n---\nCHAPTER: {header}\n{doc.page_content}\n"
        source_chunks.append({"header": header, "content": doc.page_content})

    system_prompt = (
        "You are the wiki expert for various software systems. Use the CONTEXT.\n"
        "IMPORTANT FOR IMAGES:\n"
        "1. Images are now in subfolders, e.g. images/softwarename/diagram_1.png.\n"
        "2. Identify ALL image paths in the context that match your answer.\n"
        "3. At the end of your answer, DEFINITELY name the complete paths under 'IMAGE_REFERENCE:'.\n"
        "4. Use exactly the path that is in the context (including the software folder)."
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt}\n\nCONTEXT:\n{context}\n\nQUESTION: {query}",
        "stream": False 
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=45)
        response.raise_for_status()
        answer = response.json()['response']
        
        # IMPROVED REGEX: Finds paths like images/softwarename/diagram_1.png
        # It searches for: (optional images/) + (any folder name/) + diagram_X.png
        raw_images = re.findall(r"(?:images/)?[\w-]+/diagram_\d+\.png", answer)
        
        # If the AI names the path incompletely (e.g. only "softwarename/diagram_1.png")
        clean_images = []
        for img in raw_images:
            if not img.startswith("images/"):
                img = f"images/{img}"
            clean_images.append(img)
            
        clean_answer = answer.split("IMAGE_REFERENCE:")[0].strip()
        return clean_answer, list(set(clean_images)), source_chunks
    except Exception as e:
        return f"Error connecting to Ollama: {e}", [], []

# --- SIDEBAR: SOURCE CHECK ---
with st.sidebar:
    st.header("🔍 Source Inspector")
    st.info("Here you can see the text sections that the AI is currently using as a basis.")
    if "last_sources" in st.session_state:
        for src in st.session_state.last_sources:
            st.markdown(f"**Chapter: {src['header']}**")
            st.markdown(f"<div class='source-box'>{src['content']}</div>", unsafe_allow_html=True)
    else:
        st.write("No request has been made yet.")

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "images" in message:
            for img in message["images"]:
                # Absolute path check
                full_path = IMAGE_BASE_DIR / img
                if full_path.exists():
                    st.image(str(full_path), caption=f"Screenshot: {img}")

if prompt := st.chat_input("Question about the manual..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Professor is searching the manual..."):
            answer, images, sources = ask_local_professor(prompt)
            st.session_state.last_sources = sources # Save for the sidebar
            st.markdown(answer)
            
            if images:
                # Display images in columns if there are several
                cols = st.columns(min(len(images), 2)) 
                for idx, img in enumerate(images):
                    full_path = IMAGE_BASE_DIR / img
                    if full_path.exists():
                        cols[idx % 2].image(str(full_path), caption=f"Reference: {img}")
                    else:
                        st.error(f"Path error: {full_path} not found!")
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": answer, 
                "images": images
            })
            # Update sidebar (trigger rerun)
            st.rerun()