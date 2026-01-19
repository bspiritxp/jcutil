import asyncio
import json
from io import BytesIO
from pathlib import Path

import aiofiles
import httpx
import websockets


async def get_json(url, params=None, **kwargs):
    """
    GET method with json result
    Parameters
    ----------
    url : str
        API endpoint URL
    params : dict, optional
        URL query parameters
    kwargs : dict
        Additional parameters to pass to the request

    Returns
    -------
    dict
        Parsed JSON response
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, **kwargs)
        response.raise_for_status()
        return response.json()


async def post_json(url, body, **kwargs):
    """
    POST a json body with json result
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
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=body, **kwargs)
        response.raise_for_status()
        return response.json()


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
    async with httpx.AsyncClient() as client:
        response = await client.put(url, json=body, **kwargs)
        response.raise_for_status()
        return response.json()


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
    async with httpx.AsyncClient() as client:
        response = await client.delete(url, **kwargs)
        response.raise_for_status()
        return response.json()


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
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return BytesIO(response.content), response.headers.get("content-type")
        except httpx.HTTPError:
            return None, None


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

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("GET", url, **kwargs) as response:
                response.raise_for_status()
                
                # Ensure directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                content_length = response.headers.get("content-length")
                total_size = int(content_length) if content_length else 0
                downloaded = 0
                
                async with aiofiles.open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                        await f.write(chunk)
                        downloaded += len(chunk)
                
                return True
        except httpx.HTTPError:
            return False


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

    # Prepare files for httpx
    files = {field_name: (file_path.name, open(file_path, "rb"), "application/octet-stream")}
    
    # Prepare additional data
    data = additional_data or {}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, files=files, data=data, **kwargs)
        response.raise_for_status()
        return response.json()


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
    # Handle BytesIO input
    if isinstance(file_bytes, BytesIO):
        file_bytes = file_bytes.getvalue()

    # Prepare files for httpx
    files = {field_name: (filename, file_bytes, content_type)}
    
    # Prepare additional data
    data = additional_data or {}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, files=files, data=data, **kwargs)
        response.raise_for_status()
        return response.json()


class EventSourceClient:
    """Client for Server-Sent Events (EventSource) using httpx"""

    def __init__(self, url, headers=None, reconnection_time=3.0):
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
        """
        self.url = url
        self.headers = headers or {}
        self.headers.update({"Accept": "text/event-stream"})
        self.reconnection_time = reconnection_time
        self._event_callbacks = {}
        self._running = False
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

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
        async for line in response.aiter_lines():
            line = line.strip()

            if not line:
                # Empty line means dispatch the event
                if data and event_name in self._event_callbacks:
                    event_data = "\n".join(data)
                    callback = self._event_callbacks[event_name]
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data, last_id)
                    else:
                        callback(event_data, last_id)

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
        if self._client is None:
            self._client = httpx.AsyncClient()
        
        self._running = True

        while self._running:
            try:
                async with self._client.stream(
                    "GET", self.url, headers=self.headers
                ) as response:
                    if response.status_code != 200:
                        raise ConnectionError(
                            f"Failed to connect to EventSource: {response.status_code}"
                        )

                    await self._process_events(response)
            except (httpx.RequestError, ConnectionError):
                if not self._running:
                    break
                await asyncio.sleep(self.reconnection_time)

    async def close(self):
        """Close the connection"""
        self._running = False
        if self._client:
            await self._client.aclose()
            self._client = None


class WebSocketClient:
    """Client for WebSocket connections using websockets library"""

    def __init__(self, url, headers=None):
        """
        Initialize WebSocket client

        Parameters
        ----------
        url : str
            WebSocket endpoint URL
        headers : dict, optional
            HTTP headers for the initial connection
        """
        self.url = url
        self.headers = headers or {}
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
        try:
            extra_headers = [(k, v) for k, v in self.headers.items()]
            self._ws = await websockets.connect(self.url, extra_headers=extra_headers)
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
        await self._ws.send(message)

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
        await self._ws.send(json.dumps(data))

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
        await self._ws.send(data)

    async def receive(self):
        """
        Receive a single message from WebSocket

        Returns
        -------
        str or bytes
            Received message
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")
        
        try:
            message = await self._ws.recv()
            if isinstance(message, str):
                await self._trigger_callbacks("message", message, "text")
            else:
                await self._trigger_callbacks("message", message, "binary")
            return message
        except websockets.exceptions.ConnectionClosed:
            await self._trigger_callbacks("disconnect")
            raise
        except Exception as e:
            await self._trigger_callbacks("error", e)
            raise

    async def listen(self):
        """
        Listen for messages until connection is closed
        """
        if not self._ws:
            raise ConnectionError("WebSocket not connected")

        try:
            async for message in self._ws:
                if isinstance(message, str):
                    await self._trigger_callbacks("message", message, "text")
                else:
                    await self._trigger_callbacks("message", message, "binary")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            await self._trigger_callbacks("error", e)
        finally:
            await self._trigger_callbacks("disconnect")

    async def close(self):
        """Close WebSocket connection"""
        if self._ws:
            await self._ws.close()
            self._ws = None
