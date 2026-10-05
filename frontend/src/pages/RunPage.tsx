import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, problem } from "../api/client";
import type { components } from "../api/schema";
import { Heatmap } from "../components/Heatmap";
import { Empty, Failure, Loading } from "../components/States";
import { Timeline } from "../components/Timeline";

type Status = components["schemas"]["RunStatusBody"];
type Report = components["schemas"]["SignedReport"];
type Traces = components["schemas"]["RunTraces"];

export function RunPage() {
  const { runId = "" } = useParams();
  const [status, setStatus] = useState<Status | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [traces, setTraces] = useState<Traces | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setReport(null);
    setTraces(null);
    api
      .GET("/runs/{run_id}", { params: { path: { run_id: runId } } })
      .then(async (result) => {
        if (!active) return;
        if (!result.response.ok || !result.data) {
          setError(problem(result.error, result.response));
          setLoading(false);
          return;
        }
        setStatus(result.data);
        if (result.data.status !== "succeeded") {
          setLoading(false);
          return;
        }
        const [reportResult, traceResult] = await Promise.all([
          api.GET("/runs/{run_id}/report", { params: { path: { run_id: runId } } }),
          api.GET("/runs/{run_id}/traces", { params: { path: { run_id: runId } } }),
        ]);
        if (!active) return;
        if (!reportResult.response.ok || !reportResult.data) {
          setError(problem(reportResult.error, reportResult.response));
        } else {
          setReport(reportResult.data);
        }
        if (!traceResult.response.ok || !traceResult.data) {
          setError(problem(traceResult.error, traceResult.response));
        } else {
          setTraces(traceResult.data);
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
  }, [runId]);

  return (
    <section>
      <p>
        <Link to="/">All runs</Link>
      </p>
      <h1>Run</h1>
      {loading ? <Loading label="Loading run" /> : null}
      {error ? <Failure label={error} /> : null}
      {status ? (
        <>
          <p className="id">{status.id}</p>
          <p>
            <span className={`status ${status.status}`}>{status.status}</span>{" "}
            <span className="muted">{status.agent}</span>
          </p>
          {status.error ? <Failure label={status.error} /> : null}
          {status.status !== "succeeded" && !loading ? (
            <Empty label="This run has not finished, so there is no heatmap yet." />
          ) : null}
          <p>
            <Link to={`/diff?left=${status.id}`}>Compare this run</Link>
          </p>
        </>
      ) : null}
      {report ? <Heatmap scenarios={report.report.scenarios} /> : null}
      {traces ? <Timeline scenarios={traces.scenarios} /> : null}
    </section>
  );
}
