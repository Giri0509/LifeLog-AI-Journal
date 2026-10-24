"""Bound request bodies before FastAPI parses them, including streamed bodies."""
from starlette.responses import JSONResponse

class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes=262144):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        async def reject():
            response = JSONResponse(status_code=413, content={'detail':'Request is too large. Please shorten the text.'}, headers={'Cache-Control':'no-store'})
            await response(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            if int(headers.get(b'content-length', b'0')) > self.max_bytes:
                return await reject()
        except ValueError:
            return await reject()
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > self.max_bytes:
                return await reject()
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        replayed = False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope, replay, send)
