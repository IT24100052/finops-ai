# 📚 LEARN.md — Complete Learning Guide for FinOps AI
# From Zero to Understanding Everything in This Project

> Written especially for you — someone who built this with AI tools
> but wants to truly understand every part of it.
> Read this file from top to bottom. Take your time. Learn step by step.

---

# PART 1: THE BIG PICTURE
# What Problem Does This Project Solve?

Companies that use cloud services (AWS, Azure, Google Cloud) face a problem:
their cloud bills are HUGE and confusing. A bill might have thousands of line
items — different servers, storage, databases, each with different costs.

FinOps (Financial Operations) is a practice where teams work to:
  - Understand WHERE money is being spent
  - Find WHERE money is being WASTED
  - PREDICT how much will be spent next month
  - Set ALERTS before costs go over budget

This project is a web application that does all of the above automatically,
using AI and data visualization. Think of it as:

  "A smart accountant for your cloud bills, powered by AI."

---

# PART 2: HOW THE INTERNET WORKS (The Foundation)

Before understanding this project, you need to understand how web apps work.

## What happens when you open http://localhost:5173 in your browser?

Step 1: Your browser (Chrome, Firefox, etc.) sends a REQUEST
Step 2: The web server receives that request
Step 3: The server sends back a RESPONSE (HTML, CSS, JavaScript)
Step 4: Your browser renders what it received

This is called the CLIENT-SERVER model:
  - CLIENT = your browser (asks for things)
  - SERVER = the computer/program that responds (gives things)

## What is localhost?
  - "localhost" means "this same computer"
  - Port 5173 = the "door number" on your computer where the frontend lives
  - Port 8000 = the "door number" where the backend (API) lives
  - Think of ports like apartment numbers in a building

## What is an API?
  - API = Application Programming Interface
  - It's a set of "rules" for how two programs talk to each other
  - In this project: the Frontend (React) talks to the Backend (FastAPI) via API
  - The API uses HTTP, same as websites, but instead of HTML it sends/receives JSON

## What is JSON?
  JSON is a simple way to structure data. Example:
  
    {
      "email": "user@example.com",
      "cost": 1234.56,
      "service": "EC2"
    }
  
  JSON is just text — but formatted so programs can easily read it.

## What is REST?
  REST = Representational State Transfer. It's a style of API design.
  In REST, you use HTTP "methods" to describe what you want to do:
  
    GET    → Read something    (e.g. GET /costs/summary = "give me the cost summary")
    POST   → Create something  (e.g. POST /auth/register = "create a new user")
    DELETE → Delete something  (e.g. DELETE /billing/clear = "delete my data")

---

# PART 3: THE BACKEND — Python / FastAPI
# File: backend/main.py

This is the ENTRY POINT of the backend. When you run "uvicorn main:app", Python
reads this file first.

Let's read it line by line:

    from fastapi import FastAPI                           ← Import the FastAPI library
    from fastapi.middleware.cors import CORSMiddleware    ← Import CORS tool

    from database import engine, Base    ← Import our database setup
    import models                         ← Import our database table definitions
    from routers import auth_router, upload_router, costs_router, insights_router

    Base.metadata.create_all(bind=engine)  ← Create database tables if they don't exist

    app = FastAPI(title="FinOps AI", ...)  ← Create the web application object

    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"])
    ← This allows the frontend (on port 5173) to talk to the backend (port 8000).
    ← Without this, browsers would BLOCK the request for security reasons.
    ← This is called CORS = Cross-Origin Resource Sharing.

    app.include_router(auth_router.router)      ← Add /auth/... routes
    app.include_router(upload_router.router)    ← Add /billing/... routes
    app.include_router(costs_router.router)     ← Add /costs/... routes
    app.include_router(insights_router.router)  ← Add /ai/... routes

    @app.get("/")
    def root():
        return {"status": "ok"}   ← A simple "health check" endpoint

