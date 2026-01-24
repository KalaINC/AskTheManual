# AskTheManual – A Multimodal RAG-PoC

**AskTheManual** ist ein Proof of Concept (PoC) für Multimodale Retrieval-Augmented Generation (RAG), das entwickelt wurde, um Handbücher für Ihre Kunden zu einem Chatbot umzufunktionieren. Im Gegensatz zu standardmäßigen RAG-Systemen, die nur Text verarbeiten, extrahiert diese Pipeline Bilder aus PDFs, analysiert sie mithilfe von Vision AI und integriert diesen visuellen Kontext in eine durchsuchbare Wissensdatenbank.

##  Was es ist
Dieses Projekt verwandelt statische PDF-Handbücher in einen interaktiven, bildbewussten Chatbot. Es folgt einer mehrstufigen Pipeline:
1.  **Extraktion:** Verwendet `Docling`, um PDFs in Markdown zu konvertieren, wobei Tabellenstrukturen erhalten bleiben und Bilder extrahiert werden.
2.  **Menschliche Überprüfung (Human-in-the-Loop):** Ermöglicht Benutzern, "Junk"-Bilder (Symbole, dekorative Elemente) vor der Verarbeitung herauszufiltern.
3.  **Visuelle Anreicherung:** Verwendet OpenAIs Vision-Modelle, um Screenshots zu beschreiben (z.B. "Fenster: Einstellungen, Wert: Server-IP: 127.0.0.1") und so Pixel in durchsuchbaren Text umzuwandeln.
4.  **Vektorindizierung:** Zerlegt das angereicherte Markdown in Chunks und speichert es in einer `FAISS`-Vektordatenbank unter Verwendung von `MiniLM`-Embeddings.
5.  **Lokaler Chat:** Ein `Streamlit`-Dashboard, das die Datenbank abfragt und Antworten mithilfe einer lokalen `Ollama`-Instanz generiert.

##  Vorteile

###  Lokale Kontrolle & Datenschutz
Durch die lokale Nutzung von **Ollama** und **FAISS** bleibt das Kern-"Gehirn" Ihres Chatbots auf Ihrer oder der Infrastruktur des Kunden. Ihre proprietären Handbücher werden nicht zur Generierung der endgültigen Antwort an ein Drittanbieter-LLM gesendet, wodurch die Datenhoheit gewährleistet ist.

###  Keine "Black Box"
Im Gegensatz zu proprietären "Black Box"-Lösungen bietet AskTheManual dem Dokumentenbesitzer vollständige Transparenz und Kontrolle über die gesamte Pipeline:
*   **Extraktionskontrolle:** Sehen Sie genau, welcher Text und welche Tabellen extrahiert werden, bevor sie in die Datenbank gelangen.
*   **Bildkuratierung:** Sie entscheiden, welche Bilder relevant sind und welche "Müll" sind.
*   **Flexible Anreicherung:** Sie können Cloud Vision AI für Beschreibungen verwenden, Ihre eigenen manuellen Erklärungen im Markdown verfassen oder das LLM rohe Bilder mit dem umgebenden Text assoziieren lassen.
*   **Modelltransparenz:** Sie wählen aus, welche lokalen LLMs und Embedding-Modelle verwendet werden, um sicherzustellen, dass Sie genau wissen, wie Ihre Daten verarbeitet werden.

###  Multimodales Verständnis
Die meisten RAG-Systeme sind "blind" für Bilder. AskTheManual behandelt Screenshots als erstklassige Elemente. Durch die Indizierung von Beschreibungen dessen, was *in* einem Screenshot enthalten ist (Felder, Kontrollkästchen, Pfade), kann die KI Fragen wie "Wie sollte die Standard-Server-IP im Einstellungsfenster aussehen?" beantworten, selbst wenn diese Informationen nur visuell vorhanden sind.

###  Human-in-the-Loop
Der Extraktionsprozess beinhaltet einen Überprüfungsschritt. Dies stellt sicher, dass nur relevante technische Diagramme und Screenshots in den Vektorspeicher gelangen, wodurch der Index sauber und das Kontextfenster der KI fokussiert bleibt.

![Workflow](./workflow_DE.svg)

##  Abhängigkeiten

Das Projekt basiert auf den folgenden Kernbibliotheken:
- **UI:** `streamlit`
- **PDF-Verarbeitung:** `docling`
- **Vektorspeicher:** `faiss-cpu`, `langchain-community`
- **Embeddings:** `langchain-huggingface`, `sentence-transformers`
- **LLM-Integration:** `requests` (für Ollama API), `openai` (für Vision-Anreicherung)

