from _typeshed import SupportsWrite
import datetime as dt
from collections import namedtuple
from decimal import Decimal
from io import FileIO
from json import JSONDecoder, JSONEncoder, dump, dumps, load, loads
from pathlib import Path
from typing import Any, Iterable, override, Callable
from uuid import UUID

from functools import partial
from jcramda import (
    attr,
    b64_encode,
    camelcase,
    compose,
    flat_concat,
    has_attr,
    identity,
    is_a,
    is_a_int,
    is_a_mapper,
    key_map,
    when,
)

from .pdtools import TYPE_REGS

_str_to_type = {
    "true": True,
    "false": False,
}

__all__ = (
    "SafeJsonEncoder",
    "SafeJsonDecoder",
    "to_json",
    "to_json_file",
    "pp_json",
    "fix_document",
    "to_obj",
    "from_json_file",
)

_type_regs = (
    *TYPE_REGS,
    (is_a((UUID,)), str),
    (is_a(dt.datetime), lambda o: o.strftime("%Y-%m-%d %H:%M:%S")),
    (is_a(bytes), b64_encode),
    (is_a(memoryview), compose(b64_encode, bytes)),
    (is_a(dict), flat_concat),
    (is_a_int, int),
    (has_attr("__html__"), compose(identity, attr("__html__"))),  # pyright: ignore [reportCallIssue]
    (is_a(str), lambda s: _str_to_type.get(s, s)),
)

class SafeJsonEncoder(JSONEncoder):
    @override
    def default(self, o: Any) -> Any:
        # 添加更具体的异常处理或返回None而不是强制转为字符串
        try:
            r = when(*_type_regs, else_=lambda x: None)(o)  # 或者抛出更明确的异常
            return key_map(camelcase, r)  # pyright: ignore [reportArgumentType]
        except Exception:
            # 根据具体需求决定如何处理无法序列化的对象
            raise TypeError(f"Object of type {type(o)} is not JSON serializable")


class SafeJsonDecoder(JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=fix_document, *args, **kwargs)


to_json = partial(dumps, cls=SafeJsonEncoder, ensure_ascii=False)


def to_json_file(obj: Any, fp: str|SupportsWrite[str], **kwargs: Any) -> None:
    """将对象序列化为JSON并写入文件

    Args:
        obj: 要序列化的对象
        fp: 文件路径或文件对象
        **kwargs: 其他传递给json.dump的参数
    """
    kwargs.setdefault("cls", SafeJsonEncoder)
    kwargs.setdefault("ensure_ascii", False)

    if isinstance(fp, str):
        with open(fp, "w", encoding="utf-8") as f:
            dump(obj, f, **kwargs)
    else:
        dump(obj, fp, **kwargs)


DocFixedOpt = namedtuple("DocFixedOpt", "where, fixed")


def fix_document(doc: Any, fix_options: Iterable[DocFixedOpt] = ()) -> Any | None:
    if is_a_mapper(doc):
        r = {}
        for k, v in doc.items():
            new_key, new_v = k, v
            if str(k).startswith("$"):
                if len(doc) == 1:
                    return fix_document(v, fix_options)
                new_key = k[1:]
            r[new_key] = fix_document(new_v, fix_options)
        return r
    elif is_a((list, tuple, set), doc):
        return [fix_document(x, fix_options) for x in doc]

    if str(doc).lower() in ("nan", "nat", "null"):
        return None

    return when(*fix_options, (is_a(Decimal), identity), else_=doc)(doc)


to_obj = partial(loads, cls=SafeJsonDecoder)


def from_json_file(file_path: str | Path) -> dict[str, Any] | list[Any]:
    with open(file_path, "r") as fp:
        s = load(fp, cls=SafeJsonDecoder)
    if is_a(str, s):
        s = to_obj(s)
    return s


def pp_json(obj: object) -> str:
    printed_str = dumps(obj, indent=2, ensure_ascii=False)
    try:
        from pygments import formatters, highlight, lexers

        colorful_json = highlight(
            printed_str, lexers.JsonLexer(), formatters.TerminalFormatter()
        )
    except ModuleNotFoundError:
        from jcutil.chalk import GreenChalk

        colorful_json = GreenChalk(printed_str)
    return colorful_json
