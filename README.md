# livingproof-evaluator

Evaluator contract for Living Proof Labs robot capability verification.

This repository holds:

- The **observable vocabulary**: defined terms such as base, base_height, body contact and feet, each with meaning, frame and units.
- The **observation-binding format** (`livingproof-observation-binding/1.0.0`): a declarative mapping from observables to MCAP channels and fields, including a per-robot `nominal` value for robot-dependent observables such as base_height.
- The **evaluator I/O contract**: for one trial, an evaluator receives the MCAP, the merged binding, the scenario and the run manifest, and returns a verdict per step, including `not evaluated` for an unknown step or unbound observable.
- The **evaluator identity**: every evaluator declares an id, a display name, a publisher, a version, an icon (SVG, owned by the publisher) and an execution (`deterministic` or `agentic`). Every result it returns carries that identity, so a report can show the evaluator's mark — for example the Roboto, Foxglove or Alloy logo — next to the result.
- The **shared result envelope** for two evaluator kinds. `kind` is `scenario` or `integrity`. A scenario result is a robot verdict per step, including `not evaluated`. An integrity result is a test-system status, success, a percentage, and findings, and the schema rejects a robot pass or fail. The run-integrity contract, its checks, and the design note are in [docs/run-integrity.md](docs/run-integrity.md).

It does not implement a particular evaluator, hold Gherkin step definitions, or store robot- or producer-specific bindings. Those live in other repositories, as described in the proposal. The first-party deterministic implementation is the [scenario evaluator](https://github.com/Living-Proof-Labs/livingproof-evaluator-scenario).

## Status

The shared envelope and the run-integrity contract are published here as schemas, examples, and tests. The observable vocabulary and the observation-binding format are still design. There is no evaluator implementation in this repository. The agreed design is in the [Living Proof Evaluator Skill — Feature Proposal](https://app.notion.com/p/414e1aa44c2981e0b8b2fcb28f47ea40).

## License

[Apache-2.0](LICENSE).