## What is Uvicorn?
  Uvicorn is an ASGI server. Think of it as the "engine" that:
  - Listens on port 8000 for incoming HTTP requests
  - Hands those requests to your FastAPI application
  - Sends the response back to the caller
  
  Without Uvicorn, your FastAPI app is just Python code sitting there.
  Uvicorn makes it actually listen and respond.

## What is --reload?
  The --reload flag means: "watch all Python files, and if any of them change,
  automatically restart the server." This is very convenient during development
  so you don't have to manually restart every time you edit a file.

---

# PART 4: THE DATABASE
# Files: backend/database.py and backend/models.py

## What is a Database?
  A database is a place to PERMANENTLY store data. When your server restarts,
  everything you stored in the database is still there.
  
  This project uses SQLite — a database that lives in a single file: finops.db
  You can see this file in the backend/ folder.

## database.py — How the Connection is Set Up

    SQLALCHEMY_DATABASE_URL = "sqlite:///./finops.db"
    ← This is the "address" of the database. sqlite:/// means "use SQLite".
    ← ./finops.db means "the file finops.db in the current folder"
    
    engine = create_engine(...)
    ← The engine is what actually connects Python to the database.
    
    SessionLocal = sessionmaker(...)
    ← A "session" is like an open conversation with the database.
    ← You open a session, do things (read/write), then close it.
    
    Base = declarative_base()
    ← This is the base class all our database table "models" will inherit from.
    
    def get_db():
        db = SessionLocal()    ← Open a database session
        try:
            yield db           ← Give it to whoever asked for it
        finally:
            db.close()         ← Always close it, even if an error happened

## models.py — What Tables Look Like

  SQLAlchemy lets you define database tables using Python classes. Each class
  becomes a table. Each class attribute becomes a column in that table.
  
    class User(Base):
        __tablename__ = "users"          ← The table is named "users"
        
        id = Column(Integer, primary_key=True)   ← Auto-incrementing unique ID
        email = Column(String, unique=True)       ← Email must be unique
        hashed_password = Column(String)          ← Stored as a hash (NOT plain text!)
        role = Column(String, default="user")     ← "user" or "admin"
        created_at = Column(DateTime)             ← When account was created
    
    class BillingRecord(Base):
        __tablename__ = "billing_records"
        
        id = Column(Integer, primary_key=True)
        owner_id = Column(Integer, ForeignKey("users.id"))
        ← This links each record to a specific user. ForeignKey means:
        ← "this column's value must exist in the users.id column"
        
        date = Column(Date)             ← e.g. 2024-08-01
        service = Column(String)        ← e.g. "EC2", "S3", "RDS"
        resource_id = Column(String)    ← e.g. "i-0a1b2c3d"
        instance_type = Column(String)  ← e.g. "m5.xlarge"
        usage_hours = Column(Float)     ← How many hours it ran
        avg_cpu_utilization = Column(Float)  ← Average CPU usage (0-100%)
        storage_gb = Column(Float)      ← Storage used in GB
        cost = Column(Float)            ← Money spent (in USD)

## What is ORM?
  ORM = Object-Relational Mapper.
  SQLAlchemy is an ORM. Instead of writing raw SQL like:
  
    SELECT * FROM users WHERE email = 'test@test.com'
  
  You write Python:
  
    db.query(models.User).filter(models.User.email == 'test@test.com').first()
  
  The ORM translates your Python into SQL automatically.

---

# PART 5: DATA SHAPES — Schemas
# File: backend/schemas.py

