# ⚗️ ChemPulse — Chemical Plant Equipment Analytics & AI Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB.svg?style=flat&logo=Python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-orange.svg?style=flat)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**ChemPulse** is an end-to-end industrial analytics and intelligent assistant platform for chemical processing plants. It combines automated telemetry dataset processing, equipment health & anomaly detection, interactive data visualization, and hybrid AI assistance (Text-to-SQL + Document RAG).

---

## 🌟 Key Features

### 📊 1. Equipment Telemetry & Dataset Analytics
- **Multi-Format CSV Ingestion**: Upload industrial equipment operating logs (Flowrate, Pressure, Temperature).
- **Automated Parameter Statistics**: Computes real-time averages, min/max ranges, and equipment distribution charts.
- **Telemetry Alerts & Inactive Equipment Detection**:
  - Automatically identifies offline/decommissioned equipment missing telemetry parameters.
  - Generates sensor warnings for missing or partial operational metrics.
- **Interactive Visualizations**: Powered by Chart.js (Operational ranges, equipment type distribution, and flowrate vs. pressure correlation scatter plots).

### 🤖 2. Dual-Engine Intelligent Chatbot
- **Text-to-SQL Assistant**: Queries PostgreSQL relational databases directly using natural language to perform calculations, lookups, and aggregations.
- **Document RAG (Retrieval-Augmented Generation)**:
  - Upload chemical engineering manuals, SOPs, and equipment documentation (`.pdf`, `.docx`, `.txt`).
  - Semantic vector retrieval using **NVIDIA NIM `nvidia/nemotron-3-embed-1b` (Cloud API with 0 MB Server RAM footprint)** and **ChromaDB**.
  - Uses state-of-the-art LLMs (Groq LLaMA 3.3 70B & Google Gemini) with multi-turn chat history.

### ⚡ 3. Ultra-Low Memory & Cloud Optimized (Render Free Tier Ready)
- **Zero Server RAM Embeddings**: Embeddings are computed via Google's Gemini Cloud API, keeping server RAM usage under **~80 MB** (well below Render's 512 MB free tier limit).
- **Native Single-Request Batching**: Chunks are processed in batches of 40 in a single HTTP request, using only ~3 requests for a 120-chunk document (<4% of Google AI Studio's 100 req/min free limit).
- **Automatic Exponential Backoff**: Built-in automatic retry handling for rate limits without crashing or timing out.
- **Asynchronous & Non-Blocking**: Heavy I/O and PDF parsing are offloaded to worker threads via `asyncio.to_thread`.
- **Instant Health Endpoint**: `/health` for automated uptime monitoring and keeping free cloud instances warm 24/7.

### 🔐 4. Secure Authentication & Access Control
- **JWT-Based Authentication**: Access tokens + refresh tokens with Redis token revocation blocklist.
- **Direct User Verification**: Instant onboarding and account activation without email delivery bottlenecks.
- **Data Isolation**: User-level and dataset-level role-based authorization guards.

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    User([User / Frontend]) -->|HTTP / REST| API[FastAPI Gateway]
    
    subgraph Core Services
        API --> Auth[JWT Auth & Redis Blocklist]
        API --> DatasetSvc[Dataset & Telemetry Service]
        API --> DocSvc[Document & Ingestion Service]
        API --> ChatSvc[Chat & RAG Router]
    end

    subgraph Data & Storage Layer
        DatasetSvc --> DB[(PostgreSQL Database)]
        DocSvc --> VectorDB[(ChromaDB Vector Store)]
        DocSvc --> CloudEmbed[Google Gemini Native Batch Embedding API]
    end

    subgraph AI & LLM Engine
        ChatSvc -->|NL to SQL| SQLAgent[Groq LLaMA-3.3 70B]
        SQLAgent --> DB
        ChatSvc -->|Semantic Search| Retriever[ChromaDB Retriever]
        Retriever --> RAGPrompt[RAG Context Builder]
        RAGPrompt --> LLM[Groq / Gemini LLM]
    end
```

---

## 📂 Project Structure

```text
chemical_equipment_backend/
├── frontend/                     # Modern Single-Page Dashboard
│   ├── assets/                   # Sample CSVs, icons, branding
│   ├── css/                      # Modular styling (dashboard, glassmorphism)
│   ├── js/                       # Vanilla ES Modules (api, auth, datasets, chat, ui)
│   └── index.html                # Main UI interface
├── migrations/                   # Alembic database migrations
├── src/
│   ├── auth/                     # JWT authentication, routes, schemas & services
│   ├── chatbot/                  # Chat engine, Text-to-SQL & RAG pipeline
│   │   └── rag/                  # Chunker, Document loader, Gemini embeddings, ChromaDB
│   ├── datasets/                 # CSV ingestion, data validation & telemetry analytics
│   ├── db/                       # SQLModel engine, session, and models
│   ├── Equipment/                # Equipment REST endpoints and repository
│   ├── documents/                # PDF/Doc upload, parsing and retrieval
│   ├── config.py                 # Pydantic environment configuration
│   ├── error.py                  # Global custom exception handlers
│   └── __init__.py               # FastAPI application factory & routes
├── tests/                        # Comprehensive Pytest test suite (33+ tests)
├── Dockerfile                    # Multi-stage production container
├── render.yaml                   # Infrastructure-as-Code for Render.com
├── requirements.txt              # Production Python dependencies
└── sample.csv                    # Sample chemical equipment dataset
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **PostgreSQL Database**
- **Redis Server** (optional for local dev, required for Celery worker & token blocklist)
- **API Keys**: [Groq API Key](https://console.groq.com) and [Google Gemini API Key](https://aistudio.google.com/)

---

### 🛠️ Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ankit-gadhwal/complete_chemical_plant_analytics_project.git
   cd complete_chemical_plant_analytics_project
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/chempulse_db
   REDIS_URL=redis://localhost:6379/0
   JWT_SECRET=your-super-secret-jwt-key
   JWT_ALGORITHM=HS256
   GROQ_API_KEY=your_groq_api_key
   GOOGLE_API_KEY=your_google_gemini_api_key
   DOMAIN=http://localhost:8000
   CHROMA_PERSIST_DIR=storage/chroma
   ```

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the development server**:
   ```bash
   uvicorn src:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the application**:
   - **Frontend UI**: Open `frontend/index.html` in your browser.
   - **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Running Automated Tests

ChemPulse includes an automated test suite covering authentication, dataset analytics, and document processing:

```bash
# Run all backend unit and integration tests
python run_tests.py

# Run specific test modules
pytest tests/test_auth.py tests/test_datasets.py tests/test_documents.py -v
```

---

## 🌐 Deployment Guide

### Backend (Render.com)
The repository is pre-configured with [`render.yaml`](render.yaml) for 1-click deployment on Render:
1. Connect your GitHub repository to **Render.com**.
2. Create a new **Blueprint Instance** and select this repo.
3. Provide your environment variables (`DATABASE_URL`, `GROQ_API_KEY`, `GOOGLE_API_KEY`).
4. Set up a free 10-minute ping using [Cron-job.org](https://cron-job.org) targeting `https://your-app.onrender.com/health` to keep Render warm 24/7.

### Frontend (Vercel)
1. Import the repository into **Vercel**.
2. Under **Project Settings → Environment Variables**, add:
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: `https://your-backend.onrender.com` (without trailing slash)
3. Deploy!

---

## 📄 License

This project is licensed under the **MIT License** — feel free to use and adapt it for your academic and industrial projects.
