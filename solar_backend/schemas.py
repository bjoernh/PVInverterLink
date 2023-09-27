from typing import Optional

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
class InverterAdd:
        name: str
        serial: str

@dataclass
class Inverter:
    id: int
    name: str
    serial_logger: str
    influx_bucked_id: str
    sw_version: str
    user: schemas.BaseUser[int]
    current_power: Optional[int]
    last_update: Optional[str]