import os

import pytest
from jcramda import hex_token, members

from jcutil.crypto import Mode, aes_decrypt, aes_encrypt, sha3sum, to_base64


@pytest.fixture()
def modes():
    return members(Mode)


def test_aes(modes):
    raw = os.getenv("TXT", "This is a Test text")
    print("plaintext =", raw, "| hashsum:", sha3sum(raw))
    # genrate a 32 bytes key
    key = hex_token(32)
    print("key:", key)
    for m in modes:
        print(m)
        ciphertext, iv = aes_encrypt(key, raw, mode=m)
        print(ciphertext, iv)
        r = aes_decrypt(key, mode=m, nonce_or_iv=iv)(ciphertext)
        assert r == raw
        print(to_base64(ciphertext))
