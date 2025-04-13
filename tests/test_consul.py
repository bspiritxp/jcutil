import pytest

from jcutil.consul import ConfigFormat, KvProperty


class TestA:
  name = KvProperty('name')
  bar = KvProperty('foo', format=ConfigFormat.Yaml, cached=True)

  def desc(self):
    print('my name is:', self.name)


@pytest.mark.skip(reason="需要配置Consul服务才能运行此测试")
def test_kvp():
  ta = TestA()
  ta.desc()
  assert ta.name == 'FooBar'
  print(ta.bar, ta.foo)
