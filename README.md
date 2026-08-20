
# 💸 FinOps AI — Cloud Cost Optimization Platform

> **FinOps** = Financial Operations for the Cloud.
> This project helps companies **understand, analyze, and reduce their cloud spending** using AI and data visualization.

---

## 🤔 What Is This Project?

Imagine a company uses cloud services (like AWS, Azure, or Google Cloud) to run their software. Every month they get a massive bill. This project gives them a **smart dashboard** that:

1. 📤 **Uploads** their cloud billing data (CSV file)
2. 📊 **Shows** a clear dashboard of where money is being spent
3. 🤖 **Detects wasted resources** using AI (e.g. a server running 24/7 but doing almost nothing)
4. 📈 **Predicts future costs** using machine learning
5. 🔔 **Sets budget alerts** so they know when spending goes over a limit

**In short:** It's like a smart financial advisor for cloud bills.

---

## 🏗️ How Is the Project Structured?

```
finops-ai/
├── backend/          ← Python server (the "brain" — handles data and AI)
│   ├── main.py            ← Entry point, starts the server
│   ├── models.py          ← Database table definitions
│   ├── schemas.py         ← Data shapes (what data looks like going in/out)
│   ├── database.py        ← Database connection setup
│   ├── auth.py            ← Login / signup logic
│   ├── requirements.txt   ← Python packages needed
│   ├── routers/           ← API endpoints (routes)
│   │   ├── auth_router.py      ← /auth/register, /auth/login
│   │   ├── upload_router.py    ← /upload (upload CSV billing data)
│   │   ├── costs_router.py     ← /costs (get spending data)
│   │   └── insights_router.py  ← /insights/waste, /insights/predict
│   └── ai/                ← The AI/ML modules
│       ├── waste_detection.py   ← Detects wasted cloud resources
│       └── cost_prediction.py   ← Predicts future spending
│
└── frontend/         ← React web app (the "face" — what users see)
    ├── index.html         ← The single HTML file (React lives inside this)
    ├── package.json       ← JavaScript packages needed
    ├── vite.config.js     ← Build tool configuration
    └── src/
        ├── main.jsx           ← Entry point for React
        ├── App.jsx            ← Routing between pages
        ├── api.js             ← All calls to the backend API
        ├── AuthContext.jsx    ← Manages who is logged in
        ├── index.css          ← All styling
        ├── components/        ← Reusable UI pieces
        └── pages/             ← Each screen/page of the app
            ├── AuthPage.jsx        ← Login / Register screen
            ├── Dashboard.jsx       ← Main overview of spending
            ├── UploadPage.jsx      ← Upload CSV billing file
            ├── WastePage.jsx       ← Shows wasted resources
            ├── PredictionsPage.jsx ← Future cost forecasts
            └── AlertsPage.jsx      ← Budget alert management
```

---

## 🧠 How Does the AI Work?

### 1. Waste Detection (`backend/ai/waste_detection.py`)
Uses **two layers** to find resources wasting money:

| Layer | Type | What it does |
|-------|------|--------------|
| Rule Engine | Deterministic | Flags idle servers (CPU < 5%), oversized instances, overpriced storage |
| Anomaly Detector | ML — IsolationForest | Flags resources whose cost is statistically abnormal given their usage |

**Example finding:** "Server `ec2-prod-03` ran for 720 hours but had only 2% CPU usage — you're paying for nothing. Estimated saving: $142/month."

### 2. Cost Prediction (`backend/ai/cost_prediction.py`)
Uses **Linear Regression** (numpy polyfit) to:
- Look at your past daily spending
- Fit a trend line (rising / falling / flat)
- Project that trend into the future (7, 14, 30, 60, or 90 days)
- Add a confidence band (uncertainty range)

**Example output:** "Based on your trend, you'll spend ~$4,200 next 30 days (range: $3,800–$4,600)."

---

## 🛠️ Tech Stack (Technologies Used)

