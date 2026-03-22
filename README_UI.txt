# OpenDataLoader Simple UI (Streamlit)

## Start
Double-click:
run_ui.bat

Or run:
python -m streamlit run app_streamlit.py --server.address 0.0.0.0 --server.port 8501

## Public URL (streamlit.app style)
See:
DEPLOY_STREAMLIT_CLOUD.md

## How to use
1. Upload one or more PDF files.
2. Select output format (`markdown`, `json`, or both).
3. (Optional) Enable OCR mode for scanned PDFs.
4. Click `Run conversion`.
5. Download the output ZIP.

## Output location on disk
Generated files are also saved under:
ui_runs/run_YYYYMMDD_HHMMSS/output/

## Notes
- Multiple PDFs are converted in a single `convert()` call for better efficiency.
- OCR mode requires:
  pip install -U "opendataloader-pdf[hybrid]"
- When OCR mode is enabled, the app auto-starts a local hybrid server (port 5012).
- For other PCs on the same LAN, open:
  http://<this-pc-ip>:8501
- If access fails from other PCs, allow inbound TCP 8501 in Windows Firewall.
