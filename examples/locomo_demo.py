"""
LoCoMo Memory Demo
==================
Demonstrates NucliaMemory using the LoCoMo dataset — a benchmark of long-form
conversations between two speakers spanning many sessions, with QA pairs that
test memory and recall over those conversations.

Dataset: https://snap-research.github.io/locomo/

Mapping to NucliaMemory concepts
---------------------------------
  conversation → topic
      slug = sample_id (e.g. "conv-26"), no pre-populated text
  session → entry
      text = raw formatted turns for that session
             images represented as <img alt="{blip_caption}">
      user_id = "{speaker_a}-{speaker_b}" (the pair is unique across all 10
                conversations; individual names can repeat, e.g. "John")
  QA question → ask()
  Category 5  → negative test (model should say it cannot find the answer)

event_summary and observation fields are intentionally NOT fed into memory.
They are ground-truth summaries used in step 2.5 to compare against what
the memory data-augmentation task extracts on its own.

Configuration
-------------
  DATASET_PATH  path to the downloaded locomo10.json
  SAMPLE_INDEX  which of the 10 conversations to run (0–9)
  MAX_QA        how many QA pairs to evaluate
  QA_CATEGORIES set of category ints to include (5 = adversarial / negative)

Run:
    python examples/locomo_demo.py
"""

from __future__ import annotations

import json
import textwrap
from collections import Counter
from pathlib import Path
from typing import cast

from nuclia.sdk.memory import (
    EntryAlreadyExistsError,
    NucliaMemory,
    TopicAlreadyExistsError,
)

# ─── Configuration ────────────────────────────────────────────────────────────

DATASET_PATH: Path = Path.home() / "Downloads" / "locomo10.json"
SAMPLE_INDEX: int = 0  # 0–9: which of the 10 conversations to use
MAX_QA: int = 20  # cap on QA pairs to evaluate
QA_CATEGORIES: set[int] = {1, 2, 3, 4}  # add 5 to include adversarial / negative tests

# ─── Helpers ─────────────────────────────────────────────────────────────────

SEPARATOR = "─" * 72
CATEGORY_LABELS = {
    1: "single-hop factual",
    2: "temporal",
    3: "commonsense/inference",
    4: "multi-session",
    5: "adversarial/negative",
}


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def subsection(title: str) -> None:
    print(f"\n  ▸ {title}")


# ─── Dataset helpers ──────────────────────────────────────────────────────────


def load_sample(path: Path, index: int) -> dict:
    data = json.loads(path.read_text())
    return data[index]


def format_turn(turn: dict) -> str:
    """Format one conversation turn as a text line, embedding images as alt text."""
    speaker = turn["speaker"]
    text = turn.get("text", "").strip()
    caption = turn.get("blip_caption", "")
    img_tag = f' <img alt="{caption}">' if caption else ""
    return f"{speaker}: {text}{img_tag}"


def format_session(turns: list[dict], date: str, session_n: int) -> str:
    """Format all turns of a session into a single entry text block."""
    header = f"[Session {session_n} — {date}]"
    body = "\n".join(format_turn(t) for t in turns)
    return f"{header}\n\n{body}"


def build_obs_dia_index(sample: dict) -> dict[str, str]:
    """dia_id → speaker name, from the observation field.

    Used only for determining QA question ownership (display purposes),
    not for injecting content into memory.
    """
    index: dict[str, str] = {}
    for obs_val in sample["observation"].values():
        for speaker, obs_list in obs_val.items():
            for _text, dia_id in obs_list:
                index[dia_id] = speaker
    return index


def build_dia_index(sample: dict) -> dict[str, str]:
    """dia_id → speaker name, from the raw conversation turns."""
    index: dict[str, str] = {}
    conv = sample["conversation"]
    for key, turns in conv.items():
        if key.startswith("session_") and not key.endswith("_date_time"):
            for turn in turns:
                index[turn["dia_id"]] = turn["speaker"]
    return index


def question_owner(
    question: dict,
    obs_dia_index: dict[str, str],
    dia_index: dict[str, str],
    fallback: str,
) -> str:
    """Return the speaker most associated with this question's evidence turns."""
    counts: Counter[str] = Counter()
    for dia_id in question.get("evidence", []):
        speaker = obs_dia_index.get(dia_id) or dia_index.get(dia_id)
        if speaker:
            counts[speaker] += 1
    return counts.most_common(1)[0][0] if counts else fallback