Schemas define the SHAPE of data coming in and going out of the API.
Pydantic is the library used. It automatically validates data.

    class UserCreate(BaseModel):     ← Used when registering a new user
        email: EmailStr              ← Must be a valid email format
        password: str                ← Any string
    
    class UserOut(BaseModel):        ← Used when returning user info (NOT password)
        id: int
        email: EmailStr
        role: str
    
    class Token(BaseModel):          ← Used when returning login token
        access_token: str
        token_type: str = "bearer"
    
    class WasteFinding(BaseModel):   ← Shape of one AI waste finding
        resource_id: str
        service: str
        issue: str           ← e.g. "Idle resource"
        detail: str          ← Human-readable explanation
        monthly_cost: float
        estimated_monthly_savings: float
        severity: str        ← "high", "medium", or "low"
        recommendation: str
    
    class CostPrediction(BaseModel): ← Shape of the cost forecast
        next_period_days: int        ← How many days ahead
        predicted_cost: float        ← Total predicted spend
        lower_bound: float           ← Optimistic estimate (lower end)
        upper_bound: float           ← Pessimistic estimate (higher end)
        trend: str                   ← "rising", "falling", or "flat"
        daily_avg_recent: float      ← Average daily spend (last 7 days)

Why separate schemas from models?
  - models.py defines what's in the DATABASE
  - schemas.py defines what goes IN/OUT through the API
  - You never want to accidentally send a user's hashed_password in an API response!
  - Schemas let you control exactly what data is exposed.

---

# PART 6: AUTHENTICATION — How Login Works
# Files: backend/auth.py and backend/routers/auth_router.py

## The Password Problem
  You can NEVER store a user's password as plain text in a database.
  If someone hacks your database, they'd have everyone's passwords.
  
  Solution: HASHING
  A hash is a one-way function. You put a password in, you get a scrambled
  string out. You can NEVER reverse it back to the original password.
  
  In auth.py:
    pwd_context = CryptContext(schemes=["bcrypt"])
    ← bcrypt is the hashing algorithm. It's one of the strongest available.
    
    def hash_password(plain):
        return pwd_context.hash(plain)
        ← "mysecretpassword" becomes "$2b$12$abcdef..." (looks like gibberish)
    
    def verify_password(plain, hashed):
        return pwd_context.verify(plain, hashed)
        ← Takes the plain password, hashes it, compares to stored hash.
        ← Returns True if they match, False if not.

## What is JWT (JSON Web Token)?
  JWT = JSON Web Token. This is how the server "remembers" you are logged in.
  
  Traditional approach: server stores your session in memory.
  JWT approach: server gives you a TOKEN (a string) when you log in.
  
  The token looks like: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyQGVtYWlsLmNvbSJ9.abc123
  
  It has 3 parts separated by dots:
  Part 1: Algorithm used (base64 encoded)
  Part 2: The data (your email, expiry time) — base64 encoded but NOT secret
  Part 3: A SIGNATURE — only the server can create/verify this
  
  Every time you make an API request after login, you send this token.
  The server checks the signature to verify the token wasn't tampered with.
  
  In auth.py:
    SECRET_KEY = "dev-secret-change-me-in-production"
    ← This is used to sign/verify tokens. In production, this must be secret!
    
    def create_access_token(data):
        to_encode = data.copy()          ← e.g. {"sub": "user@email.com"}
        expire = now + 24 hours          ← Token expires in 1 day
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
        ← Creates the signed token string

## auth_router.py — The Register and Login Endpoints

  REGISTER (/auth/register):
    1. Check if email already exists in the database
    2. Hash the password
    3. Create a User record in the database
    4. Return the user info (NOT the password)
  
  LOGIN (/auth/login):
    1. Find the user by email in the database
    2. Verify the password using verify_password()
    3. Create a JWT token containing the user's email
    4. Return the token

  PROTECTED ROUTES:
    In auth.py, get_current_user() is a "dependency":
    
      def get_current_user(token = Depends(oauth2_scheme), db = Depends(get_db)):
          payload = jwt.decode(token, SECRET_KEY, ...)
          email = payload.get("sub")
          user = db.query(User).filter(User.email == email).first()
          return user
    
    Any route that adds "current_user = Depends(get_current_user)" automatically
    requires the user to be logged in. If the token is missing or invalid,
    FastAPI returns a 401 Unauthorized error automatically.

---

# PART 7: FILE UPLOAD — How CSV Data Gets Into the Database
# File: backend/routers/upload_router.py

