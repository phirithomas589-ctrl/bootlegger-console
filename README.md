# Bootlegger Live Console

A Streamlit operations console for observing a live Bootlegger data stream.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The current app uses a local event simulator so the interface can be exercised immediately. Replace `make_event()` in `app.py` with a Bootlegger websocket, Kafka, or webhook consumer when the source contract is available.

Business intelligence views provide executive event and outcome mix, stream-level throughput and acceptance comparisons, plus warning and high-latency anomaly detection.

The infrastructure panel accepts a Prometheus `/metrics` endpoint and reads standard node and Prometheus gauges when available. It falls back to derived telemetry for local demos when no endpoint is configured.

Automated web ingestion accepts an HTTP(S) source URL, extracts page text and links on demand or on a 30-second, 1-minute, or 5-minute schedule, keeps the latest 20 results in the session, and supports JSON export.

The console includes a session-scoped point-in-time backup engine. It can automatically checkpoint the current event state, retain a configurable number of recovery points, restore a selected checkpoint, and export a checkpoint as JSON. Streamlit Cloud sessions are ephemeral, so export checkpoints for durable storage or replace `create_backup()` with an external object store/database when production persistence is required.

Control-room administration uses a Streamlit Secrets-backed username/password gate. Add the credentials under the app's Streamlit Cloud secrets before using the unlock button:

```toml
[control_room]
username = "admin"
password = "replace-with-the-password-you-choose"
```