# ─── Step 1: Create topic ─────────────────────────────────────────────────────


def create_topic(memory: NucliaMemory, sample: dict) -> tuple[str, str]:
    """Create one NucliaMemory topic per conversation.

    Returns (slug, user_id).
    Topic is intentionally empty — all memory is built from session entries,
    not from pre-populated summaries.
    """
    conv = sample["conversation"]
    slug = sample["sample_id"]
    speaker_a = conv["speaker_a"]
    speaker_b = conv["speaker_b"]
    # Pair is unique across all 10 conversations; individual names can repeat.
    user_id = f"{speaker_a}-{speaker_b}".lower()

    section(f"STEP 1 — Creating topic '{slug}'  ({speaker_a} & {speaker_b})")
    try:
        memory.create_topic(
            slug=slug,
            title=f"{speaker_a} & {speaker_b}",
        )
        print(f"  ✓ Topic created: '{slug}'  (user_id='{user_id}')")
    except TopicAlreadyExistsError:
        print(f"  ~ Topic already exists: '{slug}' — skipping.")

    return slug, user_id


# ─── Step 2: Remember sessions ───────────────────────────────────────────────


def remember_sessions(
    memory: NucliaMemory, sample: dict, topic: str, user_id: str
) -> None:
    """One entry per session; text = raw formatted dialogue."""
    conv = sample["conversation"]
    # All sessions that have conversation data (no artificial cap).
    session_keys = sorted(
        (k for k in conv if k.startswith("session_") and not k.endswith("_date_time")),
        key=lambda k: int(k.split("_")[1]),
    )
    section(f"STEP 2 — Ingesting {len(session_keys)} session(s)")

    ingested = 0
    for session_key in session_keys:
        if ingested >= 3:  # TODO: remove after testing
            breakpoint()
        n = int(session_key.split("_")[1])
        turns = conv[session_key]
        date = conv.get(f"session_{n}_date_time", "unknown date")
        text = format_session(turns, date, n)
        entry_id = f"{topic}-s{n}"

        subsection(f"Session {n}  [{date}]  ({len(turns)} turn(s))")
        try:
            memory.remember(
                text=text,
                topic=topic,
                user_id=user_id,
                entry_id=entry_id,
                metadata={"session": n, "date": date},
            )
            print(f"    ✓ Entry stored  (id={entry_id})")
        except EntryAlreadyExistsError:
            print(f"    ~ Already exists: '{entry_id}' — skipping.")

        ingested += 1

    print(f"\n  Sessions ingested: {ingested}")


# ─── Step 2.5: Compare extracted facts with ground-truth observations ─────────


def show_extracted_facts(
    memory: NucliaMemory, sample: dict, topic: str, user_id: str
) -> None:
    """Show memory-extracted facts alongside the dataset's ground-truth observations.

    session_summary is intentionally omitted here (too verbose); it can be
    inspected manually via sample['session_summary'][f'session_{n}_summary'].
    """
    section("STEP 2.5 — Extracted Facts vs Ground-Truth Observations")
    print(
        "\n  Left column : facts extracted by NucliaMemory (data-augmentation task)"
        "\n  Right column: per-speaker observations from the LoCoMo dataset\n"
        "\n  NOTE: background extraction may still be running; facts may be partial.\n"
    )

    obs_all = sample["observation"]
    ev_all = sample["event_summary"]
    conv = sample["conversation"]

    facts = list(memory.facts(topic=topic, user_id=user_id))
    if not facts:
        print("  (no facts extracted yet — background task may still be running)")
    else:
        print(f"  {len(facts)} fact(s) extracted:\n")
        for fact in reversed(facts):
            ts = fact.timestamp.strftime("%Y-%m-%d %H:%M UTC")
            print(f"    • [{ts}] {fact.content.text}")

    print()
    all_session_nums = sorted(
        int(k.split("_")[1]) for k in obs_all if k.endswith("_observation")
    )
    for n in all_session_nums:
        obs_key = f"session_{n}_observation"
        ev_key = f"events_session_{n}"
        session_obs = obs_all.get(obs_key)
        session_ev = ev_all.get(ev_key)
        if not session_obs and not session_ev:
            continue
        date = conv.get(f"session_{n}_date_time", "?")
        print(f"  ── Session {n}  [{date}] ──")

        if session_ev:
            print(f"    event_summary:")
            for speaker, events in session_ev.items():
                if speaker == "date":
                    continue
                for ev in events:
                    print(f"      [{speaker}] {ev}")

        if session_obs:
            print(f"    observations:")
            for speaker, obs_list in session_obs.items():
                for obs_text, dia_id in obs_list:
                    print(f"      [{speaker} / {dia_id}] {obs_text}")
        print()