When you click "Upload" and choose a CSV file:

  Step 1 — Frontend sends the file to POST /billing/upload
    (as multipart/form-data — the same way HTML forms work)
  
  Step 2 — Backend receives it:
    async def upload_billing_csv(file: UploadFile, db, current_user):
        raw = await file.read()              ← Read raw bytes from the file
        df = pd.read_csv(io.BytesIO(raw))    ← Parse CSV into a Pandas DataFrame
  
  Step 3 — Validate columns:
    missing = REQUIRED_COLUMNS - set(df.columns)
    ← Check that date, service, resource_id, cost columns exist
  
  Step 4 — Insert each row into the database:
    for i, row in df.iterrows():
        record = BillingRecord(
            owner_id=current_user.id,    ← Link to the logged-in user
            date=pd.to_datetime(row["date"]).date(),
            service=str(row["service"]),
            cost=float(row["cost"]),
            ...
        )
        db.add(record)   ← Queue the record for insertion
    db.commit()          ← Actually write everything to the database

## What is Pandas?
  Pandas is a Python library for working with tabular data (like Excel/CSV).
  A "DataFrame" is like a spreadsheet in memory:
  
    df = pd.read_csv("file.csv")
    ← Loads the CSV into a DataFrame
    
    df.columns
    ← Returns all column names: ["date", "service", "cost", ...]
    
    df.iterrows()
    ← Loops through each row, giving you (index, row_data) pairs
    
    row["cost"]
    ← Gets the value of the "cost" column for that row

---

# PART 8: THE AI — How the Machine Learning Works
# Files: backend/ai/waste_detection.py and backend/ai/cost_prediction.py

## AI Layer 1: Waste Detection (waste_detection.py)

  This file has TWO methods of finding wasted resources:

  --- METHOD A: Rule Engine (Simple but Powerful) ---
  
  Rule 1 — Idle Resources:
    idle_mask = (avg_cpu_utilization < 5.0) AND (usage_hours >= 100)
    ← If a server was running for 100+ hours but CPU was almost always below 5%,
    ← it's "idle" — nobody is using it, but you're still paying for it.
    ← Estimated saving = 90% of its cost (you could just turn it off)
  
  Rule 2 — Oversized Instances:
    oversized_mask = (instance is "large" type) AND (avg_cpu_utilization < 30%)
    ← A "large" or "xlarge" server costs a lot. If it's barely using 30% CPU,
    ← it's oversized — you're paying for power you don't need.
    ← Estimated saving = 40% of its cost (downgrade to smaller size)
  
  Rule 3 — Inefficient Storage:
    cost_per_gb = cost / storage_gb
    fleet_median = median cost_per_gb across all resources
    if cost_per_gb > fleet_median * 2: flag as inefficient
    ← If one storage resource costs 2x more per GB than average,
    ← it's probably on a premium tier that isn't needed.
    ← Estimated saving = 30% of its cost (move to cheaper tier)

  --- METHOD B: IsolationForest (Real Machine Learning) ---
  
  IsolationForest is an unsupervised ML algorithm for ANOMALY DETECTION.
  "Anomaly detection" means finding data points that don't fit the pattern.
  
  How it works conceptually:
  - Normal data points cluster together — they take many "splits" to isolate
  - Anomalous points are far from the cluster — they're isolated quickly
  - The algorithm builds random decision trees and measures how many splits
    are needed to isolate each point. Fewer splits = more anomalous.
  
  In this project:
    features = [usage_hours, avg_cpu_utilization, cost, cost_per_hour]
    model = IsolationForest(contamination=0.1)
    ← contamination=0.1 means "expect 10% of data to be anomalous"
    
    preds = model.fit_predict(features)
    ← Returns 1 for normal, -1 for anomalous
    
    anomaly_idx = df.index[preds == -1]
    ← Get the indices of anomalous resources
  
  This catches cases the rules miss — like a resource that has medium CPU
  usage but is costing 5x more than all similar resources. That's suspicious!

