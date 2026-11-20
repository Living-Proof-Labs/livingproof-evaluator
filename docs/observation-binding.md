# Observation binding

The observation binding says where each observable of the [observable vocabulary](observable-vocabulary.md) is found in one MCAP recording. Its format is `livingproof-observation-binding/1.0.0`, checked by [`schema/binding.schema.json`](../schema/binding.schema.json).

The scope is what the existing fixtures and checks need: MCAP recordings only, with no second recording kind (the observation JSON is not described here), and in practice the MCAP that livingproof-sim-mujoco writes, with the `/base_pose` channel and the three hallway terms. It is not a general channel-mapping language, and it adds no terms: a binding speaks only of terms in the vocabulary.

A binding comes in three kinds. The first two are written once, by the owner of the thing they describe. The third is made for each trial.

- **robot binding** (`kind: robot`): what only the robot knows. The robot, a configuration, and per observable the robot body whose origin is the term (`base`: `pelvis` for the G1) and the `nominal` of a term whose nominal applies per robot configuration (`base_height`: 0.78 meters for the G1 stock configuration, in the vocabulary's unit). Example: [`examples/binding/robot/unitree-g1-stock.json`](../examples/binding/robot/unitree-g1-stock.json).
- **producer binding** (`kind: producer`): what only the producer knows. Per observable, the one MCAP channel that carries it (`topic`, `encoding`, `schema`), the `fields` that hold its values as dotted paths, and the `frame` the values are in. For livingproof-sim-mujoco, `/base_pose` carries `base` (x and y) and `base_height` (z), and `/wall_contacts` carries `body_contact`, one message per contact event with `wall`, `start`, `end` and `depth`. Example: [`examples/binding/producer/livingproof-sim-mujoco.json`](../examples/binding/producer/livingproof-sim-mujoco.json).
- **merged binding** (`kind: merged`): the result for one trial. It joins the robot's entries and the producer's entries per observable, names the recording (`uri` and `sha256`) and the trial, and lists `bound_observables`, the same list a scenario request carries as `binding.bound_observables`. Example: [`examples/binding/merged/unitree-g1-stock-livingproof-sim-mujoco.json`](../examples/binding/merged/unitree-g1-stock-livingproof-sim-mujoco.json).

## Merge rules

An observable is bound only when the producer carries it and the robot supplies what it needs: the base body for `base`, and the `nominal` for a term whose nominal applies per robot configuration. Anything else is `unbound`, with a reason, and is never guessed:

- `producer-does-not-carry`: the producer binding has no channel for the term. livingproof-sim-mujoco carries all three hallway terms, `body_contact` on `/wall_contacts` ([livingproof-sim-mujoco#28](https://github.com/Living-Proof-Labs/livingproof-sim-mujoco/issues/28)), so for it nothing is unbound for this reason; a producer without a contacts channel leaves `body_contact` unbound.
- `robot-entry-missing`: the producer carries the term but the robot did not supply a required entry.

A step that names an unbound observable is `not evaluated`. A term has one channel; a robot supplies a nominal only for a term whose nominal applies per robot configuration. The tests keep the merged example equal to the merge of the other two, using the reference rules in `tests/binding_rules.py`.

## What this does not do

It does not define terms (see the vocabulary), or describe anything but MCAP recordings. Pinning a binding by an immutable reference is the follow-up [livingproof-verification#100](https://github.com/Living-Proof-Labs/livingproof-verification/issues/100); the digest of the binding itself is not part of this format yet.

## Placeholders

The examples hold placeholder values, marked so a reader and a test can see them, and still valid against the schema: the recording `uri` is on `example.invalid`, the recording `sha256` is all zeros, and the nominal's `ref` starts with `placeholder:` (its value and `measured` source are the G1's). Real values arrive with the published robot and producer bindings. The robot's base body (`pelvis` for the G1) belongs to the robot binding because it comes from the robot's description, which every producer shares.

## What the schema checks per term

For each bound term the schema fixes what the vocabulary says. `base` has the fields `x` and `y` and, from the robot, a `body`; `base_height` has the field `z` and, from the robot, a `nominal` in `meters`. The frame is `world`. A robot binding cannot give `base` a nominal, a nominal in another unit, or any entry for `body_contact`.
