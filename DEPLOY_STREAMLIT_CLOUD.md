# Deploy to Streamlit Community Cloud

This app can be deployed to a public URL like:
`https://your-app-name.streamlit.app/`

## 1) Push this folder to GitHub
- Include at least:
  - `app_streamlit.py`
  - `requirements.txt`
  - `packages.txt`

## 2) Create app on Streamlit Community Cloud
1. Open: https://share.streamlit.io/
2. Click **New app**
3. Select your GitHub repo/branch
4. Set **Main file path** to:
   `opendataloader_starter/app_streamlit.py`
5. Deploy

## 3) Notes about this app
- Java is required by `opendataloader-pdf` and is installed via `packages.txt`.
- OCR (`hybrid`) is much heavier than normal conversion.
- On small cloud instances, OCR may fail due memory limits.
- If OCR is unstable in cloud:
  - use smaller page ranges
  - keep OCR chunk size low
  - or run OCR on a larger VM/server

## 4) Local testing command
```bash
streamlit run app_streamlit.py --server.address 0.0.0.0 --server.port 8501
```
