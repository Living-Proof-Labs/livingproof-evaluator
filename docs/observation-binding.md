# Observation binding

The observation binding says where each observable of the [observable vocabulary](observable-vocabulary.md) is found in one MCAP recording. Its format is `livingproof-observation-binding/1.0.0`, checked by [`schema/binding.schema.json`](../schema/binding.schema.json).

The scope is what the existing fixtures and checks need: one recording kind (the MCAP that livingproof-sim-mujoco writes, with the `/base_pose` channel) and the three hallway terms. It is not a general channel-mapping language, and it adds no terms: a binding speaks only of terms in the vocabulary.

A binding comes in three kinds. The first two are written once, by the owner of the thing they describe. The third is made for each trial.

- **robot binding** (`kind: robot`): what only the robot knows. The robot, a configuration, and per observable the robot body whose origin is the term (`base`: `pelvis` for the G1) and the `nominal` of a term whose nominal applies per robot configuration (`base_height`: 0.78 m for the G1 stock configuration). Example: [`examples/binding/robot/unitree-g1-stock.json`](../examples/binding/robot/unitree-g1-stock.json).
- **producer binding** (`kind: producer`): what only the producer knows. Per observable, the one MCAP channel that carries it (`topic`, `encoding`, `schema`), the `fields` that hold its values as dotted paths, and the `frame` the values are in. For livingproof-sim-mujoco, `/base_pose` carries `base` (x and y) and `base_height` (z). Example: [`examples/binding/producer/livingproof-sim-mujoco.json`](../examples/binding/producer/livingproof-sim-mujoco.json).
- **merged binding** (`kind: merged`): the result for one trial. It joins the robot's entries and the producer's entries per observable, names the recording (`uri` and `sha256`) and the trial, and lists `bound_observables`, the same list a scenario request carries as `binding.bound_observables`. Example: [`examples/binding/merged/unitree-g1-stock-livingproof-sim-mujoco.json`](../examples/binding/merged/unitree-g1-stock-livingproof-sim-mujoco.json).

## Merge rules

An observable is bound only when the producer carries it and the robot supplies what it needs: the base body for `base`, and the `nominal` for a term whose nominal applies per robot configuration. Anything else is `unbound`, with a reason, and is never guessed:

- `producer-does-not-carry`: the producer binding has no channel for the term. Today that is `body_contact`: the recording has no contact channel, so the hallway's `wall_contacts` is not in the MCAP.
- `robot-entry-missing`: the producer carries the term but the robot did not supply a required entry.

A step that names an unbound observable is `not evaluated`. A term has one channel; a robot supplies a nominal only for a term whose nominal applies per robot configuration. The tests keep the merged example equal to the merge of the other two, using the reference rules in `tests/binding_rules.py`.

## What this does not do

It does not define terms (see the vocabulary), pin or verify bindings by reference, or describe recordings other than the livingproof-sim-mujoco MCAP. The `uri` and `sha256` in the example are placeholders for a real recording.
