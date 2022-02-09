import asyncio
import pytest
import logging
from .redis import new_client, connect, SpinLock


@pytest.mark.asyncio
async def test_spin_lock():
    new_client('redis://127.0.0.1:6379', 'test')
    async with SpinLock('test', 'test'):
        await asyncio.sleep(3)
        logging.info('sleep with lock')

