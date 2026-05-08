# Employee API

FastAPI backend for SQL Server (EmployeeDB) with:
- GET /employees
- GET /employees/{id}

## Setup

1) Create and activate a virtual environment.
2) Install dependencies:

```powershell
pip install -r requirements.txt
```

3) Copy .env.example to .env and adjust if needed.

## Run

```powershell
uvicorn app.main:app --reload
```

## Notes

- Requires SQL Server ODBC Driver 17 (or update MSSQL_DRIVER to 18 if installed).
- Uses Windows Authentication by default.
