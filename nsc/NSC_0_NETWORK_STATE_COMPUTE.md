# NSC-0 Network State Compute

Status: implemented for first experiment.

Goal:

```text
Test whether real network-state input can drive a small state body through
measurable transduction, instead of judging the network only by CPU-like task
speed or task-choice improvement.
```

Experiment shape:

```text
1. Start from one fixed seed state.
2. Sample real network targets over several rounds.
3. Convert each round into a network observation vector.
4. Feed the same transducer with four input streams:
   - real sequential network observations
   - fixed first observation
   - pseudo-random synthetic observations
   - shuffled real observations
5. Inject the same disturbance halfway through each stream.
6. Compare convergence, continuity, recovery, and input-state coupling.
```

Metrics:

```text
final_distance_to_goal: lower is better.
convergence_gain: how far the state moved from initial distance toward goal.
monotonicity: how often distance improved from one round to the next.
continuity: how smooth the state path is.
recovery: how much distance was repaired after injected disturbance.
coupling: whether input change magnitude and state change magnitude are linked.
effective_state_work: combined score for this NSC-0 protocol.
```

Interpretation:

```text
NSC-0 strong evidence requires real input to beat fixed, PRNG, and shuffled
controls on effective_state_work by at least 5 percent over the best control.

If real input beats all controls but stays below that margin, the result is a
weak real-network edge, not a strong advantage.

If real input only moves the state but does not beat controls, the result is
transduction observed but no network-state advantage.
```

Truth boundary:

```text
NSC-0 still runs on a material CPU to observe and score the experiment.
It does not prove CPU-free computation, endpoint-free execution, faster-than-CPU
compute, or a finished ghost computer.
```
