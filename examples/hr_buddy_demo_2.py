"""
HR Buddy Demo 2
===============
Same HR use-case as hr_buddy_demo.py, but this time the NucliaMemory SDK is
wrapped inside a clean `HRBuddy` class that exposes an HR-domain API:

  - HRBuddy.add_policy()         — upload / upsert a company HR policy
  - HRBuddy.handle_request()     — HR operator annotates + extracts a fact
  - HRBuddy.ask()                — personalised generative answer for an operator
  - HRBuddy.search()             — personalised semantic retrieval for an operator
  - HRBuddy.operator_facts()     — list an operator's distilled facts for a policy
  - HRBuddy.operator_graph()     — operator-scoped entity graph for a policy

Run:
    python examples/hr_buddy_demo_2.py
"""

from __future__ import annotations

import textwrap
import uuid
from dataclasses import dataclass, field
from typing import Iterator

from nuclia.sdk.memory import (
    AnnotationAlreadyExistsError,
    AnnotationContextMessage,
    Fact,
    GraphEdge,
    NucliaMemory,
    RecallResult,
    RelevantContextBlock,
    TopicAlreadyExistsError,
)

# ─── Domain models ────────────────────────────────────────────────────────────


@dataclass
class EmployeeRequest:
    """An employee request submitted to the HR buddy."""

    employee_id: str
    employee_name: str
    department: str
    policy_slug: str
    request_text: str


@dataclass
class RequestDecision:
    """The HR operator's decision on an employee request."""

    decision: str  # e.g. "approved" / "denied"
    summary: str  # brief decision text stored as annotation
    fact: str  # condensed one-liner stored as a fact
    reasoning: str | None = None
    context_messages: list[AnnotationContextMessage] = field(default_factory=list)
    extra_metadata: dict = field(default_factory=dict)


# ─── HRBuddy ─────────────────────────────────────────────────────────────────


class HRBuddy:
    """
    A thin HR-domain layer on top of NucliaMemory.

    Each company policy maps to a Memory *topic* (slug = policy slug).
    Each HR operator is identified by an operator_id string.
    Employee request handling produces both a rich annotation and a condensed fact.
    """

    def __init__(self) -> None:
        self._memory = NucliaMemory()
        self._memory.initialize(llm_config={"model": "chatgpt-azure-5-mini"})

    # ── Policy management ────────────────────────────────────────────────────

    def add_policy(
        self,
        slug: str,
        title: str,
        text: str,
        summary: str | None = None,
    ) -> None:
        """Upload a new HR policy. Silently skips if the policy already exists."""
        try:
            self._memory.store(
                text=text,
                slug=slug,
                title=title,
                summary=summary,
            )
            print(f"  [HRBuddy] Policy uploaded: '{title}' (slug={slug})")
        except TopicAlreadyExistsError:
            print(
                f"  [HRBuddy] Policy already exists, skipping: '{title}' (slug={slug})"
            )

    # ── Request handling ─────────────────────────────────────────────────────

    def handle_request(
        self,
        operator_id: str,
        request: EmployeeRequest,
        decision: RequestDecision,
        *,
        annotation_id: str | None = None,
    ) -> str:
        """
        Record an HR operator's decision on an employee request.

        Stores a rich annotation (full decision text + reasoning + conversation
        context) and immediately distils it into a concise searchable fact.

        Returns the annotation_id used.
        """
        aid = annotation_id or uuid.uuid4().hex
        metadata = {
            "employee_id": request.employee_id,
            "employee_name": request.employee_name,
            "department": request.department,
            "decision": decision.decision,
            **decision.extra_metadata,
        }
        try:
            self._memory.annotate(
                text=decision.summary,
                topic=request.policy_slug,
                user_id=operator_id,
                annotation_id=aid,
                reasoning=decision.reasoning,
                context=decision.context_messages or None,
                metadata=metadata,
            )
            # self._memory._extract_facts(
            #     aid,
            #     topic=request.policy_slug,
            #     user_id=operator_id,
            #     text=decision.fact,
            # )
            print(
                f"  [HRBuddy] {operator_id} handled request from {request.employee_name}"
                f" ({request.employee_id}) → {decision.decision}"
            )
        except AnnotationAlreadyExistsError:
            print(
                f"  [HRBuddy] Annotation '{aid}' already exists for {operator_id}"
                f" on '{request.policy_slug}'. Skipping."
            )
        return aid

    # ── Query interface ───────────────────────────────────────────────────────

    def ask(
        self,
        operator_id: str,
        policy_slug: str,
        question: str,
    ) -> RecallResult:
        """
        Ask a question scoped to a policy and personalised for the operator.
        Returns a generative answer grounded in the policy text and the
        operator's own annotations and facts.
        """
        return self._memory.recall(
            query=question,
            topic=policy_slug,
            user_id=operator_id,
        )

    def search(
        self,
        operator_id: str,
        policy_slug: str,
        question: str,
        top_k: int = 10,
    ) -> list[RelevantContextBlock]:
        """
        Semantic + keyword retrieval scoped to a policy and an operator.
        Returns ranked context blocks from the policy and the operator's memory.
        """
        return self._memory.retrieve(
            question=question,
            topic=policy_slug,
            user_id=operator_id,
            top_k=top_k,
        )

    # ── Inspection ───────────────────────────────────────────────────────────

    def operator_facts(
        self,
        operator_id: str,
        policy_slug: str,
    ) -> Iterator[Fact]:
        """Iterate over all facts an operator has extracted for a given policy."""
        return self._memory.facts(topic=policy_slug, user_id=operator_id)

    def operator_graph(
        self,
        operator_id: str,
        policy_slug: str,
    ) -> list[GraphEdge]:
        """Return the entity graph scoped to a policy and an operator."""
        return self._memory.graph(
            topic=policy_slug, user_id=operator_id, facts_only=True
        )