### Backend (Server / API)
| Technology | What it does |
|------------|--------------|
| **Python 3.14** | Programming language |
| **FastAPI** | Web framework — creates the API endpoints |
| **Uvicorn** | The actual web server that runs FastAPI |
| **SQLAlchemy** | Talks to the database |
| **SQLite** (`finops.db`) | Stores users, uploaded data, alerts |
| **Pandas** | Reads and processes CSV billing data |
| **NumPy** | Math operations for predictions |
| **scikit-learn** | IsolationForest ML model for anomaly detection |
| **python-jose + passlib** | Secure login (JWT tokens + password hashing) |

### Frontend (Web App / UI)
| Technology | What it does |
|------------|--------------|
| **React 18** | JavaScript UI framework |
| **Vite** | Fast development build tool |
| **React Router** | Navigation between pages |
| **Recharts** | Beautiful charts and graphs |
| **Lucide React** | Icons |
| **Vanilla CSS** | Custom styling |

---

## 🚀 How to Run the Project (Step by Step)

### ✅ Prerequisites (Install these first)
- **Python 3.9+** → https://python.org/downloads
- **Node.js 18+** → https://nodejs.org

---

### Step 1 — Install Backend Dependencies

Open a terminal and run:

```powershell
cd backend
pip install --prefer-binary -r requirements.txt
```

> This installs all Python packages the backend needs.

---

### Step 2 — Start the Backend Server

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:  Uvicorn running on http://127.0.0.1:8000
INFO:  Application startup complete.
```

> The backend is now running. **Leave this terminal open.**

---

### Step 3 — Install Frontend Dependencies

Open a **new terminal** and run:

```powershell
cd frontend
npm install
```

> This installs all JavaScript packages. Only needed once.

---

### Step 4 — Start the Frontend

```powershell
cd frontend
npm run dev
```

You should see:
```
  VITE v5.x  ready in 300ms
  ➜  Local:   http://localhost:5173/
```

---

### Step 5 — Open the App

Open your browser and visit: **http://localhost:5173**

You'll see the login screen. Register a new account and start exploring!

---

## 📖 How to Use the App

### 1. Register / Login
- Open the app → click **Register**
- Create an account with email and password
- Login to access the dashboard

### 2. Upload Billing Data
- Go to the **Upload** page
- Upload a CSV with your cloud billing data
- Required columns: `date`, `service`, `cost`, `resource_id`, `usage_hours`, `avg_cpu_utilization`, `storage_gb`
- 💡 A ready-made sample file is included: `backend/sample_billing_data.csv` — use it to try the app!

### 3. View the Dashboard
- After uploading, go to **Dashboard**
- See total spending, cost breakdown by service, and daily trends

### 4. Find Wasted Resources
- Go to the **Waste** page
- The AI lists resources wasting money, sorted by savings potential
- Each finding shows: the problem, monthly cost, estimated saving, and recommendation

### 5. Predict Future Costs
- Go to the **Predictions** page
- Choose a forecast horizon: 7, 14, 30, 60, or 90 days
- See the forecast chart with a confidence band

### 6. Set Budget Alerts
- Go to the **Alerts** page
- Create alerts for services (e.g. "alert if EC2 exceeds $500/month")
- Alerts are automatically checked and marked triggered when exceeded

---

## 🔌 API Endpoints

The backend exposes a REST API. Explore it interactively at:
**http://localhost:8000/docs** (Swagger UI — auto-generated!)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create a new user account |
| POST | `/auth/login` | Login and receive access token |
| POST | `/upload` | Upload a CSV billing file |
| GET | `/costs/summary` | Get total spending summary |
| GET | `/costs/by-service` | Get cost breakdown by service |
| GET | `/costs/daily` | Get daily spending trend |
| GET | `/insights/waste` | Get AI waste detection findings |
| GET | `/insights/predict?horizon=30` | Get 30-day cost prediction |
| GET | `/alerts` | List all budget alerts |
| POST | `/alerts` | Create a budget alert |
| DELETE | `/alerts/{id}` | Delete an alert |

---

## 🗂️ Data Flow — How Everything Connects

```
User uploads CSV
       │
       ▼
  FastAPI /upload endpoint
       │
       ▼
  Pandas reads CSV → stores rows in SQLite (finops.db)
       │
       ├──► GET /costs/summary    → Dashboard charts
       │
       ├──► GET /insights/waste   → AI Waste Detection → Waste page
       │
       └──► GET /insights/predict → ML Cost Forecast  → Predictions page
                │
                ▼
      React Frontend renders charts, tables, and alerts
