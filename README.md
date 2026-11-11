# livingproof-evaluator

Evaluator contract for Living Proof Labs robot capability verification.

This repository holds:

- The **observable vocabulary**: defined terms such as base, base_height, body contact and feet, each with meaning, frame and units.
- The **observation-binding format** (`livingproof-observation-binding/1.0.0`): a declarative mapping from observables to MCAP channels and fields, including a per-robot `nominal` value for robot-dependent observables such as base_height.
- The **evaluator I/O contract**: for one trial, an evaluator receives the MCAP, the merged binding, the scenario and the run manifest, and returns a verdict per step, including `not evaluated` for an unknown step or unbound observable.
- The **evaluator identity**: every evaluator declares an id, a display name, a publisher, a version, an icon (SVG, owned by the publisher) and a kind (`deterministic` or `agentic`). Every grade or verdict it returns carries that identity, so a report can show the evaluator's mark — for example the Roboto, Foxglove or Alloy logo — next to the verdict.

It does not implement a particular evaluator, hold Gherkin step definitions, or store robot- or producer-specific bindings. Those live in other repositories, as described in the proposal. The first-party deterministic implementation is the [scenario evaluator](https://github.com/Living-Proof-Labs/livingproof-evaluator-scenario).

## Status

Design, no code yet. The agreed design is in the [Living Proof Evaluator Skill — Feature Proposal](https://app.notion.com/p/414e1aa44c2981e0b8b2fcb28f47ea40).

## License

[Apache-2.0](LICENSE).
