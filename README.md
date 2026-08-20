# 💸 FinOps AI — Cloud Cost Optimization Platform

> **FinOps AI** is a full-stack cloud cost intelligence platform that helps organizations understand, analyze, predict, and reduce their cloud spending using data analytics, machine learning, and intelligent recommendations.

---

## 📌 Project Overview

Cloud providers such as AWS, Azure, and Google Cloud generate large amounts of billing data. Understanding where money is being spent and identifying unnecessary costs can be difficult.

**FinOps AI** provides a centralized dashboard that allows users to:

- 📤 Upload cloud billing data using CSV files
- 📊 Analyze total and service-level cloud costs
- 🤖 Detect potentially wasted cloud resources
- 📈 Predict future cloud spending
- 💡 Generate AI-powered cost insights
- 🔔 Identify high-priority cost and waste alerts
- 💰 Estimate potential monthly savings

### In simple terms

> **FinOps AI acts like an intelligent financial advisor for cloud infrastructure.**

---

# ✨ Main Features

## 🔐 Authentication

- User registration
- User login
- JWT Bearer authentication
- Password hashing
- Protected API endpoints
- User-specific billing records
- Role-based access

---

## 📤 Billing Data Upload

Users can upload billing information through a CSV file.

### Endpoint

```text
POST /billing/upload
````

### Required fields

```text
date
service
resource_id
cost
```

### Optional fields

```text
instance_type
usage_hours
avg_cpu_utilization
storage_gb
```

For accurate waste detection, it is recommended to provide:

```text
usage_hours
avg_cpu_utilization
```

### Example

```csv
date,service,resource_id,instance_type,usage_hours,avg_cpu_utilization,storage_gb,cost
2026-06-01,EC2,i-web-01,m5.large,24.0,72.3,,2.18
2026-06-01,EC2,i-idle-01,m5.xlarge,24.0,1.4,,4.21
2026-06-01,S3,s3-logs,,,0,1800,0.43
2026-06-01,RDS,db-prod,db.r5.large,24.0,55.0,,3.90
```

### Tested result

The sample billing dataset successfully inserted:

```text
Rows inserted: 1,350
Rows failed: 0
```

---

# 📊 Cost Analytics

FinOps AI analyzes uploaded billing records and provides cost summaries.

## Cost Summary

```text
GET /costs/summary
```

Example response:

```json
{
  "total_cost": 5084.02,
  "record_count": 1350,
  "service_breakdown": [
    {
      "service": "EC2",
      "cost": 3439.96
    },
    {
      "service": "RDS",
      "cost": 1100.93
    },
    {
      "service": "S3",
      "cost": 453.23
    },
    {
      "service": "Lambda",
      "cost": 89.9
    }
  ],
  "date_range": {
    "start": "2026-03-23",
    "end": "2026-06-20"
  }
}
```

### Current test data

```text
Total Cost: $5,084.02
Records: 1,350
```

The dashboard displays the same information through interactive cards and charts.

---

# 🤖 AI Module

The AI module contains three main API endpoints.

```text
GET /ai/prediction
GET /ai/waste
GET /ai/insights
```

---

## 📈 1. Cost Prediction

### Endpoint

```text
GET /ai/prediction?horizon_days=30
```

The system analyzes historical daily spending and predicts future cloud costs.

The current implementation uses a **linear trend model** based on historical billing data.

### Prediction output

```json
{
  "next_period_days": 30,
  "predicted_cost": 1859.6,
  "lower_bound": 1850.47,
  "upper_bound": 1868.73,
  "trend": "flat",
  "daily_avg_recent": 60.98
}
```

### Current result

```text
Forecast: $1,859.60
Range: $1,850.47 – $1,868.73
Daily average: $60.98
Trend: Flat
```

The frontend provides forecast horizons including:

```text
7 days
14 days
30 days
60 days
90 days
```

---

# 🗑️ 2. AI Waste Detection

### Endpoint

```text
GET /ai/waste
```

The waste detection engine identifies resources that may be unnecessarily increasing cloud costs.

It uses two layers:

### Layer 1 — Rule-Based Detection

The system checks for conditions such as:

| Detection           | Example                           |
| ------------------- | --------------------------------- |
| Idle resource       | Very low CPU utilization          |
| Oversized instance  | Large instance with low CPU usage |
| Inefficient storage | High storage cost per GB          |

### Layer 2 — Machine Learning

The system also uses:

```text
Isolation Forest
```

to identify statistically unusual cost/usage patterns.

---

## Current Waste Detection Result

The current dataset produces:

```text
6 issues detected
3 High severity
2 Medium severity
1 Low severity
```

Estimated potential monthly savings:

```text
$2,281.92
```

### Example finding

```json
{
  "resource_id": "i-old-batch-job",
  "service": "EC2",
  "instance_type": "c5.4xlarge",
  "issue": "Idle resource",
  "monthly_cost": 1530.2,
  "estimated_monthly_savings": 1377.18,
  "severity": "high"
}
```

The UI displays:

* Resource
* Service
* Instance type
* Issue
* Severity
* Monthly cost
* Estimated savings
* Recommendation

---

# 💡 3. Combined AI Insights

### Endpoint

```text
GET /ai/insights
```

This is the main AI dashboard endpoint.

It combines:

```text
Cost analytics
      +
