import { useState } from "react";

import type { components } from "../api/schema";

type ScenarioTrace = components["schemas"]["ScenarioTrace"];
type TraceEvent = components["schemas"]["TraceEvent"];

export function Timeline({ scenarios }: { scenarios: ScenarioTrace[] }) {
  const [scenarioId, setScenarioId] = useState(scenarios[0]?.scenario_id ?? "");
  const selected = scenarios.find((scenario) => scenario.scenario_id === scenarioId) ?? scenarios[0];

  return (
    <section>
      <h2>Trace</h2>
      {scenarios.length > 1 ? (
        <label className="picker">
          Scenario
          <select value={selected?.scenario_id ?? ""} onChange={(event) => setScenarioId(event.target.value)}>
            {scenarios.map((scenario) => (
              <option key={scenario.scenario_id} value={scenario.scenario_id}>
                {scenario.scenario_id}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {selected ? (
        <ol className="timeline">
          {selected.trace.events.map((event, index) => (
            <EventRow
              key={event.sequence}
              event={event}
              result={resultAfter(selected.trace.events, index)}
            />
          ))}
        </ol>
      ) : (
        <p className="state">This run has no trace events.</p>
      )}
    </section>
  );
}

function EventRow({ event, result }: { event: TraceEvent; result: string | null }) {
  const [open, setOpen] = useState(false);
  const title = event.name ? `${event.kind} ${event.name}` : event.kind;
  return (
    <li>
      <div className="event-head">
        <span className="seq">{event.sequence}</span>
        <span>{title}</span>
      </div>
      {event.kind === "tool_call" ? (
        <>
          <button type="button" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide arguments and result" : "Show arguments and result"}
          </button>
          {open ? (
            <div className="event-body">
              <h3>Arguments</h3>
              <Collapsible text={JSON.stringify(event.arguments ?? {}, null, 2)} />
              <h3>Result</h3>
              <Collapsible text={result ?? "No result was recorded."} />
            </div>
          ) : null}
        </>
      ) : null}
      {event.kind === "tool_result" && event.output ? <Collapsible text={event.output} /> : null}
      {event.kind === "final" && event.text ? <Collapsible text={event.text} /> : null}
      {event.kind === "llm_call" && event.text ? <Collapsible text={event.text} /> : null}
    </li>
  );
}

function resultAfter(events: TraceEvent[], index: number): string | null {
  const next = events[index + 1];
  if (!next || next.kind !== "tool_result") {
    return null;
  }
  return next.output ?? "";
}

function Collapsible({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const lines = text.split("\n");
  const long = text.length > 280 || lines.length > 4;
  const shown = !long || open ? text : lines.slice(0, 4).join("\n");
  return (
    <div className="block">
      <pre>{shown}</pre>
      {long ? (
        <button type="button" onClick={() => setOpen((value) => !value)}>
          {open ? "Show less" : "Show all"}
        </button>
      ) : null}
    </div>
  );
}
