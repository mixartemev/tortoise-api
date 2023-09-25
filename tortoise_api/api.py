import logging
from functools import partial
from os import getenv as env
from types import ModuleType
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Path, HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.routing import APIRoute, APIRouter
from pydantic import SecretStr, BaseModel
# from fastapi_cache import FastAPICache
# from fastapi_cache.backends.inmemory import InMemoryBackend
from starlette import status
from starlette.responses import JSONResponse
from tortoise import Tortoise
from tortoise.contrib.pydantic import pydantic_model_creator, PydanticModel
from tortoise.contrib.starlette import register_tortoise
from tortoise.signals import pre_save

from tortoise_api_model import Model, User
from tortoise_api_model.model import hash_pwd

from tortoise_api import oauth
from tortoise_api.oauth import login_for_access_token, Token, get_current_user


class Api:
    app: FastAPI
    models: {str: Model}
    user_model: User
    redis = None

    def __init__(
        self,
        models_module: ModuleType,
        debug: bool = False,
        title: str = 'FemtoAPI',
    ):
        """
        Parameters:
            debug: Debug SQL queries, api requests
            # auth_provider: Authentication Provider
        """
        if debug:
            logging.basicConfig(level=logging.DEBUG)

        # extract models from module
        models: {Model.__class__: [Model.__class__]} = {model: model.mro() for key in dir(models_module) if isinstance(model := getattr(models_module, key), Model.__class__) and model==model.mro()[0]}
        # collect parents models for hiding
        to_hide: set[Model.__class__] = set()
        [to_hide.update(m[1:]) for m in models.values()]
        # set global only top models list
        self.models: {str: Model.__class__} = {m.__name__: m for m in set(models.keys()) - to_hide}
        user_model: type[User] = self.models['User']
        pre_save(user_model)(hash_pwd)

        out_user = pydantic_model_creator(user_model)

        class InUser(BaseModel):
            username: str
            password: SecretStr
            email: str|None
            phone: int|None

        async def reg_user(new_user: InUser) -> out_user:
            data = new_user.model_dump()
            try:
                user: user_model = await user_model.create(**data)
            except Exception as e:
                raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE, detail=e.__repr__())
            return await out_user.from_tortoise_orm(user)

        # global user model inject current overriden User type
        oauth.UserModel = user_model  # todo: maybe some refactor?

        # get auth token route
        auth_routes = [
            APIRoute('/register', reg_user, methods=['POST'], tags=['auth'], name='SignUp', response_model=out_user),
            APIRoute('/token', login_for_access_token, methods=['POST'], response_model=Token, tags=['auth']),
        ]

        # main app
        self.app = FastAPI(debug=debug, routes=auth_routes, title=title, default_response_class=ORJSONResponse)
        Tortoise.init_models([models_module], "models")
        # self.set_routes()
        # db init
        load_dotenv()
        register_tortoise(self.app, db_url=env("DB_URL"), modules={"models": [models_module]}, generate_schemas=debug)
        # FastAPICache.init(InMemoryBackend(), expire=600)

    def set_routes(self):
        for name, model in self.models.items():
            pyd_model: type[PydanticModel] = pydantic_model_creator(model, name=name)
            in_model = pydantic_model_creator(model, name='New'+name, exclude_readonly=True)

            async def index(limit: int = 50, page: int = 1):
                objects: [Model] = await model.all().prefetch_related(*model._meta.fetch_fields).limit(limit).offset(limit * (page - 1))
                data = [await obj.with_rels() for obj in objects]
                return {'data': data}  # show all

            async def one(item_id: Annotated[int, Path(title=name+" ID")]):
                obj = await model.get(id=item_id).prefetch_related(*model._meta.fetch_fields)
                return await obj.with_rels()  # show one

            async def create(obj: in_model):
                obj_dict = obj.model_dump()
                obj_db: Model = await model.upsert(obj_dict)
                jsn: dict = await obj_db.with_rels()
                return ORJSONResponse(jsn, status_code=status.HTTP_201_CREATED)  # create

            async def update(obj: in_model, item_id: int):
                obj_db: Model = await model.upsert(obj.model_dump(), item_id)
                jsn: dict = await obj_db.with_rels()
                return ORJSONResponse(jsn, status_code=status.HTTP_202_ACCEPTED)  # update

            async def delete(item_id: int):
                await (await model[item_id]).delete()
                return JSONResponse(True, status_code=status.HTTP_205_RESET_CONTENT)  # delete

            ar = APIRouter(routes=[
                APIRoute('/'+name, partial(index), methods=['GET'], name=name+' objects list', response_model=list[pyd_model]),
                APIRoute('/'+name, partial(create), methods=['POST'], name=name+' object create', response_model=pyd_model, description='321321'),
                APIRoute('/'+name+'/{item_id}', partial(one), methods=['GET'], name=name+' object get', response_model=pyd_model),
                APIRoute('/'+name+'/{item_id}', partial(update), methods=['POST'], name=name+' object update', response_model=pyd_model),
                APIRoute('/'+name+'/{item_id}', partial(delete), methods=['DELETE'], name=name+' object delete'),
            ])
            self.app.include_router(ar, tags=[name], dependencies=[Depends(get_current_user)])
