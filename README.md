# JC Util

> Author: Jochen.He


## 1. Chalk

『粉笔工具』

用于在`console`输出带有颜色和样式的文字

例：
```python
from jcutil.chalk import RedChalk

print(RedChalk('This is a red hello world'))
```


## 2. Drivers

一些常用的第三方工具的驱动

### 2.1 db

数据库链接驱动，推荐使用`sqlalchemy`

```python
from jcutil.drivers import db

db_url = 'mysql://127.0.0.1:3366/mydatabase?encoding=utf8mb'
conn = db.new_client('mydb', url=db_url)
```


