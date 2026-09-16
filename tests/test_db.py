from uuid import uuid4

import pytest
from sqlalchemy import text

from jcutil.drivers import db


def test_sync_engine_registration_and_connection():
    tag = f'test-sync-{uuid4().hex}'
    db.register_sync(tag, 'sqlite:///:memory:')

    try:
        with db.connect(tag) as connection:
            connection.execute(text('CREATE TABLE values_table (value INTEGER)'))
            connection.execute(text('INSERT INTO values_table VALUES (42)'))
            assert connection.scalar(text('SELECT value FROM values_table')) == 42
        assert tag in db.instances()
    finally:
        db.dispose_sync(tag)


@pytest.mark.asyncio
async def test_async_engine_registration_and_connection():
    tag = f'test-async-{uuid4().hex}'
    db.register_async(tag, 'sqlite+aiosqlite:///:memory:')

    try:
        async with db.async_connect(tag) as connection:
            await connection.execute(text('CREATE TABLE values_table (value INTEGER)'))
            await connection.execute(text('INSERT INTO values_table VALUES (42)'))
            assert (await connection.scalar(text('SELECT value FROM values_table'))) == 42
    finally:
        await db.dispose_async(tag)


def test_load_requires_explicit_engine_mode():
    with pytest.raises(ValueError, match="requires 'url' and 'mode'"):
        db.load({'app': {'url': 'sqlite:///:memory:'}})


def test_legacy_sync_functions_delegate_to_v3_registry():
    first_tag = f'test-legacy-first-{uuid4().hex}'
    second_tag = f'test-legacy-second-{uuid4().hex}'
    first_engine = db.init_engine(first_tag, 'sqlite:///:memory:')
    db.new_client(second_tag, 'sqlite:///:memory:')

    try:
        assert db.get_client() is first_engine
        with db.conn(0) as connection:
            assert connection.scalar(text('SELECT 1')) == 1

        db.close_engine(second_tag)
        assert second_tag not in db.instances()

        db.close_all_engines()
        assert first_tag not in db.instances()
    finally:
        for tag in (first_tag, second_tag):
            if tag in db.instances():
                db.dispose_sync(tag)
