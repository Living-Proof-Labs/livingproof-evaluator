# Observable vocabulary

This is the vocabulary a scenario step may use for the hallway: the terms for what is observed about the robot. A hallway scenario is written from these terms, plus places (such as `exit` and the centreline) and numbers.

The vocabulary is deliberately small. It holds only the terms the hallway scenario and its fixtures use today. It is not an ontology: a term is added when a scenario fixture uses it, not before. Feet are not defined: a term goes in when a fixture or check first observes it.

This vocabulary does not map terms to MCAP channels or fields, and it does not name a robot model. Those belong to the observation-binding format and the robot bindings. A binding says which terms it can supply (`bound_observables`). A step that names a term the binding does not supply is `not evaluated`, as in the `examples/scenario/not-evaluated` example, whose `tail` observable is not in this vocabulary.

The definitions are published as data in [`examples/vocabulary/hallway/vocabulary.json`](../examples/vocabulary/hallway/vocabulary.json), checked by [`schema/vocabulary.schema.json`](../schema/vocabulary.schema.json). The tests keep this page, the data and the scenario examples equal.

Each term has four parts:

- **Meaning**: what the term is.
- **Frame**: what the value is measured in or against.
- **Units**: the units of the value.
- **Nominal**: whether a per-robot nominal applies, and the rule for it. `never` means the term has no per-robot nominal. `per-robot-configuration` means a nominal exists for each robot and configuration.

## `base`

Scenario text calls it "base".

- **Meaning**: The robot's base origin: the one body point a hallway scenario tracks. Its position is read at each recorded sample.
- **Frame**: The hallway world frame: x along the route, y sideways with the centreline at y = 0, z up from the floor.
- **Units**: metres for position, seconds for sample time
- **Nominal** (never): The base position has no per-robot nominal. A scenario states places (exit, centreline) and numbers, not a nominal.

Used in:

- examples/scenario/graded/request.json: steps reach-the-exit and stay-near-centerline
- livingproof-evaluator-scenario checks.py: exit crossing and distance from the route, from the base point of each trace sample (x, y)
- robot-capability-specs walk-hallway README: places, not axes (the body point is the base origin)

## `base_height`

Scenario text calls it "base height".

- **Meaning**: How high the base origin is above the floor. The hallway grades its lowest value over the trial.
- **Frame**: The hallway world frame, measured up from the floor (z = 0).
- **Units**: metres
- **Nominal** (per-robot-configuration): A spec states the fall threshold relative to the robot's nominal: base_height above 60% of nominal, so specs stay robot-neutral and the robot binding supplies the nominal (the per-robot nominal_base_height, the measured standing base height in metres). The 60% is a tuning value that can change.
- **Current implementation**: Until the evaluator reads bindings, it grades min_base_height against the manifest's absolute fall_base_height, a per-configuration value in metres. For the G1 that is 0.5 m against a nominal of 0.78 m, about 64% rather than 60%.

Used in:

- examples/scenario/graded/request.json: step stay-upright (above 60% of nominal)
- livingproof-evaluator-scenario checks.py: fail_less grades min_base_height against fall_height, which is the manifest's fall_base_height
- livingproof-evaluator-scenario run manifest: configuration.profile.locomotion.nominal_base_height and fall_base_height

## `body_contact`

Scenario text calls it "body contact".

- **Meaning**: Contact between the robot body and a named environment surface. The scenario names the surface, for example a hallway wall. Each contact has its surface, a start time, an end time and a depth, the penetration at real-geometry signed distance at or below zero.
- **Frame**: The scenario world: the world names each surface (the hallway has wall-left and wall-right) and times run from the start of the trial.
- **Units**: depth in metres, start and end in seconds
- **Nominal** (never): Body contact has no per-robot nominal. The hallway rule is that no contact with a hallway wall is recorded, a limit of zero.
- **Evaluator metric** `wall_contacts`: The hallway evaluator's wall_contacts metric is the count of body_contact events with hallway walls.

Used in:

- examples/scenario/graded/request.json: bound_observables lists body_contact
- livingproof-evaluator-scenario checks.py: fail_not_empty reads wall_contacts, the hallway metric for this term
- robot-capability-specs walk-hallway README: wall_contacts must be empty
