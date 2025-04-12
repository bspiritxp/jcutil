from jcutil.consul import ConfigFormat, KvProperty


class TestA:
  name = KvProperty('name')
  bar = KvProperty('foo', format=ConfigFormat.Yaml, cached=True)

  def desc(self):
    print('my name is:', self.name)


def test_kvp():
  ta = TestA()
  ta.desc()
  assert ta.name == 'FooBar'
  print(ta.bar, ta.foo)