## AI Layer 2: Cost Prediction (cost_prediction.py)

  This uses LINEAR REGRESSION — the most fundamental ML concept.
  
  The idea: fit a straight line through historical data, then extend it.
  
  In this project:
    x = [0, 1, 2, 3, ..., n-1]    ← Day numbers (0=first day, 1=second day, etc.)
    y = [24.5, 26.1, 25.8, ...]   ← Total cost each day
    
    slope, intercept = np.polyfit(x, y, 1)
    ← Fits a line: cost = slope * day + intercept
    ← slope > 0 = costs rising over time
    ← slope < 0 = costs falling over time
    ← slope ≈ 0 = costs flat/stable
    
    future_x = [n, n+1, n+2, ..., n+horizon]
    future_y = slope * future_x + intercept
    predicted_total = sum(future_y)
    ← Project the line forward to predict future days
    
    residuals = actual_y - fitted_y
    residual_std = standard deviation of residuals
    band = residual_std * sqrt(horizon_days)
    ← The confidence band: how uncertain we are grows with time
    ← (Like a weather forecast — more accurate for tomorrow than next month)
  
  Trend classification:
    if slope > 0.5:  trend = "rising"    ← Costs going up
    if slope < -0.5: trend = "falling"   ← Costs going down
    else:            trend = "flat"      ← Costs stable

---

# PART 9: THE FRONTEND — React Web Application
# Folder: frontend/src/

## What is React?
  React is a JavaScript library for building user interfaces.
  
  The core idea: instead of manually updating the webpage HTML (which is tedious
  and error-prone), you describe WHAT the UI should look like given the current
  DATA, and React automatically updates the webpage whenever data changes.
  
  React apps are made of COMPONENTS — small, reusable pieces of UI.
  Each component is a JavaScript function that returns HTML-like code (JSX).

## What is JSX?
  JSX = JavaScript XML. It lets you write HTML inside JavaScript:
  
    function MyButton() {
      return <button className="btn">Click me</button>
    }
  
  This looks like HTML but it's actually JavaScript. Vite compiles it to
  regular JavaScript that the browser can understand.

## What is Vite?
  Vite is a BUILD TOOL and DEV SERVER for frontend projects.
  
  - It compiles your JSX into regular JavaScript
  - It bundles all your files together
  - During development (npm run dev), it serves files instantly with hot reload
  - When you change a file, the browser updates automatically without full refresh

## frontend/src/main.jsx — The Entry Point

    import { StrictMode } from 'react'
    import { createRoot } from 'react-dom/client'
    import App from './App.jsx'
    
    createRoot(document.getElementById('root')).render(<App />)
    ← This is the very first code that runs.
    ← It finds the <div id="root"> in index.html and renders your React app inside it.

## frontend/src/App.jsx — The Router

    This file sets up NAVIGATION between pages using React Router.
    React apps are "Single Page Applications" (SPA) — there's only ONE HTML page.
    React Router fakes multiple pages by showing/hiding different components
    based on the URL.
    
    <BrowserRouter>          ← Enables URL-based routing
      <Routes>
        <Route path="/login"  element={<AuthPage />} />      ← Login page
        <Route path="/*"      element={<ProtectedLayout />}  ← All other pages
      </Routes>
    </BrowserRouter>
    
    ProtectedLayout:
    - Checks if user is logged in (isAuthed)
    - If NOT logged in → redirects to /login
    - If logged in → shows the Sidebar + the correct page based on URL:
        /              → Dashboard
        /predictions   → PredictionsPage
        /waste         → WastePage
        /alerts        → AlertsPage
        /upload        → UploadPage

## frontend/src/AuthContext.jsx — Shared Login State

    React has a concept called CONTEXT — a way to share data between
    components without passing it as props through every level.
    
    AuthContext stores:
    - isAuthed: boolean — is the user currently logged in?
    - login(token): saves the JWT token to localStorage, sets isAuthed=true
    - logout(): removes the token, sets isAuthed=false
    
    Any component can access this with:
      const { isAuthed, login, logout } = useAuth()

