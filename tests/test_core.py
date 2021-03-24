import time
from jcutil.core import map_async


def test_map_async():
    start = time.perf_counter()
    r = map_async(lambda x: x**x, range(10**7))
    end = time.perf_counter()
    print(f'expand time: {end - start}s')


if __name__ == '__main__':
    test_map_async()

