from __future__ import annotations

import importlib.util
import io
import os
import re
import socket
import subprocess
import shutil
import sys
import time
import zipfile
from pathlib import Path
from urllib import error, request

import opendataloader_pdf
import streamlit as st
from pypdf import PdfReader, PdfWriter


APP_DIR = Path(__file__).resolve().parent
RUN_ROOT = APP_DIR / "ui_runs"
RUN_ROOT.mkdir(exist_ok=True)
HYBRID_PORT = 5012
HYBRID_STARTUP_TIMEOUT_SEC = int(os.getenv("HYBRID_STARTUP_TIMEOUT_SEC", "240"))


def build_zip_bytes(folder: Path) -> bytes:
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(folder))
    memory_file.seek(0)
    return memory_file.read()


CHUNK_MD_RE = re.compile(r"^(?P<base>.+)__p(?P<start>\d+)-(?P<end>\d+)\.md$")


def parse_pages_spec(spec: str, total_pages: int) -> list[int]:
    if not spec.strip():
        return list(range(1, total_pages + 1))

    pages: set[int] = set()
    for token in spec.split(","):
        part = token.strip()
        if not part:
            continue
        if "-" in part:
            a_str, b_str = part.split("-", 1)
            a = int(a_str)
            b = int(b_str)
            if a > b:
                a, b = b, a
            for p in range(a, b + 1):
                if 1 <= p <= total_pages:
                    pages.add(p)
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p)
    return sorted(pages)


def split_pdf_for_ocr(
    src_pdf: Path,
    out_dir: Path,
    page_spec: str,
    chunk_size: int,
) -> list[Path]:
    reader = PdfReader(str(src_pdf))
    selected_pages = parse_pages_spec(page_spec, len(reader.pages))
    if not selected_pages:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []
    for i in range(0, len(selected_pages), chunk_size):
        chunk = selected_pages[i : i + chunk_size]
        writer = PdfWriter()
        for page_num in chunk:
            writer.add_page(reader.pages[page_num - 1])
        start, end = chunk[0], chunk[-1]
        chunk_path = out_dir / f"{src_pdf.stem}__p{start:04d}-{end:04d}.pdf"
        with chunk_path.open("wb") as f:
            writer.write(f)
        chunks.append(chunk_path)
    return chunks


def merge_chunk_markdown_files(output_dir: Path) -> list[Path]:
    groups: dict[str, list[tuple[int, Path]]] = {}
    for md_path in output_dir.glob("*.md"):
        m = CHUNK_MD_RE.match(md_path.name)
        if not m:
            continue
        base = m.group("base")
        start = int(m.group("start"))
        groups.setdefault(base, []).append((start, md_path))

    merged_files: list[Path] = []
    for base, items in groups.items():
        items.sort(key=lambda x: x[0])
        if len(items) == 1:
            continue
        merged_path = output_dir / f"{base}.md"
        with merged_path.open("w", encoding="utf-8") as out_f:
            for idx, (_, p) in enumerate(items):
                text = p.read_text(encoding="utf-8")
                if idx:
                    out_f.write("\n\n<!-- page chunk -->\n\n")
                out_f.write(text)
        merged_files.append(merged_path)
    return merged_files


