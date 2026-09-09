from __future__ import annotations

import json
from datetime import datetime, timezone
from random import choice, randint, uniform
from time import time
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Bootlegger Live Console",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)


EVENT_TYPES = ["transaction", "heartbeat", "alert", "snapshot"]
EVENT_STATUS = ["accepted", "accepted", "accepted", "queued", "warning"]
STREAMS = ["orders", "inventory", "telemetry", "customers"]


def seed_events(count: int = 18) -> list[dict]:
    now = time()
    return [make_event(now - (count - index) * 2.5) for index in range(count)]


def make_event(timestamp: float | None = None) -> dict:
    event_time = timestamp or time()
    event_type = choice(EVENT_TYPES)
    return {
        "id": f"evt_{int(event_time * 1000)}_{randint(100, 999)}",
        "timestamp": datetime.fromtimestamp(event_time, tz=timezone.utc),
        "stream": choice(STREAMS),
        "type": event_type,
        "status": choice(EVENT_STATUS),
        "records": randint(1, 240) if event_type != "heartbeat" else 0,
        "latency_ms": round(uniform(18, 220), 1),
    }


def append_live_event() -> None:
    st.session_state.events.insert(0, make_event())
    st.session_state.events = st.session_state.events[:100]


def filtered_events() -> list[dict]:
    events = st.session_state.events
    selected_stream = st.session_state.selected_stream
    selected_type = st.session_state.selected_type
    if selected_stream != "all":
        events = [event for event in events if event["stream"] == selected_stream]
    if selected_type != "all":
        events = [event for event in events if event["type"] == selected_type]
    return events


def event_to_json(event: dict) -> dict:
    return {**event, "timestamp": event["timestamp"].isoformat()}


def create_backup(reason: str) -> None:
    snapshot = {
        "id": f"bkp_{uuid4().hex[:10]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "events": [event_to_json(event) for event in st.session_state.events],
    }
    st.session_state.backups.insert(0, snapshot)
    st.session_state.backups = st.session_state.backups[: st.session_state.backup_retention]
    st.session_state.last_backup_at = time()


def restore_backup(snapshot: dict) -> None:
    st.session_state.events = [
        {**event, "timestamp": datetime.fromisoformat(event["timestamp"])}
        for event in snapshot["events"]
    ]


def maybe_create_backup() -> None:
    interval = {"30 sec": 30, "1 min": 60, "5 min": 300}.get(st.session_state.backup_frequency)
    if interval and time() - st.session_state.last_backup_at >= interval:
        create_backup("automatic")


def parse_prometheus_metrics(payload: str) -> dict[str, float]:
    metrics = {}
    for line in payload.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        name, value = line.rsplit(" ", 1)
        metric_name = name.split("{", 1)[0]
        try:
            metrics[metric_name] = float(value)
        except ValueError:
            continue
    return metrics


def infrastructure_metrics(source: str, endpoint: str, events: list[dict]) -> tuple[dict[str, float], str]:
    if source == "Prometheus endpoint":
        try:
            with urlopen(endpoint, timeout=2) as response:
                return parse_prometheus_metrics(response.read().decode("utf-8")), "Prometheus scrape healthy"
        except (OSError, URLError, ValueError):
            return {}, "Prometheus endpoint unavailable"

    event_count = len(events)
    average_latency = sum(event["latency_ms"] for event in events) / max(event_count, 1)
    accepted_rate = sum(event["status"] == "accepted" for event in events) / max(event_count, 1)
    return {
        "bootlegger_cpu_utilization": min(92, 24 + average_latency / 5),
        "bootlegger_memory_utilization": min(88, 41 + event_count / 8),
        "bootlegger_disk_utilization": 62 + event_count / 20,
        "bootlegger_load1": max(0.1, average_latency / 100),
        "bootlegger_active_series": 1200 + event_count * 7,
        "bootlegger_queue_depth": max(0, int((1 - accepted_rate) * event_count)),
    }, "Derived telemetry simulator"


if "events" not in st.session_state:
    st.session_state.events = seed_events()
if "started_at" not in st.session_state:
    st.session_state.started_at = time()
if "selected_stream" not in st.session_state:
    st.session_state.selected_stream = "all"
if "selected_type" not in st.session_state:
    st.session_state.selected_type = "all"
if "backups" not in st.session_state:
    st.session_state.backups = []
if "backup_frequency" not in st.session_state:
    st.session_state.backup_frequency = "1 min"
if "backup_retention" not in st.session_state:
    st.session_state.backup_retention = 12
if "last_backup_at" not in st.session_state:
    st.session_state.last_backup_at = time()