## frontend/src/api.js — All Backend Communication

    This file is the "bridge" between the frontend and backend.
    All HTTP requests to the backend go through here.
    
    The request() function:
    1. Gets the JWT token from localStorage
    2. Adds it as an Authorization header: "Bearer eyJhbGci..."
    3. Makes the HTTP request using fetch() (built into browsers)
    4. If response is 401 → token expired → redirect to login
    5. If response is error → throw an Error
    6. Otherwise → return the JSON data
    
    Specific API calls:
      api.register(email, password)  → POST /auth/register
      api.login(email, password)     → POST /auth/login
      api.uploadCSV(file)            → POST /billing/upload
      api.getSummary()               → GET /costs/summary
      api.getWaste()                 → GET /ai/waste
      api.getPrediction(days)        → GET /ai/prediction?horizon_days=30

## What is localStorage?
    localStorage is a place in your browser where websites can store small
    amounts of data permanently (until you clear your browser data).
    
    In this project, the JWT token is stored there:
      localStorage.setItem('finops_token', token)   ← save
      localStorage.getItem('finops_token')           ← read
      localStorage.removeItem('finops_token')        ← delete (logout)
    
    This way, if you close and reopen the browser, you're still logged in
    (until the token expires after 24 hours).

---

# PART 10: EACH PAGE EXPLAINED

## AuthPage.jsx — Login / Register
  - Shows a form with email and password fields
  - Has tabs to switch between "Login" and "Register"
  - On submit: calls api.login() or api.register()
  - On success: saves the token → redirects to Dashboard

## Dashboard.jsx — Main Overview
  - On load (useEffect): calls api.getSummary() and api.getDailyCosts()
  - Shows summary cards: Total Spend, Top Service, Number of Resources
  - Shows a line chart of daily spending over time (using Recharts)
  - Shows a pie/bar chart of spending by service

## UploadPage.jsx — Upload Billing Data
  - Provides a file input (or drag-and-drop area)
  - When a CSV is selected: calls api.uploadCSV(file)
  - Shows success/error feedback and number of rows imported
  - Also has a "Clear All Data" button that calls api.clearBilling()

## WastePage.jsx — AI Waste Findings
  - On load: calls api.getWaste()
  - Shows each waste finding as a card with:
    - Severity badge (high=red, medium=orange, low=yellow)
    - Resource ID and service
    - The problem description
    - Monthly cost and estimated saving
    - Recommendation of what to do

## PredictionsPage.jsx — Cost Forecast
  - Has buttons to select forecast horizon: 7, 14, 30, 60, 90 days
  - On horizon change: calls api.getPrediction(days)
  - Shows a Recharts ComposedChart with:
    - Historical daily costs (area chart)
    - Predicted future costs (line chart, different color)
    - Confidence band (shaded area between lower and upper bound)
    - A ReferenceLine separating "past" from "future"

## AlertsPage.jsx — Budget Alerts
  - Shows all existing alerts
  - Form to create a new alert: service name + budget threshold ($)
  - Alerts are stored in the database
  - An alert is "triggered" when the actual cost exceeds the threshold

---

# PART 11: HOW REACT HOOKS WORK

Hooks are special functions in React that let components "hook into" features.
You MUST call them at the top level of a component (not inside if/for).

## useState — Store and update data

    const [data, setData] = useState(null)
    ← data = current value (starts as null)
    ← setData = function to update the value
    
    When you call setData(newValue), React re-renders the component
    with the new value automatically.
    
    Example:
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [costs, setCosts] = useState([])

## useEffect — Run code when something changes

    useEffect(() => {
      // This code runs when the component first appears on screen
      api.getSummary().then(data => setCosts(data))
    }, [])   ← Empty array = run only once on mount
    
    useEffect(() => {
      // This runs every time "horizon" changes
      api.getPrediction(horizon).then(data => setPrediction(data))
    }, [horizon])   ← Runs when "horizon" changes

## useContext — Access shared data

    const { isAuthed, login } = useAuth()
    ← Gets the auth state from AuthContext anywhere in the app

