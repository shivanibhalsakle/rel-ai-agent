"""
M8.8 -- the design doc's own named completion criterion for this milestone:
"an integration test verifying that no code path can create an event
without a confirmed: true approval record" / "the approval gate has
explicit automated test coverage proving unconfirmed proposals never call
the create-event tool."

This is deliberately not one test but three different KINDS of proof,
each closing a different way the guarantee could quietly fail:

1. Behavioral (already written, M8.5/M8.6, referenced not repeated here):
   tests/integration/test_agent_conversations.py's
   test_add_to_calendar_confirmed_creates_the_event and
   test_add_to_calendar_rejected_never_calls_create_calendar_event run the
   REAL compiled graph end to end and prove the confirmed/rejected paths
   behave correctly through a real interrupt/resume.

2. Function-level (tests/unit/test_create_calendar_event.py's
   test_refuses_to_create_without_a_confirmed_approval_decision /
   test_refuses_to_create_when_approval_decision_was_never_set): proves
   create_calendar_event refuses to act even if handed a fully-formed
   pending_approval directly, regardless of how it was reached. This is
   the strongest guarantee of the three -- it holds even if graph.py's
   wiring were wrong.

3. Structural (this file): proves graph.py's wiring is ALSO correct
   (belt-and-suspenders, not redundant -- (2) protects against a future
   bug in create_calendar_event forgetting to check approval_decision on
   some new code path added later; this protects against a future
   graph.py edit accidentally adding a second, unguarded edge into
   create_calendar_event) and that CalendarProvider.create_event is only
   ever invoked from the one function that carries that guard, not
   duplicated or bypassed anywhere else in the codebase.
"""
import ast
from pathlib import Path

from app.agent.graph import build_graph

_APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _iter_call_sites(method_name: str):
    """Yields (path, lineno) for every `<expr>.<method_name>(...)` call
    site under backend/app -- an AST-based search, not a text grep, so a
    method DEFINITION (`def create_event(self, ...)`, no receiver) never
    false-matches a CALL (`provider.create_event(...)`)."""
    for path in _APP_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == method_name
            ):
                yield path.relative_to(_APP_ROOT), node.lineno


def test_create_event_is_called_from_exactly_one_place_in_the_whole_backend():
    """The literal write to Google Calendar. If this ever finds a second
    call site, that's a new, unaudited way to create a calendar event --
    exactly the "no other code path" the design doc names."""
    sites = list(_iter_call_sites("create_event"))

    assert [str(p) for p, _ in sites] == [str(Path("agent/nodes/create_calendar_event.py"))]


def test_calendar_action_audit_writes_are_called_from_exactly_one_place():
    """The Firestore audit trail (calendarActions) that record_confirmed
    now happens before the API call. If some other code path could write
    an "action" record, M8.9's live check and any future history UI could
    be shown an event that was never actually gated by approval -- so
    this needs the same single-call-site guarantee as create_event
    itself, not just the write it accompanies."""
    for method_name in ("record_confirmed", "mark_created"):
        sites = list(_iter_call_sites(method_name))
        assert [str(p) for p, _ in sites] == [str(Path("agent/nodes/create_calendar_event.py"))], method_name


def test_create_calendar_event_node_has_exactly_one_incoming_graph_edge():
    """Structural proof that agent/graph.py's wiring itself is right:
    the compiled graph has exactly one edge INTO the create_calendar_event
    node, and its source is check_budget_calendar_write -- the tool-budget
    gate that only follows _route_after_approval's "confirmed" branch. If
    a future edit added a second edge (e.g. accidentally wiring
    prepare_calendar_proposal straight to create_calendar_event, skipping
    the interrupt entirely), this test catches it even though the
    behavioral tests above would too -- this one points directly at the
    edge, not just the symptom."""
    graph = build_graph()
    drawable = graph.get_graph()

    incoming = [edge for edge in drawable.edges if edge.target == "create_calendar_event"]

    assert len(incoming) == 1
    assert incoming[0].source == "check_budget_calendar_write"


def _assigns_approval_decision(tree: ast.AST) -> bool:
    """True if `tree` contains either a {"approval_decision": ...} dict-
    literal key or a `x["approval_decision"] = ...` subscript assignment
    -- the two shapes a node could use to set this state field. Deliberately
    AST-based, not a text/substring search: state.get("approval_decision")
    (a READ -- see create_calendar_event's guard) must NOT count as a
    write, and a naive substring match can't tell the two apart."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "approval_decision":
                    return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "approval_decision"
                ):
                    return True
    return False


def test_request_user_approval_is_the_only_node_that_sets_approval_decision():
    """The field create_calendar_event's guard (and _route_after_approval's
    routing) both trust completely -- if any OTHER node in agent/nodes/
    could also set it, the guard would no longer mean what it claims to."""
    nodes_dir = _APP_ROOT / "agent" / "nodes"
    offenders = []
    for path in nodes_dir.rglob("*.py"):
        if path.name == "request_user_approval.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _assigns_approval_decision(tree):
            offenders.append(path.relative_to(_APP_ROOT))

    assert offenders == []
