"""
HR Buddy Demo
=============
Demonstrates NucliaMemory in an HR assistant use case:

1. Company uploads HR policies as memory topics.
2. Two HR operators (Alice and Bob) each handle 4 employee requests,
   annotating their decisions with context and reasoning.
3. Recall is called for each operator to show that answers are personalised
   (i.e. each operator's annotations influence the generated answer).

Run:
    python examples/hr_buddy_demo.py
"""

from __future__ import annotations

import textwrap

from nuclia.sdk.memory import (
    AnnotationAlreadyExistsError,
    AnnotationContextMessage,
    NucliaMemory,
    TopicAlreadyExistsError,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

SEPARATOR = "─" * 72


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def subsection(title: str) -> None:
    print(f"\n  ▸ {title}")


def annotate(
    memory: NucliaMemory,
    *,
    annotation_id: str,
    text: str,
    topic: str,
    user_id: str,
    **kwargs,
) -> None:
    """Annotate a topic and immediately extract a condensed fact from that annotation."""
    try:
        memory.annotate(
            text=text,
            topic=topic,
            user_id=user_id,
            annotation_id=annotation_id,
            **kwargs,
        )
    except AnnotationAlreadyExistsError:
        print(
            f"\n    ! Annotation with ID '{annotation_id}' already exists. Skipping annotation and fact extraction."
        )


def show_recall(
    memory: NucliaMemory, *, question: str, topic: str, user_id: str
) -> None:
    result = memory.recall(query=question, topic=topic, user_id=user_id)
    indent = "       "
    print(f"\n    Q: {question}")
    print(
        f"    A ({user_id}): {textwrap.fill(result.answer, width=68, subsequent_indent=indent)}"
    )
    if result.citations:
        print(f"\n    Citations:")
        for key, block in result.citations.items():
            snippet = textwrap.fill(
                block.text,
                width=64,
                initial_indent="        ",
                subsequent_indent="        ",
            )
            print(f"      [{key}] (score={block.score:.3f})")
            print(snippet)


# ─── 1. Upload HR Policies ────────────────────────────────────────────────────

POLICIES: dict[str, dict[str, str]] = {
    "vacation-policy": {
        "title": "Vacation Policy",
        "summary": "Rules governing employee paid time off.",
        "text": textwrap.dedent("""\
            # Vacation Policy

            ## Accrual
            Full-time employees accrue 1.5 days of paid vacation per month (18 days/year).
            Part-time employees accrue vacation on a pro-rata basis.
            Vacation begins accruing from the first day of employment.

            ## Carry-over
            Employees may carry over a maximum of 5 unused vacation days into the next calendar year.
            Any excess days are forfeited on January 1st unless a written exception is approved by HR.

            ## Approval
            Vacation requests must be submitted at least 2 weeks in advance via the HR portal.
            Managers may deny requests if they conflict with critical business needs.

            ## Payout on Termination
            Accrued but unused vacation days will be paid out upon voluntary or involuntary termination,
            up to the carry-over cap of 5 days.
        """),
    },
    "remote-work-policy": {
        "title": "Remote Work Policy",
        "summary": "Guidelines for working from home or remote locations.",
        "text": textwrap.dedent("""\
            # Remote Work Policy

            ## Eligibility
            Employees who have completed their 90-day probationary period are eligible to request remote work.
            Remote work is a privilege, not a right, and is subject to manager approval.

            ## Work-from-home days
            Eligible employees may work remotely up to 3 days per week.
            At least 2 days per week must be spent in the office.

            ## Equipment
            The company provides a laptop. Employees are responsible for their own internet connection.
            A $50/month home-office stipend is available for employees working 3 remote days per week.

            ## Performance expectations
            Remote employees are expected to be available during core hours (10:00–16:00 local time).
            Productivity will be reviewed quarterly. Sustained underperformance may result in revocation of remote work privileges.
        """),
    },
    "parental-leave-policy": {
        "title": "Parental Leave Policy",
        "summary": "Paid and unpaid leave entitlements for new parents.",
        "text": textwrap.dedent("""\
            # Parental Leave Policy

            ## Primary caregiver
            The primary caregiver is entitled to 16 weeks of fully paid parental leave.
            Leave may begin up to 2 weeks before the expected due date.

            ## Secondary caregiver
            The secondary caregiver is entitled to 4 weeks of fully paid parental leave.

            ## Adoption
            Adoptive parents receive the same entitlements as biological parents, based on their caregiver role.

            ## Notice
            Employees should notify HR at least 8 weeks before the anticipated start of leave.
            Documentation (birth certificate or adoption order) must be provided within 30 days of the event.

            ## Return to work
            Employees returning from parental leave are guaranteed their original role or an equivalent position.
        """),
    },
    "performance-review-policy": {
        "title": "Performance Review Policy",
        "summary": "Process and cadence for employee performance evaluations.",
        "text": textwrap.dedent("""\
            # Performance Review Policy

            ## Cycle
            Formal performance reviews are conducted twice a year: in June and December.
            New employees complete a 90-day probationary review before joining the standard cycle.

            ## Rating scale
            Performance is rated on a 5-point scale:
              1 – Does not meet expectations
              2 – Partially meets expectations
              3 – Meets expectations
              4 – Exceeds expectations
              5 – Outstanding

            ## Compensation impact
            Ratings of 4 or 5 are eligible for merit increases (typically 3–8%).
            Ratings of 1 or 2 trigger a Performance Improvement Plan (PIP).

            ## Self-assessment
            Employees must complete a self-assessment form in the HR portal at least 1 week before the review meeting.

            ## Appeal
            Employees who disagree with their rating may submit a written appeal to HR within 14 days.
        """),
    },
}


def upload_policies(memory: NucliaMemory) -> None:
    section("STEP 1 — Uploading HR Policies")
    for slug, policy in POLICIES.items():
        try:
            memory.store(
                text=policy["text"],
                slug=slug,
                title=policy["title"],
                summary=policy["summary"],
            )
            print(f"  ✓ Uploaded: '{policy['title']}' (slug={slug})")
        except TopicAlreadyExistsError:
            print(f"  ~ Already exists: '{policy['title']}' (slug={slug})")


# ─── 2. HR Operator Annotations ──────────────────────────────────────────────

# Each operator is assigned 4 employee requests.
# Their annotations include their decision, reasoning, and context.

ALICE_ID = "alice-hr"
BOB_ID = "bob-hr"


def alice_handles_requests(memory: NucliaMemory) -> None:
    section("STEP 2a — Alice (HR Operator) handles employee requests")

    # Request 1 — Vacation carry-over exception
    subsection("Request 1: Maria asks for a carry-over exception (8 days)")
    annotate(
        memory,
        annotation_id="alice-annotation-001",
        text="Approved carry-over exception for Maria (employee ID: EMP-1042). "
        "She was unable to take her remaining 8 vacation days due to a critical product launch in Q4. "
        "Exception approved for the full 8 days as a one-time allowance.",
        topic="vacation-policy",
        user_id=ALICE_ID,
        reasoning="The product launch was a company-wide priority that required Maria's presence. "
        "Denying the exception would penalise her for meeting business needs.",
        context=[
            AnnotationContextMessage(
                author="Maria (employee)",
                text="I had 8 vacation days remaining but couldn't take them because of the Q4 launch. Can I carry them over?",
            ),
            AnnotationContextMessage(
                author="Maria's manager",
                text="Confirmed — Maria's presence was essential during the entire Q4 period.",
            ),
        ],
        metadata={
            "employee_id": "EMP-1042",
            "employee_name": "Maria Santos",
            "department": "Engineering",
            "decision": "approved",
            "days_requested": 8,
            "exception_type": "carry-over",
            "supporting_evidence": ["manager_confirmation", "business_critical_event"],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 2 — Remote work 4 days/week
    subsection("Request 2: James asks to work remotely 4 days per week")
    annotate(
        memory,
        annotation_id="alice-annotation-002",
        text="Denied remote work extension for James (EMP-2317). "
        "Policy allows a maximum of 3 remote days per week; no exceptions are currently being granted.",
        topic="remote-work-policy",
        user_id=ALICE_ID,
        reasoning="Standard policy cap is 3 days. James has not provided a compelling reason (e.g. medical) "
        "that would warrant a policy exception review.",
        context=[
            AnnotationContextMessage(
                author="James (employee)",
                text="I'd like to work remotely 4 days a week — I find I'm more productive at home.",
            ),
        ],
        metadata={
            "employee_id": "EMP-2317",
            "employee_name": "James Liu",
            "department": "Product",
            "decision": "denied",
            "days_requested": 4,
            "exception_type": "remote-work-extension",
            "supporting_evidence": [],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 3 — Parental leave start date
    subsection("Request 3: Sophie asks to start parental leave 3 weeks early")
    annotate(
        memory,
        annotation_id="alice-annotation-003",
        text="Approved early start of parental leave for Sophie (EMP-3891) — 3 weeks before due date "
        "(1 week beyond the standard 2-week pre-birth allowance). "
        "Medical note from her OB-GYN on file.",
        topic="parental-leave-policy",
        user_id=ALICE_ID,
        reasoning="Sophie's physician recommended reduced activity due to a high-risk pregnancy. "
        "An extra week pre-birth is warranted on medical grounds.",
        context=[
            AnnotationContextMessage(
                author="Sophie (employee)",
                text="My doctor recommends I start leave 3 weeks before the due date due to complications.",
            ),
            AnnotationContextMessage(
                author="Sophie's doctor (note)",
                text="Patient is advised to avoid commuting and office work from week 37 of pregnancy.",
            ),
        ],
        metadata={
            "employee_id": "EMP-3891",
            "employee_name": "Sophie Martin",
            "department": "Finance",
            "decision": "approved",
            "caregiver_role": "primary",
            "exception_type": "early-leave-start",
            "weeks_early": 3,
            "supporting_evidence": ["medical_note"],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 4 — Performance review appeal
    subsection("Request 4: David appeals his performance rating of 2")
    annotate(
        memory,
        annotation_id="alice-annotation-004",
        text="Appeal accepted for David (EMP-4455). Rating revised from 2 to 3 after reviewing additional "
        "project contributions that were not reflected in the original evaluation.",
        topic="performance-review-policy",
        user_id=ALICE_ID,
        reasoning="David provided evidence of three successful deliverables completed in the review period "
        "that his manager had overlooked. Evidence reviewed and found credible.",
        context=[
            AnnotationContextMessage(
                author="David (employee)",
                text="I believe my rating of 2 is unfair. I delivered three major projects on time this period.",
            ),
            AnnotationContextMessage(
                author="David's skip-level manager",
                text="I can confirm David's contributions to the platform migration were significant.",
            ),
        ],
        metadata={
            "employee_id": "EMP-4455",
            "employee_name": "David Osei",
            "department": "Engineering",
            "decision": "appeal_accepted",
            "original_rating": 2,
            "revised_rating": 3,
            "review_cycle": "2026-H1",
            "supporting_evidence": ["skip_level_confirmation", "project_deliverables"],
        },
    )
    print("    ✓ Annotation recorded.")


def bob_handles_requests(memory: NucliaMemory) -> None:
    section("STEP 2b — Bob (HR Operator) handles employee requests")

    # Request 1 — Vacation carry-over exception (different stance)
    subsection("Request 1: Leo asks for a carry-over exception (6 days)")
    annotate(
        memory,
        annotation_id="bob-annotation-001",
        text="Denied carry-over exception for Leo (EMP-5512). "
        "Leo had adequate opportunity to schedule vacation during the year and did not do so. "
        "The 6 days will be forfeited per standard policy.",
        topic="vacation-policy",
        user_id=BOB_ID,
        reasoning="Unlike cases involving company-mandated business needs, Leo's unused days reflect "
        "personal planning choices. Policy should be applied as written.",
        context=[
            AnnotationContextMessage(
                author="Leo (employee)",
                text="I forgot to use 6 vacation days. Can I carry them over to next year?",
            ),
        ],
        metadata={
            "employee_id": "EMP-5512",
            "employee_name": "Leo Fernandez",
            "department": "Sales",
            "decision": "denied",
            "days_requested": 6,
            "exception_type": "carry-over",
            "supporting_evidence": [],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 2 — Remote work during probation
    subsection("Request 2: Nina asks to work remotely while still in probation")
    annotate(
        memory,
        annotation_id="bob-annotation-002",
        text="Denied remote work request for Nina (EMP-6780). "
        "Nina is 45 days into her 90-day probationary period and is not yet eligible.",
        topic="remote-work-policy",
        user_id=BOB_ID,
        reasoning="Eligibility is explicitly tied to completing the 90-day probationary period. "
        "Nina should reapply after day 90.",
        context=[
            AnnotationContextMessage(
                author="Nina (employee)",
                text="I've been here 45 days and would like to work from home 2 days a week.",
            ),
        ],
        metadata={
            "employee_id": "EMP-6780",
            "employee_name": "Nina Patel",
            "department": "Customer Success",
            "decision": "denied",
            "days_in_company": 45,
            "probation_days_remaining": 45,
            "exception_type": "pre-probation-remote-work",
            "supporting_evidence": [],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 3 — Secondary caregiver parental leave split
    subsection(
        "Request 3: Carlos asks to split his secondary caregiver leave into two blocks"
    )
    annotate(
        memory,
        annotation_id="bob-annotation-003",
        text="Approved split parental leave for Carlos (EMP-7023). "
        "He will take 2 weeks immediately after birth and the remaining 2 weeks in month 4. "
        "Both blocks are fully paid.",
        topic="parental-leave-policy",
        user_id=BOB_ID,
        reasoning="Policy does not prohibit splitting leave. Splitting benefits both the family and "
        "continuity of Carlos's team project. Manager has confirmed coverage is available.",
        context=[
            AnnotationContextMessage(
                author="Carlos (employee)",
                text="Can I take my 4-week secondary caregiver leave in two separate blocks?",
            ),
            AnnotationContextMessage(
                author="Carlos's manager",
                text="Happy to accommodate — we can plan around both windows.",
            ),
        ],
        metadata={
            "employee_id": "EMP-7023",
            "employee_name": "Carlos Romero",
            "department": "Design",
            "decision": "approved",
            "caregiver_role": "secondary",
            "exception_type": "split-leave",
            "leave_blocks": [
                {"week": 1, "duration_weeks": 2, "timing": "immediately_after_birth"},
                {"week": 2, "duration_weeks": 2, "timing": "month_4"},
            ],
            "supporting_evidence": ["manager_confirmation"],
        },
    )
    print("    ✓ Annotation recorded.")

    # Request 4 — PIP challenge
    subsection("Request 4: Rachel disputes being placed on a PIP")
    annotate(
        memory,
        annotation_id="bob-annotation-004",
        text="PIP upheld for Rachel (EMP-8899). "
        "Rating of 1 was confirmed after reviewing her manager's documentation. "
        "Rachel has been provided with the formal PIP plan and 90-day improvement timeline.",
        topic="performance-review-policy",
        user_id=BOB_ID,
        reasoning="Manager provided detailed evidence of missed deadlines and quality issues "
        "over the review period. No procedural errors found in the evaluation process.",
        context=[
            AnnotationContextMessage(
                author="Rachel (employee)",
                text="I don't think it's fair that I'm on a PIP. My workload was unreasonable.",
            ),
            AnnotationContextMessage(
                author="Rachel's manager",
                text="Rachel missed 7 out of 10 delivery milestones. Workload was comparable to peers.",
            ),
        ],
        metadata={
            "employee_id": "EMP-8899",
            "employee_name": "Rachel Kim",
            "department": "Operations",
            "decision": "pip_upheld",
            "rating": 1,
            "pip_duration_days": 90,
            "review_cycle": "2026-H1",
            "milestones_missed": 7,
            "milestones_total": 10,
            "supporting_evidence": ["manager_documentation", "peer_comparison"],
        },
    )
    print("    ✓ Annotation recorded.")


# ─── 2.5. Inspect Extracted Facts ────────────────────────────────────────────


def show_extracted_facts(memory: NucliaMemory) -> None:
    section("STEP 2.5 — Extracted Facts (simulated data-augmentation task)")

    print(
        "\n  Each annotation was immediately distilled into a concise fact.\n"
        "  In production these would be produced by an async DA task.\n"
    )

    for user_id, label in [(ALICE_ID, "Alice"), (BOB_ID, "Bob")]:
        print(f"\n  ── {label}'s facts ──")
        for slug in POLICIES:
            facts = list(memory.facts(topic=slug, user_id=user_id))
            if not facts:
                continue
            print(f"\n    [{slug}]")
            for fact in reversed(facts):  # oldest-first for readability
                ts = fact.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                print(f"      • [{ts}] {fact.content.text}")


# ─── 3. Personalised Recall ───────────────────────────────────────────────────

RECALL_QUESTIONS: list[dict] = [
    {
        "topic": "vacation-policy",
        "question": "Have you ever approved a carry-over exception beyond the 5-day cap, and if so, under what conditions?",
    },
    {
        "topic": "remote-work-policy",
        "question": "Has any employee on your team been granted more than 3 remote days per week, or have all such requests been denied?",
    },
    {
        "topic": "parental-leave-policy",
        "question": "Have you handled any parental leave requests that required a non-standard arrangement, such as an early start or split leave?",
    },
    {
        "topic": "performance-review-policy",
        "question": "Have any performance rating appeals or PIP disputes been resolved on your end this cycle, and what was the outcome?",
    },
]


def demonstrate_personalisation(memory: NucliaMemory) -> None:
    section("STEP 3 — Personalised Recall: Alice vs Bob")

    print(
        "\n  The same question is asked for each policy topic, once as Alice and once as Bob.\n"
        "  Notice how each operator's past decisions and reasoning shape the generated answer.\n"
    )

    for item in RECALL_QUESTIONS:
        topic = item["topic"]
        question = item["question"]
        print(f"\n  Policy topic : {topic}")
        print(f"  Question     : {question}")
        print()
        show_recall(memory, question=question, topic=topic, user_id=ALICE_ID)
        show_recall(memory, question=question, topic=topic, user_id=BOB_ID)
        print()


# ─── 4. Graph Personalisation ─────────────────────────────────────────────────


def show_graph(memory: NucliaMemory, *, topic: str, user_id: str, label: str) -> None:
    edges = memory.graph(topic=topic, user_id=user_id)
    if not edges:
        print(f"    ({label}: no graph edges found)")
        return
    print(f"\n    Graph for {label} ({len(edges)} edge(s)):")
    for edge in edges:
        src_group = f"/{edge.source.group}" if edge.source.group else ""
        dst_group = f"/{edge.destination.group}" if edge.destination.group else ""
        ctx = (
            f"  ← block {edge.metadata.context_block_id}"
            if edge.metadata and edge.metadata.context_block_id
            else ""
        )
        print(
            f"      [{edge.source.type}{src_group}] {edge.source.value!r}"
            f"  ──{edge.relation.label}({edge.relation.type})──▶ "
            f"[{edge.destination.type}{dst_group}] {edge.destination.value!r}"
            f"{ctx}"
        )


def demonstrate_graph_personalisation(memory: NucliaMemory) -> None:
    section("STEP 4 — Personalised Knowledge Graph: Alice vs Bob")

    print(
        "\n  The entity graph is queried for each policy topic, once scoped to Alice\n"
        "  and once to Bob. Each operator's annotations contribute different entities\n"
        "  and relations, making the graph a personalised view of the policy space.\n"
    )

    for slug, policy in POLICIES.items():
        print(f"\n  ── {policy['title']} ({slug}) ──")
        show_graph(memory, topic=slug, user_id=ALICE_ID, label="Alice")
        show_graph(memory, topic=slug, user_id=BOB_ID, label="Bob")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n" + "═" * 72)
    print("  HR BUDDY DEMO  —  Personalised HR Assistant with NucliaMemory")
    print("═" * 72)

    memory = NucliaMemory()
    memory.initialize(llm_config={"model": "chatgpt-azure-5-mini"})
    upload_policies(memory)
    alice_handles_requests(memory)
    bob_handles_requests(memory)
    show_extracted_facts(memory)
    demonstrate_personalisation(memory)
    demonstrate_graph_personalisation(memory)

    print(f"\n{SEPARATOR}")
    print("  Demo complete.")
    print(SEPARATOR + "\n")


if __name__ == "__main__":
    main()
