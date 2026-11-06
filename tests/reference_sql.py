"""
Hand-written reference queries, keyed by the exact question text.
run_evals.py runs both the model's SQL and the reference SQL, then checks that
every reference value appears in the model's result. Questions with no entry
here keep the row-count check only.
Add entries only after confirming the reference query by hand in SQL Developer / pgAdmin / SSMS.
"""
REFERENCE = {
    "How many employees are there?":
        ("HR", "SELECT COUNT(*) AS employee_count FROM hr_employees"),
    "What is the highest salary across all employees?":
        ("HR", "SELECT MAX(salary) AS max_salary FROM hr_employees"),
    "What is the average salary across all employees?":
        ("HR", "SELECT AVG(salary) AS avg_salary FROM hr_employees"),
}
