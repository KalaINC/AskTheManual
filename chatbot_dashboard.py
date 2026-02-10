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
IMAGE_BASE_DIR = Path("extracted_data") 

# --- UI SETUP ---
st.set_page_config(page_title="Handbuch KI Chatbot", page_icon="", layout="wide")

# CSS für schönere Bilder und Chat-Layout
st.markdown("""
    <style>
    .stImage { border: 2px solid #444; border-radius: 8px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3); }
    .source-box { background-color: #1e1e1e; padding: 10px; border-radius: 5px; border-left: 3px solid #00ff00; margin-bottom: 10px; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("Handbuch Chatbot")

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
        "Du bist ein hilfreicher interner Experte für unsere Software. Deine Aufgabe ist es, Fragen basierend auf dem folgenden HANDBUCH-KONTEXT zu beantworten.\n\n"
        
        "ANWEISUNGEN:\n"
        "1. ANALYSE: Verstehe das Problem des Nutzers. Ignoriere irrelevante Füllwörter (z.B. 'Mein Chef sagt', 'Ich bin genervt'). Konzentriere dich auf den technischen Kern.\n"
        "2. WISSENSBASIS: Nutze NUR die Informationen aus dem untenstehenden KONTEXT. Erfinde keine Fakten.\n"
        "3. TRANSFERLEISTUNG: Wenn der Nutzer Begriffe verwendet, die nicht exakt im Text stehen (z.B. 'verknüpfen' statt 'integrieren' oder 'Knopf' statt 'Button'), erkenne den Sinn und antworte trotzdem.\n"
        "4. Identifiziere ALLE Bildpfade im Kontext, die zu deiner Antwort passen, versuche jedoch redundanz zu vermeiden, nutze hierfür die für dich vorbereiteten Bildbeschreibungen. Nenne am Ende deiner Antwort UNBEDINGT die vollständigen Pfade unter 'BILD_REFERENZ:'.\n"
        "5. SRACHE: Antworte professionell, direkt und per 'Du'.\n\n"
        
        "WICHTIG:\n"
        "Wenn der Kontext KEINE Lösung für das technische Problem bietet, antworte, ohne Bilder anzuhängen:\n"
        "'Dazu liegen mir im aktuellen Handbuch keine Informationen vor. Bitte wende dich an unsere Hotline.'\n"
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt}\n\n{history_context}\nKONTEXT:\n{context}\n\nAKTUELLE FRAGE: {query}",
        "stream": False,
        "options": {
            "temperature": 0.1 
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=45)
        response.raise_for_status()
        full_response = response.json()['response']
        
        # --- BILD-EXTRAKTION (Dein existierender Code, leicht optimiert) ---
        raw_images = re.findall(r"(?:images/)?[\w-]+/diagramm_\d+\.png", full_response)
        
        clean_images = []
        for img in raw_images:
            if not img.startswith("images/"):
                img = f"images/{img}"
            clean_images.append(img)
            
        # Text bereinigen (Pfade im Text entfernen, damit sie nicht doppelt wirken)
        clean_answer = full_response
        for img in raw_images:
            clean_answer = clean_answer.replace(img, "")
            
        # Markdown-Bildreste entfernen
        clean_answer = re.sub(r'!\[.*?\]\(\s*\)', '', clean_answer)
        clean_answer = re.sub(r'Bild_Referenz:?', '', clean_answer, flags=re.IGNORECASE)
        clean_answer = re.sub(r'^\s*[\*\-\•]\s*$', '', clean_answer, flags=re.MULTILINE)
        clean_answer = re.sub(r'\n\s*\n', '\n\n', clean_answer).strip()
        clean_answer = clean_answer.strip()
        
        # Duplikate entfernen und sortieren
        seen = set()
        unique_images = []
        for img in clean_images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)
        
        # Nach Diagramm-Nummer sortieren (diagramm_3 vor diagramm_4)
        def extract_number(path):
            match = re.search(r'diagramm_(\d+)', path)
            return int(match.group(1)) if match else 0
        
        unique_images.sort(key=extract_number)
        
        return clean_answer, unique_images, source_chunks

    except Exception as e:
        return f"Fehler bei der Verbindung zu Ollama: {e}", [], []

# --- SIDEBAR: QUELLEN-CHECK ---
with st.sidebar:
    st.header("Quellen")
    st.info("Textabschnitte, die die KI gerade als Basis nutzt.")
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