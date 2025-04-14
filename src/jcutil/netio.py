import asyncio
import json
from io import BytesIO
from pathlib import Path

import aiofiles
import aiohttp


async def get_json(url, params, **kwargs):
    """
    GET method with json result
    Parameters
    ----------
    url : str
        API endpoint URL
    params : dict
        URL query parameters
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, params=params, headers={"content-type": "application/json"}, **kwargs
        ) as resp:
            if resp.content_type == "application/json":
                return await resp.json()
            else:
                return json.loads(await resp.text())


async def post_json(url, body, **kwargs):
    """
    post a json body with json result
    Parameters
    ----------
    url : str
        API endpoint URL
    body : dict
        Request body to be serialized as JSON
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, **kwargs) as resp:
            return await resp.json()


async def put_json(url, body, **kwargs):
    """
    PUT method with json request and response

    Parameters
    ----------
    url : str
        API endpoint URL
    body : dict
        Request body to be serialized as JSON
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=body, **kwargs) as resp:
            return await resp.json()


async def delete_json(url, **kwargs):
    """
    DELETE method with json response

    Parameters
    ----------
    url : str
        API endpoint URL
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, **kwargs) as resp:
            return await resp.json()


async def download(url, **kwargs):
    """
    Download file from URL

    Parameters
    ----------
    url : str
        URL to download from
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    tuple
        BytesIO object with file content and content type
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, **kwargs) as resp:
            if resp.status >= 400:
                return None, None
            return BytesIO(await resp.content.read()), resp.content_type


async def download_to_file(url, destination_path, chunk_size=1024 * 1024, **kwargs):
    """
    Download file from URL and save to disk with progress tracking

    Parameters
    ----------
    url : str
        URL to download from
    destination_path : str or Path
        Path where to save the file
    chunk_size : int
        Size of chunks to download at once
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    bool
        True if download was successful, False otherwise
    """
    dest_path = Path(destination_path)
    if dest_path.exists() and not kwargs.get("overwrite", False):
        return False

    async with aiohttp.ClientSession() as session:
        async with session.get(url, **kwargs) as resp:
            if resp.status >= 400:
                return False

            # Ensure directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            async with aiofiles.open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    await f.write(chunk)
                    downloaded += len(chunk)

            return True


async def upload_file(
    url, file_path, field_name="file", additional_data=None, **kwargs
):
    """
    Upload file to server using multipart/form-data

    Parameters
    ----------
    url : str
        Upload endpoint URL
    file_path : str or Path
        Path to the file to be uploaded
    field_name : str
        Form field name for the file
    additional_data : dict
        Additional form fields to include
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    data = aiohttp.FormData()
    data.add_field(
        field_name,
        open(file_path, "rb"),
        filename=file_path.name,
        content_type="application/octet-stream",
    )

    if additional_data:
        for key, value in additional_data.items():
            data.add_field(key, str(value))

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, **kwargs) as resp:
            return await resp.json()


