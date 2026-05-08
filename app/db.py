import os
import pyodbc


def _build_conn_str() -> str:
    conn_str = os.getenv("MSSQL_CONN_STR")
    if conn_str:
        return conn_str

    server = os.getenv("MSSQL_SERVER", "localhost")
    database = os.getenv("MSSQL_DATABASE", "EmployeeDB")
    driver = os.getenv("MSSQL_DRIVER", "{ODBC Driver 17 for SQL Server}")
    trusted = os.getenv("MSSQL_TRUSTED_CONNECTION", "yes").lower()

    if trusted in {"1", "true", "yes"}:
        return f"Driver={driver};Server={server};Database={database};Trusted_Connection=yes;"

    user = os.getenv("MSSQL_USER", "")
    password = os.getenv("MSSQL_PASSWORD", "")
    return (
        f"Driver={driver};Server={server};Database={database};"
        f"UID={user};PWD={password};"
    )


def get_connection() -> pyodbc.Connection:
    conn_str = _build_conn_str()
    return pyodbc.connect(conn_str)


def _row_to_employee(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "joined_date": row.joined_date,
        "salary": float(row.salary),
        "role": row.role,
        "department": row.department,
        "active": bool(row.active),
        "date_of_resign": row.date_of_resign,
    }


def fetch_employee_by_id(employee_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, joined_date, salary, role, department, active, date_of_resign
            FROM dbo.Employees
            WHERE id = ?
            """,
            employee_id,
        )
        row = cursor.fetchone()

    if not row:
        return None

    return _row_to_employee(row)


def run_select_query(sql: str) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({column: value for column, value in zip(columns, row)})

    return results
