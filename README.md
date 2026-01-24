# AskTheManual – A Multimodal RAG-PoC

**AskTheManual** is a Multimodal Retrieval-Augmented Generation (RAG) Proof of Concept designed to read, see, and explain manuals to your customers. It transforms static PDF manuals into an interactive chatbot that understands both text and images.

**New:** Now features a **Guided User Interface (GUI)** to make the data ingestion process simple and intuitive!

![image](./GUI.png)

##  What it is
This project follows a multi-stage pipeline to create a searchable knowledge base:
1.  **Extraction:** Converts detailed PDF manuals into Markdown.
2.  **Human-in-the-Loop Review:** A GUI allows you to filter out "junk" images (icons, decorative elements) and keep only relevant diagrams.
3.  **Vision Enrichment:** Uses AI (or human input) to describe screenshots, turning visual information into searchable text.
4.  **Vector Indexing:** Stores the enriched content in a local vector database.
5.  **Local Chat:** A Streamlit dashboard to query your manual.

##  Advantages
*   **Local Control & Privacy:** Uses local **Ollama** and **FAISS** for the core "brain". Your proprietary manual text stays local.
*   **No "Black Box":** You control the extraction. You decide which images strictly belong in the knowledge base.
*   **Multimodal:** The bot understands what's inside screenshots (e.g., "The default IP is 127.0.0.1") because the ingestion pipeline explicitly captures it.

![Workflow](./workflow_ENG.svg)

---

## 🛠️ Installation

### 1. Requirements
Ensure you have Python 3.10+ installed.

```bash
pip install streamlit docling langchain-huggingface langchain-community faiss-cpu sentence-transformers requests ttkbootstrap openai
```
*(Note: `ttkbootstrap` is required for the new GUI.)*

### 2. Setup Ollama (Local LLM)
1.  Install **Ollama** from [ollama.com](https://ollama.com).
2.  Pull a model (e.g., Qwen 2.5):
    ```bash
    ollama pull qwen2.5:7b
    ```
3.  Make sure the Ollama server is running.

### 3. OpenAI API Key (Optional but Recommended)
For automatic image description (**Vision AI**), you need an OpenAI API key. 
-   Export it: `export OPENAI_API_KEY="sk-..."` 
-   Or paste it into `image_to_information.py` (not recommended for production).

---

## 📂 Usage Workflow

### Step 1: Ingest & Process (The GUI)
We have replaced the complex script chain with a single App.

Run the GUI:
```bash
python AskTheManual_GUI.py
```

**The App will guide you through 3 stages:**

1.  **Extraction & Review**:
    *   Select your PDF. (it has to be in the main directory of the projectfolder)
    *   The app extracts all images.
    *   **Interactive Review**: A gallery appears. Use **Arrow Keys** to navigate. Press **'DELETE'** to Delete junk images, **'KEEP'** to Keep valid ones.
    
2.  **Enrichment**:
    *   **Vision AI (Auto but maybe not every description is correct)**: Sends kept images to OpenAI to generate detailed technical descriptions.
    *   **Human Description (recommended - if you want to be sure everything is correct)**: If you don't have an API key, you can manually type descriptions for each image in the GUI.

3.  **Indexing**:
    *   Click "Update Vector Index" to finalize the database.

### Step 2: Chat with your Manual
Once indexing is complete, launch the chat interface:

```bash
streamlit run chatbot_dashboard.py
```

---

## ⚠️ Disclaimer
This PoC is intended for internal testing and demonstration. It serves as a blueprint for how technical documentation can be made "intelligent" by combining text parsers, Vision AI, and Vector Search.
