import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

// Custom metrics
const loginRate = new Rate('login_success_rate');
const createProjectRate = new Rate('create_project_success_rate');
const createDatasetRate = new Rate('create_dataset_success_rate');
const runPipelineRate = new Rate('run_pipeline_success_rate');
const getInsightsRate = new Rate('get_insights_success_rate');
const responseTime = new Trend('api_response_time');
const errorCount = new Counter('api_errors');

// Test configuration
export const options = {
  scenarios: {
    // Ramp-up phase - simulate users logging in
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },   // Ramp up to 10 users
        { duration: '1m', target: 10 },    // Stay at 10 users
        { duration: '30s', target: 25 },   // Ramp up to 25 users
        { duration: '2m', target: 25 },    // Stay at 25 users
        { duration: '30s', target: 50 },   // Ramp up to 50 users
        { duration: '3m', target: 50 },    // Sustained load at 50 users
        { duration: '30s', target: 0 },    // Ramp down
      ],
      gracefulRampDown: '10s',
    },
    // Steady state - constant load
    steady_state: {
      executor: 'constant-vus',
      vus: 20,
      duration: '5m',
      startTime: '30s', // Start after ramp-up begins
    },
    // Spike test - sudden burst
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },  // Sudden spike
        { duration: '30s', target: 100 },  // Hold spike
        { duration: '10s', target: 0 },    // Drop
      ],
      startTime: '6m', // Run after main tests
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<2000', 'p(99)<5000'],
    'http_req_failed': ['rate<0.05'],
    'login_success_rate': ['rate>0.95'],
    'create_project_success_rate': ['rate>0.90'],
    'create_dataset_success_rate': ['rate>0.90'],
    'run_pipeline_success_rate': ['rate>0.85'],
    'get_insights_success_rate': ['rate>0.90'],
  },
};

// Base URL for API
const BASE_URL = __ENV.API_URL || 'http://localhost:8000/api/v1';

// Test users per tenant (simulate multi-tenancy)
const TENANTS = [
  { code: 'tenant-acme', name: 'ACME Corp', users: 5 },
  { code: 'tenant-globex', name: 'Globex Inc', users: 5 },
  { code: 'tenant-initech', name: 'Initech LLC', users: 5 },
  { code: 'tenant-umbrella', name: 'Umbrella Corp', users: 5 },
  { code: 'tenant-wayne', name: 'Wayne Enterprises', users: 5 },
];

// Pre-create test credentials (in real scenario, these would be created via setup)
const testUsers = new SharedArray('test-users', function() {
  const users = [];
  for (const tenant of TENANTS) {
    for (let i = 1; i <= tenant.users; i++) {
      users.push({
        email: `user${i}@${tenant.code}.com`,
        password: 'TestPass123!',
        tenantCode: tenant.code,
      });
    }
  }
  return users;
});

// Helper function to make authenticated requests
function authenticatedRequest(method, url, token, body = null, params = {}) {
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    ...params.headers,
  };
  
  const startTime = new Date();
  let response;
  
  if (method === 'GET') {
    response = http.get(url, { headers, ...params });
  } else if (method === 'POST') {
    response = http.post(url, JSON.stringify(body), { headers, ...params });
  } else if (method === 'PATCH') {
    response = http.patch(url, JSON.stringify(body), { headers, ...params });
  } else if (method === 'DELETE') {
    response = http.del(url, null, { headers, ...params });
  }
  
  responseTime.add(new Date() - startTime);
  
  if (response.status >= 400) {
    errorCount.add(1);
  }
  
  return response;
}

// Login and get token
function login(user) {
  const response = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: user.email,
    password: user.password,
  }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  
  const success = check(response, {
    'login successful': (r) => r.status === 200,
    'has access token': (r) => {
      try {
        const data = r.json();
        return data.access_token !== undefined;
      } catch {
        return false;
      }
    },
  });
  
  loginRate.add(success);
  
  if (success) {
    try {
      return response.json().access_token;
    } catch {
      return null;
    }
  }
  return null;
}

