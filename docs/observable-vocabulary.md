# Observable vocabulary

This is the vocabulary a scenario step may use for the hallway: the terms for what is observed about the robot. A hallway scenario is written from these terms, plus places (such as `exit` and the centerline) and numbers.

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
- **Frame**: The world frame, in meters: x and y along the floor, z up from the floor. Lateral distance is measured from the route centerline: the line y = 0 in the straight hallway, the route polyline in the corner worlds.
- **Units**: meters for position, seconds for sample time
- **Nominal** (never): The base position has no per-robot nominal. A scenario states places (exit, centerline) and numbers, not a nominal.

Used in:

- examples/scenario/graded/request.json: steps reach-the-exit and stay-near-centerline
- livingproof-evaluator-scenario checks.py: exit crossing and distance from the route, from the base point of each trace sample (x, y)
- robot-capability-specs walk-hallway README: places, not axes (the body point is the base origin)

## `base_height`

Scenario text calls it "base height".

- **Meaning**: How high the base origin is above the floor. The hallway grades its lowest value over the trial.
- **Frame**: The world frame, measured up from the floor (z = 0).
- **Units**: meters
- **Nominal** (per-robot-configuration): The fall threshold is the absolute fall_height that the walk-hallway spec grades against: the configuration profile's locomotion.fall_base_height, in meters (0.5 m for the G1). The nominal, the per-robot nominal_base_height, is the measured standing base height in meters (0.78 m for the G1 stock configuration). It is reference data only and is not the grading threshold. A threshold stated as a ratio of nominal would be a separate spec change.

Used in:

- examples/scenario/graded/request.json: step stay-upright (the step text states the threshold relative to nominal; the spec grades the absolute fall_height)
- livingproof-evaluator-scenario checks.py: fail_less grades min_base_height against fall_height, which is the manifest's fall_base_height
- livingproof-evaluator-scenario run manifest: configuration.profile.locomotion.nominal_base_height and fall_base_height

## `body_contact`

Scenario text calls it "body contact".

- **Meaning**: Contact between the robot body and a named environment surface. The scenario names the surface, for example a hallway wall. Each contact has its surface, a start time, an end time and a depth: how far the farthest collision part reaches past the surface's inner face, the largest while the contact lasts. That depth is an intrusion, not a penetration depth.
- **Frame**: The scenario world: the world names each surface (the hallway has wall-left and wall-right) and times run from the start of the trial.
- **Units**: depth in meters, start and end in seconds
- **Nominal** (never): Body contact has no per-robot nominal. The hallway rule is that no contact with a hallway wall is recorded, a limit of zero.
- **Evaluator metric** `wall_contacts`: The hallway evaluator's wall_contacts metric is the list of body_contact events with hallway walls, each {wall, start, end, depth}. The hallway passes when the list is empty.

Used in:

- examples/scenario/graded/request.json: bound_observables lists body_contact
- livingproof-evaluator-scenario checks.py: fail_not_empty reads wall_contacts, the hallway metric for this term
- robot-capability-specs walk-hallway README: wall_contacts must be empty
