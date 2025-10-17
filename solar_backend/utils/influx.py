import structlog
from influxdb_client import (
    Bucket,
    InfluxDBClient,
    OrganizationsService,
    AddResourceMemberRequestBody,
    User,
    Organization,
    Authorization,
)
from influxdb_client.domain.permission import Permission
from influxdb_client.domain.permission_resource import PermissionResource
from solar_backend.config import settings
# from solar_backend.users import User as UserBackend  #TODO: cycle import

from influxdb_client.client.exceptions import InfluxDBError

logger = structlog.get_logger()


class NoValuesException(Exception):
    """Raised when InfluxDB query returns no data."""

    pass


class InfluxConnectionError(Exception):
    """Raised when InfluxDB is not reachable or connection fails."""

    pass


class InfluxUnavailableError(Exception):
    """Raised when InfluxDB service is temporarily unavailable."""

    pass


class InfluxManagement:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.token = settings.INFLUX_OPERATOR_TOKEN
        self.connected = False
        self._client: InfluxDBClient | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning("Error closing InfluxDB client", error=str(e))
        return False  # Don't suppress exceptions

    def _test_connection(self) -> bool:
        """
        Test if InfluxDB is reachable and responding.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            health = self._client.health()
            is_healthy = health.status == "pass"
            if not is_healthy:
                logger.warning(
                    "InfluxDB health check failed",
                    status=health.status,
                    message=health.message,
                )
            return is_healthy
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection test failed", error=str(e), url=self.db_url
            )
            return False
        except Exception as e:
            logger.error("InfluxDB health check error", error=str(e), url=self.db_url)
            return False

    def connect(
        self,
        org: str = None,
        username: str = None,
        password: str = None,
        token: str = None,
    ):
        """
        Connect to InfluxDB and verify the connection is working.

        Args:
            org: Organization name
            username: Username for authentication (optional)
            password: Password for authentication (optional)
            token: Token for authentication (optional)

        Raises:
            InfluxConnectionError: If connection to InfluxDB fails
        """
        try:
            if not username:
                self._client = InfluxDBClient(
                    url=self.db_url,
                    token=token if token else self.token,
                    org=org,
                    enable_gzip=False
                )
            else:
                self._client = InfluxDBClient(
                    url=self.db_url,
                    username=username,
                    password=password,
                    org=org,
                    enable_gzip=False
                )

            # Test the connection
            if not self._test_connection():
                raise InfluxConnectionError(
                    f"InfluxDB at {self.db_url} is not healthy or not reachable"
                )

            self.connected = True
            logger.info(
                f"successfully connected to {self.db_url}", org=org, url=self.db_url
            )

        except InfluxConnectionError:
            # Re-raise our custom exception
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection failed", error=str(e), url=self.db_url, org=org
            )
            raise InfluxConnectionError(
                f"Cannot connect to InfluxDB at {self.db_url}: {str(e)}"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error connecting to InfluxDB",
                error=str(e),
                url=self.db_url,
                org=org,
            )
            raise InfluxConnectionError(
                f"Failed to connect to InfluxDB: {str(e)}"
            ) from e

    def create_organization(self, name) -> Organization:
        """
        Create an InfluxDB organization.

        Args:
            name: Organization name

        Returns:
            Created Organization object

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        try:
            org_api = self._client.organizations_api()
            return org_api.create_organization(name=name)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in create_organization",
                error=str(e),
                org_name=name,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to create organization: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in create_organization",
                    error=str(e),
                    org_name=name,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def create_influx_user_and_org(
        self, username: str, password: str
    ) -> (User, Organization, str):
        """
        Create InfluxDB user and organization.

        Args:
            username: Username for the new user
            password: Password for the new user

        Returns:
            Tuple of (User, Organization, token)

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        # TODO: check that user don't exist

        try:
            user_api = self._client.users_api()
            user = user_api.create_user(username)
            logger.info("User for influx created", user=username)

            user_api.update_password(user, password)
            logger.info("Password was updated", user=username)

            org = self.create_organization(username)
            logger.info(f"Organization {org.name} created", org=org)

            organization_service = OrganizationsService(
                api_client=self._client.api_client
            )

            member_request = AddResourceMemberRequestBody(id=user.id)
            member = organization_service.post_orgs_id_owners(
                org_id=org.id, add_resource_member_request_body=member_request
            )
            logger.info(f"user added to organisation", member=member)

            authorization = self.create_authorization(org.id)

            return (user, org, authorization.token)

        except InfluxConnectionError:
            # Re-raise connection errors
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in create_influx_user_and_org",
                error=str(e),
                username=username,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to create user: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in create_influx_user_and_org",
                    error=str(e),
                    username=username,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def create_bucket(
        self, bucket_name: str, org_id, retention_seconds: int = 63072000
    ) -> Bucket:
        """
        Create a bucket with specified retention policy.

        Args:
            bucket_name: Name of the bucket
            org_id: Organization ID
            retention_seconds: Data retention period in seconds (default: 63072000 = 2 years)

        Returns:
            Created Bucket object

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        try:
            bucket_api = self._client.buckets_api()
            bucket = bucket_api.create_bucket(
                bucket_name=bucket_name,
                org_id=org_id,
                retention_rules=[{"type": "expire", "everySeconds": retention_seconds}],
            )
            logger.info(
                "Bucket created with retention policy",
                bucket=bucket.name,
                retention_days=retention_seconds // 86400,
            )
            return bucket
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in create_bucket",
                error=str(e),
                bucket_name=bucket_name,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to create bucket: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in create_bucket",
                    error=str(e),
                    bucket_name=bucket_name,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def update_bucket_retention(
        self, bucket_id: str, retention_seconds: int = 63072000
    ):
        """
        Update retention policy for an existing bucket.

        Args:
            bucket_id: Bucket ID to update
            retention_seconds: Data retention period in seconds (default: 63072000 = 2 years)

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            ValueError: If bucket not found
        """
        try:
            bucket_api = self._client.buckets_api()
            bucket = bucket_api.find_bucket_by_id(bucket_id)
            if bucket:
                bucket.retention_rules = [
                    {"type": "expire", "everySeconds": retention_seconds}
                ]
                bucket_api.update_bucket(bucket)
                logger.info(
                    "Bucket retention policy updated",
                    bucket_id=bucket_id,
                    bucket_name=bucket.name,
                    retention_days=retention_seconds // 86400,
                )
            else:
                logger.warning(
                    "Bucket not found for retention update", bucket_id=bucket_id
                )
                raise ValueError(f"Bucket {bucket_id} not found")
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in update_bucket_retention",
                error=str(e),
                bucket_id=bucket_id,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to update bucket: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in update_bucket_retention",
                    error=str(e),
                    bucket_id=bucket_id,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def delete_bucket(self, bucket_id: str):
        """
        Delete an InfluxDB bucket.

        Args:
            bucket_id: ID of bucket to delete

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        try:
            bucket_api = self._client.buckets_api()
            bucket_api.delete_bucket(bucket_id)
            logger.info(f"Bucket deleted", bucket_id=bucket_id)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in delete_bucket",
                error=str(e),
                bucket_id=bucket_id,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to delete bucket: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in delete_bucket",
                    error=str(e),
                    bucket_id=bucket_id,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def update_user_password(self, username: str, new_password: str):
        """
        Update password for an InfluxDB user.

        Args:
            username: Username to update
            new_password: New password

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            ValueError: If user not found
        """
        try:
            user_api = self._client.users_api()
            # Find user by name (email)
            users = user_api.find_users()
            user = next((u for u in users if u.name == username), None)
            if user:
                user_api.update_password(user, new_password)
                logger.info("InfluxDB password updated", username=username)
            else:
                logger.warning(
                    "InfluxDB user not found for password update", username=username
                )
                raise ValueError(f"InfluxDB user {username} not found")
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in update_user_password",
                error=str(e),
                username=username,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to update password: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in update_user_password",
                    error=str(e),
                    username=username,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def delete_organization(self, org_id: str):
        """
        Delete an InfluxDB organization.

        Args:
            org_id: Organization ID to delete

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        try:
            org_api = self._client.organizations_api()
            org_api.delete_organization(org_id)
            logger.info("InfluxDB organization deleted", org_id=org_id)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in delete_organization",
                error=str(e),
                org_id=org_id,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to delete organization: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in delete_organization",
                    error=str(e),
                    org_id=org_id,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def set_default_permission(self):
        auth_api = self._client.authorizations_api()
        resource = PermissionResource(org_id=org_id, type="buckets", id=bucket_id)
        read_buckets = Permission(action="read", resource=resource)
        write_buckets = Permission(
            action="write", resource=PermissionResource(type="buckets", id=bucket.id)
        )
        auth_api.create_authorization(
            org_id=ORG, permissions=[read_buckets, write_buckets]
        )

    def create_authorization(self, org_id: str) -> Authorization:
        """
        Create authorization token for an organization.

        Args:
            org_id: Organization ID

        Returns:
            Created Authorization object

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
        """
        try:
            authorization = self._client.authorizations_api()
            resource = PermissionResource(org_id=org_id, type="buckets")
            read_bucket = Permission(action="read", resource=resource)
            write_bucket = Permission(action="write", resource=resource)
            permissions = [read_bucket, write_bucket]
            authorization = authorization.create_authorization(
                org_id=org_id, permissions=permissions
            )
            logger.info("authorization created", authorization=authorization)
            return authorization
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in create_authorization",
                error=str(e),
                org_id=org_id,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB to create authorization: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in create_authorization",
                    error=str(e),
                    org_id=org_id,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            raise  # Re-raise other InfluxDB errors

    def get_latest_values(self, user, bucket: str) -> dict:
        """
        Get latest power values from InfluxDB.

        Args:
            user: User object with email
            bucket: Bucket name to query

        Returns:
            Tuple of (timestamp, power_value)

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            NoValuesException: If no data found in query
        """
        try:
            query_api = self._client.query_api()
            tables = query_api.query(
                f"""from(bucket:"{bucket}")
                                 |> range(start: -24h)
                                 |> filter(fn: (r) => r["_measurement"] == "grid")
                                 |> filter(fn: (r) => r["_field"] == "total_output_power")
                                 |> timedMovingAverage(every: 5m, period: 10m)
                                 |> last()""",
                org=user.email,
            )
            last = tables[0].records[0]
            return (last.get_time(), int(last.get_value()))
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in get_latest_values",
                error=str(e),
                bucket=bucket,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB for query: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in get_latest_values",
                    error=str(e),
                    bucket=bucket,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            # For query errors (unauthorized, not found, etc), raise NoValuesException
            logger.error("No values in InfluxDB", error=str(e), bucket=bucket)
            raise NoValuesException(f"InfluxDB query failed: {str(e)}")
        except (IndexError, KeyError) as e:
            logger.error("No values in InfluxDB", error=str(e), bucket=bucket)
            raise NoValuesException(f"InfluxDB query returned no data: {str(e)}")

    def get_power_timeseries(
        self, user, bucket: str, time_range: str = "1h"
    ) -> list[dict]:
        """
        Get time-series power data for dashboard graphs.

        Args:
            user: User object with email for org lookup
            bucket: Bucket name to query
            time_range: Time range string (1h, 6h, 24h, 7d, 30d)

        Returns:
            List of dicts with timestamp and power values

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            NoValuesException: If no data found in query
        """
        # Map time range to aggregation window
        aggregation_map = {
            "1h": "1m",
            "6h": "5m",
            "24h": "10m",
            "7d": "1h",
            "30d": "4h",
        }

        window = aggregation_map.get(time_range, "5m")

        try:
            query_api = self._client.query_api()

            query = f"""
                from(bucket:"{bucket}")
                |> range(start: -{time_range})
                |> filter(fn: (r) => r["_measurement"] == "grid")
                |> filter(fn: (r) => r["_field"] == "total_output_power")
                |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
                |> yield(name: "mean")
            """

            tables = query_api.query(query, org=user.email)

            data_points = []
            for table in tables:
                for record in table.records:
                    data_points.append(
                        {
                            "time": record.get_time().isoformat(),
                            "power": int(record.get_value())
                            if record.get_value()
                            else 0,
                        }
                    )

            logger.info(
                "Retrieved time-series data",
                bucket=bucket,
                time_range=time_range,
                data_points=len(data_points),
            )

            return data_points

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in get_power_timeseries",
                error=str(e),
                bucket=bucket,
                time_range=time_range,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB for query: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in get_power_timeseries",
                    error=str(e),
                    bucket=bucket,
                    time_range=time_range,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            # For query errors (unauthorized, not found, etc), raise NoValuesException
            logger.error(
                "Failed to retrieve time-series data",
                error=str(e),
                bucket=bucket,
                time_range=time_range,
            )
            raise NoValuesException(f"InfluxDB time-series query failed: {str(e)}")
        except (IndexError, KeyError) as e:
            logger.error(
                "Failed to retrieve time-series data",
                error=str(e),
                bucket=bucket,
                time_range=time_range,
            )
            raise NoValuesException(f"InfluxDB query returned no data: {str(e)}")

    def get_today_energy_production(self, user, bucket: str) -> float:
        """
        Get total energy production for today (from midnight to now).

        Args:
            user: User object with email for org lookup
            bucket: Bucket name to query

        Returns:
            Total energy produced today in kWh

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            NoValuesException: If no data found in query
        """
        try:
            query_api = self._client.query_api()

            # Query from start of today (midnight server local time) to now
            # Use integral() to calculate energy (area under power curve)
            # integral() returns Watt-seconds, convert to kWh
            query = f"""
                from(bucket:"{bucket}")
                |> range(start: today())
                |> filter(fn: (r) => r["_measurement"] == "grid")
                |> filter(fn: (r) => r["_field"] == "total_output_power")
                |> integral(unit: 1s)
                |> map(fn: (r) => ({{ r with _value: r._value / 3600000.0 }}))
                |> last()
            """

            tables = query_api.query(query, org=user.email)

            if tables and len(tables) > 0 and len(tables[0].records) > 0:
                energy_kwh = tables[0].records[0].get_value()
                logger.info(
                    "Retrieved today's energy production",
                    bucket=bucket,
                    energy_kwh=energy_kwh,
                )
                return float(energy_kwh) if energy_kwh else 0.0
            else:
                logger.info(
                    "No energy data for today",
                    bucket=bucket,
                )
                return 0.0

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in get_today_energy_production",
                error=str(e),
                bucket=bucket,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB for query: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in get_today_energy_production",
                    error=str(e),
                    bucket=bucket,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            # For query errors, log but return 0 instead of raising
            logger.warning(
                "No energy data for today",
                error=str(e),
                bucket=bucket,
            )
            return 0.0
        except Exception as e:
            logger.warning(
                "Failed to retrieve today's energy production",
                error=str(e),
                bucket=bucket,
            )
            return 0.0

    def get_last_hour_average(self, user, bucket: str) -> int:
        """
        Get average power for the last hour.

        Args:
            user: User object with email for org lookup
            bucket: Bucket name to query

        Returns:
            Average power in Watts for the last hour

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            NoValuesException: If no data found in query
        """
        try:
            query_api = self._client.query_api()

            # Query last hour and calculate mean
            query = f"""
                from(bucket:"{bucket}")
                |> range(start: -1h)
                |> filter(fn: (r) => r["_measurement"] == "grid")
                |> filter(fn: (r) => r["_field"] == "total_output_power")
                |> mean()
            """

            tables = query_api.query(query, org=user.email)

            if tables and len(tables) > 0 and len(tables[0].records) > 0:
                avg_power = tables[0].records[0].get_value()
                logger.info(
                    "Retrieved last hour average power",
                    bucket=bucket,
                    avg_power=avg_power,
                )
                return int(avg_power) if avg_power else 0
            else:
                logger.info(
                    "No data for last hour average",
                    bucket=bucket,
                )
                return 0

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in get_last_hour_average",
                error=str(e),
                bucket=bucket,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB for query: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in get_last_hour_average",
                    error=str(e),
                    bucket=bucket,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            # For query errors, log but return 0 instead of raising
            logger.warning(
                "No data for last hour average",
                error=str(e),
                bucket=bucket,
            )
            return 0
        except Exception as e:
            logger.warning(
                "Failed to retrieve last hour average",
                error=str(e),
                bucket=bucket,
            )
            return 0

    def get_today_maximum_power(self, user, bucket: str) -> int:
        """
        Get maximum power for today (from midnight to now).

        Args:
            user: User object with email for org lookup
            bucket: Bucket name to query

        Returns:
            Maximum power in Watts for today

        Raises:
            InfluxConnectionError: If InfluxDB is not reachable
            NoValuesException: If no data found in query
        """
        try:
            query_api = self._client.query_api()

            # Query from start of today (midnight server local time) to now
            # Get maximum value
            query = f"""
                from(bucket:"{bucket}")
                |> range(start: today())
                |> filter(fn: (r) => r["_measurement"] == "grid")
                |> filter(fn: (r) => r["_field"] == "total_output_power")
                |> max()
            """

            tables = query_api.query(query, org=user.email)

            if tables and len(tables) > 0 and len(tables[0].records) > 0:
                max_power = tables[0].records[0].get_value()
                logger.info(
                    "Retrieved today's maximum power",
                    bucket=bucket,
                    max_power=max_power,
                )
                return int(max_power) if max_power else 0
            else:
                logger.info(
                    "No data for today's maximum power",
                    bucket=bucket,
                )
                return 0

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "InfluxDB connection error in get_today_maximum_power",
                error=str(e),
                bucket=bucket,
            )
            raise InfluxConnectionError(
                f"Cannot reach InfluxDB for query: {str(e)}"
            ) from e
        except InfluxDBError as e:
            if (
                "connection" in str(e).lower()
                or "refused" in str(e).lower()
                or "unavailable" in str(e).lower()
            ):
                logger.error(
                    "InfluxDB unavailable in get_today_maximum_power",
                    error=str(e),
                    bucket=bucket,
                )
                raise InfluxConnectionError(
                    f"InfluxDB service unavailable: {str(e)}"
                ) from e
            # For query errors, log but return 0 instead of raising
            logger.warning(
                "No data for today's maximum power",
                error=str(e),
                bucket=bucket,
            )
            return 0
        except Exception as e:
            logger.warning(
                "Failed to retrieve today's maximum power",
                error=str(e),
                bucket=bucket,
            )
            return 0
