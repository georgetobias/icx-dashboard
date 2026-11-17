from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import charts, metrics
from .settings import APP_ROOT
from .lifecycle import sessions


class CsvSourcePayload(BaseModel):
    path: str | None = None


app = FastAPI(title="Internal CX Dashboard", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"app": "Internal CX Dashboard", "version": "1.1.0"}


@app.get("/api/source-revision")
def source_revision() -> dict:
    return metrics.source_revision()


@app.websocket("/api/session")
async def browser_session(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin != f"http://{websocket.headers.get('host')}":
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session = uuid4().hex
    sessions.connect(session)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sessions.disconnect(session)


@app.get("/api/status")
def api_status() -> dict:
    return metrics.data_status()


@app.get("/api/app-settings")
def api_app_settings() -> dict:
    return metrics.app_settings()


@app.post("/api/app-settings/csv-source")
def api_set_csv_source(payload: CsvSourcePayload) -> dict:
    try:
        return metrics.update_csv_source_path(payload.path)
    except metrics.CsvSourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/app-settings/csv-source/upload")
async def api_upload_csv_source(
    request: Request,
    x_filename: str | None = Header(default=None),
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > 50 * 1024 * 1024
        except ValueError:
            too_large = False
        if too_large:
            raise HTTPException(status_code=413, detail="The selected CSV is larger than the 50 MB import limit.")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="The selected CSV is larger than the 50 MB import limit.")
    try:
        return await run_in_threadpool(metrics.import_csv_source, bytes(content), x_filename)
    except metrics.CsvSourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/home-summary")
def api_home_summary(perspective: str = Query("provider", pattern="^(provider|customer)$")) -> dict:
    return metrics.home_summary(perspective)                          


@app.get("/api/groups")
def api_groups(perspective: str = Query("provider", pattern="^(provider|customer)$")) -> dict:
    return {"groups": metrics.groups(perspective)}                          


@app.get("/api/group/{group_name}")
def api_group(group_name: str) -> dict:
    return metrics.group_profile(group_name)


@app.get("/api/group/{group_name}/comparison")
def api_group_comparison(
    group_name: str,
    perspective: str = Query("provider", pattern="^(provider|customer)$"),
) -> dict:
    return metrics.group_comparison(group_name, perspective)                          


@app.get("/api/gaps/received-gave")
def api_received_gave(group: str = "All Groups") -> dict:
    return metrics.received_gave_summary(group)


@app.get("/api/gaps/inter-intra")
def api_inter_intra(group: str = "All Groups") -> dict:
    return metrics.inter_intra_summary(group)


@app.get("/api/blue-breakdown")
def api_blue_breakdown(
    perspective: str = Query("provider", pattern="^(provider|customer)$"),
    group: str = "All Groups",
    analysis: str = Query("groups", pattern="^(groups|service|division|territory)$"),
) -> dict:
    return metrics.blue_breakdown(perspective, group, analysis)                          


@app.get("/api/blue-service-queues")
def api_blue_service_queues(
    group: str,
    perspective: str = Query("provider", pattern="^(provider|customer)$"),
) -> dict:
    return metrics.blue_service_queues(group, perspective)                          


@app.get("/api/service-blue-breakdown")
def api_service_blue_breakdown(
    group: str = "All Groups",
    perspective: str = Query("provider", pattern="^(provider|customer)$"),
) -> dict:
    return metrics.service_blue_breakdown(group, perspective)                          


@app.get("/api/chart/{view}")
def api_chart(
    view: str,
    perspective: str = Query("provider", pattern="^(provider|customer)$"),
    group: str = "All Groups",
    analysis: str = Query("groups", pattern="^(groups|service_clusters|division_only|division_territory|territory_only)$"),
    min_ratings: int = Query(1, ge=1, le=100),
    show_labels: bool = True,
    full_labels: bool = False,
    mean_line: bool = True,
    scatter_size: float = Query(1.05, ge=0.85, le=1.25),
    band: str = Query("Busted", pattern="^(Busted|Leveled|Uplifted|Exceptional)$"),
) -> dict:
    try:
        return charts.chart_payload(
            view=view,
            perspective=perspective,                          
            group=group,
            analysis=analysis,
            min_ratings=min_ratings,
            show_labels=show_labels,
            full_labels=full_labels,
            mean_line=mean_line,
            scatter_size=scatter_size,
            band=band,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/data-qa")
def api_data_qa() -> dict:
    return metrics.data_qa()


FRONTEND_DIST = APP_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}")
def spa(path: str) -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    target = (FRONTEND_DIST / path).resolve()
    if path.startswith("api/") or not target.is_relative_to(FRONTEND_DIST.resolve()):
        raise HTTPException(status_code=404, detail="Not found")
    if target.exists() and target.is_file():
        return FileResponse(target, headers={"Cache-Control": "no-store"} if target == index.resolve() else None)
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    raise HTTPException(
        status_code=404,
        detail="Frontend build not found. Run `pnpm --dir frontend build`.",
    )