```

---

## ❓ Common Problems & Fixes

| Problem | Fix |
|---------|-----|
| `uvicorn` not recognized | Run `pip install uvicorn` |
| `npm run dev` fails with "vite not found" | Run `npm install` in the frontend folder |
| `pandas` fails to install | Use `pip install --prefer-binary pandas` |
| Backend starts but frontend can't connect | Make sure backend is running on port 8000 |
| Login fails | Make sure you registered first |
| Port 8000 already in use | Change to `--port 8001` and update `frontend/src/api.js` |

---

## 📚 Concepts to Learn (for Students)

| Concept | Where it's used |
|---------|----------------|
| REST APIs | Backend ↔ Frontend communication |
| JWT Authentication | Secure login in `auth.py` |
| SQLAlchemy ORM | Database access in `models.py` |
| React Hooks (`useState`, `useEffect`) | All frontend pages |
| IsolationForest (ML) | `ai/waste_detection.py` |
| Linear Regression | `ai/cost_prediction.py` |
| Pandas DataFrames | CSV processing in `upload_router.py` |
| Recharts | Charts in `Dashboard.jsx`, `PredictionsPage.jsx` |

---

*Built with ❤️ — A full-stack AI-powered FinOps platform for learning and real-world use.*
 — Cloud Cost Optimization Platform

> AI-powered cloud cost management: predict spend, detect waste, and act on intelligent recommendations — built as a full-stack portfolio project demonstrating AI + Cloud + industry-grade engineering.

---

## 🚀 Live Demo Flow

```
1. Register → sign in
2. Upload → sample_billing_data.csv  (or your own AWS/Azure export)
3. Dashboard → see cost overview + AI insight cards
4. Predictions → 7–90 day forecast with confidence band
5. Waste → per-resource findings sorted by savings potential
6. Alerts → auto-generated threshold warnings
```

---

## 🧠 AI Components

### 1. Cost Prediction (Linear Regression)
**File:** `backend/ai/cost_prediction.py`

Fits a linear trend (OLS via `numpy.polyfit`) to the daily cost time-series, projects it `N` days forward, and computes a confidence band from the residual standard deviation (σ × √horizon). This is intentionally explainable — every step can be walked through in a technical interview.

**Upgrade path:** swap the `polyfit` model for an LSTM (PyTorch / Keras) to capture non-linear seasonality without changing any API contract.

### 2. Waste Detection (Rules + Isolation Forest)
**File:** `backend/ai/waste_detection.py`

**Layer 1 — Rule engine** (deterministic, explainable FinOps heuristics):
| Rule | Threshold | Action |
|------|-----------|--------|
| Idle resource | CPU < 5% and hours ≥ 100/month | Stop / schedule |
| Oversized instance | Large family + CPU < 30% | Downgrade tier |
| Inefficient storage | Cost/GB > 2× fleet median | Move to cold tier |

**Layer 2 — Anomaly detection** (`sklearn.IsolationForest`):
Trains on `[usage_hours, avg_cpu_utilization, cost_per_hour]` across the fleet, flags resources whose cost is statistically anomalous relative to their own usage pattern. Contamination factor = 0.10.

### 3. Recommendation Engine
Built into the waste detection output — every finding includes a concrete, actionable `recommendation` string surfaced in the UI.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  React Frontend (Vite + Recharts)                       │
│  Dashboard │ Predictions │ Waste │ Alerts │ Upload      │
└───────────────────────┬─────────────────────────────────┘
                        │ REST (JWT Bearer)
┌───────────────────────▼─────────────────────────────────┐
│  FastAPI Backend                                         │
│  /auth  /billing  /costs  /ai                           │
│                                                          │
│  ┌──────────────┐  ┌────────────────────────────────┐   │
│  │ SQLAlchemy   │  │ AI Engine                      │   │
│  │ ORM          │  │ cost_prediction.py             │   │
│  │              │  │ waste_detection.py             │   │
│  └──────┬───────┘  └────────────────────────────────┘   │
│         │                                                │
│  ┌──────▼───────┐                                        │
│  │ SQLite (dev) │  → swap URL for PostgreSQL in prod     │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

### Cloud Deployment (AWS Equivalent)
| Component | Dev | Production (AWS) |
|-----------|-----|-----------------|
| Frontend  | Vite dev server / Vite build | S3 + CloudFront / Vercel |
| Backend   | Uvicorn local | EC2 / ECS / App Runner |
| Database  | SQLite file   | RDS PostgreSQL |
| File storage | local | S3 (billing CSV uploads) |
| CI/CD     | manual        | GitHub Actions → ECR → ECS |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, React Router 6, Recharts, Lucide Icons, Vite |
| Backend  | Python 3.11, FastAPI, SQLAlchemy, Pydantic v2 |
| AI/ML    | NumPy, Pandas, scikit-learn (IsolationForest) |
| Auth     | JWT (python-jose), bcrypt (passlib) |
| Database | SQLite (dev) → PostgreSQL (prod, zero code change) |
| Styling  | Custom CSS design system (dark industrial FinOps aesthetic) |

---

## ⚙️ Setup & Run

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend
```bash
cd backend
pip install -r requirements.txt

