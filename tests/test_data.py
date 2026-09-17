import asyncio
import io
import threading
from datetime import timedelta
from uuid import uuid4

import joblib
import pytest
import pytest_asyncio
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError, TimeoutError

from jcutil.data import clear_mem, mem_cache, persistence, redis_cache


@pytest.fixture
def redis_store():
    client = Redis.from_url('redis://127.0.0.1:6379/15', socket_connect_timeout=1, socket_timeout=1)
    try:
        try:
            client.ping()
        except (ConnectionError, TimeoutError) as exc:
            pytest.skip(f'Redis unavailable: {exc}')
        yield client
    finally:
        client.close()


@pytest_asyncio.fixture
async def async_redis_store():
    client = AsyncRedis.from_url('redis://127.0.0.1:6379/15', socket_connect_timeout=1, socket_timeout=1)
    try:
        try:
            await client.ping()
        except (ConnectionError, TimeoutError) as exc:
            pytest.skip(f'Redis unavailable: {exc}')
        yield client
    finally:
        await client.aclose()


def test_cache_cleanup_rejects_escape_and_symlink(tmp_path):
    root = tmp_path / 'cache'
    (root / 'joblib').mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    marker = outside / 'keep'
    marker.write_text('untouched')
    (root / 'joblib' / 'link').symlink_to(outside, target_is_directory=True)
    for path in (str(outside), '../outside', 'link'):
        with pytest.raises(ValueError):
            clear_mem(path, root)
        assert marker.read_text() == 'untouched'
    (root / 'joblib' / 'link').unlink()
    (root / 'joblib').rmdir()
    (root / 'joblib').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        clear_mem(cache_dir=root)
    assert marker.read_text() == 'untouched'


def test_local_cache_nested_directory_and_invalidation(tmp_path):
    calls = []
    root = tmp_path / 'nested' / 'cache'

    @mem_cache(root)
    def compute(value):
        calls.append(value)
        return value * 2

    assert compute(3) == 6
    assert compute(3) == 6
    assert calls == [3]
    clear_mem(cache_dir=root)
    assert compute(3) == 6
    assert calls == [3, 3]


def test_redis_key_types_binding_and_explicit_closure_identity(redis_store):
    namespace = uuid4().hex
    calls = []

    @redis_cache(namespace=namespace, redis_connector=lambda: redis_store, expires=30)
    def identify(value, factor=1):
        calls.append(None)
        return type(value).__name__, len(calls), factor

    try:
        assert identify((1, 2)) == ('tuple', 1, 1)
        assert identify(value=(1, 2), factor=1) == ('tuple', 1, 1)
        assert identify([1, 2]) == ('list', 2, 1)
        assert identify(True) == ('bool', 3, 1)
        assert identify(1) == ('int', 4, 1)
        assert identify.invalidate((1, 2)) == 1
        assert identify((1, 2)) == ('tuple', 5, 1)
    finally:
        for value in ((1, 2), [1, 2], True, 1):
            identify.invalidate(value)

    def make(value, scope):
        @redis_cache(namespace=scope, redis_connector=lambda: redis_store)
        def read():
            return value
        return read

    first, second = make('first', namespace + '-a'), make('second', namespace + '-b')
    try:
        assert first() == 'first'
        assert second() == 'second'
    finally:
        first.invalidate()
        second.invalidate()


def test_ambiguous_closure_requires_explicit_cache_identity():
    value = 'captured'
    with pytest.raises(ValueError):
        redis_cache()(lambda: value)


def test_corrupt_cache_refresh_negative_cache_and_precise_ttl(redis_store):
    calls = []

    @redis_cache(
        expires=timedelta(milliseconds=750), namespace=uuid4().hex,
        redis_connector=lambda: redis_store, cache_none=True,
    )
    def compute():
        calls.append(None)
        return None

    key = compute.cache_key()
    try:
        redis_store.set(key, b'')
        assert compute() is None
        assert compute() is None
        assert len(calls) == 1
        assert 0 < redis_store.pttl(key) <= 750
        assert compute(update_cache=True) is None
        assert len(calls) == 2
    finally:
        compute.invalidate()


def test_json_codec_rejects_lossy_types_and_versions_invalidate(redis_store):
    namespace = uuid4().hex
    state = {'value': {'ok': [1, None]}}

    def read():
        return state['value']

    one = redis_cache(namespace=namespace, codec='json', redis_connector=lambda: redis_store)(read)
    two = redis_cache(namespace=namespace, version='2', codec='json', redis_connector=lambda: redis_store)(read)
    try:
        assert one() == {'ok': [1, None]}
        state['value'] = {'changed': True}
        assert one() == {'ok': [1, None]}
        assert two() == {'changed': True}
        state['value'] = (1, 2)
        with pytest.raises(TypeError):
            one(update_cache=True)
        # Failed serialization did not replace the last valid entry.
        assert one() == {'ok': [1, None]}
    finally:
        one.invalidate()
        two.invalidate()


