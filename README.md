# Tortoise-API
###### Simplest fastest minimal REST API CRUD generator for Tortoise ORM models.
Fully async Zero config One line ASGI app

#### Requirements
- Python >= 3.9

### INSTALL
```bash
pip install tortoise-api
```

### Run your app
- Describe your db models with Tortoise ORM in `models.py` module
```python
from tortoise_api import Model

class User(Model):
    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(255, unique=True, null=False)
    posts: fields.ReverseRelation["Post"]

class Post(Model):
    id: int = fields.IntField(pk=True)
    text: str = fields.CharField(4095)
    user: User = fields.ForeignKeyField('models.User', related_name='posts')
    _name = 'text' # `_name` sets the attr for displaying related Post instace inside User (default='name')
```
- Write run script `main.py`: pass your models module in Api app:
```python
from tortoise_api import Api
import models

app = Api().start(models)
```
- Set `DB_URL` env variable in `.env` file
- Run it:
```bash
uvicorn main:app
```
Or you can just fork Completed minimal runnable example from [sample apps](https://github.com/mixartemev/tortoise-api/blob/master/sample_apps/minimal/).

#### And voila:
You have menu with all your models at root app route: http://127.0.0.1:8000

<img width="245" alt="Home - Models list" src="https://github.com/mixartemev/tortoise-api/assets/5181924/0ddaa015-2193-43e1-a6d1-2dbad09bfc7b">


And JSON resources for each db Entity at [/{modelName}]() routes:

<img width="450" alt="User JSON resources" src="https://github.com/mixartemev/tortoise-api/assets/5181924/d4497aa5-1f10-45f3-82e8-f5145b72572e">


And one separate Entity at [/{modelName}/{entity_id}]() routes:

<img width="362" alt="User 1 JSON resource" src="https://github.com/mixartemev/tortoise-api/assets/5181924/f1fed04c-8bf2-462c-ad71-fbee35652b1a">


---
Made with ❤ on top of the Starlette and Tortoise ORM.
