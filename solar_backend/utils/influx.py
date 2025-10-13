import structlog
from influxdb_client import Bucket, InfluxDBClient, OrganizationsService, AddResourceMemberRequestBody, User, Organization, Authorization
from influxdb_client.domain.permission import Permission
from influxdb_client.domain.permission_resource import PermissionResource
from solar_backend.config import settings
#from solar_backend.users import User as UserBackend  #TODO: cycle import

from influxdb_client.client.exceptions import InfluxDBError

logger = structlog.get_logger()


class NoValuesException(Exception):
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
            self._client.close()
    
    def connect(self, org: str = None, username: str = None, password: str = None, token: str = None):
        if not username:
            self._client = InfluxDBClient(url=self.db_url, token=token if token else self.token, org=org)
        else:
            self._client = InfluxDBClient(url=self.db_url, username=username, password=password, org=org)
        self.connected = True
        logger.info(f"successful connected to {self.db_url}", org=org, url=self.db_url)

    
    def create_organization(self, name) -> Organization:
        org_api = self._client.organizations_api()
        return org_api.create_organization(name=name)
    
    def create_influx_user_and_org(self, username: str, password: str) -> (User, Organization, str):
        #TODO: check that user don't exist
        
        user_api = self._client.users_api()
        user = user_api.create_user(username)
        logger.info("User for influx created", user=username)
        
        user_api.update_password(user, password)
        logger.info("Password was updated", user=username)
        
        org = self.create_organization(username)
        logger.info(f"Organization {org.name} created", org=org)
        
        organization_service = OrganizationsService(api_client=self._client.api_client)

        member_request = AddResourceMemberRequestBody(id=user.id)
        member = organization_service.post_orgs_id_owners(org_id=org.id, add_resource_member_request_body=member_request)
        logger.info(f"user added to organisation", member=member)

        authorization = self.create_authorization(org.id)
        
        return (user, org, authorization.token)

    def create_bucket(self, bucket_name: str, org_id) -> Bucket:
        bucket_api = self._client.buckets_api()
        bucket = bucket_api.create_bucket(bucket_name=bucket_name, org_id=org_id)  #TODO: decide how long data will be kept in the database (in seconds)
        logger.info("Bucket created", bucket=bucket)
        return bucket
    
    def delete_bucket(self, bucket_id: str):
        bucket_api = self._client.buckets_api()
        bucket_api.delete_bucket(bucket_id)
        logger.info(f"Bucket deleted", bucket_id=bucket_id)

    def update_user_password(self, username: str, new_password: str):
        """Update password for an InfluxDB user."""
        user_api = self._client.users_api()
        # Find user by name (email)
        users = user_api.find_users()
        user = next((u for u in users if u.name == username), None)
        if user:
            user_api.update_password(user, new_password)
            logger.info("InfluxDB password updated", username=username)
        else:
            logger.warning("InfluxDB user not found for password update", username=username)
            raise ValueError(f"InfluxDB user {username} not found")

    def delete_organization(self, org_id: str):
        """Delete an InfluxDB organization."""
        org_api = self._client.organizations_api()
        org_api.delete_organization(org_id)
        logger.info("InfluxDB organization deleted", org_id=org_id)
    
    def set_default_permission(self):
        auth_api = self._client.authorizations_api()
        resource = PermissionResource(org_id=org_id, type="buckets", id=bucket_id)
        read_buckets = Permission(action="read", resource=resource)
        write_buckets = Permission(action="write", resource=PermissionResource(type="buckets", id=bucket.id))
        auth_api.create_authorization(org_id=ORG, permissions=[read_buckets, write_buckets])

    def create_authorization(self, org_id: str) -> Authorization:
        authorization = self._client.authorizations_api()
        resource = PermissionResource(org_id=org_id, type="buckets")
        read_bucket = Permission(action="read", resource=resource)
        write_bucket = Permission(action="write", resource=resource)
        permissions = [read_bucket, write_bucket]
        authorization = authorization.create_authorization(org_id=org_id, permissions=permissions)
        logger.info("authorization created", authorization=authorization)
        return authorization
    
    def get_latest_values(self, user, bucket: str) -> dict:
        query_api = self._client.query_api()
        
        try:
            tables = query_api.query(f"""from(bucket:"{bucket}") 
                                 |> range(start: -24h)
                                 |> filter(fn: (r) => r["_measurement"] == "grid")
                                 |> filter(fn: (r) => r["_field"] == "total_output_power")
                                 |> timedMovingAverage(every: 5m, period: 10m)
                                 |> last()""", org=user.email)
            last = tables[0].records[0]
            return ( last.get_time(), int(last.get_value()) )
        except (InfluxDBError, IndexError, KeyError) as e:
            logger.error("No values in InfluxDB", error=str(e), bucket=bucket)
            raise NoValuesException(f"InfluxDB query failed: {str(e)}")