def _find_java_exe() -> Path | None:
    java_cmd = shutil.which("java")
    if java_cmd:
        return Path(java_cmd)

    roots = [
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Java"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for java_exe in root.glob("**/bin/java.exe"):
            if java_exe.is_file():
                return java_exe
    return None


def ensure_java_on_path() -> tuple[bool, str]:
    java_exe = _find_java_exe()
    if not java_exe:
        return False, "Java (11+) not found. Install Java and restart this app."

    java_bin = str(java_exe.parent)
    os.environ["JAVA_HOME"] = str(java_exe.parent.parent)
    if java_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = java_bin + os.pathsep + os.environ.get("PATH", "")
    return True, f"Java detected: {java_exe}"


def missing_hybrid_modules() -> list[str]:
    needed = ["fastapi", "uvicorn", "docling"]
    return [name for name in needed if importlib.util.find_spec(name) is None]


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def is_hybrid_ready(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with request.urlopen(url, timeout=2) as resp:  # noqa: S310
            return resp.status == 200
    except (error.URLError, TimeoutError, OSError):
        return False


def ensure_hybrid_server(
    port: int = HYBRID_PORT,
    force_ocr: bool = True,
    ocr_lang: str = "ja,en",
) -> tuple[bool, str]:
    desired_cfg = (port, force_ocr, ocr_lang)
    prev_cfg = st.session_state.get("hybrid_server_cfg")
    prev_pid = st.session_state.get("hybrid_server_pid")
    if prev_cfg != desired_cfg and prev_pid:
        stop_hybrid_server()

    if is_hybrid_ready(port):
        return True, f"Hybrid server is ready on port {port}."

    hybrid_cmd = shutil.which("opendataloader-pdf-hybrid")
    if hybrid_cmd:
        cmd = [hybrid_cmd, "--port", str(port)]
    else:
        cmd = [sys.executable, "-m", "opendataloader_pdf.hybrid_server", "--port", str(port)]
    if force_ocr:
        cmd.append("--force-ocr")
    if ocr_lang.strip():
        cmd.extend(["--ocr-lang", ocr_lang.strip()])

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    st.session_state["hybrid_server_pid"] = proc.pid
    st.session_state["hybrid_server_cfg"] = desired_cfg

    deadline = time.monotonic() + HYBRID_STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if is_hybrid_ready(port):
            return True, f"Hybrid server started on port {port}."
        if proc.poll() is not None:
            return False, "Could not start hybrid server. Check OCR dependencies."
        time.sleep(0.25)

    return (
        False,
        f"Hybrid server startup timed out ({HYBRID_STARTUP_TIMEOUT_SEC}s). "
        "Try again after 1-2 minutes, or reduce page range.",
    )


def stop_hybrid_server() -> None:
    pid = st.session_state.get("hybrid_server_pid")
    if not pid:
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass
    st.session_state.pop("hybrid_server_pid", None)


def main() -> None:
    st.set_page_config(page_title="OpenDataLoader UI", layout="centered")
    st.title("OpenDataLoader PDF Converter")
    st.write("Upload PDF files and convert to Markdown/JSON.")

    ok, java_message = ensure_java_on_path()
    if ok:
        st.caption(java_message)
    else:
        st.error(java_message)
        st.stop()

    uploaded_files = st.file_uploader(
        "Select PDF file(s)",
        type=["pdf"],
        accept_multiple_files=True,
    )
    selected_formats = st.multiselect(
        "Output format",
        options=["markdown", "json"],
        default=["markdown", "json"],
    )
    page_selection = st.text_input(
        "Page range (optional, e.g. 1-20 or 1,3,5-7)",
        value="",
    )
    use_ocr = st.checkbox("OCR mode (for scanned PDFs)", value=False)
    ocr_lang = "ja,en"
    force_ocr_all_pages = True
    ocr_chunk_size = 1
    allow_java_fallback = False

    if use_ocr:
        force_ocr_all_pages = st.checkbox("Force OCR on all pages", value=True)
        ocr_lang = st.text_input("OCR language codes", value="ja,en")
        ocr_chunk_size = int(
            st.number_input(
                "OCR chunk size (pages per request)",
                min_value=1,
                max_value=10,
                value=1,
                step=1,
            )
        )
        allow_java_fallback = st.checkbox(
            "Allow Java fallback if OCR fails (may create image-only markdown)",
            value=False,
        )
        missing = missing_hybrid_modules()
        if missing:
            st.error(
                "OCR dependencies are missing: "
                + ", ".join(missing)
                + ". Run: pip install -U \"opendataloader-pdf[hybrid]\""
            )
            st.stop()
        st.caption(f"OCR mode uses a local hybrid server on port {HYBRID_PORT}.")
        st.caption("For large PDFs, run OCR in smaller page ranges to avoid timeout.")

    can_run = bool(uploaded_files) and bool(selected_formats)
    if st.button("Run conversion", disabled=not can_run):
        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_dir = RUN_ROOT / f"run_{run_id}"
        input_dir = run_dir / "input"
        ocr_split_dir = run_dir / "ocr_split"
        output_dir = run_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        input_paths: list[str] = []
        for i, file in enumerate(uploaded_files):
            safe_name = Path(file.name).name
            target = input_dir / safe_name
            if target.exists():
                target = input_dir / f"{i + 1}_{safe_name}"
            target.write_bytes(file.getbuffer())
            input_paths.append(str(target))

        if not input_paths:
            st.error("No PDF files were uploaded.")
            return

        conversion_input_paths: list[str] = input_paths
        if use_ocr:
            split_inputs: list[str] = []
            try:
                for in_path in input_paths:
                    src_pdf = Path(in_path)
                    chunk_paths = split_pdf_for_ocr(
                        src_pdf=src_pdf,
                        out_dir=ocr_split_dir / src_pdf.stem,
                        page_spec=page_selection.strip(),
                        chunk_size=ocr_chunk_size,
                    )
                    split_inputs.extend(str(p) for p in chunk_paths)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to split PDF for OCR: {exc}")
                return
            if not split_inputs:
                st.error("No pages selected for OCR conversion.")
                return
            conversion_input_paths = split_inputs
            st.info(f"OCR split files: {len(conversion_input_paths)}")

        format_arg = ",".join(selected_formats)
        try:
            with st.spinner("Converting..."):
                if use_ocr:
                    st.info(
                        "Starting OCR backend. First run can take a few minutes "
                        "(model download + warm-up)."
                    )
                if use_ocr:
                    progress = st.progress(0.0, text="OCR conversion in progress...")
                    total = len(conversion_input_paths)
                    for idx, one_input in enumerate(conversion_input_paths, start=1):
                        stop_hybrid_server()
                        started, msg = ensure_hybrid_server(
                            port=HYBRID_PORT,
                            force_ocr=force_ocr_all_pages,
                            ocr_lang=ocr_lang,
                        )
                        if not started:
                            st.error(msg)
                            return
                        convert_kwargs = {
                            "hybrid": "docling-fast",
                            "hybrid_mode": "full" if force_ocr_all_pages else "auto",
                            "hybrid_url": f"http://127.0.0.1:{HYBRID_PORT}",
                            "hybrid_timeout": "240000",
                            "hybrid_fallback": allow_java_fallback,
                        }
                        opendataloader_pdf.convert(
                            input_path=[one_input],
                            output_dir=str(output_dir),
                            format=format_arg,
                            **convert_kwargs,
                        )
                        progress.progress(
                            idx / total,
                            text=f"OCR conversion in progress... ({idx}/{total})",
                        )
                    stop_hybrid_server()
                else:
                    convert_kwargs = {}
                    if page_selection.strip():
                        convert_kwargs["pages"] = page_selection.strip()
                    opendataloader_pdf.convert(
                        input_path=conversion_input_paths,
                        output_dir=str(output_dir),
                        format=format_arg,
                        **convert_kwargs,
                    )
        except Exception as exc:  # noqa: BLE001
            stop_hybrid_server()
            st.exception(exc)
            return

        merged_md_files: list[Path] = []
        if use_ocr and "markdown" in selected_formats:
            merged_md_files = merge_chunk_markdown_files(output_dir)
            if merged_md_files:
                st.info(f"Merged markdown files: {len(merged_md_files)}")

        files_created = [p for p in output_dir.rglob("*") if p.is_file()]
        st.success(f"Done. Generated {len(files_created)} file(s).")
        st.write(f"Output folder: `{output_dir}`")

        for p in sorted(files_created):
            size_kb = p.stat().st_size / 1024
            st.write(f"- `{p.relative_to(output_dir)}` ({size_kb:.1f} KB)")

        zip_bytes = build_zip_bytes(output_dir)
        st.download_button(
            label="Download output ZIP",
            data=zip_bytes,
            file_name=f"opendataloader_output_{run_id}.zip",
            mime="application/zip",
        )


if __name__ == "__main__":
    main()