async def upload_bytes(
    url,
    file_bytes,
    filename,
    field_name="file",
    content_type="application/octet-stream",
    additional_data=None,
    **kwargs,
):
    """
    Upload in-memory bytes to server using multipart/form-data

    Parameters
    ----------
    url : str
        Upload endpoint URL
    file_bytes : bytes or BytesIO
        File content as bytes or BytesIO
    filename : str
        Name to give the file
    field_name : str
        Form field name for the file
    content_type : str
        MIME type of the file
    additional_data : dict
        Additional form fields to include
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    data = aiohttp.FormData()

    if isinstance(file_bytes, BytesIO):
        file_bytes = file_bytes.getvalue()

    data.add_field(field_name, file_bytes, filename=filename, content_type=content_type)

    if additional_data:
        for key, value in additional_data.items():
            data.add_field(key, str(value))

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, **kwargs) as resp:
            return await resp.json()


class EventSourceClient:
    """Client for Server-Sent Events (EventSource)"""

    def __init__(self, url, headers=None, reconnection_time=3.0, session=None):
        """
        Initialize EventSource client

        Parameters
        ----------
        url : str
            EventSource endpoint URL
        headers : dict, optional
            HTTP headers to send
        reconnection_time : float
            Time in seconds to wait before reconnecting
        session : aiohttp.ClientSession, optional
            Session to use for connections
        """
        self.url = url
        self.headers = headers or {}
        self.headers.update({"Accept": "text/event-stream"})
        self.reconnection_time = reconnection_time
        self._session = session
        self._should_close_session = session is None
        self._event_callbacks = {}
        self._running = False

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._should_close_session and self._session:
            await self._session.close()

    def on(self, event_name, callback):
        """
        Register callback for specific event type

        Parameters
        ----------
        event_name : str
            Name of the event to listen for ('message' for default events)
        callback : callable
            Function to call when event is received
        """
        self._event_callbacks[event_name] = callback
        return self

    async def _process_events(self, response):
        """Process event stream from response"""
        event_name = "message"
        data = []
        last_id = None

        # Process the EventSource stream
        async for line in response.content:
            line = line.decode("utf-8").strip()

            if not line:
                # Empty line means dispatch the event
                if data and event_name in self._event_callbacks:
                    event_data = "".join(data)
                    callback = self._event_callbacks[event_name]
                    await callback(event_data, last_id)

                # Reset for next event
                event_name = "message"
                data = []
                continue

            if line.startswith(":"):
                # Comment, ignore
                continue

            if ":" in line:
                field, value = line.split(":", 1)
                if value.startswith(" "):
                    value = value[1:]

                if field == "event":
                    event_name = value
                elif field == "data":
                    data.append(value)
                elif field == "id":
                    last_id = value
                elif field == "retry":
                    try:
                        self.reconnection_time = int(value) / 1000.0
                    except ValueError:
                        pass

    async def connect(self):
        """
        Connect to EventSource endpoint and start processing events
        """
        self._running = True

        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._should_close_session = True

        while self._running:
            try:
                async with self._session.get(
                    self.url, headers=self.headers
                ) as response:
                    if response.status != 200:
                        raise ConnectionError(
                            f"Failed to connect to EventSource: {response.status}"
                        )

                    await self._process_events(response)
            except (aiohttp.ClientError, ConnectionError):
                if not self._running:
                    break
                await asyncio.sleep(self.reconnection_time)

    async def close(self):
        """Close the connection"""
        self._running = False
        if self._should_close_session and self._session:
            await self._session.close()
            self._session = None


class WebSocketClient:
    """Client for WebSocket connections"""

    def __init__(self, url, headers=None, session=None):
        """
        Initialize WebSocket client

        Parameters
        ----------
        url : str
            WebSocket endpoint URL
        headers : dict, optional
            HTTP headers for the initial connection
        session : aiohttp.ClientSession, optional
            Session to use for connections
        """
        self.url = url
        self.headers = headers or {}
        self._session = session
        self._should_close_session = session is None
        self._ws = None
        self._callbacks = {"message": [], "connect": [], "disconnect": [], "error": []}

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def on(self, event_type, callback):
        """
        Register callback for specific event

        Parameters
        ----------
        event_type : str
            Type of event: 'message', 'connect', 'disconnect', 'error'
        callback : callable
            Function to call when event occurs
        """
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
        return self

    async def _trigger_callbacks(self, event_type, *args):
        """Trigger all callbacks for an event type"""
        for callback in self._callbacks.get(event_type, []):
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)

    async def connect(self):
        """Connect to WebSocket endpoint"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._should_close_session = True

        try:
            self._ws = await self._session.ws_connect(self.url, headers=self.headers)
            await self._trigger_callbacks("connect")
        except Exception as e:
            await self._trigger_callbacks("error", e)
            raise

    async def send_text(self, message):
        """
        Send text message to WebSocket

        Parameters
        ----------
        message : str
            Text message to send
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send_str(message)

    async def send_json(self, data):
        """
        Send JSON message to WebSocket

        Parameters
        ----------
        data : dict
            Data to be serialized as JSON and sent
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send_json(data)

    async def send_bytes(self, data):
        """
        Send binary message to WebSocket

        Parameters
        ----------
        data : bytes
            Binary data to send
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send_bytes(data)

    async def receive(self):
        """
        Receive a single message from WebSocket

        Returns
        -------
        aiohttp.WSMessage
            Received message
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")
        msg = await self._ws.receive()

        if msg.type == aiohttp.WSMsgType.TEXT:
            await self._trigger_callbacks("message", msg.data, "text")
        elif msg.type == aiohttp.WSMsgType.BINARY:
            await self._trigger_callbacks("message", msg.data, "binary")
        elif msg.type == aiohttp.WSMsgType.ERROR:
            await self._trigger_callbacks("error", msg.data)
        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
            await self._trigger_callbacks("disconnect")

        return msg

    async def listen(self):
        """
        Listen for messages until connection is closed
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._trigger_callbacks("message", msg.data, "text")
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await self._trigger_callbacks("message", msg.data, "binary")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    await self._trigger_callbacks("error", msg.data)
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                    break
        finally:
            await self._trigger_callbacks("disconnect")

    async def close(self):
        """Close WebSocket connection"""
        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._should_close_session and self._session:
            await self._session.close()
            self._session = None
