# EduAssess – AI-Driven Agentic Assessment System

**EduAssess** is a stateful, conversational AI agent built as a submission for the Generative AI Assessment Task. It functions as a collaborative guide for teachers, allowing them to dynamically generate student assessments. By mapping natural language inputs to standardized curriculum boundaries (Domains, Subdomains, Learning Outcomes) and retrieving specific textbook context, it constructs highly relevant, accurate test materials.

Built completely strictly according to the provided requirements, this application heavily leverages **LangGraph** to construct a robust Human-in-the-Loop state machine, ensuring precise conversational flow, pausing/resuming over HTTP cycles, and episodic memory persistence.

---

## 🎯 Project Info & The Problem Solved

**The Task:** Build a stateful conversational agent to navigate a teacher through the entire process of test generation, moving from generic intent ("I want an assessment on gravity") to specific granular curriculum targets, and finally to multiple-choice or short-answer questions grounded solely in provided textbook chunks.

### Workflow Accomplished:
**Part One: Discovery & Planning**
- **Greeting & Intent:** The agent welcomes the teacher and handles natural, dynamic input.
- **Curriculum Semantic Search:** It reasons across teacher explanations of student weaknesses or desired topics, presenting aligned **Domains**, **Subdomains**, and **Learning Outcomes (LOs)**.
- **Dynamic Pivoting:** Responds accurately to changing constraints or broad descriptions.

**Part Two: Content Retrieval & Generation**
- **Chunk Retrieval:** Uses Vector Search to fetch text chunks that match the teacher's selected LOs and summarizes them.
- **Human-in-the-loop Refinement:** The teacher can reject chunks (e.g., "This is too advanced"). The agent reasons over this feedback to adjust its semantic queries and propose better materials.
- **Markdown Assessment Generation:** Finally, upon the teacher's approval, it generates targeted questions (e.g., 1-2 per LO) formatted cleanly in Markdown.

---

## 🛠️ Tech Stack & AI Models

This system is built leveraging cutting-edge tools suited for compound agent workflows:

- **AI Framework:** **LangGraph** (State machine execution for cyclic conversational tasks) & **LangChain**
- **OpenAI Models Used:** 
  - **`gpt-4o`** for reasoning, chunk summarization, intent routing, and assessment generation.
  - **`text-embedding-3-small`** for high-quality, efficient vector embeddings.
- **Backend:** Python 3.10+, FastAPI (Asynchronous API endpoints)
- **Database & Memory:** MongoDB + MongoDB Atlas Vector Search (Maintains cross-session episodic memory completely in the backend)
- **Frontend:** React, Vite, Mermaid.js (for runtime graph visualizations)

---

## 📁 Architecture Documentation

For a deep dive into the reasoning behind utilizing LangGraph over standard chains, choosing MongoDB for episodic memory, and a comprehensive look at the backend state machine logic, please refer to the **[ARCHITECTURE.md](./ARCHITECTURE.md)** included in the root directory.

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Node.js v16+
- A clustered MongoDB instance (Local or Atlas)
- An OpenAI API Key

### 1. Backend Setup

Open a terminal and navigate to the `Backend` directory:

```bash
cd Backend

# Create a virtual environment
python -m venv venv
# Activate it (Windows)
venv\Scripts\activate
# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `Backend` directory:
```env
OPENAI_API_KEY=your-openai-api-key-here
MONGO_URI=mongodb://localhost:27017  # or your Atlas URI
DB_NAME=eduassess
FRONTEND_URL=http://localhost:5173
```

Run the backend server:
```bash
uvicorn src.main:app --reload --port 8000
```
> **Note:** Upon the very first startup, the FastAPI lifespan events will automatically read the provided documents, create the Vector Search indexes, and embed the curriculum and chunks into your MongoDB database. Please allow a minute or two for the initial seeding process.

### 2. Frontend Setup

Open a separate terminal and navigate to the `Frontend` directory:

```bash
cd Frontend

# Install NPM dependencies
npm install
```

Create a `.env` file in the `Frontend` directory:
```env
VITE_BACKEND_URL=http://localhost:8000
```

Start the frontend development server:
```bash
npm run dev
```

---

## 📖 How to Use the App

1. **Start a Session:** Open your browser to the local frontend URL (usually `http://localhost:5173`).
2. **Greet the Agent:** Say "Hello, I want to create an assessment."
3. **Specify Topics:** Describe what you want. For example: *"I want to assess my students on the solar system and gravity."*
4. **Approve LOs:** The agent will present domains and learning outcomes. Tell it which ones you want to proceed with.
5. **Review Content:** The agent will pull textbook chunks and summarize them.
6. **Refine or Generate:** If the chunks look wrong, tell the agent why. If they look good, ask it to *"Generate the assessment with multiple-choice questions."*
7. **Complete:** The agent will print out your assessment in Markdown!

---

## 📁 Documentation

For a deep dive into the reasoning behind utilizing LangGraph over standard chains, choosing MongoDB for episodic memory, and a comprehensive look at the backend state machine logic, please refer to the [ARCHITECTURE.md](./ARCHITECTURE.md) included in the root directory.