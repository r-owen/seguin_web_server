import pkgutil
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from .loom_server import LoomServer

# Avoid warnings about no event loop in unit tests
# by constructing when the server starts
loom_server: LoomServer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, FastAPI]:
    global loom_server
    async with LoomServer(emulate_loom=True, verbose=True) as loom_server:
        yield


app = FastAPI(lifespan=lifespan)


def get_file(filename: str) -> str:
    """Get the contents of text file from src/seguin_loom_driver"""
    bindata = pkgutil.get_data(package="seguin_loom_server", resource=filename)
    assert bindata is not None
    return bindata.decode()


@app.get("/")
async def get() -> HTMLResponse:
    display_html_template = get_file("display.html_template")

    display_css = get_file("display.css")

    display_js = get_file("display.js")

    display_html = display_html_template.format(
        display_css=display_css, display_js=display_js
    )

    return HTMLResponse(display_html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global loom_server
    assert loom_server is not None
    await loom_server.run_client(websocket=websocket)


def start_seguin_loom_server() -> None:
    uvicorn.run(
        "seguin_loom_server.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
    )
