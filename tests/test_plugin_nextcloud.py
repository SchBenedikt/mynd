import re

from data.plugins import nextcloud


VTODO_RESPONSE = """<multistatus xmlns:d=\"DAV:\">
<d:response><d:href>/tasks.ics</d:href><d:propstat><d:prop><calendar-data xmlns=\"urn:ietf:params:xml:ns:caldav\"><VCALENDAR>
BEGIN:VTODO
SUMMARY:Open task
DUE:20260820
STATUS:NEEDS-ACTION
END:VTODO
BEGIN:VTODO
SUMMARY:Completed task
DUE:20260810
STATUS:COMPLETED
END:VTODO
BEGIN:VTODO
SUMMARY:In range
DUE:20260815
STATUS:IN-PROCESS
END:VTODO
</VCALENDAR></calendar-data></d:prop></d:propstat></d:response>
</multistatus>"""


class Response:
    status_code = 207
    text = VTODO_RESPONSE


def _setup(monkeypatch):
    monkeypatch.setattr(nextcloud, "_nc", lambda: ("https://cloud.example", "/dav", "alice", "secret"))
    monkeypatch.setattr(nextcloud, "_caldav_discover", lambda *args: [("Tasks", "/remote.php/dav/calendars/alice/tasks/")])
    monkeypatch.setattr(nextcloud.requests, "request", lambda *args, **kwargs: Response())


def test_tasks_query_hides_completed_by_default(monkeypatch):
    _setup(monkeypatch)

    result = nextcloud.nextcloud_tasks_query()

    assert "Open task" in result
    assert "In range" in result
    assert "Completed task" not in result


def test_tasks_query_can_include_completed_and_filter_due_dates(monkeypatch):
    _setup(monkeypatch)

    result = nextcloud.nextcloud_tasks_query(include_completed=True, due_after="2026-08-12", due_before="2026-08-16")

    assert "In range" in result
    assert "Open task" not in result
    assert "Completed task" not in result


def test_tasks_tool_schema_exposes_filters():
    tool = next(item for item in nextcloud.TOOLS if item["function"]["name"] == "nextcloud_tasks_query")
    properties = tool["function"]["parameters"]["properties"]

    assert set(properties) == {"include_completed", "due_before", "due_after"}
    assert properties["include_completed"]["type"] == "boolean"
    assert not tool["function"]["parameters"]["required"]
