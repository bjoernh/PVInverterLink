import structlog
from influxdb_client import InfluxDBClient, OrganizationsService, AddResourceMemberRequestBody
from influxdb_client.domain.permission import Permission
from influxdb_client.domain.permission_resource import PermissionResource

#TODO: move to config
# THIS must be an operator TOKEN!
AUTH_TOKEN = "RT0HJE7H2MozT4HQCcq46xxSryV2Y1Nr1vUQZlU1jzplCFnlOayWQZV_IYZ-WKNddhXC3skguvxSkWDoH2RfvA=="


logger = structlog.get_logger()


class InfluxManagement:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.token = AUTH_TOKEN
        self.connected = False
    
    def connect(self, org: str = None, username: str = None, password: str = None):
        if not username:
            self._client = InfluxDBClient(url=self.db_url, token=self.token, org=org)
        else:
            self._client = InfluxDBClient(url=self.db_url, username=username, password=password, org=org)
        self.connect = True
        logger.info(f"successful connected to {self.db_url}", org=org, url=self.db_url)
    
    def create_organization(self, name):
        org_api = self._client.organizations_api()
        return org_api.create_organization(name=name)
    
    def create_influx_user_and_org(self, username: str, password: str):
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
        
        return (user, org)

    def create_bucket(self, bucket_name: str, org_id):
        bucket_api = self._client.buckets_api()
        bucket = bucket_api.create_bucket(bucket_name=bucket_name, org_id=org_id)  #TODO: decide how long data will be kept in the database (in seconds)
        logger.info("Bucket created", bucket=bucket)
        return bucket
    
    def set_default_permission(self):
        auth_api = self._client.authorizations_api()
        per = Permission(action="write", resource=PermissionResource(type="buckets", id=bucket.id, ))
        auth_api.create_authorization(org_id=ORG, permissions=per)


inflx = InfluxManagement(db_url="http://localhost:8086")
inflx.connect(org='wtf')


if __name__ == "__main__":
    user, org = inflx.create_influx_user_and_org("tester16", "test1234")
    bucket = inflx.create_bucket("test_bucket16", org_id=org)
