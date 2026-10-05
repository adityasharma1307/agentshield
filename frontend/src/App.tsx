import { Link, Route, Routes } from "react-router-dom";

import { DiffPage } from "./pages/DiffPage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";

export function App() {
  return (
    <>
      <header className="top">
        <Link className="brand" to="/">
          Agentshield
        </Link>
        <nav>
          <Link to="/">Runs</Link>
          <Link to="/diff">Compare</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunPage />} />
          <Route path="/diff" element={<DiffPage />} />
        </Routes>
      </main>
    </>
  );
}
