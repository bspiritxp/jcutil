from html import escape
from typing import Callable, Union, override, cast, Tuple, Any

from jcramda import when
from jcramda.base.comparison import is_a_str, is_a_tuple


def _escape(raw: str) -> str:
    if raw.startswith("{{") and raw.endswith("}}"):
        return raw.strip("{{").strip("}}")
    if is_a_str(raw):
        return f"'{escape(raw)}'"
    return str(raw)


_value_check = cast(
    Callable[[Union[str, Tuple[str, str]]], str],
    when(
        (is_a_str, lambda s: f" = {_escape(s)}"),
        (is_a_tuple, lambda tp: f"{tp[0]} {_escape(tp[1])}"),
        else_=str,
    )
)

class Where:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw: dict[str, Any] = raw

    @override
    def __str__(self) -> str:
        tn = getattr(type(self.raw), "__name__")
        method = getattr(self, f"from_{tn}")
        if callable(method):
            result = method()
            if isinstance(result, str):
                return result
            raise ValueError(f"{result} is not a string")
        else:
            return str(self.raw)

    def from_dict(self) -> str:
        """
        Example:
        >>> w = Where({'name': 'someone', 'age': ('>', 32), 'birthday': '{{CURRENT_DATE}}'})
        >> print(w)
           name = 'someone' AND 'age' > 32 AND birthday = CURRENT_DATE
        """
        return " AND ".join(
            [f"{key} {_value_check(value)}" for key, value in self.raw.items()]
        )