# Optional: generate 90-day synthetic demo data
python generate_sample_data.py

# Start API server
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

### Quick start (both together)
```bash
# Terminal 1
cd backend && uvicorn main:app --reload

# Terminal 2
cd frontend && npm run dev
```

### Default demo account
After running the backend, register at http://localhost:5173/login — the first user becomes admin automatically. Upload `backend/sample_billing_data.csv` to see full AI insights.

---

## 📁 Project Structure

```
finops-ai/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, route registration
│   ├── database.py               # SQLAlchemy engine + session
│   ├── models.py                 # ORM: User, BillingRecord
│   ├── schemas.py                # Pydantic request/response schemas
│   ├── auth.py                   # JWT creation + validation
│   ├── requirements.txt
│   ├── generate_sample_data.py   # Synthetic billing CSV generator
│   ├── ai/
│   │   ├── cost_prediction.py    # Linear regression forecasting
│   │   └── waste_detection.py    # Rule engine + Isolation Forest
│   └── routers/
│       ├── auth_router.py        # POST /auth/register, /auth/login
│       ├── upload_router.py      # POST /billing/upload
│       ├── costs_router.py       # GET /costs/summary, /daily, /by-resource
│       └── insights_router.py    # GET /ai/prediction, /waste, /insights
│
└── frontend/
    ├── index.html
    ├── vite.config.js            # Dev proxy → backend:8000
    └── src/
        ├── App.jsx               # Router + auth guard
        ├── AuthContext.jsx       # Global auth state (JWT decode)
        ├── api.js                # Typed API client
        ├── index.css             # Design system (tokens, components)
        ├── components/
        │   └── Sidebar.jsx
        └── pages/
            ├── AuthPage.jsx      # Login / register
            ├── Dashboard.jsx     # KPI cards + charts
            ├── PredictionsPage.jsx # Forecast + confidence band
            ├── WastePage.jsx     # Findings table + severity filter
            ├── AlertsPage.jsx    # Auto-generated threshold alerts
            └── UploadPage.jsx    # Drag-and-drop CSV upload
```

---

## 🔐 Security

- JWT Bearer tokens (HS256), 24-hour expiry
- Passwords hashed with bcrypt (via passlib)
- Role-based access: first registered user → admin; subsequent → user
- All data routes are authenticated; users only see their own records
- Move `FINOPS_SECRET_KEY` to env variable / secrets manager before production

---

## 🗺️ Roadmap (v2 Ideas)

- [ ] LSTM cost forecasting (PyTorch) for seasonal workloads
- [ ] Direct AWS Cost & Usage Report (CUR) S3 sync
- [ ] Multi-user team workspaces
- [ ] Email / Slack alert notifications
- [ ] Reserved Instance / Savings Plan ROI calculator
- [ ] Kubernetes pod cost attribution
- [ ] PostgreSQL + Docker Compose production setup

---

## 📄 License

MIT — free to use, fork, and adapt for your own portfolio or organisation.

