import aiohttp
import json
from io import BytesIO
from .data import mem_cache


async def get_json(url, params, **kwargs):
    """
    GET method with json result
    Parameters
    ----------
    url
    params
    kwargs

    Returns
    -------

    """

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params,
                               headers={'content-type': 'application/json'},
                               **kwargs) as resp:
            return await resp.json() if resp.content_type == 'application/json' \
                else json.loads(await resp.text())


async def post_json(url, body, **kwargs):
    """
    post a json body with json result
    Parameters
    ----------
    url
    body
    kwargs dict

    Returns
    -------

    """
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, **kwargs) as resp:
            return await resp.json()


async def download(url, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.get(url,
                               **kwargs) as resp:
            if resp.status >= 400:
                return None, None
            return BytesIO(await resp.content.read()), resp.content_type


@mem_cache()
def cache_request(req_func, *args, **kwargs):
    resp = req_func(*args, **kwargs)
    if resp.ok and resp.status_code < 400:
        return resp
    raise RuntimeError(f'request error: {args[0]}')