---

# PART 12: HOW RECHARTS WORKS (The Charts)

Recharts is the charting library. Here's how a line chart is built:

    <ResponsiveContainer width="100%" height={300}>
      ← Makes the chart fill its parent container's width
      
      <ComposedChart data={chartData}>
        ← chartData = array of objects: [{date: "Jan", cost: 100}, ...]
        
        <CartesianGrid strokeDasharray="3 3" />   ← Background grid lines
        
        <XAxis dataKey="date" />     ← X axis labels from the "date" field
        <YAxis />                    ← Y axis (auto-scaled to your data)
        
        <Tooltip content={<CustomTooltip />} />
        ← What shows when you hover over the chart
        
        <Area dataKey="cost" fill="#6366f1" stroke="#6366f1" />
        ← Draws a filled area chart using the "cost" field
        
        <Line dataKey="predicted" stroke="#f59e0b" strokeDasharray="5 5" />
        ← Draws a dashed line for predicted values
        
        <ReferenceLine x="2024-08-19" stroke="red" label="Today" />
        ← Draws a vertical line at a specific x value
        
      </ComposedChart>
    </ResponsiveContainer>

---

# PART 13: THE COMPLETE REQUEST JOURNEY
# (What happens when you click "Get Predictions")

Step 1: User clicks the "30 days" button on PredictionsPage
Step 2: React calls setHorizon(30) → state updates → useEffect runs
Step 3: useEffect calls api.getPrediction(30)
Step 4: api.js calls fetch('/ai/prediction?horizon_days=30') with JWT token in header
Step 5: Vite's proxy (vite.config.js) forwards the request to http://localhost:8000
Step 6: Uvicorn receives the request on port 8000
Step 7: FastAPI routes it to the correct endpoint in insights_router.py
Step 8: FastAPI checks the JWT token using get_current_user()
Step 9: insights_router.py queries the database for this user's billing records
Step 10: It groups records by date to get daily totals
Step 11: It calls predict_next_period_cost(daily_costs, horizon_days=30)
Step 12: cost_prediction.py does the linear regression math
Step 13: Returns a CostPrediction object
Step 14: FastAPI converts it to JSON and sends it back
Step 15: api.js receives the JSON and returns it to PredictionsPage
Step 16: PredictionsPage calls setPrediction(data) → state updates
Step 17: React re-renders the component with the new prediction data
Step 18: Recharts draws the updated chart

TOTAL TIME: usually under 100 milliseconds.

---

# PART 14: WHAT IS VITE'S PROXY?
# File: frontend/vite.config.js

There's a problem: the frontend runs on port 5173 and the backend on port 8000.
When you call fetch('/ai/waste'), where does that request go?

The answer: Vite has a PROXY configured. It intercepts certain requests and
forwards them to the backend:

    export default {
      server: {
        proxy: {
          '/auth':    'http://localhost:8000',
          '/billing': 'http://localhost:8000',
          '/costs':   'http://localhost:8000',
          '/ai':      'http://localhost:8000',
        }
      }
    }

So /ai/waste goes to http://localhost:8000/ai/waste automatically.
This only works during development. In production, you'd use a proper
reverse proxy like Nginx to do the same thing.

---

# PART 15: LEARNING ROADMAP
# What to Study Next, in Order

## Level 1 — The Basics (Start Here)
  1. Python basics — variables, functions, classes, lists, dicts
     → Tutorial: https://docs.python.org/3/tutorial/
  2. HTML & CSS basics — how web pages are structured and styled
     → Tutorial: https://www.w3schools.com/html/
  3. JavaScript basics — variables, functions, fetch(), async/await
     → Tutorial: https://javascript.info/

## Level 2 — Web Development
  4. What is HTTP? GET, POST, status codes (200, 401, 404, 500)
  5. What is JSON? How to parse and create it
  6. FastAPI — https://fastapi.tiangolo.com/tutorial/
  7. React — https://react.dev/learn (official tutorial, very good)

