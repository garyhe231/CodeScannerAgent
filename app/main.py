"""Code Scanner Agent — FastAPI app."""
import shutil

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services import scanner, analyst, session_store

app = FastAPI(title="Code Scanner Agent")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


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

        context = scanner.build_context(files, max_chars=120_000)
        tree = scanner.file_tree(files)
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


@app.post("/ask")
async def ask(question: str = Form(...)):
    """Ask a question about the currently scanned repository."""
    session = session_store.get_session()
    if session is None:
        raise HTTPException(status_code=400, detail="No repository scanned yet. Please scan a repo first.")

    answer = analyst.answer_question(
        question=question,
        repo_context=session.repo_context,
        file_tree=session.file_tree,
        history=session.history,
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
