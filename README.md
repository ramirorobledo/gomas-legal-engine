# Gomas Legal Engine

**Gomas Legal Engine** is a local-first, privacy-aware system for processing, analyzing, and reasoning over complex legal documents. It leverages advanced OCR, normalization, and **PageIndex** technology to create hierarchical, reasoning-ready indices of legal PDFs without relying on traditional vector databases.

## 🚀 Features

- **Automated Pipeline**: Watchdog-based monitoring of an input folder for seamless processing.
- **Robust OCR**: Converts scanned PDFs to Markdown with high fidelity.
- **Normalization**: Cleans and standardizes text for consistent analysis.
- **Classification**: Automatically categorizes legal documents (Amparos, Sentencias, Acuerdos, etc.).
- **Reasoning-based RAG**: improved retrieval using [PageIndex](https://github.com/VectifyAI/PageIndex), enabling "Tree Search" over document structures instead of flat semantic similarity.
- **Local & Private**: Designed to run locally, ensuring sensitive legal data remains under your control.

## 🏗️ Architecture

The system follows a linear processing pipeline:

1.  **Input/Watchdog**: Detects new PDF files in the `input/` directory.
2.  **Stabilization & Hashing**: Ensures file integrity and prevents duplicate processing.
3.  **OCR Service**: Extracts text and layout information, saving results to `ocr_output/`.
4.  **Normalization**: Cleans artifacts and standardizes format in `normalized/`.
5.  **Classification**: Determines the document type and urgency.
6.  **Indexing (PageIndex)**: Generates a hierarchical JSON tree in `indices/` for reasoning agents.

## 🛠️ Installation

### Prerequisites

- Python 3.10+
- [Node.js](https://nodejs.org/) (v18+)
- [Git](https://git-scm.com/)
- API Keys for LLM services (Anthropic/OpenAI)

### Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/ramirorobledo/gomas-legal-engine.git
    cd gomas_legal_engine
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Frontend Dependencies**
    ```bash
    cd frontend
    npm install
    cd ..
    ```

4.  **Configure Environment**
    Create a `.env` file in the root directory:
    ```env
    # Required for Reasoning (Page Index, Cleaning)
    ANTHROPIC_API_KEY=sk-ant-api03-...

    # Optional for OCR (defaults to local PyMuPDF if missing/invalid)
    MISTRAL_API_KEY=your_mistral_key
    ```

4.  **Initialize PageIndex**
    Ensure the submodule is initialized (if applicable) or the library is present in `lib/PageIndex`.

## ▶️ Usage

1.  **Start the Engine**
    ```bash
    python main.py
    ```
    The system will start monitoring the `input/` folder.

    **Alternatively (Recommended)**:
    To start **both** the Watchdog and the API server at once, run:
    ```powershell
    ./start_all.ps1
    ```

2.  **Process Documents**
    Simply drop a PDF file into the `input/` folder. The engine will automatically pick it up and process it through the pipeline.

3.  **Check Results**
    - **OCR**: `ocr_output/[doc_id]/`
    - **Normalized Text**: `normalized/norm_[filename].md`
    - **Indices**: `indices/index_[doc_id].json`
    - **Logs**: `logs/gomas_engine.log`

    - **Logs**: `logs/gomas_engine.log`

4.  **Start the API (Optional)**
    If you want to use the REST API for uploading and querying:
    ```bash
    uvicorn api:app --reload
    ```
    Access the interactive documentation at `http://localhost:8000/docs`.

## 📂 Directory Structure

- `input/`: Drop files here for processing.
- `processing/`: Staging area for active files.
- `ocr_output/`: Raw OCR results (Markdown & JSON).
- `normalized/`: Cleaned text files ready for indexing.
- `indices/`: Hierarchical PageIndex JSON trees.
- `lib/`: External libraries and modules (including PageIndex).
- `review_queue/`: Documents flagged for manual review.

## 🤝 Contributing

Contributions are welcome! Please ensure any PRs maintain the privacy-first philosophy of the project.

## 📄 License

[MIT License](LICENSE)
