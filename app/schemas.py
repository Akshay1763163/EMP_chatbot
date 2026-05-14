from datetime import date
from pydantic import BaseModel


class EmployeeOut(BaseModel):
    id: int
    name: str
    joined_date: date
    salary: float
    role: str
    department: str
    active: bool
    date_of_resign: date | None = None


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    results: list[dict] = []
    sql: str | None = None
