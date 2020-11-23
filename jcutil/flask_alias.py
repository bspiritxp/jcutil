from enum import Flag, auto, Enum
from functools import partial
from typing import Union

from jcramda.base.datetimes import locnow
try:
    from quart import request, abort, jsonify, current_app
except ImportError:
    from flask import request, abort, jsonify, current_app

from .chalk import RedChalk
from jcramda import (attr, compose, in_, map_, filter_, nameof, getitem, locnow)


class RestfulMethod(Flag):
    GET = auto()
    POST = auto()
    PUT = auto()
    PATCH = auto()
    DELETE = auto()
    # 组合
    ALL = GET | POST | PUT | PATCH | DELETE
    NO_DEL = GET | POST | PUT | PATCH
    NO_CREATE = GET | PUT | PATCH | DELETE
    NO_EDIT = GET | POST | DELETE

    @property
    def methods(self):
        return compose(
            map_(attr('name')),
            filter_(in_(self))
        )([self.GET, self.POST, self.PUT, self.PATCH, self.DELETE])

    def eq(self, method_name):
        return method_name == self.name


def restful_api(get_func=None, post_func=None, put_func=None,
                patch_func=None, delete_func=None):
    """
    注册RESTFul类型的方法
    :param get_func: GET 请求时的方法
    :param post_func: POST 请求时的方法
    :param put_func: PUT 请求时的方法
    :param patch_func: PATCH 请求时的方法
    :param delete_func: DELETE 请求时的方法
    :return: 当前METHOD对应的方法，如未找到则返回404
    """
    method = compose(getitem, nameof(request.method))(RestfulMethod)({
        RestfulMethod.GET: get_func,
        RestfulMethod.POST: post_func,
        RestfulMethod.PUT: put_func,
        RestfulMethod.PATCH: patch_func,
        RestfulMethod.DELETE: delete_func,
    })
    return method or partial(abort, 404)


def json_abort(status: int, payload: Union[str, dict, Enum]):
    if isinstance(Enum, payload) and hasattr(payload, 'text'):
        payload = {'errmsg': payload.text}
    resp = jsonify({'errmsg': payload} if isinstance(str, payload) else payload)
    resp.status_code = status
    resp.content_type = 'application/json'
    resp.content_encoding = 'utf-8'
    abort(resp)


def debug_print(msg, *args):
    if current_app.config['DEBUG']:
        now = locnow()
        print(RedChalk(f'[{now}][DEBUG]{msg}'), *args)


async def get_json_body(fields: dict = None):
    body = await request.get_json()
    try:
        debug_print(body)
        for key in fields or {}:
            assert key in body, f'not found {key} in request body.'
            valid_method = fields[key] or bool
            assert valid_method(body[key]), f'[{key}] has a bad value: {body[key]}'
    except AssertionError as err:
        debug_print(err)
        json_abort(400, 'bad request')
    return body