with st.sidebar:
    st.markdown("## ◉ BOOTLEGGER")
    st.caption("Live data operations console")
    st.divider()

    st.markdown("### Connection")
    connection = st.selectbox("Source", ["Bootlegger simulator", "Custom adapter"], label_visibility="collapsed")
    st.text_input("Endpoint", value="ws://localhost:8765/stream", disabled=connection == "Bootlegger simulator")
    refresh_rate = st.select_slider("Refresh rate", options=["250 ms", "1 sec", "5 sec", "Manual"], value="1 sec")

    st.divider()
    st.markdown("### Infrastructure telemetry")
    telemetry_source = st.selectbox("Metrics source", ["Derived simulator", "Prometheus endpoint"])
    prometheus_endpoint = st.text_input("Prometheus URL", value="http://localhost:9090/metrics", disabled=telemetry_source == "Derived simulator")
    scrape_interval = st.selectbox("Scrape interval", ["On refresh", "15 sec", "30 sec"])

    st.divider()
    st.markdown("### View filters")
    st.session_state.selected_stream = st.selectbox("Stream", ["all", *STREAMS], format_func=lambda value: "All streams" if value == "all" else value.title())
    st.session_state.selected_type = st.selectbox("Event type", ["all", *EVENT_TYPES], format_func=lambda value: "All event types" if value == "all" else value.title())

    st.divider()
    st.markdown("### Point-in-time backups")
    st.session_state.backup_frequency = st.selectbox("Automatic checkpoint", ["30 sec", "1 min", "5 min", "Manual"], index=1)
    st.session_state.backup_retention = st.slider("Retain checkpoints", 3, 30, st.session_state.backup_retention)
    if st.button("Create checkpoint", use_container_width=True):
        create_backup("manual")
        st.rerun()
    if st.session_state.backups:
        backup_options = {
            f'{backup["created_at"][:19].replace("T", " ")} · {backup["reason"]} · {len(backup["events"])} events': index
            for index, backup in enumerate(st.session_state.backups)
        }
        selected_backup = st.selectbox("Restore checkpoint", list(backup_options))
        restore_col, download_col = st.columns(2)
        with restore_col:
            if st.button("Restore", use_container_width=True):
                restore_backup(st.session_state.backups[backup_options[selected_backup]])
                st.rerun()
        with download_col:
            st.download_button(
                "Export",
                data=json.dumps(st.session_state.backups[backup_options[selected_backup]], indent=2),
                file_name="bootlegger-backup.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.caption("No checkpoints yet")

    st.divider()
    st.caption("Adapter status")
    st.success("Connected")
    st.caption(f"Session started {datetime.fromtimestamp(st.session_state.started_at).strftime('%H:%M:%S')}")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --ink: #13221d; --muted: #66756d; --mint: #b8f2d0; --lime: #d9f36b; --paper: #f4f5ef; --line: #d9ded4; }
    html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stSidebar"] { background: #e8eee5; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] * { color: var(--ink); }
    h1, h2, h3 { letter-spacing: -0.04em; }
    h1 { font-size: 2.35rem !important; margin-bottom: 0; }
    .eyebrow { color: #3f6654; font-family: 'DM Mono', monospace; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
    .subtle { color: var(--muted); }
    .metric-card { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 1rem 1.1rem; min-height: 112px; }
    .metric-label { color: var(--muted); font-size: .76rem; text-transform: uppercase; letter-spacing: .08em; }
    .metric-value { color: var(--ink); font-family: 'DM Mono', monospace; font-size: 1.75rem; margin-top: .45rem; }
    .status-pill { background: var(--lime); border-radius: 999px; color: var(--ink); display: inline-block; font-family: 'DM Mono', monospace; font-size: .72rem; padding: .38rem .65rem; }
    .stButton > button { border-radius: 5px; border-color: #a6b6aa; color: var(--ink); }
    .stButton > button[kind="primary"] { background: var(--ink); color: white; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">OPERATIONS / STREAM 01</div>', unsafe_allow_html=True)
header_left, header_right = st.columns([4, 1])
with header_left:
    st.title("Live data console")
    st.markdown('<span class="subtle">Observe, filter, and inspect the Bootlegger event stream.</span>', unsafe_allow_html=True)
with header_right:
    st.markdown('<div style="text-align:right; margin-top:1.1rem"><span class="status-pill">● LIVE</span></div>', unsafe_allow_html=True)

st.write("")
controls = st.columns([1, 1, 3, 1])
with controls[0]:
    if st.button("Pause stream" if st.session_state.get("streaming", True) else "Resume stream", use_container_width=True):
        st.session_state.streaming = not st.session_state.get("streaming", True)
        st.rerun()
with controls[1]:
    if st.button("Clear events", use_container_width=True):
        st.session_state.events = []
        st.rerun()
with controls[3]:
    st.caption(f"{datetime.now().strftime('%H:%M:%S')} local")

if "streaming" not in st.session_state:
    st.session_state.streaming = True

refresh_seconds = {"250 ms": 0.25, "1 sec": 1.0, "5 sec": 5.0}.get(refresh_rate)
if st.session_state.streaming and refresh_seconds:
    @st.fragment(run_every=refresh_seconds)
    def refresh_live_console() -> None:
        st.rerun()

    refresh_live_console()

if st.session_state.streaming:
    append_live_event()
maybe_create_backup()

visible_events = filtered_events()
accepted = sum(event["status"] == "accepted" for event in st.session_state.events)
record_count = sum(event["records"] for event in st.session_state.events)
avg_latency = sum(event["latency_ms"] for event in st.session_state.events) / max(len(st.session_state.events), 1)

st.write("")
metrics = st.columns(4)
metric_values = [
    ("Events received", f"{len(st.session_state.events):,}", "+12.4%"),
    ("Records processed", f"{record_count:,}", "stream total"),
    ("Acceptance rate", f"{accepted / max(len(st.session_state.events), 1) * 100:.1f}%", "within target"),
    ("Mean latency", f"{avg_latency:.0f} ms", "p95 · 340 ms"),
]
for column, (label, value, detail) in zip(metrics, metric_values):
    with column:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="subtle">{detail}</div></div>', unsafe_allow_html=True)

st.write("")
st.markdown("### Business intelligence")
bi_overview, bi_streams, bi_risk = st.tabs(["Executive overview", "Stream performance", "Risk & anomalies"])
bi_data = pd.DataFrame(st.session_state.events)
if not bi_data.empty:
    bi_data["timestamp"] = pd.to_datetime(bi_data["timestamp"], utc=True)

with bi_overview:
    if bi_data.empty:
        st.info("Waiting for enough events to calculate business intelligence.")
    else:
        overview_left, overview_right = st.columns(2)
        with overview_left:
            st.caption("Event mix")
            event_mix = bi_data["type"].value_counts().rename_axis("Event type").to_frame("Events")
            st.bar_chart(event_mix, height=220, color="#77a982")
        with overview_right:
            st.caption("Outcome mix")
            outcome_mix = bi_data["status"].value_counts().rename_axis("Status").to_frame("Events")
            st.bar_chart(outcome_mix, height=220, color="#d6ad60")

with bi_streams:
    if bi_data.empty:
        st.info("Waiting for stream activity.")
    else:
        stream_summary = bi_data.groupby("stream").agg(
            Events=("id", "count"),
            Records=("records", "sum"),
            Latency=("latency_ms", "mean"),
            Accepted=("status", lambda values: (values == "accepted").mean() * 100),
        ).sort_values("Records", ascending=False)
        stream_left, stream_right = st.columns([1.15, 1])
        with stream_left:
            st.caption("Records processed by stream")
            st.bar_chart(stream_summary["Records"], height=250, color="#77a982")
        with stream_right:
            stream_table = stream_summary.reset_index().rename(columns={"stream": "Stream", "Latency": "Mean latency", "Accepted": "Acceptance rate"})
            st.dataframe(
                stream_table,
                hide_index=True,
                use_container_width=True,
                height=250,
                column_config={
                    "Mean latency": st.column_config.NumberColumn(format="%.1f ms"),
                    "Acceptance rate": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

with bi_risk:
    if bi_data.empty:
        st.info("Waiting for events to identify operational risk.")
    else:
        latency_limit = bi_data["latency_ms"].quantile(0.95)
        risk_events = bi_data[(bi_data["status"] == "warning") | (bi_data["latency_ms"] >= latency_limit)]
        risk_metrics = st.columns(3)
        risk_metrics[0].metric("Warnings", int((bi_data["status"] == "warning").sum()))
        risk_metrics[1].metric("Latency p95", f"{latency_limit:.0f} ms")
        risk_metrics[2].metric("At-risk events", len(risk_events))
        if risk_events.empty:
            st.success("No warning or high-latency events in the current window.")
        else:
            risk_view = risk_events[["timestamp", "id", "stream", "type", "status", "latency_ms", "records"]].copy()
            risk_view["timestamp"] = risk_view["timestamp"].dt.strftime("%H:%M:%S")
            risk_view = risk_view.rename(columns={"timestamp": "Time", "id": "Event ID", "stream": "Stream", "type": "Type", "status": "Status", "latency_ms": "Latency", "records": "Records"})
            st.dataframe(risk_view, hide_index=True, use_container_width=True, height=220, column_config={"Latency": st.column_config.NumberColumn(format="%.1f ms")})

st.write("")
st.markdown("### Prometheus infrastructure")
infra_values, infra_status = infrastructure_metrics(telemetry_source, prometheus_endpoint, st.session_state.events)
if telemetry_source == "Prometheus endpoint" and not infra_values:
    st.warning(f"{infra_status}. Showing the panel without live values.")
else:
    st.caption(f"{infra_status} · {scrape_interval.lower()}")

cpu = infra_values.get("bootlegger_cpu_utilization", infra_values.get("node_cpu_utilization_ratio", 0) * 100)
memory = infra_values.get("bootlegger_memory_utilization", 0)
if "node_memory_MemTotal_bytes" in infra_values and "node_memory_MemAvailable_bytes" in infra_values:
    memory = (1 - infra_values["node_memory_MemAvailable_bytes"] / max(infra_values["node_memory_MemTotal_bytes"], 1)) * 100
disk = infra_values.get("bootlegger_disk_utilization", 0)
if "node_filesystem_size_bytes" in infra_values and "node_filesystem_avail_bytes" in infra_values:
    disk = (1 - infra_values["node_filesystem_avail_bytes"] / max(infra_values["node_filesystem_size_bytes"], 1)) * 100
load = infra_values.get("bootlegger_load1", infra_values.get("node_load1", 0))
series = infra_values.get("bootlegger_active_series", infra_values.get("prometheus_tsdb_head_series", 0))
queue = infra_values.get("bootlegger_queue_depth", 0)
infra_cards = st.columns(6)
infra_metrics = [
    ("CPU", f"{cpu:.1f}%", "utilization"),
    ("Memory", f"{memory:.1f}%", "used"),
    ("Disk", f"{disk:.1f}%", "used"),
    ("Load 1m", f"{load:.2f}", "system load"),
    ("Active series", f"{series:,.0f}", "Prometheus"),
    ("Queue depth", f"{queue:,.0f}", "events"),
]
for column, (label, value, detail) in zip(infra_cards, infra_metrics):
    with column:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="subtle">{detail}</div></div>', unsafe_allow_html=True)

st.write("")
left, right = st.columns([1.5, 1])
with left:
    st.markdown("### Throughput")
    chart_data = pd.DataFrame(st.session_state.events)
    if not chart_data.empty:
        chart_data["time"] = chart_data["timestamp"].dt.tz_convert(None).dt.floor("s")
        throughput = chart_data.groupby("time")["records"].sum().tail(30)
        st.area_chart(throughput, height=220, color="#77a982")
    else:
        st.info("Waiting for events...")
with right:
    st.markdown("### Stream health")
    health_rows = pd.DataFrame({"Signal": ["Connection", "Consumer lag", "Schema", "Backpressure"], "Value": ["Healthy", "42 ms", "v2.4 valid", "None"]})
    st.dataframe(health_rows, hide_index=True, use_container_width=True, height=220)

st.write("")
backup_left, backup_right = st.columns([1.5, 1])
with backup_left:
    st.markdown("### Backup timeline")
    if st.session_state.backups:
        backup_rows = pd.DataFrame([
            {
                "Checkpoint": backup["id"],
                "Created": backup["created_at"].replace("T", " ")[:19],
                "Mode": backup["reason"].title(),
                "Events": len(backup["events"]),
            }
            for backup in st.session_state.backups
        ])
        st.dataframe(backup_rows, hide_index=True, use_container_width=True, height=190)
    else:
        st.info("Automatic checkpoints will appear here.")
with backup_right:
    st.markdown("### Recovery point")
    if st.session_state.backups:
        latest_backup = st.session_state.backups[0]
        st.markdown(f'<div class="metric-card"><div class="metric-label">Latest checkpoint</div><div class="metric-value">{len(st.session_state.backups)}</div><div class="subtle">{latest_backup["created_at"].replace("T", " ")[:19]} UTC · {len(latest_backup["events"])} events</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="metric-card"><div class="metric-label">Latest checkpoint</div><div class="metric-value">--</div><div class="subtle">Waiting for the first checkpoint</div></div>', unsafe_allow_html=True)

st.write("")
st.markdown(f"### Event feed <span class='subtle'>· {len(visible_events)} visible</span>", unsafe_allow_html=True)
if visible_events:
    feed = pd.DataFrame(visible_events)
    feed["timestamp"] = feed["timestamp"].dt.strftime("%H:%M:%S.%f").str[:-3]
    feed = feed.rename(columns={"id": "Event ID", "timestamp": "Time", "stream": "Stream", "type": "Type", "status": "Status", "records": "Records", "latency_ms": "Latency"})
    st.dataframe(feed[["Time", "Event ID", "Stream", "Type", "Status", "Records", "Latency"]], hide_index=True, use_container_width=True, height=360, column_config={"Latency": st.column_config.NumberColumn(format="%.1f ms")})
else:
    st.info("No events match the current filters.")

st.caption("Bootlegger adapter ready: replace make_event() with your websocket, Kafka, or webhook consumer.")