## Installation & Einrichtung

### 1. Python-Anforderungen installieren
Stellen Sie sicher, dass Python 3.10+ installiert ist, und führen Sie dann Folgendes aus:
```bash
pip install streamlit docling langchain-huggingface langchain-community faiss-cpu sentence-transformers requests
```

### 2. Ollama einrichten (Lokales LLM)
- Laden Sie **Ollama** von ollama.com herunter und installieren Sie es.
- Laden Sie das benötigte Modell herunter:
  ```bash
  ollama pull qwen2.5:7b
  ```
- Stellen Sie sicher, dass der Ollama-Server läuft (normalerweise auf Port 11434).

### 3. DocLing einrichten
DocLing wird für hochpräzises PDF-Parsing verwendet. Es wird über pip installiert (in Schritt 1 enthalten). Beim ersten Start lädt es möglicherweise notwendige KI-Modelle für die Layout-Analyse herunter.

### 4. Embeddings (MiniLM)
Das Projekt verwendet `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Sie müssen dies nicht manuell herunterladen; `langchain-huggingface` wird es beim ersten Indexierungslauf automatisch abrufen.

### 5. OpenAI API-Schlüssel (für Vision)
Um das Skript `image_to_information.py` zu verwenden, benötigen Sie einen OpenAI API-Schlüssel.
- Exportieren Sie ihn als Umgebungsvariable oder bearbeiten Sie die Variable `OPENAI_API_KEY` im Skript.  

Sie können natürlich jeden bevorzugten KI-Anbieter Ihrer Wahl verwenden. Stellen Sie einfach sicher, dass er Bilder als Eingabe verarbeiten kann.  

## 📂 Projekt-Workflow

### 1. Erfassung & Überprüfung (Erforderlich)
Führen Sie `unified_extraction_review.py` aus, um Ihr PDF zu verarbeiten. Dieser Schritt beinhaltet eine **Human-in-the-Loop**-Überprüfung, bei der Sie manuell auswählen, welche Bilder beibehalten und welche verworfen werden sollen.

### 2. Anreicherung (Optional)
Erweitern Sie Ihre Dokumentation, indem Sie KI-generierte Beschreibungen zu extrahierten Bildern hinzufügen.
*   **Vorschau & Kostenoptimierung:** Bevor Sie die vollständige Anreicherung durchführen, verwenden Sie `image_to_information_testing.py`. Dieses Skript generiert eine Datei `openai_prompts_preview.json`, die es Ihnen ermöglicht, den genauen Textkontext und die API-Nutzlast zu überprüfen, die an die Vision AI gesendet würden. Dies ist entscheidend, um zu überprüfen, ob der "debug_context_used" korrekt ist, bevor Ihnen Token-Kosten entstehen.
*   **Ausführung:** Führen Sie `image_to_information.py` aus, um die eigentliche Analyse durchzuführen und Ihr Markdown mit `[AI-ANALYSIS]`-Tags zu aktualisieren.

> **Hinweis:** Wenn Sie diesen Schritt überspringen, stellen Sie sicher, dass Sie den System-Prompt in `chatbot_dashboard.py` anpassen. Ohne Anreicherung sollte das LLM angewiesen werden, Bilder basierend auf ihrer Nähe zu relevantem Text zu referenzieren, anstatt sich auf beschreibende KI-Analyse-Tags zu verlassen.

### 3. Index & Chat
*   **Index:** Führen Sie `vector_transformer.py` aus, um die FAISS-Vektordatenbank zu erstellen oder zu aktualisieren.
*   **Chat:** Starten Sie das interaktive Dashboard:
    ```bash
    streamlit run chatbot_dashboard.py
    ```

---

### ⚠️ Haftungsausschluss
Dieses PoC ist derzeit für Demonstrations- und interne Testzwecke vorgesehen. Das bereitgestellte Dashboard ist ein visueller Prototyp, um die Technologie zu präsentieren. Für den Produktionseinsatz sollten Sie eine benutzerdefinierte Chat-Oberfläche entwickeln, die auf Ihre spezifische Softwareumgebung zugeschnitten ist, und evaluieren, ob die KI-Modelle auf lokaler Kundenhardware oder Ihren eigenen oder zentralen sicheren Servern von Drittanbietern gehostet werden sollen.

---
*Entwickelt als PoC für Documentation Intelligence.*