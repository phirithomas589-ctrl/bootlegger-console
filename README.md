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
