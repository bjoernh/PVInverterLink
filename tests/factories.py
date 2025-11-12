"""
Test factories for creating test data using factory-boy and Faker.
"""

import factory
from faker import Faker

from solar_backend.schemas import InverterAdd, InverterAddMetadata, UserCreate

faker = Faker()


class UserCreateFactory(factory.Factory):
    """Factory for UserCreate schema (for registration)"""

    class Meta:
        model = UserCreate

    first_name = factory.LazyFunction(lambda: faker.first_name())
    last_name = factory.LazyFunction(lambda: faker.last_name())
    email = factory.LazyFunction(lambda: faker.email())
    password = factory.LazyFunction(lambda: faker.password(length=12))


class InverterAddFactory(factory.Factory):
    """Factory for InverterAdd schema (for creating inverters)"""

    class Meta:
        model = InverterAdd

    name = factory.LazyFunction(lambda: f"Inverter {faker.random_int(1, 9999)}")
    serial = factory.LazyFunction(lambda: faker.uuid4())


class InverterAddMetadataFactory(factory.Factory):
    """Factory for InverterAddMetadata schema"""

    class Meta:
        model = InverterAddMetadata

    rated_power = factory.LazyFunction(lambda: faker.random_int(3000, 15000))
    number_of_mppts = factory.LazyFunction(lambda: faker.random_int(1, 4))


# Database model factories (for when objects need to be in the DB)
class UserDBFactory(factory.Factory):
    """Factory for User database model"""

    class Meta:
        model = dict  # We'll create dicts that can be used to create User objects

    first_name = factory.LazyFunction(lambda: faker.first_name())
    last_name = factory.LazyFunction(lambda: faker.last_name())
    email = factory.LazyFunction(lambda: faker.email())
    hashed_password = factory.LazyFunction(lambda: "$2b$12$KIXxN7qXvZ5Wn3Z5Z5Z5ZO")  # Dummy hash
    is_active = True
    is_superuser = False
    is_verified = True
    influx_url = "http://localhost:8086"
    influx_org_id = factory.LazyFunction(lambda: faker.uuid4())
    influx_token = factory.LazyFunction(lambda: faker.uuid4())


class InverterDBFactory(factory.Factory):
    """Factory for Inverter database model"""

    class Meta:
        model = dict  # We'll create dicts that can be used to create Inverter objects

    name = factory.LazyFunction(lambda: f"Inverter {faker.random_int(1, 9999)}")
    serial_logger = factory.LazyFunction(lambda: faker.uuid4())
    sw_version = factory.LazyFunction(lambda: f"v{faker.random_int(1, 3)}.{faker.random_int(0, 9)}")
    influx_bucked_id = factory.LazyFunction(lambda: faker.uuid4())
    rated_power = factory.LazyFunction(lambda: faker.random_int(3000, 15000))
    number_of_mppts = factory.LazyFunction(lambda: faker.random_int(1, 4))
