import type { components } from "../api/schema";

type Scenario = components["schemas"]["ScenarioOutcome"];

export function Heatmap({ scenarios }: { scenarios: Scenario[] }) {
  const suites = unique(scenarios.map((scenario) => scenario.suite));
  const columns = unique(scenarios.map((scenario) => scenario.id));

  return (
    <section>
      <h2>Heatmap</h2>
      <p className="legend">
        Each cell is one scenario. <span className="outcome pass">Pass</span> and{" "}
        <span className="outcome fail">Fail</span> are labeled, not only colored.
      </p>
      <div className="scroll">
        <table className="heatmap">
          <thead>
            <tr>
              <th scope="col">Suite</th>
              {columns.map((id) => (
                <th key={id} scope="col">
                  {id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {suites.map((suite) => (
              <tr key={suite}>
                <th scope="row">{suite}</th>
                {columns.map((id) => {
                  const scenario = scenarios.find((item) => item.suite === suite && item.id === id);
                  if (!scenario) {
                    return <td key={id} className="empty-cell" />;
                  }
                  const label = scenario.passed ? "Pass" : "Fail";
                  return (
                    <td key={id} className={scenario.passed ? "cell pass" : "cell fail"}>
                      <span className={scenario.passed ? "outcome pass" : "outcome fail"}>{label}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
