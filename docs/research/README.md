# Research formulation and evaluation protocol

## Task assignment

At tick t, let R be available robots and J be queued transport jobs. Binary x(r,j)
selects at most one job per robot and at most one robot per job:

\[
\sum_j x_{rj}\le1,\qquad \sum_r x_{rj}\le1,\qquad x_{rj}\in\{0,1\}.
\]

A candidate edge exists only if known-map routes exist from robot to pickup,
pickup to destination, and destination to its dedicated charger. Their lengths are
l1, l2, l3. Battery feasibility is l1 + l2 + l3 + 8 <= battery. Payload feasibility
is checked at task validation/submission; tote exclusivity is enforced by the queue.

For priority p=4 (urgent) or p=1 (normal), deadline d(j), and submission tick a(j):

\[
c_{rj}=2(l_1+l_2)+10p_j\max(0,t+l_1+l_2+2-d_j)-p_j(t-a_j).
\]

CP-SAT maximizes \(\sum_{rj}(M-c_{rj})x_{rj}\), where
\(M=1+\sum_{rj}|c_{rj}|\). Thus serving more feasible jobs takes precedence over
cost, with cost breaking ties. This is a bounded assignment problem with a one-second
solver limit, one worker, and fixed seed. Feasible results are accepted even if the
solver times out before proving optimality. The +2 term approximates pickup/delivery
service ticks; deadlines are soft (20 ticks urgent, 50 normal).

Grid BFS routes over the observed map. Starting cells and accepted target cells are
reserved for the entire tick. These conservative constraints imply no vertex
collision or edge swap in the modeled transition, but do not imply shortest joint
paths, deadlock freedom, continuous-space safety, or hard deadline feasibility.
Energy costs are one unit per moved cell; stationary electronics and payload-dependent
power are omitted. The code does not solve the general coupled scheduling/routing
problem optimally.

## Partial observability

Dynamic obstacle presence is hidden outside local sensor range. The planner uses a
shared last-observed map; a change is incorporated only after observation. The initial
inventory and stations are trusted. This is partial observability of obstacles, not
an implemented Bayesian filter over object identities or localization errors.

## Clarification learning

The tabular experimental state is (uncertainty category, operator burden). Categories
are verified, uncertain perception, and ambiguous instruction. Actions are ask,
inspect, proceed, and defer. Action masks prevent proceed in uncertain states and
prevent inspection from resolving an ambiguous instruction by itself.

The synthetic transition model assumes that asking a cooperative human resolves
uncertainty and costs 2 or 6 reward units depending on workload. Inspection costs
1.5 units and succeeds with probability .75. Proceeding after verification yields
10; deferring yields -4. Episodes have an eight-step cap. Tabular Q-learning uses
learning rate .15, discount .95, and decaying epsilon-greedy exploration.

This is a small experimental decision process over observed uncertainty categories,
not a general Dec-POMDP solver or MARL navigation policy. Transition probabilities
and rewards are assumptions requiring calibration from real interaction data.

## Connection to robot execution

When the known map has no route, the simulator invokes the selected assistance
policy with perceptual uncertainty and the current operator-workload flag. Inspection
costs one simulated battery unit and extends that robot's observation radius from
one to three. It can discover a previously hidden opening and enable replanning.
Asking emits an operator-facing feedback event; it does not magically clear an aisle.
Two inspections per assignment and an energy guard limit repeated attempts. Movement
remains governed by the planner and reservations, irrespective of policy output.

The integrated stale-barrier fixture compares the learned policy with both fixed
policies in the actual world. Its sensor model differs from the assumed .75-success
training model; this is a transfer demonstration, not evidence of calibrated returns
or generalization. The default is the fixed inspection baseline because the reported
synthetic experiment does not establish a clear learning advantage over it.

## Questions and baselines

| Question | Implemented support | Further evidence needed |
|---|---|---|
| Grounded task interpretation | Rules baseline, Ollama adapter, explicit-ID guard, model-contract tests, live-model evaluation CLI | Actual model runs; broader paraphrases; retrieval ablation; repeated generations |
| Clarification cost | Q-learning, always-ask and inspect-when-possible comparisons | Held-out transition probabilities, human response noise and human studies |
| Dynamic coordination | Static/dynamic three-robot scenarios and assignment counterexample | More layouts, workloads and seeds; joint MAPF baseline; timeout/deadlock analysis |

Evaluation output records real execution of the synthetic fixtures. Five independent
training seeds are paired with separate evaluation seeds; every method uses the same
initial state for each evaluation episode. Means and sample standard deviations are
descriptive, not confidence intervals or significance tests. The tiny retrieval set
is a sanity check, not a statistically representative language benchmark. Differences
in total movement across the two warehouse cases also include robot-to-task assignment
changes and charger return; they are not evidence that obstacles improve efficiency.

## Reproduction

Run `uv run cwi-evaluate --output outputs/evaluation.json --policy outputs/clarification-policy.json`.
Results and the selected seed-7 policy are JSON. Run `uv run cwi-evaluate-llm --model NAME`
only with a local installed model; its report records model failures as failures.
No measured live LLM or speech results are included without a corresponding run.