# ─── CLI helpers ─────────────────────────────────────────────────────────────

SEPARATOR = "─" * 72


def section(title: str) -> None:
    print(f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}")


def subsection(title: str) -> None:
    print(f"\n  ▸ {title}")


def print_recall(result: RecallResult, operator_id: str) -> None:
    indent = "       "
    print(
        f"    A ({operator_id}): {textwrap.fill(result.answer, width=68, subsequent_indent=indent)}"
    )
    if result.citations:
        print("\n    Citations:")
        for key, block in result.citations.items():
            snippet = textwrap.fill(
                block.text,
                width=64,
                initial_indent="        ",
                subsequent_indent="        ",
            )
            print(f"      [{key}] (score={block.score:.3f})")
            print(snippet)


def print_graph(edges: list[GraphEdge], operator_id: str) -> None:
    if not edges:
        print(f"    ({operator_id}: no graph edges)")
        return
    print(f"\n    Graph ({operator_id}, {len(edges)} edge(s)):")
    for e in edges:
        src_g = f"/{e.source.group}" if e.source.group else ""
        dst_g = f"/{e.destination.group}" if e.destination.group else ""
        ctx = (
            f"  ← block {e.metadata.context_block_id}"
            if e.metadata and e.metadata.context_block_id
            else ""
        )
        print(
            f"      [{e.source.type}{src_g}] {e.source.value!r}"
            f"  ──{e.relation.label}({e.relation.type})──▶ "
            f"[{e.destination.type}{dst_g}] {e.destination.value!r}{ctx}"
        )


# ─── 1. Company policies ─────────────────────────────────────────────────────

