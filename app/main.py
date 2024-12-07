from contextlib import asynccontextmanager
from typing import AsyncGenerator

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


@app.get("/")
async def get() -> HTMLResponse:
    with open("display.html_template", "r") as f:
        display_html = f.read()

    with open("display.css", "r") as f:
        display_css = f.read()

    with open("display_script.js", "r") as f:
        display_script = f.read()

    display_html = display_html.format(
        display_css=display_css, display_script=display_script
    )

    return HTMLResponse(display_html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global loom_server
    assert loom_server is not None
    await loom_server.run_client(websocket=websocket)
