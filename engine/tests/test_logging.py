import json
import logging

from catty_engine.logging import configure_logging, logged_process, logged_request


def test_structured_logging_uses_stderr_and_redacts_credentials(capsys):
    configure_logging()
    logging.getLogger("catty_engine.test").warning('api_key="secret-value" Authorization: Bearer token-value')
    captured = capsys.readouterr()
    assert captured.out == ""
    entry = json.loads(captured.err)
    assert entry["catty_log"] is True
    assert entry["level"] == "WARNING"
    assert "secret-value" not in entry["message"]
    assert "token-value" not in entry["message"]


def test_request_scope_reaches_process_logs_and_resets(capsys):
    @logged_process
    def prepare():
        return 42

    @logged_request
    def request(payload):
        prepare()
        logging.getLogger("catty_engine.test").info("Working")
        return {"result": True}

    assert request({"id": "job-1", "method": "test.prepare"}) == {"result": True}
    logging.getLogger("catty_engine.test").info("Outside request")
    entries = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert all(entry["request_id"] == "job-1" for entry in entries[:-1])
    assert entries[-1]["request_id"] == "-"
    assert any("completed" in entry["message"] for entry in entries)


def test_ipc_failure_is_logged_without_polluting_stdout(capsys):
    from catty_engine.ipc import handle_request
    result = handle_request({"version": 1, "id": "bad-job", "method": "media.probe", "params": {}})
    assert "error" in result
    captured = capsys.readouterr()
    assert captured.out == ""
    entries = [json.loads(line) for line in captured.err.splitlines()]
    assert entries[-1]["level"] == "ERROR"
    assert entries[-1]["request_id"] == "bad-job"
