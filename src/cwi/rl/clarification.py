"""Small reproducible Q-learning experiment for uncertainty-resolution actions.

This synthetic decision process is not a trained navigation or physical safety policy.
Instruction ambiguity and uncertain perception are distinct observed belief categories.
"""

import json
import random
from pathlib import Path
from typing import Literal

Action = Literal["ask", "inspect", "proceed", "defer"]
State = tuple[int, int]  # uncertainty: 0 verified, 1 perceptual, 2 instruction; burden: 0/1
ACTIONS: tuple[Action, ...] = ("ask", "inspect", "proceed", "defer")


def allowed(state: State) -> tuple[Action, ...]:
    if state[0] == 0:
        return ("proceed", "defer")
    if state[0] == 2:
        return ("ask", "defer")
    return ("ask", "inspect", "defer")


def transition(state: State, action: Action, rng: random.Random) -> tuple[State, float, bool]:
    if action not in allowed(state):
        raise ValueError("Action masked by uncertainty guard")
    uncertainty, burden = state
    if action == "proceed":
        return state, 10.0, True
    if action == "defer":
        return state, -4.0, True
    if action == "ask":
        # A cooperative operator resolves the uncertainty, with higher interruption cost when busy.
        return (0, burden), -(2.0 + burden * 4.0), False
    # An inspection sometimes fails to disambiguate the hidden object state.
    return (0 if rng.random() < 0.75 else uncertainty, burden), -1.5, False


class ClarificationPolicy:
    def __init__(self, q: dict[State, dict[Action, float]] | None = None) -> None:
        self.q = q or {
            (u, b): {a: 0.0 for a in allowed((u, b))} for u in range(3) for b in range(2)
        }

    def choose(self, state: State) -> Action:
        return max(allowed(state), key=lambda a: self.q[state].get(a, 0.0))

    def train(self, episodes: int = 5000, seed: int = 7) -> None:
        rng = random.Random(seed)
        for episode in range(episodes):
            state = (rng.randrange(3), rng.randrange(2))
            epsilon = max(0.05, 0.3 * (1 - episode / episodes))
            for _ in range(8):
                action = (
                    rng.choice(allowed(state)) if rng.random() < epsilon else self.choose(state)
                )
                next_state, reward, done = transition(state, action, rng)
                target = reward if done else reward + 0.95 * max(self.q[next_state].values())
                self.q[state][action] += 0.15 * (target - self.q[state][action])
                state = next_state
                if done:
                    break

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({f"{u},{b}": q for (u, b), q in self.q.items()}, indent=2) + "\n"
        )

    @classmethod
    def load(cls, path: Path) -> "ClarificationPolicy":
        raw = json.loads(path.read_text())
        q: dict[State, dict[Action, float]] = {}
        for u in range(3):
            for b in range(2):
                values = raw[f"{u},{b}"]
                q[(u, b)] = {a: float(values[a]) for a in allowed((u, b))}
        return cls(q)


def evaluate(
    policy: ClarificationPolicy, seed: int = 1007, episodes: int = 1000, baseline: str | None = None
) -> dict[str, float]:
    rng = random.Random(seed)
    reward_total = 0.0
    asks = 0
    inspections = 0
    successes = 0
    for episode in range(episodes):
        rng = random.Random(seed * 10000 + episode)
        state = (rng.randrange(3), rng.randrange(2))
        for _ in range(8):
            if baseline == "always_ask":
                action: Action = "proceed" if state[0] == 0 else "ask"
            elif baseline == "inspect_when_possible":
                action = "proceed" if state[0] == 0 else "inspect" if state[0] == 1 else "ask"
            else:
                action = policy.choose(state)
            next_state, reward, done = transition(state, action, rng)
            reward_total += reward
            asks += action == "ask"
            inspections += action == "inspect"
            successes += action == "proceed"
            state = next_state
            if done:
                break
    return {
        "mean_return": reward_total / episodes,
        "asks_per_episode": asks / episodes,
        "inspections_per_episode": inspections / episodes,
        "success_rate": successes / episodes,
    }
