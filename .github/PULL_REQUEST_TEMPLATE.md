## Summary

<!-- What changed, and which roadmap phase it belongs to. -->

## Test plan

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy`
- [ ] `pytest`
- [ ] `mkdocs build --strict` (when docs changed)

## Security

- [ ] No real credentials, keys, or `.env` files in this change. Test secrets are obviously fake.
- [ ] If this touches the sandbox, tools, or the Action, the change is checked against [docs/threat-model.md](https://github.com/adityasharma1307/agentshield/blob/main/docs/threat-model.md).

## Changelog

- [ ] User-visible change recorded under `## [Unreleased]` in `CHANGELOG.md`, or this change has no user-visible effect.
