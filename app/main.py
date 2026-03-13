"""Code Scanner Agent — FastAPI app."""
import os
import shutil
from typing import List

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import MAX_SCAN_CHARS
from app.services import scanner, analyst, session_store, file_processor

app = FastAPI(title="Code Scanner Agent")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/repos")
async def list_repos():
    """List local git repositories under the home directory."""
    home = os.path.expanduser("~")
    repos = []
    try:
        for name in sorted(os.listdir(home)):
            path = os.path.join(home, name)
            if os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git")):
                repos.append({"name": name, "path": path})
    except Exception:
        pass
    return JSONResponse({"repos": repos})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = session_store.get_session()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "session": session,
    })


@app.post("/scan")
async def scan(repo_path: str = Form(...)):
    """Scan a local path or GitHub URL and generate a summary."""
    source = repo_path.strip()
    tmp_dir = None
    display_label = source  # shown in the UI header

    try:
        if scanner.is_github_url(source):
            try:
                tmp_dir = scanner.clone_github_repo(source)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            scan_root = tmp_dir
        else:
            scan_root = source

        try:
            files, skipped = scanner.scan_repo(scan_root)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not files:
            raise HTTPException(status_code=400, detail="No scannable files found.")

        context = scanner.build_context(files, max_chars=MAX_SCAN_CHARS)
        tree = scanner.file_tree(files, max_files=500)
        summary = analyst.summarize_repo(context, tree)

        session = session_store.Session(
            repo_path=display_label,
            files=files,
            repo_context=context,
            file_tree=tree,
            summary=summary,
        )
        session_store.set_session(session)

        return JSONResponse({
            "repo_path": display_label,
            "file_count": len(files),
            "skipped_dirs": skipped,
            "file_tree": tree,
            "summary": summary,
        })
    finally:
        # Always clean up the temp clone
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Process uploaded files and return extracted content for use in chat."""
    results = []
    for f in files:
        data = await f.read()
        if len(data) > file_processor.MAX_FILE_BYTES:
            results.append({
                "filename": f.filename,
                "type": "unsupported",
                "error": f"File too large (max 20 MB): {len(data):,} bytes",
            })
            continue
        result = file_processor.process_file(f.filename, data)
        # Don't send raw image bytes back to client — just confirm type
        if result["type"] == "image":
            results.append({
                "filename": result["filename"],
                "type": "image",
                "media_type": result["media_type"],
                "image_data": result["image_data"],
                "error": result["error"],
            })
        else:
            results.append({
                "filename": result["filename"],
                "type": result["type"],
                "content": result["content"],
                "error": result["error"],
            })
    return JSONResponse({"files": results})


@app.post("/ask")
async def ask(question: str = Form(...), attachments: str = Form(default="[]")):
    """Ask a question about the currently scanned repository, with optional file attachments."""
    import json
    session = session_store.get_session()
    if session is None:
        raise HTTPException(status_code=400, detail="No repository scanned yet. Please scan a repo first.")

    try:
        parsed_attachments = json.loads(attachments)
    except Exception:
        parsed_attachments = []

    answer = analyst.answer_question(
        question=question,
        repo_context=session.repo_context,
        file_tree=session.file_tree,
        history=session.history,
        attachments=parsed_attachments,
    )
    session_store.append_turn(question, answer)

    return JSONResponse({"question": question, "answer": answer})


@app.post("/clear")
async def clear():
    """Clear the current session."""
    session_store.clear_session()
    return JSONResponse({"status": "cleared"})


@app.get("/session")
async def get_session_info():
    session = session_store.get_session()
    if session is None:
        return JSONResponse({"active": False})
    return JSONResponse({
        "active": True,
        "repo_path": session.repo_path,
        "file_count": len(session.files),
        "file_tree": session.file_tree,
        "summary": session.summary,
        "history_turns": len(session.history) // 2,
    })