@pytest.mark.parametrize('expires', [0, -1, float('inf'), timedelta(0)])
def test_invalid_cache_expiration_is_rejected(expires):
    with pytest.raises(ValueError):
        redis_cache(expires=expires)


@pytest.mark.asyncio
async def test_native_sync_and_async_caches_work_inside_event_loop(redis_store, async_redis_store):
    sync_calls, async_calls = [], []

    @redis_cache(namespace=uuid4().hex, redis_connector=lambda: redis_store)
    def sync_read():
        sync_calls.append(None)
        return len(sync_calls)

    @redis_cache(namespace=uuid4().hex, redis_connector=lambda: async_redis_store)
    async def async_read():
        async_calls.append(None)
        return len(async_calls)

    try:
        assert sync_read() == sync_read() == 1
        assert await async_read() == 1
        assert await async_read() == 1
        assert await async_read.invalidate() == 1
        assert await async_read() == 2
    finally:
        sync_read.invalidate()
        await async_read.invalidate()


def test_persistence_snapshots_mutable_results_and_borrows_stream():
    entered, release = threading.Event(), threading.Event()

    class DelayedStream(io.BytesIO):
        def write(self, data):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('writer gate timed out')
            return super().write(data)

    destination = DelayedStream()
    data = {'items': [1]}
    writer = persistence(destination, lambda: data)
    try:
        completion = writer.submit()
        assert entered.wait(5)
        data['items'].append(2)
        release.set()
        assert completion.result(timeout=5) is data
        writer.flush()
    finally:
        release.set()
        writer.close()
    assert not destination.closed
    assert joblib.load(io.BytesIO(destination.getvalue())) == {'items': [1]}
    with pytest.raises(RuntimeError):
        writer()


def test_persistence_failure_is_observable_and_preserves_primary_error():
    closed = []

    class BrokenDestination:
        def write(self, data):
            raise OSError('destination rejected write')

        def close(self):
            closed.append(True)
            raise RuntimeError('secondary close failure')

    writer = persistence(BrokenDestination, lambda: {'value': 1})
    completion = writer.submit()
    with pytest.raises(OSError, match='destination rejected write'):
        completion.result(timeout=5)
    with pytest.raises(OSError, match='destination rejected write'):
        writer.flush()
    writer.close()
    assert closed == [True]


def test_persistence_atomic_path_survives_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / 'result.joblib'
    joblib.dump({'old': True}, target)

    def deny_replace(source, destination):
        raise PermissionError('replacement denied')

    monkeypatch.setattr('jcutil.data.os.replace', deny_replace)
    writer = persistence(target, lambda: {'new': True})
    writer()
    with pytest.raises(PermissionError):
        writer.close()
    assert joblib.load(target) == {'old': True}
    assert list(tmp_path.iterdir()) == [target]


def test_persistence_file_upload_mode_and_factory_ownership():
    payloads, closed = [], []

    class Upload:
        def write(self, stream):
            payloads.append(stream.read())

        def close(self):
            closed.append(True)

    with persistence(Upload, lambda value: value, write_mode='file') as writer:
        assert writer({'a': 1}) == {'a': 1}
        assert writer({'b': 2}) == {'b': 2}
    assert [joblib.load(io.BytesIO(payload)) for payload in payloads] == [{'a': 1}, {'b': 2}]
    assert closed == [True, True]


@pytest.mark.asyncio
async def test_async_persistence_writes_awaited_result(tmp_path):
    async def compute(value):
        await asyncio.sleep(0)
        return {'value': value}

    target = tmp_path / 'async.joblib'
    async with persistence(target, compute) as writer:
        assert await writer(3) == {'value': 3}
        await writer.aflush()
        assert joblib.load(target) == {'value': 3}
        completion = await writer.submit(4)
        assert await asyncio.wrap_future(completion) == {'value': 4}
    assert joblib.load(target) == {'value': 4}


def test_custom_cache_keys_isolate_tenants_and_redis_errors_propagate(redis_store):
    from redis.exceptions import ResponseError

    class Tenant:
        def __init__(self, name):
            self.name = name

    @redis_cache(
        namespace=uuid4().hex, redis_connector=lambda: redis_store,
        key_fn=lambda tenant: tenant.name, codec='json',
    )
    def lookup(tenant):
        return tenant.name

    first, second = Tenant('first'), Tenant('second')
    try:
        assert lookup(first) == 'first'
        assert lookup(second) == 'second'
        lookup.invalidate(first)
        redis_store.hset(lookup.cache_key(first), 'field', 'value')
        with pytest.raises(ResponseError):
            lookup(first)
    finally:
        lookup.invalidate(first)
        lookup.invalidate(second)


def test_persistence_handles_partial_binary_writes():
    class PartialStream(io.BytesIO):
        def write(self, data):
            return super().write(data[:3])

    destination = PartialStream()
    with persistence(destination, lambda: {'data': list(range(10))}) as writer:
        writer()
    assert joblib.load(io.BytesIO(destination.getvalue())) == {'data': list(range(10))}
