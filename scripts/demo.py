"""Exercise a running ISMS API against its real demo endpoint.

Set ISMS_ADMIN_TOKEN in the process environment for cloud runs. No key is
accepted on the command line or printed. This does not certify email receipt.
"""
import argparse
import json
import os
import time
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--require-ai", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    token = os.environ.get("ISMS_ADMIN_TOKEN", "")
    def call(path, data=None, method="GET"):
        headers = {"Content-Type":"application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(base + "/api/v1" + path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=65) as response: return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{path}: HTTP {exc.code}: {exc.read().decode()[:500]}") from exc
    call("/demo/mode", {"mode":"ONLINE"}, "PUT")
    # Warm the dedicated target before measuring it with a three-second probe.
    # Its first Lambda initialization can exceed that operational timeout.
    with urllib.request.urlopen(base + "/demo/health", timeout=65) as response:
        assert response.status == 200
    service = call("/services", {"service_name":"ISMS live demonstration", "url":base + "/demo/health", "is_active":False, "timeout":3, "response_time_threshold":500, "failure_threshold":3, "recovery_threshold":2}, "POST")
    sid = service["service_id"]
    def check():
        record = call(f"/monitoring/{sid}/check-now", {}, "POST")["data"]
        print(json.dumps({k:record.get(k) for k in ("status_code","response_time","health_state","ml_status","incident_id")}))
        return record
    try:
        assert check()["request_success"] == 1
        call("/demo/mode", {"mode":"HTTP_503"}, "PUT")
        for _ in range(3): record = check()
        iid = record["incident_id"]
        assert iid
        call(f"/incidents/{iid}", {"status":"ACKNOWLEDGED", "resolution_notes":"Live demo acknowledged by authenticated operator"}, "PATCH")
        assert check()["incident_id"] == iid
        # Cloud stream is asynchronous; poll for completed/unavailable status.
        for _ in range(30):
            incident = call(f"/incidents/{iid}")
            if incident.get("ai_status") in {"completed", "unavailable"}: break
            time.sleep(2)
        print(json.dumps({"ai_status":incident.get("ai_status"), "ai_provider":incident.get("ai_analysis", {}).get("provider"), "notification_history":incident.get("notifications", [])}))
        if args.require_ai: assert incident.get("ai_status") == "completed", "Real AI did not complete"
        answer = call("/ai/chat", {"query":"Why did this service fail? Separate observed evidence from possible causes.", "service_id":sid,"incident_id":iid}, "POST")
        print(json.dumps({"assistant_provider":answer["provider"],"sources":answer["sources"],"answer":answer["answer"]}))
        call("/demo/mode", {"mode":"RECOVERY"}, "PUT")
        assert check()["health_state"] == "RECOVERED"
        assert check()["health_state"] == "HEALTHY"
        assert call(f"/incidents/{iid}")["status"] == "RESOLVED"
        print(json.dumps({"result":"healthy -> failure -> incident -> acknowledgement -> recovery -> resolved", "notifications":call("/notifications/status"), "email_receipt_verified":False}))
    finally:
        call("/demo/mode", {"mode":"ONLINE"}, "PUT")
        call(f"/services/{sid}", method="DELETE")


if __name__ == "__main__": main()
