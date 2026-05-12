SCHEMAS = {
    "employees": """
Table: dbo.Employees
Columns:
- id (int, primary key)
- name (varchar) - full name of the employee
- joined_date (date) - date the employee joined
- salary (decimal) - monthly salary
- role (varchar) - job title e.g. HR Manager, Software Engineer, CTO
- department (varchar) - HR, IT, Finance, Marketing, Sales, Management
- active (bit) - 1 = current employee, 0 = ex-employee
- date_of_resign (date, nullable) - null if still employed

Rules:
- Always use LIKE '%value%' for name searches, never = for names
- Use active = 1 for current employees, active = 0 for ex-employees
- date_of_resign is NULL for active employees
- Only SELECT statements are allowed
"""
}
