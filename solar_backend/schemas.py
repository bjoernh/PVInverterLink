from typing import Optional

from pydantic.dataclasses import dataclass

from fastapi_users import schemas

from solar_backend.db import User



class UserRead(schemas.BaseUser[int]):
    first_name: str
    last_name: str
    tmp_pass: Optional[str] = None

class UserCreate(schemas.BaseUserCreate):
    first_name: str
    last_name: str
    tmp_pass: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    first_name: str
    last_name: str
    tmp_pass: Optional[str] = None


@dataclass
class InverterAdd:
        name: str
        serial: str

@dataclass
class InverterAddMetadata:
        rated_power: int
        number_of_mppts: int

@dataclass
class Inverter:
    id: int
    name: str
    serial_logger: str
    influx_bucked_id: str
    sw_version: str
    user: schemas.BaseUser[int]
    current_power: Optional[int] = None
    last_update: Optional[str] = None
    rated_power: Optional[int] = None
    number_of_mppts: Optional[int] = None