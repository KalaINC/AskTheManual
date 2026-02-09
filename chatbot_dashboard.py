import streamlit as st
import os
import re
import requests
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# --- KONFIGURATION ---
SERVER_IP = "127.0.0.1" 
OLLAMA_URL = f"http://{SERVER_IP}:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"
INDEX_PATH = "faiss_index"
IMAGE_BASE_DIR = Path("extracted_data") # Basis-Ordner deiner Daten

# --- UI SETUP ---
st.set_page_config(page_title="Handbuch KI Chatbot", page_icon="🤖", layout="wide")

# CSS für schönere Bilder und Chat-Layout
st.markdown("""
    <style>
    .stImage { border: 2px solid #444; border-radius: 8px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3); }
    .source-box { background-color: #1e1e1e; padding: 10px; border-radius: 5px; border-left: 3px solid #00ff00; margin-bottom: 10px; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 Handbuch Chatbot")

# --- RESSOURCEN LADEN ---
@st.cache_resource
def load_resources():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_db = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    return vector_db

vector_db = load_resources()

# --- LOGIK FUNKTION ---
def build_contextual_query(query, chat_history, max_history=3):
    """
    Baut eine erweiterte Suchanfrage aus der aktuellen Frage + letzten Nachrichten.
    Das hilft bei Pronomen wie 'sie', 'es', 'das' die sich auf vorherige Themen beziehen.
    """
    if not chat_history:
        return query
    
    # Letzte N Nachrichten sammeln (nur User + Assistant content)
    recent_context = []
    for msg in chat_history[-max_history * 2:]:  # *2 weil User+Assistant Paare
        recent_context.append(msg["content"][:200])  # Begrenzen um Token zu sparen
    
    # Kombinierte Anfrage für bessere Vektorsuche
    combined = " ".join(recent_context) + " " + query
    return combined

def format_chat_history(chat_history, max_turns=4):
    """
    Formatiert die Chat-Historie für den LLM Prompt.
    """
    if not chat_history:
        return ""
    
    formatted = "\n--- BISHERIGER GESPRÄCHSVERLAUF ---\n"
    # Letzte N Nachrichten-Paare
    for msg in chat_history[-(max_turns * 2):]:
        role = "Kunde" if msg["role"] == "user" else "Assistent"
        # Antworten kürzen um Token zu sparen
        content = msg["content"][:500] if msg["role"] == "assistant" else msg["content"]
        formatted += f"{role}: {content}\n"
    formatted += "--- ENDE GESPRÄCHSVERLAUF ---\n"
    return formatted

def ask_local_professor(query, chat_history=None):
    # Erweiterte Suche: Kontext aus Chat-Historie einbeziehen
    search_query = build_contextual_query(query, chat_history or [])
    docs = vector_db.similarity_search(search_query, k=5)
    
    context = ""
    source_chunks = []
    for doc in docs:
        header = doc.metadata.get('Header 2') or doc.metadata.get('Header 1') or "Allgemein"
        context += f"\n---\nKAPITEL: {header}\n{doc.page_content}\n"
        source_chunks.append({"header": header, "content": doc.page_content})

    # Chat-Historie für den Prompt formatieren
    history_context = format_chat_history(chat_history)

    system_prompt = (
        "Du bist der Wiki-Experte für verschiedene Software-Systeme. Nutze den KONTEXT.\n"
        "WICHTIG: Beachte den BISHERIGEN GESPRÄCHSVERLAUF um Bezüge wie 'sie', 'es', 'das' zu verstehen.\n"
        "Wenn der Kunde z.B. fragt 'Wie starte ich sie?' und vorher über Software X gesprochen wurde, "
        "beziehe dich auf Software X.\n\n"
        "WICHTIG FÜR BILDER:\n"
        "1. Bilder liegen jetzt in Unterordnern, z.B. images/softwarename/diagramm_1.png.\n"
        "2. Identifiziere ALLE Bildpfade im Kontext, die zu deiner Antwort passen.\n"
        "3. Nenne am Ende deiner Antwort UNBEDINGT die vollständigen Pfade unter 'BILD_REFERENZ:'.\n"
        "4. Nutze exakt den Pfad, der im Kontext steht (inklusive Software-Ordner)."
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt}\n\n{history_context}\nKONTEXT:\n{context}\n\nAKTUELLE FRAGE: {query}",
        "stream": False 
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=45)
        response.raise_for_status()
        answer = response.json()['response']
        
        # VERBESSERTER REGEX: Findet Pfade wie images/turbomed/diagramm_1.png
        # Er sucht nach: (optional images/) + (beliebiger Ordnername/) + diagramm_X.png
        raw_images = re.findall(r"(?:images/)?[\w-]+/diagramm_\d+\.png", answer)
        
        # Falls die KI den Pfad unvollständig nennt (z.B. nur "turbomed/diagramm_1.png")
        clean_images = []
        for img in raw_images:
            if not img.startswith("images/"):
                img = f"images/{img}"
            clean_images.append(img)
            
        clean_answer = answer.split("BILD_REFERENZ:")[0].strip()
        return clean_answer, list(set(clean_images)), source_chunks
    except Exception as e:
        return f"Fehler bei der Verbindung zu Ollama: {e}", [], []

# --- SIDEBAR: QUELLEN-CHECK ---
with st.sidebar:
    st.header("🔍 Quellen-Inspektor")
    st.info("Hier siehst du die Textabschnitte, die die KI gerade als Basis nutzt.")
    if "last_sources" in st.session_state:
        for src in st.session_state.last_sources:
            st.markdown(f"**Kapitel: {src['header']}**")
            st.markdown(f"<div class='source-box'>{src['content']}</div>", unsafe_allow_html=True)
    else:
        st.write("Noch keine Anfrage gestellt.")

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "images" in message:
            for img in message["images"]:
                # Absolute Pfadprüfung
                full_path = IMAGE_BASE_DIR / img
                if full_path.exists():
                    st.image(str(full_path), caption=f"Screenshot: {img}")

if prompt := st.chat_input("Frage zum Handbuch..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Professor durchsucht das Handbuch..."):
            answer, images, sources = ask_local_professor(prompt, st.session_state.messages)
            st.session_state.last_sources = sources # Für die Sidebar speichern
            st.markdown(answer)
            
            if images:
                # Bilder in Spalten anzeigen, falls es mehrere sind
                cols = st.columns(min(len(images), 2)) 
                for idx, img in enumerate(images):
                    full_path = IMAGE_BASE_DIR / img
                    if full_path.exists():
                        cols[idx % 2].image(str(full_path), caption=f"Referenz: {img}")
                    else:
                        st.error(f"Pfad-Fehler: {full_path} nicht gefunden!")
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": answer, 
                "images": images
            })
            # Sidebar aktualisieren (Rerun auslösen)
            st.rerun()