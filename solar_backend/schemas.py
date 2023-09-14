from typing import Optional
import uuid

from pydantic.dataclasses import dataclass

from fastapi_users import schemas

from solar_backend.db import User



class UserRead(schemas.BaseUser[int]):
    first_name: Optional[str]
    last_name: Optional[str]


class UserCreate(schemas.BaseUserCreate):
    first_name: Optional[str]
    last_name: Optional[str]


class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str]
    last_name: Optional[str]

@dataclass
class Inverter:
    id: uuid.UUID
    name: str
    user: schemas.BaseUser[int]