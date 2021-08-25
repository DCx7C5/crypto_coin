import os
from typing import Union
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from aiohttp.web_ws import WebSocketResponse

WS_FILE = os.path.join(os.path.dirname(__file__), "websocket.html")

print(WS_FILE)
bash_block_notify = '#!/bin/bash\ncurl "http://{host}:{port}/block" -d "$@"'


async def block_notify_handler(request: Request) -> Union[WebSocketResponse, Response]:
    resp = WebSocketResponse()
    available = resp.can_prepare(request)
    if not available:
        with open(WS_FILE, "rb") as fp:
            return Response(body=fp.read(), content_type="text/html")

    await resp.prepare(request)

    await resp.send_str("Welcome!!!")

    try:
        print("Someone joined.")
        for ws in request.app["sockets"]:
            await ws.send_str("Someone joined")
        request.app["sockets"].append(resp)

        async for msg in resp:
            if msg.type == web.WSMsgType.BINARY:
                for ws in request.app["sockets"]:
                    if ws is not resp:
                        await ws.send_str(msg.data)
            else:
                return resp
        return resp

    finally:
        request.app["sockets"].remove(resp)
        print("Someone disconnected.")
        for ws in request.app["sockets"]:
            await ws.send_str("Someone disconnected.")


async def on_shutdown(app: web.Application) -> None:
    for ws in app["sockets"]:
        await ws.close()


def init() -> web.Application:
    app = web.Application()
    app["sockets"] = []
    app.router.add_get("/", block_notify_handler)
    app.on_shutdown.append(on_shutdown)
    return app


web.run_app(init())
