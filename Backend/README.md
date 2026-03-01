# EduAssess — AI-Driven Agentic Assessment System

An AI-powered conversational backend that helps teachers generate student assessments. The system uses curriculum data (Domains -> Subdomains -> Learning Outcomes) and textbook content to dynamically create relevant assessment materials through a guided, multi-phase conversation.

## Features

-   **Conversational Agent**: LangGraph state machine guides teachers through a multi-phase assessment creation flow.
-   **Curriculum Reasoning**: GPT-4o reasons across 25 Learning Outcomes in 3 science domains to find the best matches for teacher needs.
-   **Vector Search**: MongoDB Atlas Vector Search retrieves semantically relevant textbook content using OpenAI embeddings.
-   **Assessment Generation**: Produces 1-2 MCQ/Short Answer questions per LO with full metadata in Markdown format.
-   **Stateful Sessions**: MongoDB-backed session persistence enables seamless back-and-forth refinement.
-   **Review & Refinement**: Teachers can reject content and the agent re-reasons over the curriculum.
-   **Asynchronous**: Built async-first with FastAPI, Motor, and async OpenAI SDK.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | **FastAPI** (async) |
| Data Models | **Pydantic v2** |
| Database | **MongoDB Atlas** via **Motor** (async driver) |
| Vector Search | **MongoDB Atlas Vector Search** (cosine, 1536 dims) |
| Agent | **LangGraph** state machine with conditional routing |
| LLM | **OpenAI GPT-4o** |
| Embeddings | **OpenAI text-embedding-3-small** (1536 dims) |
| Deployment | **Docker** / **Railway** |

## Project Structure

```
Backend/src/
├── main.py                 # FastAPI app with lifespan (startup seeding)
├── config.py               # Pydantic Settings (.env loader)
├── database.py             # Motor client, collections, indexes
├── models/
│   ├── curriculum.py       # Domain, Subdomain, LearningOutcome
│   ├── chunk.py            # TextbookChunk (with embedding vector)
│   ├── session.py          # Session, SessionState, Message
│   ├── assessment.py       # Question, Assessment
│   └── api.py              # AnswerRequest, AnswerResponse
├── services/
│   ├── embedding.py        # OpenAI embeddings wrapper
│   ├── vector_search.py    # $vectorSearch aggregation
│   └── seed.py             # Curriculum + chunk seeding
├── agent/
│   ├── state.py            # AgentState TypedDict for LangGraph
│   ├── prompts.py          # System & phase-specific prompts
│   ├── nodes.py            # Node functions (7 phases)
│   └── graph.py            # StateGraph definition & compilation
└── routers/
    └── answer.py           # POST /answer/ endpoint
```

## Setup

### Prerequisites

-   Python 3.11+
-   MongoDB Atlas cluster (M0 free tier works; M10+ for Atlas Vector Search)
-   OpenAI API key

### 1. Install Dependencies

```bash
cd Backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=eduassess
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
FRONTEND_URL=http://localhost:3000
```

### 3. Atlas Vector Search Index

Create a vector search index on the `textbook_chunks` collection:

-   **Index name:** `vector_index`
-   **Field:** `embedding` (vector, 1536 dims, cosine)

The app attempts to create this automatically on startup.

### 4. Run the Server

```bash
cd Backend
uvicorn src.main:app --reload
```

On first startup the app seeds curriculum data and embeds all 105 textbook chunks from `docs/chunks.json`.

Swagger docs available at `http://localhost:8000/docs`.

## API Endpoints

### `POST /answer/`

Single conversational endpoint that accepts user input and returns the agent's response.

**Request:**
```json
{ "session_id": null, "message": "Hello" }
```

**Response:**
```json
{
  "session_id": "a1b2c3d4...",
  "response": "Hello! I'm EduAssess...",
  "state": "topic_identification",
  "data": null
}
```

### `GET /health`

Returns `{"status": "ok"}`.

## Conversation Flow

```
Greeting → Topic Identification → Domain Reasoning → Topic Selection
→ Content Retrieval → Review & Refinement → Assessment Generation → Complete
```

## Deployment

Includes `Dockerfile` and `railway.toml` for Railway deployment:

```bash
docker build -t eduassess-backend ./Backend
docker run -p 8080:8080 --env-file Backend/.env eduassess-backend
```