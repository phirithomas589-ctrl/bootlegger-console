from __future__ import annotations

from datetime import datetime, timezone
from random import choice, randint, uniform
from time import time

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


if "events" not in st.session_state:
    st.session_state.events = seed_events()
if "started_at" not in st.session_state:
    st.session_state.started_at = time()
if "selected_stream" not in st.session_state:
    st.session_state.selected_stream = "all"
if "selected_type" not in st.session_state:
    st.session_state.selected_type = "all"


with st.sidebar:
    st.markdown("## ◉ BOOTLEGGER")
    st.caption("Live data operations console")
    st.divider()

    st.markdown("### Connection")
    connection = st.selectbox("Source", ["Bootlegger simulator", "Custom adapter"], label_visibility="collapsed")
    st.text_input("Endpoint", value="ws://localhost:8765/stream", disabled=connection == "Bootlegger simulator")
    refresh_rate = st.select_slider("Refresh rate", options=["250 ms", "1 sec", "5 sec", "Manual"], value="1 sec")

    st.divider()
    st.markdown("### View filters")
    st.session_state.selected_stream = st.selectbox("Stream", ["all", *STREAMS], format_func=lambda value: "All streams" if value == "all" else value.title())
    st.session_state.selected_type = st.selectbox("Event type", ["all", *EVENT_TYPES], format_func=lambda value: "All event types" if value == "all" else value.title())

    st.divider()
    st.caption("Adapter status")
    st.success("Connected", icon="●")
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
st.markdown(f"### Event feed <span class='subtle'>· {len(visible_events)} visible</span>", unsafe_allow_html=True)
if visible_events:
    feed = pd.DataFrame(visible_events)
    feed["timestamp"] = feed["timestamp"].dt.strftime("%H:%M:%S.%f").str[:-3]
    feed = feed.rename(columns={"id": "Event ID", "timestamp": "Time", "stream": "Stream", "type": "Type", "status": "Status", "records": "Records", "latency_ms": "Latency"})
    st.dataframe(feed[["Time", "Event ID", "Stream", "Type", "Status", "Records", "Latency"]], hide_index=True, use_container_width=True, height=360, column_config={"Latency": st.column_config.NumberColumn(format="%.1f ms")})
else:
    st.info("No events match the current filters.")

st.caption("Bootlegger adapter ready: replace make_event() with your websocket, Kafka, or webhook consumer.")
