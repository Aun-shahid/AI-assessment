import React, { useEffect, useState } from 'react';
import mermaid from 'mermaid';

const langGraphFlow = `
flowchart TB
    %% Styling Classes
    classDef memory fill:#fdfd96,stroke:#333,stroke-width:2px;
    classDef router fill:#ffd1dc,stroke:#333,stroke-width:2px;
    classDef handler fill:#aec6cf,stroke:#333,stroke-width:1px;
    classDef state fill:#b19cd9,stroke:#333,stroke-width:2px,color:#000;
    classDef mainLoop fill:#e6f2ff,stroke:#66b2ff,stroke-width:3px,stroke-dasharray: 5 5;

    subgraph GlobalLoop ["Global Human-in-the-Loop (HTTP Request Cycle)"]
        direction TB
        User((Teacher Input)):::user
        Session[(MongoDB Session)]:::memory
        Output((Agent Reply)):::user
        
        User -->|1. HTTP POST /answer| Session
        Session -->|2. Loads History & State| Router
        
        %% LangGraph Internal Pass
        subgraph LG ["LangGraph: Single Execution Pass"]
            direction TB
            Router{LLM Router Node}:::router
            
            HandleGreeting[handle_greeting]:::handler
            ReasonTopics[reason_topics]:::handler
            ShowLoList[show_lo_list]:::handler
            HandleSelection[handle_selection]:::handler
            RetrieveContent[retrieve_content]:::handler
            HandleRefinement[handle_refinement]:::handler
            GenerateAssessment[generate_assessment]:::handler
            
            Router -->|greeting| HandleGreeting
            Router -->|topic_input| ReasonTopics
            Router -->|info_request| ShowLoList
            Router -->|selection| HandleSelection
            Router -->|approval| RetrieveContent
            Router -->|rejection| HandleRefinement
            Router -->|generate| GenerateAssessment
            
            %% All edges terminate to END internally, which saves state
            HandleGreeting -->|Update State| EndGraph((END))
            ReasonTopics -->|Update State| EndGraph
            ShowLoList -->|Update State| EndGraph
            HandleSelection -->|Update State| EndGraph
            RetrieveContent -->|Update State| EndGraph
            HandleRefinement -->|Update State| EndGraph
            GenerateAssessment -->|Update State| EndGraph
        end
        
        EndGraph -->|3. Save State to DB| Output
        Output -.->|4. Waits for Human Input| User
    end

    class GlobalLoop mainLoop;
`;

export default function Graph() {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    mermaid.initialize({ 
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif'
    });
    mermaid.render('mermaid-graph-svg', langGraphFlow)
      .then((result) => {
        setSvg(result.svg);
      })
      .catch((err) => {
        console.error('Mermaid parsing error:', err);
        setError(String(err));
      });
  }, []);

  return (
    <div style={{ padding: '2rem', minHeight: '100vh', background: '#f5f5f5', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <h1 style={{ marginBottom: '1rem', color: '#333' }}>LangGraph Architecture</h1>
      <p style={{ marginBottom: '2rem', color: '#666', textAlign: 'center', maxWidth: '800px' }}>
        A detailed view of the application flow, including user interaction loops, session memory persistence to MongoDB,
        the routing LLM classifier, individual reasoning nodes, and the state-machine transition wait steps.
      </p>
      {error && (
        <pre style={{ color: 'red', background: '#fff0f0', padding: '1rem', borderRadius: '8px', maxWidth: '90vw', overflowX: 'auto' }}>
          Diagram error: {error}
        </pre>
      )}
      {!svg && !error && (
        <p style={{ color: '#999' }}>Rendering diagram…</p>
      )}
      {svg && (
        <div
          dangerouslySetInnerHTML={{ __html: svg }}
          style={{
            background: 'white',
            padding: '2rem',
            borderRadius: '12px',
            boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
            width: '95vw',
            overflow: 'auto',
            border: '1px solid #eaeaea',
          }}
        />
      )}
    </div>
  );
}
