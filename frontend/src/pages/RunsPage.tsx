import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, problem } from "../api/client";
import type { components } from "../api/schema";
import { Empty, Failure, Loading } from "../components/States";

type RunSummary = components["schemas"]["RunSummary"];

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .GET("/runs")
      .then((result) => {
        if (!active) return;
        if (!result.response.ok || !result.data) {
          setError(problem(result.error, result.response));
          setRuns([]);
          return;
        }
        setRuns(result.data.runs);
      })
      .catch(() => {
        if (active) setError("The service could not be reached.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h1>Runs</h1>
      {error ? <Failure label={error} /> : null}
      {runs === null && !error ? <Loading label="Loading runs" /> : null}
      {runs !== null && runs.length === 0 && !error ? <Empty label="No runs yet." /> : null}
      {runs !== null && runs.length > 0 ? (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Status</th>
                <th scope="col">Time</th>
                <th scope="col">Passed</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <Link to={`/runs/${run.id}`}>{run.id}</Link>
                    <div className="muted">{run.agent}</div>
                  </td>
                  <td>
                    <span className={`status ${run.status}`}>{run.status}</span>
                  </td>
                  <td>{formatTime(run.created_at)}</td>
                  <td>
                    {run.passed_count} passed
                    <div className="muted">of {run.scenario_count}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function formatTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}