POLICIES = {
    "vacation-policy": {
        "title": "Vacation Policy",
        "summary": "Rules governing employee paid time off.",
        "text": textwrap.dedent("""\
            # Vacation Policy

            ## Accrual
            Full-time employees accrue 1.5 days of paid vacation per month (18 days/year).
            Part-time employees accrue vacation on a pro-rata basis.

            ## Carry-over
            Employees may carry over a maximum of 5 unused vacation days into the next calendar year.
            Any excess days are forfeited on January 1st unless a written exception is approved by HR.

            ## Approval
            Vacation requests must be submitted at least 2 weeks in advance via the HR portal.
            Managers may deny requests if they conflict with critical business needs.

            ## Payout on Termination
            Accrued but unused vacation days will be paid out upon termination, up to the carry-over cap.
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
            The company provides a laptop. A $50/month home-office stipend is available for employees
            working 3 remote days per week.

            ## Performance expectations
            Remote employees must be available during core hours (10:00–16:00 local time).
            Sustained underperformance may result in revocation of remote work privileges.
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

            ## Notice
            Employees should notify HR at least 8 weeks before the anticipated start of leave.
            Documentation must be provided within 30 days of the event.

            ## Return to work
            Employees returning from parental leave are guaranteed their original role or an equivalent.
        """),
    },
    "performance-review-policy": {
        "title": "Performance Review Policy",
        "summary": "Process and cadence for employee performance evaluations.",
        "text": textwrap.dedent("""\
            # Performance Review Policy

            ## Cycle
            Formal performance reviews are conducted twice a year: in June and December.

            ## Rating scale
            1 – Does not meet expectations  |  2 – Partially meets  |  3 – Meets
            4 – Exceeds expectations        |  5 – Outstanding

            ## Compensation impact
            Ratings of 4 or 5 are eligible for merit increases (3–8%).
            Ratings of 1 or 2 trigger a Performance Improvement Plan (PIP).

            ## Appeal
            Employees who disagree with their rating may submit a written appeal to HR within 14 days.
        """),
    },
}


def load_policies(buddy: HRBuddy) -> None:
    section("STEP 1 — Loading Company HR Policies")
    for slug, p in POLICIES.items():
        buddy.add_policy(
            slug=slug, title=p["title"], text=p["text"], summary=p["summary"]
        )


# ─── 2. Operator request handling ────────────────────────────────────────────

ALICE = "alice-hr"
BOB = "bob-hr"