Waste detection
      +
Cost prediction
      +
Recommendations
```

The response generates plain-English insight cards.

### Example

```json
{
  "total_cost": 5084.02,
  "total_potential_savings": 2281.92,
  "waste_percentage": 44.9
}
```

### Headline insights

Example:

> You could be wasting 45% of your cloud budget (~$2,281.92/month).

Another example:

> Estimated cost for the next 30 days: $1,859.60.

The dashboard also identifies the most expensive waste issue.

---

# 🔔 Monitoring & Alerts

The Monitoring section provides cost and waste warnings.

Current example alerts include:

### High Priority

```text
High Waste Ratio
3 Idle High-Cost Resources
```

### Medium Priority

```text
EC2 is 68% of Total Spend
```

Alerts help users quickly identify areas that require attention.

---

# 🖥️ Frontend

The frontend is built using:

* React
* Vite
* React Router
* Recharts
* Lucide React
* Custom CSS

## Main Pages

```text
Login / Register
      ↓
Dashboard
      ↓
Predictions
      ↓
Waste Detection
      ↓
Alerts
      ↓
Data Upload
```

### Dashboard

Displays:

* Total cloud cost
* Number of billing records
* Service cost breakdown
* Spending trends
* AI insight cards

### Predictions

Displays:

* Forecast horizon
* Predicted cost
* Confidence range
* Daily average
* Spending trend
* Historical vs forecast chart

### Waste Detection

Displays:

* Number of issues
* Estimated savings
* Severity counts
* Resource-level findings
* Recommendations

### Alerts

Displays:

* High priority alerts
* Medium priority alerts
* Low priority alerts
* Waste warnings
* Spending concentration warnings

### Data Upload

Allows users to:

* Download sample CSV
* Drag and drop billing data
* Browse for a CSV file
* Upload billing records
* Clear uploaded data

---

# 🏗️ System Architecture

```text
                 ┌───────────────────────────┐
                 │       React Frontend      │
                 │      Vite + Recharts      │
                 │                           │
                 │ Dashboard                 │
                 │ Predictions               │
                 │ Waste                     │
                 │ Alerts                    │
                 │ Data Upload               │
                 └─────────────┬─────────────┘
                               │
                         REST API + JWT
                               │
                 ┌─────────────▼─────────────┐
                 │      FastAPI Backend      │
                 │                           │
                 │ Authentication            │
                 │ Billing Upload            │
                 │ Cost Analytics            │
                 │ AI Prediction             │
                 │ AI Waste Detection        │
                 │ AI Insights               │
                 └─────────────┬─────────────┘
                               │
                 ┌─────────────▼─────────────┐
                 │        PostgreSQL         │
                 │                           │
                 │ Users                     │
                 │ Billing Records           │
                 │ Alerts                    │
                 └───────────────────────────┘
