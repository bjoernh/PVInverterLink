from fastapi_users import schemas
from pydantic.dataclasses import dataclass


class UserRead(schemas.BaseUser[int]):
    first_name: str
    last_name: str


class UserCreate(schemas.BaseUserCreate):
    first_name: str
    last_name: str


class UserUpdate(schemas.BaseUserUpdate):
    first_name: str
    last_name: str


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
    sw_version: str
    user: schemas.BaseUser[int]
    current_power: int | None = None
    last_update: str | None = None
    rated_power: int | None = None
    number_of_mppts: int | None = None


@dataclass
class InverterMetadataResponse:
    id: int
    serial_logger: str
    name: str
    rated_power: int | None
    number_of_mppts: int | None
    sw_version: str
