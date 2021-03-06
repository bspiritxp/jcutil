# need install kafka-python
import json
import os
import asyncio
from enum import Enum, auto
from typing import Union, Tuple, Callable, Any, Protocol, Optional
from kafka import KafkaProducer, KafkaAdminClient, KafkaConsumer
from kafka.admin import NewTopic
from jcutil.core import async_run


__clients = {}

__cache = {
    'idx': 0
}


class AutoOffsetRest(Enum):
    EARLIEST = auto()
    LATEST = auto()
    NONE = auto()

    @property
    def sv(self):
        return self.name.lower()


class BaseMessage(Protocol):
    topic: str
    key: Optional[str]
    timestamp: int
    offset: int
    headers: list


class MockMessage(BaseMessage):
    def __init__(self, **kwargs):
        self.topic = kwargs.get('topic')
        self.key = kwargs.get('key')
        self.timestamp = kwargs.get('timestamp')
        self.offset = kwargs.get('offset', 0)
        self.headers = kwargs.get('headers', [])


def load(conf):
    for key in conf:
        __clients[key] = conf[key]


def new_client(tag, *servers):
    __clients[tag] = ','.join(servers)


def _convert(raw) -> bytes:
    try:
        s = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    except TypeError:
        s = str(raw)

    return s.encode('utf8')


def send(tag, topic, msg, on_success=None, on_error=None, **kwargs):
    assert tag in __clients, 'not found tag in clients'
    producer = KafkaProducer(bootstrap_servers=__clients[tag])
    f = producer.send(topic, _convert(msg), **kwargs)
    if on_success:
        f.add_callback(on_success)
    if on_error:
        f.add_errback(on_error)
    return f


def _value_des(raw):
    s = raw.decode()
    try:
        r = json.loads(s)
        return json.loads(r) if isinstance(r, str) else r
    except (json.JSONDecodeError, ValueError, TypeError):
        return s


async def subscribe(tag, group_id, / ,
                    topics: Union[Tuple, str] = (),
                    offset_reset: AutoOffsetRest = AutoOffsetRest.LATEST,
                    handler: Callable[[Any, BaseMessage], Any] = None,
                    debug=False,
                    **kwargs
                    ):
    """
    ??????????????????????????????????????????handler??????????????????

    Parameters
    ----------
    tag
        ????????????mq?????? ?????????????????????tag???
    group_id
        ??????????????????group_id??????group?????????????????????
    topics
        ????????? ?????? "oneTopic", ("foo", "bar"), "^foo.*" ????????????
    offset_reset: AutoOffsetRest
        ????????????????????????'latest'????????????????????????????????????
    handler: Callable[[Any, Message], Any]
        ?????????????????????????????????
    debug: bool
        ????????????debug?????????False. ??????????????????????????????????????????
    client_id: str ???????????????
    value_deserializer: Callable ?????????????????????????????????????????????????????????_value_des??????

    Returns
    -------


    Examples
    -------------------
        import asyncio
        asyncio.run(subscribe('someTag', 'testGroup', 'testTopic', handler=print))
    """
    assert tag in __clients
    config = dict(
        client_id=kwargs.get('client_id', f'{group_id}-{os.getpid()}-{__cache["idx"]}'),
        bootstrap_servers=__clients[tag],
        group_id=group_id,
        auto_offset_reset=offset_reset.sv,
        value_deserializer=kwargs.get('value_deserializer', _value_des),
    )
    __cache['idx'] += 1
    consumer = KafkaConsumer(**config)
    topics_params = dict(topics=topics) if isinstance(topics, Tuple) \
        else dict(pattern=topics)

    consumer.subscribe(**topics_params)
    print('group_id: {}, subscribe topics: {} '.format(group_id, topics_params))

    for msg in consumer:
        try:
            coro = handler(msg.value, msg) if asyncio.iscoroutinefunction(handler) \
                else async_run(handler, msg.value, msg)
            r = await coro
            while asyncio.isfuture(r):
                r = await r
            if debug:
                if r == 'exit':
                    break
                print(msg, r)
        except RuntimeError as err:
            print(err)
    print('stop subscribe.')


def create_topic(tag, topic):
    admin = KafkaAdminClient(bootstrap_servers=__clients[tag])
    new_topic = NewTopic(topic, 3, 1)
    admin.create_topics((new_topic,))