```

---

# 🧠 AI Architecture

```text
                  Billing Data
                       │
                       ▼
              ┌─────────────────┐
              │ Data Processing │
              │    Pandas       │
              └────────┬────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
 ┌─────────────────┐       ┌──────────────────┐
 │ Cost Prediction │       │ Waste Detection  │
 │                 │       │                  │
 │ Linear Trend    │       │ Rule Engine      │
 │ NumPy           │       │       +          │
 │                 │       │ Isolation Forest │
 └────────┬────────┘       └────────┬─────────┘
          │                         │
          └────────────┬────────────┘
                       ▼
              ┌──────────────────┐
              │ Combined Insights│
              │                  │
              │ Recommendations  │
              │ Savings          │
              │ Forecast         │
              └──────────────────┘
```

---

# 🛠️ Technology Stack

## Backend

| Technology       | Purpose                      |
| ---------------- | ---------------------------- |
| Python           | Backend programming language |
| FastAPI          | REST API framework           |
| Uvicorn          | ASGI server                  |
| SQLAlchemy       | Database ORM                 |
| PostgreSQL       | Relational database          |
| Pandas           | Billing CSV processing       |
| NumPy            | Numerical calculations       |
| scikit-learn     | Machine learning             |
| python-jose      | JWT authentication           |
| Passlib / bcrypt | Password hashing             |
| Pydantic         | Data validation              |

## Frontend

| Technology   | Purpose                         |
| ------------ | ------------------------------- |
| React        | User interface                  |
| Vite         | Frontend development/build tool |
| React Router | Page navigation                 |
| Recharts     | Charts and visualization        |
| Lucide React | Icons                           |
| CSS          | Custom UI styling               |

---

# 📁 Project Structure

```text
finops-ai/
│
├── .env.example
├── .gitignore
├── README.md
├── API_GUIDE.md
├── LEARN.md
├── start.sh
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── requirements.txt
│   ├── generate_sample_data.py
│   ├── sample_billing_data.csv
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── cost_prediction.py
│   │   └── waste_detection.py
│   │
│   └── routers/
│       ├── __init__.py
│       ├── auth_router.py
│       ├── upload_router.py
│       ├── costs_router.py
│       └── insights_router.py
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    │
    └── src/
        ├── App.jsx
        ├── AuthContext.jsx
        ├── api.js
        ├── index.css
        │
        ├── components/
        │   └── Sidebar.jsx
        │
        └── pages/
            ├── AuthPage.jsx
            ├── Dashboard.jsx
            ├── PredictionsPage.jsx
            ├── WastePage.jsx
            ├── AlertsPage.jsx
            └── UploadPage.jsx
```

---

# 🔌 API Endpoints

All protected endpoints require a JWT Bearer token.

## Authentication

| Method | Endpoint         | Description           |
| ------ | ---------------- | --------------------- |
| POST   | `/auth/register` | Register a new user   |
| POST   | `/auth/login`    | Login and receive JWT |

## Billing

| Method | Endpoint          | Description        |
| ------ | ----------------- | ------------------ |
| POST   | `/billing/upload` | Upload billing CSV |

## Cost Analytics

| Method | Endpoint            | Description               |
| ------ | ------------------- | ------------------------- |
| GET    | `/costs/summary`    | Overall cost summary      |
| GET    | `/costs/by-service` | Cost breakdown by service |
| GET    | `/costs/daily`      | Daily spending trend      |

## AI

| Method | Endpoint         | Description                         |
| ------ | ---------------- | ----------------------------------- |
| GET    | `/ai/prediction` | Predict future cloud costs          |
| GET    | `/ai/waste`      | Detect potentially wasted resources |
| GET    | `/ai/insights`   | Generate combined AI insights       |

## Documentation

```text
http://127.0.0.1:8000/docs
```

FastAPI automatically generates interactive Swagger documentation.

---

# 🚀 How to Run

## Prerequisites

Install:

* Python 3.10+
* Node.js 18+
* PostgreSQL

---

## 1. Clone the Repository

```bash
git clone https://github.com/IT24100052/finops-ai.git
cd finops-ai
```

---

## 2. Backend Setup

```powershell
cd backend
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

