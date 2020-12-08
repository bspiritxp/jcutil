# depend on pycryptodomex module
from Cryptodome.Cipher import AES
import hashlib

BS = AES.block_size


def padding_pkcs5(value):
    return str.encode(value + (BS - len(value) % BS) * chr(BS - len(value) % BS))


def padding_zero(value):
    while len(value) % 16 != 0:
        value += '\0'
    return str.encode(value)


def aes_ecb_encrypt(key, value):
    # AES/ECB/PKCS5padding
    # key is sha1prng encrypted before
    cryptor = AES.new(bytes.fromhex(key), AES.MODE_ECB)
    padding_value = padding_pkcs5(value)  # padding content with pkcs5
    ciphertext = cryptor.encrypt(padding_value)
    return ''.join(['%02x' % i for i in ciphertext]).upper()


def aes_ecb_decrypt(key: str, value: str) -> str:
    """ AES/ECB/NoPadding decrypt """
    key = bytes.fromhex(key)
    cryptor = AES.new(key, AES.MODE_ECB)
    ciphertext = cryptor.decrypt(bytes.fromhex(value))
    return unpad(ciphertext.decode('utf-8'))


def get_sha1prng_key(key):
    """[summary]
    encrypt key with SHA1PRNG
    same as java AES crypto key generator SHA1PRNG
    Arguments:
        key {[string]} -- [key]

    Returns:
        [string] -- [hexstring]
    """
    signature = hashlib.sha1(key.encode()).digest()
    signature = hashlib.sha1(signature).digest()
    return ''.join(['%02x' % i for i in signature]).upper()[:32]


def unpad(s):
    return s[:-ord(s[len(s) - 1:])]