def alice_handles_requests(buddy: HRBuddy) -> None:
    section("STEP 2a — Alice handles employee requests")

    subsection("Maria: carry-over exception (8 days)")
    buddy.handle_request(
        ALICE,
        EmployeeRequest(
            employee_id="EMP-1042",
            employee_name="Maria Santos",
            department="Engineering",
            policy_slug="vacation-policy",
            request_text="I had 8 vacation days remaining but couldn't take them because of the Q4 launch. Can I carry them over?",
        ),
        RequestDecision(
            decision="approved",
            summary=(
                "Approved carry-over exception for Maria (EMP-1042). "
                "She was unable to use 8 vacation days due to a company-wide Q4 product launch. "
                "Exception granted for the full 8 days as a one-time allowance."
            ),
            fact="EMP-1042 (Maria Santos, Engineering): carry-over exception approved for 8 days — Q4 product launch prevented vacation use; manager confirmed business-critical need.",
            reasoning="The Q4 launch was a company priority that required Maria's continuous presence. Denying the exception would penalise her for meeting business needs.",
            context_messages=[
                AnnotationContextMessage(
                    author="Maria (employee)",
                    text="I had 8 vacation days remaining but couldn't take them because of the Q4 launch. Can I carry them over?",
                ),
                AnnotationContextMessage(
                    author="Maria's manager",
                    text="Confirmed — Maria's presence was essential during the entire Q4 period.",
                ),
            ],
            extra_metadata={
                "days_requested": 8,
                "exception_type": "carry-over",
                "supporting_evidence": [
                    "manager_confirmation",
                    "business_critical_event",
                ],
            },
        ),
        annotation_id="alice-001",
    )

    subsection("James: 4 remote days/week request")
    buddy.handle_request(
        ALICE,
        EmployeeRequest(
            employee_id="EMP-2317",
            employee_name="James Liu",
            department="Product",
            policy_slug="remote-work-policy",
            request_text="I'd like to work remotely 4 days a week — I find I'm more productive at home.",
        ),
        RequestDecision(
            decision="denied",
            summary=(
                "Denied remote work extension for James (EMP-2317). "
                "Policy caps remote days at 3 per week; no exception criteria were met."
            ),
            fact="EMP-2317 (James Liu, Product): request for 4 remote days/week denied — policy cap is 3 days; no medical or business exception presented.",
            reasoning="No compelling exception justification (medical, disability, etc.) was provided.",
            context_messages=[
                AnnotationContextMessage(
                    author="James (employee)",
                    text="I'd like to work remotely 4 days a week — I find I'm more productive at home.",
                ),
            ],
            extra_metadata={
                "days_requested": 4,
                "exception_type": "remote-work-extension",
            },
        ),
        annotation_id="alice-002",
    )

    subsection("Sophie: parental leave start 3 weeks early")
    buddy.handle_request(
        ALICE,
        EmployeeRequest(
            employee_id="EMP-3891",
            employee_name="Sophie Martin",
            department="Finance",
            policy_slug="parental-leave-policy",
            request_text="My doctor recommends I start leave 3 weeks before the due date due to pregnancy complications.",
        ),
        RequestDecision(
            decision="approved",
            summary=(
                "Approved early parental leave start for Sophie (EMP-3891) — 3 weeks before due date "
                "(1 week beyond the standard 2-week allowance). Medical note from OB-GYN on file."
            ),
            fact="EMP-3891 (Sophie Martin, Finance): parental leave approved to start 3 weeks early — high-risk pregnancy; OB-GYN medical note on file.",
            reasoning="Sophie's physician recommended reduced activity due to a high-risk pregnancy. The extra week is medically warranted.",
            context_messages=[
                AnnotationContextMessage(
                    author="Sophie (employee)",
                    text="My doctor recommends I start leave 3 weeks before the due date due to complications.",
                ),
                AnnotationContextMessage(
                    author="Sophie's OB-GYN (note)",
                    text="Patient advised to avoid commuting and office work from week 37.",
                ),
            ],
            extra_metadata={
                "caregiver_role": "primary",
                "weeks_early": 3,
                "supporting_evidence": ["medical_note"],
            },
        ),
        annotation_id="alice-003",
    )

    subsection("David: performance rating appeal (2 → 3)")
    buddy.handle_request(
        ALICE,
        EmployeeRequest(
            employee_id="EMP-4455",
            employee_name="David Osei",
            department="Engineering",
            policy_slug="performance-review-policy",
            request_text="I believe my rating of 2 is unfair. I delivered three major projects on time this period.",
        ),
        RequestDecision(
            decision="appeal_accepted",
            summary=(
                "Appeal accepted for David (EMP-4455). "
                "Rating revised from 2 to 3 after verifying project contributions overlooked in the original evaluation."
            ),
            fact="EMP-4455 (David Osei, Engineering): performance appeal accepted for 2026-H1 — rating raised from 2 to 3; three overlooked deliverables verified.",
            reasoning="David provided evidence of three on-time deliverables his manager had missed. Evidence confirmed by skip-level manager.",
            context_messages=[
                AnnotationContextMessage(
                    author="David (employee)",
                    text="I believe my rating of 2 is unfair. I delivered three major projects on time this period.",
                ),
                AnnotationContextMessage(
                    author="David's skip-level manager",
                    text="I can confirm David's contributions to the platform migration were significant.",
                ),
            ],
            extra_metadata={
                "original_rating": 2,
                "revised_rating": 3,
                "review_cycle": "2026-H1",
                "supporting_evidence": [
                    "skip_level_confirmation",
                    "project_deliverables",
                ],
            },
        ),
        annotation_id="alice-004",
    )


