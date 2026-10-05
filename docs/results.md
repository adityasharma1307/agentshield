# Results

`RESULTS.md` is rendered from `results/examples.json`:

```bash
python -m agentshield.bench render results/examples.json --out RESULTS.md
```

The JSON is a local run of `examples.careful_agent` and `examples.leaky_agent` on the shipped suites, scored at `high`. The careful agent passed every suite. The leaky agent failed most scenarios. Regenerate the JSON with:

```bash
python -m agentshield.bench local --out results/examples.json
```

A live model list is a different command. It writes `results/<date>.json` and does not invent numbers. If a provider key is missing, it exits 2 and prints the variable name:

```bash
python -m agentshield.bench live models.txt
```

That command needs the `bench` extra (`litellm`). CI does not run it. A five-model table and a demo recording are still open.
