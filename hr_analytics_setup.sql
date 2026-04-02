-- Ensure we are in the right database
-- In pgAdmin, make sure you have selected 'hr_analytics' as your active database.

-- 0. Setup Schema and Extensions
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS hr_employees (
    emp_id INT PRIMARY KEY,
    name VARCHAR(100),
    department VARCHAR(50),
    salary DECIMAL(10, 2),
    hire_date DATE
);

CREATE TABLE IF NOT EXISTS hr_feedback (
    feedback_id SERIAL PRIMARY KEY,
    emp_id INT REFERENCES hr_employees(emp_id),
    feedback_text TEXT,
    embedding vector(3) -- Using 3 dimensions for this demo
);

-- 1. Clear existing data to avoid primary key conflicts
-- We use TRUNCATE to quickly wipe the tables before the 10k reload
TRUNCATE TABLE hr_feedback CASCADE;
TRUNCATE TABLE hr_employees CASCADE;

-- 2. Generate 10,000 Employees
INSERT INTO hr_employees (emp_id, name, department, salary, hire_date)
SELECT 
    gs AS emp_id,
    -- Randomly pick a name from a list of first and last names
    (ARRAY['Alice', 'Bob', 'Charlie', 'Diana', 'Evan', 'Fiona', 'George', 'Hannah', 'Ian', 'Julia'])[floor(random() * 10 + 1)] || ' ' ||
    (ARRAY['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez'])[floor(random() * 10 + 1)] AS name,
    -- Randomly assign one of five departments
    (ARRAY['Engineering', 'HR', 'Marketing', 'Finance', 'Sales'])[floor(random() * 5 + 1)] AS department,
    -- Randomize salary between 50k and 150k
    ROUND((random() * 100000 + 50000)::numeric, 2) AS salary,
    -- Randomize hire date over the last 5 years
    CURRENT_DATE - (random() * 1825)::int AS hire_date
FROM generate_series(1001, 11000) AS gs;

-- 3. Generate 5,000 Feedback Records
-- We give feedback to about half the employees
INSERT INTO hr_feedback (emp_id, feedback_text, embedding)
SELECT 
    emp_id,
    -- Randomly pick a sentiment
    (ARRAY[
        'Exceeding expectations in current role.',
        'Requested more training on cloud architecture.',
        'Feeling slightly burnt out with the current sprint cycle.',
        'Compensation is fair, but looking for more leadership opportunities.',
        'Great team player, very reliable during deadlines.',
        'Struggling with work-life balance since the project launch.',
        'Excellent technical skills, needs to work on communication.',
        'Very happy with the recent bonus structure.'
    ])[floor(random() * 8 + 1)] AS feedback_text,
    -- Generate a random 3-dimensional vector for testing
    -- Format: [val1, val2, val3]
    ('[' || random() || ',' || random() || ',' || random() || ']')::vector AS embedding
FROM hr_employees
WHERE random() < 0.5; -- Assign feedback to roughly 50% of employees

-- 4. Verify the counts
SELECT 
    (SELECT COUNT(*) FROM hr_employees) AS total_employees,
    (SELECT COUNT(*) FROM hr_feedback) AS total_feedback_records;