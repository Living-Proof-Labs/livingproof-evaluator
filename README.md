# livingproof-evaluator

Evaluator contract for Living Proof Labs robot capability verification.

**[Start here: documentation (source preview)](docs/index.md)** — rendered publication is pending verification.

This repository holds:

- The **observable vocabulary**: defined terms, each with meaning, frame, units and a rule for when a per-robot `nominal` applies. The hallway terms (base, base_height, body_contact) are published in [docs/observable-vocabulary.md](docs/observable-vocabulary.md).
- The **observation-binding format** (`livingproof-observation-binding/1.0.0`): a declarative mapping from observables to MCAP channels and fields, including a per-robot `nominal` value for robot-dependent observables such as base_height. See [docs/observation-binding.md](docs/observation-binding.md).
- The **evaluator I/O contract**: for one trial, an evaluator receives the MCAP, the merged binding, the scenario and the run manifest, and returns a verdict per step, including `not evaluated` for an unknown step or unbound observable.
- The **evaluator identity**: every evaluator declares an id, a display name, a publisher, a version, an icon (SVG, owned by the publisher) and an execution (`deterministic` or `agentic`). Every result it returns carries that identity, so a report can show the evaluator's mark — for example the Roboto, Foxglove or Alloy logo — next to the result.
- The **shared result envelope**. `kind` is `scenario`, `integrity`, or `advisory`. A scenario result is a robot verdict per step, including `not evaluated`. An integrity result is a test-system status, success, a percentage, and findings, and the schema rejects a robot pass or fail. An advisory result is an observation: it never grades, and it never changes Scenario, Run Integrity, or the evidence. The run-integrity contract is in [docs/run-integrity.md](docs/run-integrity.md). The advisory contract is in [docs/advisory.md](docs/advisory.md).
- An optional **descriptor** on a `livingproof-evaluator-result/1.1.0` result. The evaluator supplies its own name, mark, tier, and findings. The name is the evaluator's title, used exactly. A consumer does not append the word "evaluator". The descriptor's `kind` is display copy and does not select the payload. The contract is in [docs/evaluator-descriptor.md](docs/evaluator-descriptor.md).
- An evaluator implementation ships an **implementation descriptor** (`livingproof-evaluator-implementation/1`) so a loader can install and run it from that implementation's own repository at the same commit, with no code that knows the implementation by name. `kind` is `integrity`, `advisory`, or `scenario`. `scenario` is `grading: robot`; `integrity` and `advisory` stay `grading: none`. At most one evaluator in a run may grade the robot, and that rule is left to the consumer. The contract is in [docs/implementation-descriptor.md](docs/implementation-descriptor.md).

It does not implement a particular evaluator, hold Gherkin step definitions, or store robot- or producer-specific bindings. Those live in other repositories, as described in the proposal. The first-party deterministic implementation is the [scenario evaluator](https://github.com/Living-Proof-Labs/livingproof-evaluator-scenario).

## Status

The shared envelope, the optional 1.1 descriptor, and the run-integrity contract are published here as schemas, examples, and tests. The fixtures are example data, except the publisher check, which records one real GitHub run. The hallway observable vocabulary is published as a schema, a fixture and a guide. The observation-binding format is published as a schema, three worked examples and a guide ([docs/observation-binding.md](docs/observation-binding.md)). There is no evaluator implementation in this repository. The agreed design is in the [Living Proof Evaluator Skill — Feature Proposal](https://app.notion.com/p/414e1aa44c2981e0b8b2fcb28f47ea40).

## License

[Apache-2.0](LICENSE).
