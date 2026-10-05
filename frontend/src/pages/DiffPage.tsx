import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, problem } from "../api/client";
import type { components } from "../api/schema";
import { Empty, Failure, Loading } from "../components/States";

type RunSummary = components["schemas"]["RunSummary"];
type ScenarioDiff = components["schemas"]["ScenarioDiff"];

export function DiffPage() {
  const [params] = useSearchParams();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [left, setLeft] = useState(params.get("left") ?? "");
  const [right, setRight] = useState("");
  const [changes, setChanges] = useState<ScenarioDiff[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .GET("/runs")
      .then((result) => {
        if (!active) return;
        if (!result.response.ok || !result.data) {
          setError(problem(result.error, result.response));
          setRuns([]);
        } else {
          setRuns(result.data.runs);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError("The service could not be reached.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function compare() {
    setComparing(true);
    setError(null);
    setChanges(null);
    try {
      const result = await api.GET("/runs/{run_id}/diff/{other_id}", {
        params: { path: { run_id: left, other_id: right } },
      });
      if (!result.response.ok || !result.data) {
        setError(problem(result.error, result.response));
        return;
      }
      setChanges(result.data.scenarios);
    } catch {
      setError("The service could not be reached.");
    } finally {
      setComparing(false);
    }
  }

  return (
    <section>
      <h1>Compare runs</h1>
      <p>Scenario ids whose pass or fail changed between two runs.</p>
      {loading ? <Loading label="Loading runs" /> : null}
      {error ? <Failure label={error} /> : null}
      {runs !== null && runs.length === 0 && !error ? <Empty label="No runs to compare." /> : null}
      {runs !== null && runs.length > 0 ? (
        <form
          className="compare"
          onSubmit={(event) => {
            event.preventDefault();
            void compare();
          }}
        >
          <label>
            First run
            <select value={left} onChange={(event) => setLeft(event.target.value)}>
              <option value="">Choose a run</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Second run
            <select value={right} onChange={(event) => setRight(event.target.value)}>
              <option value="">Choose a run</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.id}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={!left || !right || left === right || comparing}>
            {comparing ? "Comparing" : "Compare"}
          </button>
        </form>
      ) : null}
      {changes !== null && changes.length === 0 ? (
        <Empty label="No scenario changed outcome." />
      ) : null}
      {changes !== null && changes.length > 0 ? (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Scenario</th>
                <th scope="col">Severity</th>
                <th scope="col">First run</th>
                <th scope="col">Second run</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((change) => (
                <tr key={change.id}>
                  <td>{change.id}</td>
                  <td>{change.severity}</td>
                  <td>{outcomeLabel(change.left_passed)}</td>
                  <td>{outcomeLabel(change.right_passed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function outcomeLabel(passed: boolean | null): string {
  if (passed === null) return "Missing";
  return passed ? "Pass" : "Fail";
}