def bob_handles_requests(buddy: HRBuddy) -> None:
    section("STEP 2b — Bob handles employee requests")

    subsection("Leo: carry-over exception (6 days)")
    buddy.handle_request(
        BOB,
        EmployeeRequest(
            employee_id="EMP-5512",
            employee_name="Leo Fernandez",
            department="Sales",
            policy_slug="vacation-policy",
            request_text="I forgot to use 6 vacation days. Can I carry them over to next year?",
        ),
        RequestDecision(
            decision="denied",
            summary=(
                "Denied carry-over exception for Leo (EMP-5512). "
                "No business justification was provided; the 6 days are forfeited per standard policy."
            ),
            fact="EMP-5512 (Leo Fernandez, Sales): carry-over exception denied for 6 days — personal planning choice; no business reason; standard forfeiture applies.",
            reasoning="Unlike business-critical situations, Leo's unused days reflect personal scheduling choices. Policy must be applied as written.",
            context_messages=[
                AnnotationContextMessage(
                    author="Leo (employee)",
                    text="I forgot to use 6 vacation days. Can I carry them over to next year?",
                ),
            ],
            extra_metadata={"days_requested": 6, "exception_type": "carry-over"},
        ),
        annotation_id="bob-001",
    )

    subsection("Nina: remote work during probation")
    buddy.handle_request(
        BOB,
        EmployeeRequest(
            employee_id="EMP-6780",
            employee_name="Nina Patel",
            department="Customer Success",
            policy_slug="remote-work-policy",
            request_text="I've been here 45 days and would like to work from home 2 days a week.",
        ),
        RequestDecision(
            decision="denied",
            summary=(
                "Denied remote work request for Nina (EMP-6780). "
                "She is 45 days into her 90-day probationary period and is not yet eligible."
            ),
            fact="EMP-6780 (Nina Patel, Customer Success): remote work denied — 45 days into 90-day probation; must reapply after day 90.",
            reasoning="Eligibility explicitly requires completing the 90-day probationary period.",
            context_messages=[
                AnnotationContextMessage(
                    author="Nina (employee)",
                    text="I've been here 45 days and would like to work from home 2 days a week.",
                ),
            ],
            extra_metadata={
                "days_in_company": 45,
                "probation_days_remaining": 45,
                "exception_type": "pre-probation-remote-work",
            },
        ),
        annotation_id="bob-002",
    )

    subsection("Carlos: split secondary caregiver leave")
    buddy.handle_request(
        BOB,
        EmployeeRequest(
            employee_id="EMP-7023",
            employee_name="Carlos Romero",
            department="Design",
            policy_slug="parental-leave-policy",
            request_text="Can I take my 4-week secondary caregiver leave in two separate blocks?",
        ),
        RequestDecision(
            decision="approved",
            summary=(
                "Approved split parental leave for Carlos (EMP-7023). "
                "2 weeks taken immediately after birth; remaining 2 weeks taken in month 4. Both blocks fully paid."
            ),
            fact="EMP-7023 (Carlos Romero, Design): 4-week secondary caregiver leave approved in two blocks (2 weeks at birth + 2 weeks at month 4) — policy permits splitting; manager confirmed coverage.",
            reasoning="Policy does not prohibit splitting. Splitting benefits the family and team continuity. Manager confirmed coverage for both windows.",
            context_messages=[
                AnnotationContextMessage(
                    author="Carlos (employee)",
                    text="Can I take my 4-week secondary caregiver leave in two separate blocks?",
                ),
                AnnotationContextMessage(
                    author="Carlos's manager",
                    text="Happy to accommodate — we can plan around both windows.",
                ),
            ],
            extra_metadata={
                "caregiver_role": "secondary",
                "exception_type": "split-leave",
                "supporting_evidence": ["manager_confirmation"],
            },
        ),
        annotation_id="bob-003",
    )

    subsection("Rachel: disputes PIP placement")
    buddy.handle_request(
        BOB,
        EmployeeRequest(
            employee_id="EMP-8899",
            employee_name="Rachel Kim",
            department="Operations",
            policy_slug="performance-review-policy",
            request_text="I don't think it's fair that I'm on a PIP. My workload was unreasonable.",
        ),
        RequestDecision(
            decision="pip_upheld",
            summary=(
                "PIP upheld for Rachel (EMP-8899). Rating of 1 confirmed after reviewing manager documentation. "
                "Formal 90-day improvement plan issued."
            ),
            fact="EMP-8899 (Rachel Kim, Operations): PIP upheld for 2026-H1 — rating 1 confirmed; 7/10 milestones missed; 90-day improvement plan issued.",
            reasoning="Manager provided detailed evidence of missed deadlines. Workload was comparable to peers. No procedural errors found.",
            context_messages=[
                AnnotationContextMessage(
                    author="Rachel (employee)",
                    text="I don't think it's fair that I'm on a PIP. My workload was unreasonable.",
                ),
                AnnotationContextMessage(
                    author="Rachel's manager",
                    text="Rachel missed 7 out of 10 delivery milestones. Workload was comparable to peers.",
                ),
            ],
            extra_metadata={
                "rating": 1,
                "pip_duration_days": 90,
                "review_cycle": "2026-H1",
                "milestones_missed": 7,
                "milestones_total": 10,
                "supporting_evidence": ["manager_documentation", "peer_comparison"],
            },
        ),
        annotation_id="bob-004",
    )