---

## 3. Configure Environment Variables

Create:

```text
backend/.env
```

Add the required database and authentication configuration.

Example:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/finops
JWT_SECRET=your-secret-key
```

> Never commit the real `.env` file to GitHub.

Use `.env.example` as the safe template.

---

## 4. Start Backend

From the `backend` directory:

```powershell
uvicorn main:app --reload --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## 5. Start Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# 🧪 Tested Application Flow

The complete application has been tested using the following flow:

```text
Register
   ↓
Login
   ↓
Receive JWT
   ↓
Upload billing CSV
   ↓
1,350 billing records inserted
   ↓
Dashboard
   ↓
Cost Summary
   ↓
AI Prediction
   ↓
AI Waste Detection
   ↓
AI Combined Insights
   ↓
Monitoring Alerts
```

### Tested Billing Upload

```text
Rows inserted: 1,350
Rows failed: 0
```

### Tested Cost Summary

```text
Total Cost: $5,084.02
Records: 1,350
```

### Tested AI Prediction

```text
30-day predicted cost: $1,859.60
Trend: Flat
```

### Tested Waste Detection

```text
Issues detected: 6
High severity: 3
Medium severity: 2
Low severity: 1

Potential monthly savings: $2,281.92
```

### Tested Combined Insights

```text
Total cost: $5,084.02
Potential savings: $2,281.92
Waste percentage: 44.9%
```

---

# 🔐 Security

The application implements:

* JWT Bearer authentication
* Password hashing
* Protected API routes
* User-specific billing data
* Environment-based secrets
* `.env` excluded from Git
* `.venv` excluded from Git

### Important

Never commit:

```text
.env
.venv/
```

The repository contains:

```text
.env.example
```

as a safe configuration template.

---

# 📊 Example Dashboard

The dashboard provides a centralized view of:

```text
┌─────────────────────────────────────────────┐
│              FINOPS AI                      │
├──────────────┬──────────────┬───────────────┤
│ Total Cost   │ Records      │ Potential     │
│ $5,084.02    │ 1,350        │ Savings       │
│              │              │ $2,281.92     │
├──────────────┴──────────────┴───────────────┤
│                                             │
│             Cost Analytics                  │
│                                             │
├─────────────────────────────────────────────┤
│ AI Insights                                 │
│                                             │
│ 45% Potential Waste                         │
│ Next 30-Day Forecast: $1,859.60             │
│ Top Issue: Idle EC2 Resource                │
└─────────────────────────────────────────────┘
```

---

# 🎓 Learning Concepts Demonstrated

This project demonstrates practical knowledge of:

* REST API development
* FastAPI
* React
* JWT authentication
* Password hashing
* PostgreSQL
* SQLAlchemy ORM
* CSV processing
* Pandas
* NumPy
* Machine Learning
* Isolation Forest
* Linear regression
* Data visualization
* API integration
* Frontend/backend architecture
* Environment variables
* Git and GitHub
* Cloud FinOps concepts

---

# ☁️ Future Improvements

Possible future versions could include:

* [ ] AWS Cost & Usage Report integration
* [ ] Azure Cost Management integration
* [ ] Google Cloud billing integration
* [ ] LSTM/advanced forecasting
* [ ] Email notifications
* [ ] Slack notifications
* [ ] Team workspaces
* [ ] AWS Savings Plan recommendations
* [ ] Reserved Instance optimization
* [ ] Kubernetes cost monitoring
* [ ] Docker deployment
* [ ] PostgreSQL production deployment
* [ ] Cloud deployment with CI/CD

---

# 📄 License

MIT License.

This project is developed for educational, portfolio, and demonstration purposes.

---

# 👨‍💻 Project

**FinOps AI — Cloud Cost Optimization Platform**

GitHub:

[https://github.com/IT24100052/finops-ai](https://github.com/IT24100052/finops-ai)

Built with:

**React + FastAPI + PostgreSQL + Machine Learning**

````