## Level 3 — Database & Auth
  8. SQL basics — SELECT, INSERT, WHERE, JOIN
  9. SQLAlchemy ORM — https://docs.sqlalchemy.org/
  10. How JWT works — https://jwt.io/ (paste a token here to decode it!)
  11. Password hashing — why bcrypt, why not MD5 or SHA1

## Level 4 — Data Science & AI (Most Exciting!)
  12. NumPy — arrays, math operations — https://numpy.org/learn/
  13. Pandas — DataFrames, CSV, groupby — https://pandas.pydata.org/docs/
  14. Linear Regression — the math behind it (slope, intercept, residuals)
  15. Scikit-learn — https://scikit-learn.org/stable/getting_started.html
  16. IsolationForest specifically:
      https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html

## Level 5 — Advanced Topics in This Project
  17. CORS — why it exists and how to configure it
  18. React Context API — sharing state without prop-drilling
  19. React Router — client-side routing in SPAs
  20. Recharts — https://recharts.org/en-US/examples
  21. Vite proxy — https://vite.dev/config/server-options#server-proxy

---

# PART 16: PRACTICAL EXERCISES TO UNDERSTAND THE PROJECT

Do these one by one. Each one will teach you something:

EXERCISE 1: Open http://localhost:8000/docs
  → This is Swagger UI — auto-generated API documentation.
  → Try the /auth/register endpoint directly from the browser.
  → See exactly what JSON goes in and what comes back.

EXERCISE 2: Try the API with curl (command line HTTP client):
  → curl http://localhost:8000/
  → You'll see {"status": "ok", "service": "FinOps AI backend"}

EXERCISE 3: Decode a JWT token
  → Login in the app → open DevTools (F12) → Application tab → Local Storage
  → Copy the "finops_token" value → paste it at https://jwt.io/
  → See what data is stored inside (your email and expiry time)

EXERCISE 4: Open the database directly
  → Install "DB Browser for SQLite": https://sqlitebrowser.org/
  → Open backend/finops.db
  → Browse the "users" and "billing_records" tables
  → See your actual data in the database

EXERCISE 5: Read the sample CSV
  → Open backend/sample_billing_data.csv in Excel or a text editor
  → Look at the columns: date, service, resource_id, cost, etc.
  → This is the exact format the upload expects

EXERCISE 6: Add a print() to the backend
  → Open backend/routers/insights_router.py
  → Add: print("Prediction requested!")  somewhere in the predict endpoint
  → Check the terminal where uvicorn is running
  → You'll see the message every time you click "Get Predictions"

EXERCISE 7: Break something on purpose
  → Remove a column from the sample CSV
  → Try to upload it → see what error the backend returns
  → This shows you how validation works

---

# SUMMARY — The Architecture in One Picture

    BROWSER (Chrome/Firefox)
         │
         │  User visits http://localhost:5173
         ▼
    VITE DEV SERVER (port 5173)
    - Serves React app (JavaScript files)
    - Proxies /auth, /billing, /costs, /ai requests to port 8000
         │
         │  API calls (HTTP + JSON + JWT token)
         ▼
    UVICORN (port 8000)
    - ASGI server, receives HTTP requests
         │
         ▼
    FASTAPI APPLICATION (main.py)
    - Routes requests to correct router
    - Validates JWT tokens (auth.py)
         │
         ├──► auth_router.py    → Register/Login → SQLite (users table)
         │
         ├──► upload_router.py  → Parse CSV → SQLite (billing_records table)
         │
         ├──► costs_router.py   → Query SQLite → Return cost summaries
         │
         └──► insights_router.py
                   │
                   ├──► waste_detection.py
                   │    ├── Rule Engine (idle, oversized, storage)
                   │    └── IsolationForest ML (anomalies)
                   │
                   └──► cost_prediction.py
                        └── Linear Regression (numpy polyfit)

---

You built something genuinely impressive.
Now take the time to understand it — one file at a time.
The more you understand, the more you can improve it.

Good luck on your learning journey!
