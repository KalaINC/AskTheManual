# AskTheManual – A Multimodal RAG-PoC

**AskTheManual** is a Multimodal Retrieval-Augmented Generation (RAG) Proof of Concept designed to read, see, and explain manuals to your customers by making it a Chatbot. Unlike standard RAG systems that only process text, this pipeline extracts images from PDFs, analyzes them using Vision AI, and integrates that visual context into a searchable knowledge base.

##  What it is
This project transforms static PDF manuals into an interactive, image-aware chatbot. It follows a multi-stage pipeline:
1.  **Extraction:** Uses `Docling` to convert PDFs to Markdown while preserving table structures and extracting images.
2.  **Human-in-the-Loop Review:** Allows users to filter out "junk" images (icons, decorative elements) before processing.
3.  **Vision Enrichment:** Uses OpenAI's Vision models to describe screenshots (e.g., "Window: Settings, Value: Server IP: 127.0.0.1"), turning pixels into searchable text.
4.  **Vector Indexing:** Chunks the enriched Markdown and stores it in a `FAISS` vector database using `MiniLM` embeddings.
5.  **Local Chat:** A `Streamlit` dashboard that queries the database and generates answers using a local `Ollama` instance.

##  Advantages

###  Local Control & Privacy
By using **Ollama** and **FAISS** locally, the core "brain" of your chatbot stays on your or the customer's infrastructure. Your proprietary manuals aren't sent to a third-party LLM for the final answer generation, ensuring data sovereignty.

###  No "Black Box"
Unlike proprietary "black box" solutions, AskTheManual gives the document owner total visibility and control over the entire pipeline:
*   **Extraction Control:** See exactly what text and tables are extracted before they hit the database.
*   **Image Curation:** You decide which images are relevant and which are "junk."
*   **Flexible Enrichment:** You can choose to use Cloud Vision AI for descriptions, write your own manual explanations in the Markdown, or let the LLM associate raw images with surrounding text.
*   **Model Transparency:** You choose which local LLMs and embedding models are used, ensuring you know exactly how your data is being processed.

###  Multimodal Understanding
Most RAG systems are "blind" to images. AskTheManual treats screenshots as first-class citizens. By indexing descriptions of what is *inside* a screenshot (fields, checkboxes, paths), the AI can answer questions like "What should the default server IP look like in the settings window?" even if that information only exists visually.

###  Human-in-the-Loop
The extraction process includes a review step. This ensures that only relevant technical diagrams and screenshots enter the vector store, keeping the index clean and the AI's context window focused.

![Workflow](./workflow_ENG.svg)

##  Dependencies

The project relies on the following core libraries:
- **UI:** `streamlit`
- **PDF Processing:** `docling`
- **Vector Store:** `faiss-cpu`, `langchain-community`
- **Embeddings:** `langchain-huggingface`, `sentence-transformers`
- **LLM Integration:** `requests` (for Ollama API), `openai` (for Vision enrichment)

## Installation & Setup

### 1. Install Python Requirements
Ensure you have Python 3.10+ installed, then run:
```bash
pip install streamlit docling langchain-huggingface langchain-community faiss-cpu sentence-transformers requests
```

### 2. Setup Ollama (Local LLM)
- Download and install **Ollama** from ollama.com.
- Pull the required model:
  ```bash
  ollama pull qwen2.5:7b
  ```
- Ensure the Ollama server is running (usually on port 11434).

### 3. Setup DocLing
DocLing is used for high-fidelity PDF parsing. It is installed via pip (included in step 1). On first run, it may download necessary AI models for layout analysis.

### 4. Embeddings (MiniLM)
The project uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. You don't need to download this manually; `langchain-huggingface` will fetch it automatically during the first indexing run.

### 5. OpenAI API Key (For Vision)
To use the `image_to_information.py` script, you need an OpenAI API key.
- Export it as an environment variable or edit the `OPENAI_API_KEY` variable in the script.  

You can of course use any preferred AI provider of your liking. Just be sure it can process images as input.  

## 📂 Project Workflow

### 1. Ingest & Review (Required)
Run `unified_extraction_review.py` to process your PDF. This step includes a **Human-in-the-Loop** review where you manually select which images to keep and which to discard.

### 2. Enrich (Optional)
Enhance your documentation by adding AI-generated descriptions to extracted images.
*   **Preview & Cost Optimization:** Before running the full enrichment, use `image_to_information_testing.py`. This script generates an `openai_prompts_preview.json` file, allowing you to inspect the exact text context and API payload that would be sent to the Vision AI. This is crucial for verifying that the "debug_context_used" is accurate before you incur token costs.
*   **Execution:** Run `image_to_information.py` to perform the actual analysis and update your Markdown with `[AI-ANALYSIS]` tags.

> **Note:** If you skip this step, ensure you adjust the system prompt in `chatbot_dashboard.py`. Without enrichment, the LLM should be instructed to reference images based on their proximity to relevant text rather than relying on descriptive AI analysis tags.

### 3. Index & Chat
*   **Index:** Run `vector_transformer.py` to create or update the FAISS vector database.
*   **Chat:** Launch the interactive dashboard:
    ```bash
    streamlit run chatbot_dashboard.py
    ```

---

### ⚠️ Disclaimer
This PoC is currently intended for demonstration and internal testing purposes. The provided dashboard is a visual prototype to showcase the technology. For production use, you should develop a custom chat interface tailored to your specific software environment and evaluate whether to host the AI models on local customer hardware or your own or third-party centralized secure servers.

---
*Developed as a PoC for Documentation Intelligence.*