# ─── 3. Inspect extracted facts ──────────────────────────────────────────────


def show_facts(buddy: HRBuddy) -> None:
    section("STEP 3 — Extracted Facts per Operator")
    print(
        "\n  Each handled request was immediately distilled into a concise fact.\n"
        "  In production these would be produced by an async data-augmentation task.\n"
    )
    for op_id, label in [(ALICE, "Alice"), (BOB, "Bob")]:
        print(f"\n  ── {label}'s facts ──")
        for slug in POLICIES:
            facts = list(buddy.operator_facts(op_id, slug))
            if not facts:
                continue
            print(f"\n    [{slug}]")
            for fact in reversed(facts):
                ts = fact.timestamp.strftime("%Y-%m-%d %H:%M UTC")
                print(f"      • [{ts}] {fact.content.text}")


# ─── 4. Personalised ask ─────────────────────────────────────────────────────

QUESTIONS = [
    (
        "vacation-policy",
        "Have you ever approved a carry-over exception beyond the 5-day cap, and under what conditions?",
    ),
    (
        "remote-work-policy",
        "Have any remote-work requests above the 3-day limit come up on your end, and how did you resolve them?",
    ),
    (
        "parental-leave-policy",
        "Have you handled any non-standard parental leave arrangements, such as an early start or split blocks?",
    ),
    (
        "performance-review-policy",
        "Were there any performance rating appeals or PIP disputes on your end this cycle, and what was the outcome?",
    ),
]


def show_personalised_answers(buddy: HRBuddy) -> None:
    section("STEP 4 — Personalised Answers: Alice vs Bob")
    print(
        "\n  The same question is asked twice — once as Alice, once as Bob.\n"
        "  Each answer is grounded in that operator's own annotations and facts.\n"
    )
    for slug, question in QUESTIONS:
        print(f"\n  Policy : {slug}")
        print(f"  Q      : {question}\n")
        for op_id in (ALICE, BOB):
            result = buddy.ask(op_id, slug, question)
            print_recall(result, op_id)
            print()


# ─── 5. Personalised graph ───────────────────────────────────────────────────


def show_personalised_graphs(buddy: HRBuddy) -> None:
    section("STEP 5 — Personalised Knowledge Graphs: Alice vs Bob")
    print(
        "\n  The entity graph is scoped to each operator so only entities and\n"
        "  relations extracted from their own annotations are visible.\n"
    )
    for slug, policy in POLICIES.items():
        print(f"\n  ── {policy['title']} ({slug}) ──")
        for op_id, label in [(ALICE, "Alice"), (BOB, "Bob")]:
            edges = buddy.operator_graph(op_id, slug)
            print_graph(edges, label)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n" + "═" * 72)
    print("  HR BUDDY DEMO 2  —  HRBuddy class wrapping NucliaMemory")
    print("═" * 72)

    buddy = HRBuddy()

    load_policies(buddy)
    alice_handles_requests(buddy)
    bob_handles_requests(buddy)
    show_facts(buddy)
    show_personalised_answers(buddy)
    show_personalised_graphs(buddy)

    print(f"\n{'─' * 72}")
    print("  Demo complete.")
    print(f"{'─' * 72}\n")


if __name__ == "__main__":
    main()
