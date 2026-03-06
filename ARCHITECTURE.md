# EduAssess Architecture & Implementation Decisions

This document details the inner workings of the EduAssess Agentic System, the flow of the application, and the rationales behind the technical decisions made to satisfy the problem statement requirements.

## 1. System Overview

EduAssess is a stateful, conversational agent designed to guide teachers through the process of creating student assessments. It takes highly dynamic natural language inputs from a teacher, maps them to a strictly defined educational curriculum (Domains, Subdomains, Learning Outcomes), surfaces relevant textbook content (Chunks), handles iterative feedback, and generates a formatted Markdown assessment.

## 2. Core Technologies

-   **Backend:** FastAPI (Python)
-   **AI Framework:** LangGraph & LangChain
-   **Database & Vector Store:** MongoDB (Storage + Atlas Vector Search)
-   **Frontend:** React, Vite, Mermaid.js (for flow visualization)

## 3. Implementation Decisions & Reasoning

### A. Why LangGraph?
The problem statement strictly dictates a back-and-forth conversational flow with a distinct sequence of milestones (Greeting -> Topic Selection -> Chunk Approval -> Refinement -> Generation). 
- **Reasoning:** Traditional sequential chains or standard conversational agents (like raw LLM + chat history) struggle to rigidly adhere to multi-step state pipelines over long, interrupted sessions. LangGraph allows us to model this explicitly as a Directed Acyclic Graph (DAG) with a State machine. 
- **Human-in-the-Loop:** LangGraph inherently supports pausing execution and waiting for human input (HTTP cycles), which matches the requirement of "breaking the flow and involving humans, then starting from where we left off."

### B. Stateful Architecture & MongoDB Episodic Memory
- **Requirement:** Maintain session memory/episodic memory entirely in the backend with a single `/answer` API endpoint.
- **Reasoning:** The FastAPI backend endpoints themselves are completely stateless. Instead, every HTTP request contains a `session_id`. We load the LangGraph state (the `State` object defined in `state.py`) and message history directly from MongoDB. When the LangGraph cycle finishes a pass, we serialize the updated state back to MongoDB. This guarantees robustness—the server can restart without losing ongoing teacher sessions.

### C. Embedding & Vector Search (RAG)
- **Requirement:** Reason across book chunks and Learning Outcomes (LOs).
- **Decision:** As recommended in the guidelines, the LOs act as the semantic bridge. We utilize Vector Search embeddings. When a teacher inputs a natural language description (e.g., "gravity and solar system"), we convert this to an embedding and perform a vector similarity search against the Curriculum LOs. Once LOs are approved, we perform a second vector search against the provided Textbook Chunks mapped to those LOs.

### D. LLM Routing Node
- **Implementation:** The Graph utilizes an `LLM Router Node` at its entry point rather than a monolithic agent.
- **Reasoning:** Relying on a single prompt to handle greetings, curriculum reasoning, chunk refinement, and assessment generation leads to prompt bloat and hallucination. The Router LLM acts as an intent classifier. It looks at the user's latest message and the graph's *current state*, and routes the transaction to exactly one specialized reasoning node (e.g., `handle_greeting`, `reason_topics`, `handle_selection`).

---

## 4. Detailed Application Flow (The LangGraph Nodes)

The application flow strictly follows the Two-Part requirement structure via specific nodes:

### Part One: Discovery
1.  **`handle_greeting`**: A simple LLM pass to respond to casual user interactions. Updates the history, but leaves the state machine ready for topic input.
2.  **`reason_topics`**: Triggers when the teacher describes what they want to assess. It performs a Semantic Search against the curriculum database to find related Domains -> Subdomains -> LOs.
3.  **`show_lo_list`**: Assembles the located Curriculum hierarchy and presents it to the teacher in a readable format, asking for selection.

### Part Two: Generation & Refinement
4.  **`handle_selection`**: Parses the teacher's approval or exclusion of specific LOs.
5.  **`retrieve_content`**: Uses the approved LOs to query the database for the associated book chunks. It passes these chunks through a summarization LLM to present a digestible overview to the teacher.
6.  **`handle_refinement`**: If the teacher rejects certain summaries (e.g., "This isn't what I meant by gravity"), this node records the *reasons* for rejection. It uses these reasons to refine the vector search query, attempting to fetch better-suited textbook chunks.
7.  **`generate_assessment`**: Once the teacher approves the summary chunks, this ultimate node is invoked. It prompts the LLM with the strictly approved LOs and Chunks to generate exactly 1-2 questions (MCQ or Short Answer depending on request) per LO. The output is strictly formatted in Markdown. The session is then considered "Complete".

## 5. Startup & Lifespan
To ensure a seamless reviewer experience, the FastAPI application uses lifespan events. Upon running the server, it automatically:
1. Validates MongoDB connection and creates Vector Indexes.
2. Parses the curriculum hierarchy and seeds the Domains/LOs.
3. Parses `chunks.json`, generates embeddings, and seeds the vector store.
(This happens automatically on the very first run).