// Create a project
function createProject(token, tenantCode) {
  const projectCode = `PROJ-${tenantCode}-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
  const response = authenticatedRequest('POST', `${BASE_URL}/projects`, token, {
    code: projectCode,
    name: `Test Project ${projectCode}`,
    plant_id: 'plant-1', // Assume plant exists
    owner_id: 'user-1',  // Assume user exists
    description: 'Load test project',
    problem_statement: 'High defect rate in production',
    goal_statement: 'Reduce defects by 50%',
  });
  
  const success = check(response, {
    'project created': (r) => r.status === 201,
    'has project id': (r) => {
      try {
        return r.json().id !== undefined;
      } catch {
        return false;
      }
    },
  });
  
  createProjectRate.add(success);
  
  if (success) {
    try {
      return response.json();
    } catch {
      return null;
    }
  }
  return null;
}

// Create a dataset
function createDataset(token, projectId) {
  const response = authenticatedRequest('POST', `${BASE_URL}/projects/${projectId}/datasets`, token, {
    name: `dataset-${Date.now()}`,
    description: 'Load test dataset',
    source_type: 'csv',
    source_config: { delimiter: ',' },
  });
  
  const success = check(response, {
    'dataset created': (r) => r.status === 201,
    'has dataset id': (r) => {
      try {
        return r.json().id !== undefined;
      } catch {
        return false;
      }
    },
  });
  
  createDatasetRate.add(success);
  
  if (success) {
    try {
      return response.json();
    } catch {
      return null;
    }
  }
  return null;
}

// Trigger pipeline run
function runPipeline(token, projectCode, datasetName) {
  const response = authenticatedRequest('POST', `${BASE_URL}/runs`, token, {
    project_code: projectCode,
    dataset_name: datasetName,
    config: { phases: ['define', 'measure', 'analyze'] },
  });
  
  const success = check(response, {
    'run created': (r) => r.status === 201,
    'has run id': (r) => {
      try {
        return r.json().id !== undefined;
      } catch {
        return false;
      }
    },
  });
  
  runPipelineRate.add(success);
  
  if (success) {
    try {
      return response.json();
    } catch {
      return null;
    }
  }
  return null;
}

// Get insights for a run
function getInsights(token, runId) {
  const response = authenticatedRequest('GET', `${BASE_URL}/runs/${runId}/insights`, token);
  
  const success = check(response, {
    'insights retrieved': (r) => r.status === 200,
    'is array': (r) => {
      try {
        return Array.isArray(r.json());
      } catch {
        return false;
      }
    },
  });
  
  getInsightsRate.add(success);
  return success;
}

// Get projects list
function getProjects(token) {
  const response = authenticatedRequest('GET', `${BASE_URL}/projects`, token);
  
  return check(response, {
    'projects retrieved': (r) => r.status === 200,
  });
}

// Main test function
export default function() {
  // Pick a random user (simulates different tenants)
  const user = testUsers[Math.floor(Math.random() * testUsers.length)];
  
  // Login
  const token = login(user);
  if (!token) {
    return; // Skip if login failed
  }
  
  sleep(1); // Think time
  
  // Get projects (read-heavy operation)
  getProjects(token);
  sleep(0.5);
  
  // Create project (write operation)
  const project = createProject(token, user.tenantCode);
  if (!project) {
    return;
  }
  
  sleep(1);
  
  // Create dataset
  const dataset = createDataset(token, project.id);
  if (!dataset) {
    return;
  }
  
  sleep(1);
  
  // Trigger pipeline run
  const run = runPipeline(token, project.code, dataset.name);
  if (!run) {
    return;
  }
  
  sleep(2); // Wait for pipeline to potentially start
  
  // Get insights (simulate checking results)
  getInsights(token, run.id);
  
  sleep(1);
}

// Teardown - cleanup (optional, runs once per VU)
export function teardown(data) {
  // Could add cleanup logic here if needed
  console.log('Test completed');
}