import { BrowserRouter, Routes, Route } from "react-router-dom";
import ChatInterface from "./Components/ChatInterface";
import Graph from "./Components/Graph";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatInterface />} />
        <Route path="/graph" element={<Graph />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