# ─── Step 3: QA evaluation ────────────────────────────────────────────────────


def evaluate_qa(memory: NucliaMemory, sample: dict, topic: str, user_id: str) -> None:
    section(
        f"STEP 3 — QA Evaluation  "
        f"(up to {MAX_QA} questions, categories {sorted(QA_CATEGORIES)})"
    )

    obs_dia_index = build_obs_dia_index(sample)
    dia_index = build_dia_index(sample)
    speaker_a = sample["conversation"]["speaker_a"]

    qa_pairs = [q for q in sample["qa"] if q.get("category") in QA_CATEGORIES][:MAX_QA]

    print(f"\n  {len(qa_pairs)} question(s) selected.\n")

    correct = 0
    total = 0

    for i, qa in enumerate(qa_pairs, 1):
        question = qa["question"]
        category = qa.get("category")
        is_adversarial = category == 5
        expected = str(qa.get("answer", "")).strip() if not is_adversarial else None
        adversarial = qa.get("adversarial_answer", "")
        owner = question_owner(qa, obs_dia_index, dia_index, fallback=speaker_a)

        label = CATEGORY_LABELS.get(category, str(category))
        print(f"  [{i:02d}] [{label}]  (evidence owner: {owner})")
        print(f"       Q: {question}")
        if is_adversarial:
            print(f"       Expected: <unanswerable>  (adversarial: '{adversarial}')")
        else:
            print(f"       Expected: {expected}")

        result = memory.ask(query=question, topic=topic, user_id=user_id)
        answer = result.answer.strip()
        indent = "                "
        wrapped = textwrap.fill(
            answer, width=72, initial_indent=indent, subsequent_indent=indent
        )
        print(f"       Got:      {wrapped.lstrip()}")

        if not is_adversarial:
            # naive substring match; upgrade to LLM-as-judge for
            # proper LoCoMo-style evaluation (GPT-4 scorer used in the paper).
            expected = cast(str, expected)
            hit = expected.lower() in answer.lower()
            print(f"       Match: {'✓' if hit else '✗'}\n")
            correct += hit
            total += 1
        else:
            print()

    if total:
        print(
            f"  Accuracy (substring match, categories 1–4): "
            f"{correct}/{total} = {correct / total:.0%}"
        )


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n" + "═" * 72)
    print("  LoCoMo MEMORY DEMO  —  Long-form Conversation Recall with Nuclia")
    print("═" * 72)

    sample = load_sample(DATASET_PATH, SAMPLE_INDEX)
    conv = sample["conversation"]
    n_sessions = sum(
        1 for k in conv if k.startswith("session_") and not k.endswith("_date_time")
    )
    print(
        f"\n  Dataset  : {DATASET_PATH}"
        f"\n  Sample   : {sample['sample_id']}  "
        f"({conv['speaker_a']} & {conv['speaker_b']})"
        f"\n  Sessions : {n_sessions}  |  QA questions : {MAX_QA}"
    )

    memory = NucliaMemory()
    memory.initialize(
        rules=[
            "Attribute each fact to the speaker who expressed it.",
            "Preserve temporal context (dates, relative time) whenever present.",
            "Facts must be grounded in what was explicitly said; do not infer.",
        ],
    )
    breakpoint()
    topic, user_id = create_topic(memory, sample)
    remember_sessions(memory, sample, topic, user_id)
    show_extracted_facts(memory, sample, topic, user_id)
    evaluate_qa(memory, sample, topic, user_id)

    print(f"\n{SEPARATOR}")
    print("  Demo complete.")
    print(SEPARATOR + "\n")


if __name__ == "__main__":
    main()
