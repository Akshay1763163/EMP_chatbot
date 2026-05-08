import os

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from .db import fetch_employee_by_id, run_select_query
from .schemas import ChatRequest, ChatResponse, EmployeeOut

load_dotenv()

app = FastAPI(title="Employee API")
sql_llm: ChatGroq | None = None


def _sanitize_sql(sql: str) -> str | None:
    if not sql or not isinstance(sql, str):
        return None

    cleaned = sql.strip().rstrip(";")
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if not lowered.startswith("select"):
        return None

    blocked = ["insert", "update", "delete", "drop", "alter", "truncate", "exec", "merge"]
    if any(keyword in lowered for keyword in blocked):
        return None

    if "dbo.employees" not in lowered:
        return None

    return cleaned


def _generate_sql(question: str) -> str:
    prompt = (
        "You write a single SELECT query for SQL Server. "
        "Only use the table dbo.Employees with columns id, name, joined_date, salary, role, department, active, date_of_resign. "
        "Return SQL only, no markdown, no explanation. "
        "If the question asks for employees, select id, name, joined_date, salary, role, department, active, date_of_resign. "
        f"Question: {question}"
    )
    response = sql_llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


@tool
def query_employees_nl(question: str) -> dict:
    """Generate and run a safe SELECT query against dbo.Employees."""
    if not sql_llm:
        return {"error": "GROQ_API_KEY is not set."}

    sql = _generate_sql(question)
    if not sql or not isinstance(sql, str):
        return {"error": "Generated SQL was empty."}
    safe_sql = _sanitize_sql(sql)
    if not safe_sql:
        return {"error": "Generated SQL did not pass safety checks."}

    try:
        rows = run_select_query(safe_sql)
    except Exception as exc:
        return {"error": f"Query failed: {exc}"}

    return {"sql": safe_sql, "rows": rows}


def _build_agent() -> AgentExecutor | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, api_key=api_key)
    global sql_llm
    sql_llm = llm
    tools = [query_employees_nl]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
            "system",
            "You are an HR assistant. Use ONLY the provided tools to answer questions about employees. "
            "The employee table has these columns: id, name, joined_date, salary, role, department, active, date_of_resign. "
            "active = 1 means current employee, active = 0 means ex-employee. "

            "Always call query_employees_nl for any user question. "

            "Call each tool only ONCE. "
            "Never retry the same tool twice. "
            "If no records match, say so in a friendly sentence. "
            "Do not describe tool calls or internal steps. "
            "Answer directly using the tool results only.",
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        return_intermediate_steps=True,
    )


agent_executor = _build_agent()


def _extract_employees(steps: list[tuple]) -> list[dict]:
    results = []
    seen_ids = set()

    if steps is None:
        return results
    if not steps:
        return results

    for _, observation in steps:
        if isinstance(observation, dict):
            if "rows" in observation and isinstance(observation["rows"], list):
                for item in observation["rows"]:
                    if isinstance(item, dict) and {
                        "id",
                        "name",
                        "joined_date",
                        "salary",
                    }.issubset(item.keys()):
                        employee_id = item.get("id")
                        if employee_id not in seen_ids:
                            seen_ids.add(employee_id)
                            results.append(item)
                continue
            if {
                "id",
                "name",
                "joined_date",
                "salary",
            }.issubset(observation.keys()):
                employee_id = observation.get("id")
                if employee_id not in seen_ids:
                    seen_ids.add(employee_id)
                    results.append(observation)
        elif isinstance(observation, list):
            for item in observation:
                if isinstance(item, dict) and {
                    "id",
                    "name",
                    "joined_date",
                    "salary",
                }.issubset(item.keys()):
                    employee_id = item.get("id")
                    if employee_id not in seen_ids:
                        seen_ids.add(employee_id)
                        results.append(item)

    return results


def _extract_sql(steps: list[tuple]) -> str | None:
    if not steps:
        return None

    for _, observation in steps:
        if isinstance(observation, dict) and observation.get("sql"):
            return observation["sql"]

    return None


@app.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int):
    employee = fetch_employee_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    if not agent_executor:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set. Add it to the .env file and restart the server.",
        )

    try:
        result = agent_executor.invoke({"input": payload.message})
    except Exception as exc:
        error_text = str(exc).lower()
        if "rate limit" in error_text or "429" in error_text:
            return ChatResponse(
                reply="The AI service rate limit has been reached. Please wait a moment and try again.",
                results=[],
                sql=None,
            )
        return ChatResponse(
            reply=f"Sorry, I ran into an error: {exc}",
            results=[],
            sql=None,
        )

    reply = result.get("output", "")
    steps = result.get("intermediate_steps", [])
    results = _extract_employees(steps)
    sql = _extract_sql(steps)
    return ChatResponse(reply=reply, results=results, sql=sql)
