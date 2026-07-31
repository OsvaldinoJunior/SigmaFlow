"""
Locust Load Tests for SigmaFlow
================================
Simulates multi-tenant, multi-project usage patterns.
Run with: locust -f load-tests/locustfile.py --host=http://localhost:8000/api/v1
"""

import random
import time
from locust import HttpUser, task, between, events
from locust.exception import StopUser


# Test configuration
TENANTS = [
    {"code": "tenant-acme", "name": "ACME Corp", "user_count": 10},
    {"code": "tenant-globex", "name": "Globex Inc", "user_count": 10},
    {"code": "tenant-initech", "name": "Initech LLC", "user_count": 10},
    {"code": "tenant-umbrella", "name": "Umbrella Corp", "user_count": 10},
    {"code": "tenant-wayne", "name": "Wayne Enterprises", "user_count": 10},
]

# Pre-generated test users (in real scenario, these would be created in setup)
TEST_USERS = []
for tenant in TENANTS:
    for i in range(1, tenant["user_count"] + 1):
        TEST_USERS.append({
            "email": f"user{i}@{tenant['code']}.com",
            "password": "TestPass123!",
            "tenant_code": tenant["code"],
        })


class SigmaFlowUser(HttpUser):
    """
    Simulates a SigmaFlow user performing typical DMAIC workflow operations.
    """
    wait_time = between(1, 3)  # Think time between tasks
    
    def on_start(self):
        """Login and get authentication token."""
        self.token = None
        self.current_user = random.choice(TEST_USERS)
        self.project_id = None
        self.project_code = None
        self.dataset_id = None
        self.run_id = None
        
        self.login()
    
    def login(self):
        """Authenticate and store token."""
        response = self.client.post(
            "/auth/login",
            data={
                "username": self.current_user["email"],
                "password": self.current_user["password"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="/auth/login"
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                self.token = data.get("access_token")
                self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            except:
                self.environment.events.request.fire(
                    request_type="POST",
                    name="/auth/login",
                    response_time=0,
                    response_length=0,
                    exception=Exception("Failed to parse login response"),
                )
        else:
            self.environment.events.request.fire(
                request_type="POST",
                name="/auth/login",
                response_time=0,
                response_length=0,
                exception=Exception(f"Login failed: {response.status_code}"),
            )
            # Stop user if login fails
            raise StopUser()
    
    def auth_headers(self):
        """Return headers with authentication."""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}
    
    @task(10)
    def get_projects(self):
        """List projects - frequent read operation."""
        with self.client.get(
            "/projects",
            headers=self.auth_headers(),
            name="/projects (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list projects: {response.status_code}")
    
    @task(8)
    def get_plants(self):
        """List plants - read operation."""
        with self.client.get(
            "/plants",
            headers=self.auth_headers(),
            name="/plants (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list plants: {response.status_code}")
    
    @task(5)
    def get_tenants(self):
        """List tenants - read operation."""
        with self.client.get(
            "/tenants",
            headers=self.auth_headers(),
            name="/tenants (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list tenants: {response.status_code}")
    
    @task(3)
    def get_current_user(self):
        """Get current user profile."""
        with self.client.get(
            "/auth/me",
            headers=self.auth_headers(),
            name="/auth/me",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to get user: {response.status_code}")
    
    @task(2)
    def create_project(self):
        """Create a new project - write operation."""
        if not self.token:
            return
            
        project_code = f"LOAD-{self.current_user['tenant_code']}-{int(time.time())}-{random.randint(1000, 9999)}"
        
        with self.client.post(
            "/projects",
            json={
                "code": project_code,
                "name": f"Load Test Project {project_code}",
                "plant_id": "plant-1",
                "owner_id": "user-1",
                "description": "Project created during load test",
                "problem_statement": "High variance in process output",
                "goal_statement": "Reduce variance by 30%",
            },
            headers=self.auth_headers(),
            name="/projects (create)",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                try:
                    data = response.json()
                    self.project_id = data.get("id")
                    self.project_code = data.get("code")
                except:
                    response.failure("Failed to parse project creation response")
            else:
                response.failure(f"Failed to create project: {response.status_code}")
    
    @task(2)
    def create_dataset(self):
        """Create a dataset for the project."""
        if not self.token or not self.project_id:
            return
            
        with self.client.post(
            f"/projects/{self.project_id}/datasets",
            json={
                "name": f"dataset-{int(time.time())}",
                "description": "Dataset created during load test",
                "source_type": "csv",
                "source_config": {"delimiter": ","},
            },
            headers=self.auth_headers(),
            name="/projects/{id}/datasets (create)",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                try:
                    data = response.json()
                    self.dataset_id = data.get("id")
                except:
                    response.failure("Failed to parse dataset creation response")
            else:
                response.failure(f"Failed to create dataset: {response.status_code}")
    
    @task(1)
    def trigger_pipeline_run(self):
        """Trigger a DMAIC pipeline run."""
        if not self.token or not self.project_code:
            return
            
        with self.client.post(
            "/runs",
            json={
                "project_code": self.project_code,
                "config": {"phases": ["define", "measure", "analyze"]},
            },
            headers=self.auth_headers(),
            name="/runs (create)",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                try:
                    data = response.json()
                    self.run_id = data.get("id")
                except:
                    response.failure("Failed to parse run creation response")
            else:
                response.failure(f"Failed to trigger pipeline: {response.status_code}")
    
    @task(3)
    def get_run_insights(self):
        """Get insights for a run."""
        if not self.token or not self.run_id:
            return
            
        with self.client.get(
            f"/runs/{self.run_id}/insights",
            headers=self.auth_headers(),
            name="/runs/{id}/insights",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to get insights: {response.status_code}")
    
    @task(2)
    def list_runs(self):
        """List runs for the project."""
        if not self.token or not self.project_id:
            return
            
        with self.client.get(
            f"/projects/{self.project_id}/runs",
            headers=self.auth_headers(),
            name="/projects/{id}/runs (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list runs: {response.status_code}")
    
    @task(1)
    def create_action_item(self):
        """Create an action item."""
        if not self.token or not self.project_id:
            return
            
        with self.client.post(
            "/action-items",
            json={
                "project_id": self.project_id,
                "title": f"Action Item {int(time.time())}",
                "description": "Action item created during load test",
                "category": "improvement",
                "priority": random.randint(1, 5),
            },
            headers=self.auth_headers(),
            name="/action-items (create)",
            catch_response=True
        ) as response:
            if response.status_code != 201:
                response.failure(f"Failed to create action item: {response.status_code}")
    
    @task(2)
    def list_action_items(self):
        """List action items for the project."""
        if not self.token or not self.project_id:
            return
            
        with self.client.get(
            f"/projects/{self.project_id}/action-items",
            headers=self.auth_headers(),
            name="/projects/{id}/action-items (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list action items: {response.status_code}")
    
    @task(1)
    def get_scheduled_runs(self):
        """Get scheduled runs."""
        if not self.token:
            return
            
        with self.client.get(
            "/scheduled-runs",
            headers=self.auth_headers(),
            name="/scheduled-runs (list)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to list scheduled runs: {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulates an admin user performing administrative operations.
    """
    wait_time = between(5, 10)
    weight = 1  # Fewer admin users
    
    def on_start(self):
        self.token = None
        # Use a superuser account
        response = self.client.post(
            "/auth/login",
            data={
                "username": "admin@sigmaflow.com",
                "password": "AdminPass123!",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="/auth/login (admin)"
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                self.token = data.get("access_token")
                self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            except:
                raise StopUser()
        else:
            raise StopUser()
    
    @task(3)
    def list_all_tenants(self):
        """List all tenants (admin only)."""
        with self.client.get(
            "/tenants",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/tenants (admin)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Admin failed to list tenants: {response.status_code}")
    
    @task(2)
    def create_tenant(self):
        """Create a new tenant."""
        tenant_code = f"tenant-load-{int(time.time())}"
        with self.client.post(
            "/tenants",
            json={
                "code": tenant_code,
                "name": f"Load Test Tenant {tenant_code}",
                "description": "Tenant created during load test",
            },
            headers={"Authorization": f"Bearer {self.token}"},
            name="/tenants (create)",
            catch_response=True
        ) as response:
            if response.status_code != 201:
                response.failure(f"Failed to create tenant: {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Health check endpoint."""
        with self.client.get(
            "/health",
            name="/health (admin)",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("SigmaFlow Load Test Started")
    print(f"Target: {environment.host}")
    print(f"Test Users: {len(TEST_USERS)} across {len(TENANTS)} tenants")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=" * 60)
    print("SigmaFlow Load Test Completed")
    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    if exception:
        print(f"ERROR: {request_type} {name} - {exception}")