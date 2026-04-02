-- Create the Database
CREATE DATABASE HealthcareClaims;
GO

USE HealthcareClaims;
GO

-- Create Claims Table
CREATE TABLE Claims (
    ClaimID INT PRIMARY KEY IDENTITY(1,1),
    MemberID VARCHAR(20),
    ServiceDate DATE,
    ProviderName VARCHAR(100),
    DiagnosisCode VARCHAR(10), -- e.g., ICD-10
    ProcedureCode VARCHAR(10),
    BilledAmount DECIMAL(10, 2),
    PaidAmount DECIMAL(10, 2),
    ClaimStatus VARCHAR(20) -- Approved, Denied, Pending
);
GO

-- Generate 10,000 Sample Records
SET NOCOUNT ON;
DECLARE @Counter INT = 1;
DECLARE @Status VARCHAR(20);
DECLARE @Billed DECIMAL(10,2);
DECLARE @Paid DECIMAL(10,2);
DECLARE @RandomDays INT;

WHILE @Counter <= 10000
BEGIN
    -- Randomly determine status (weighted: 70% Approved, 20% Denied, 10% Pending)
    SET @Status = CASE 
        WHEN ABS(CHECKSUM(NEWID())) % 10 < 7 THEN 'Approved'
        WHEN ABS(CHECKSUM(NEWID())) % 10 < 9 THEN 'Denied'
        ELSE 'Pending'
    END;

    -- Randomize Billed Amount between $50 and $5000
    SET @Billed = (ABS(CHECKSUM(NEWID())) % 4950) + 50;
    
    -- Paid amount is usually a percentage if approved, 0 if denied
    SET @Paid = CASE 
        WHEN @Status = 'Approved' THEN @Billed * (0.7 + (ABS(CHECKSUM(NEWID())) % 20) / 100.0)
        ELSE 0 
    END;

    -- Randomize Service Date within the year 2024
    SET @RandomDays = ABS(CHECKSUM(NEWID())) % 366;

    INSERT INTO Claims (
        MemberID, 
        ServiceDate, 
        ProviderName, 
        DiagnosisCode, 
        ProcedureCode, 
        BilledAmount, 
        PaidAmount, 
        ClaimStatus
    )
    VALUES (
        'MEM-' + CAST((ABS(CHECKSUM(NEWID())) % 5000 + 1000) AS VARCHAR),
        DATEADD(DAY, @RandomDays, '2024-01-01'),
        CASE (ABS(CHECKSUM(NEWID())) % 5)
            WHEN 0 THEN 'City General Hospital'
            WHEN 1 THEN 'Valley Health Clinic'
            WHEN 2 THEN 'Metro Imaging'
            WHEN 3 THEN 'Orthopedic Specialists'
            ELSE 'Northside Family Practice'
        END,
        CASE (ABS(CHECKSUM(NEWID())) % 4)
            WHEN 0 THEN 'J45.909'
            WHEN 1 THEN 'E11.9'
            WHEN 2 THEN 'M54.5'
            ELSE 'S82.001A'
        END,
        CASE (ABS(CHECKSUM(NEWID())) % 4)
            WHEN 0 THEN '99214'
            WHEN 1 THEN '99213'
            WHEN 2 THEN '72141'
            ELSE '27447'
        END,
        @Billed,
        @Paid,
        @Status
    );

    SET @Counter = @Counter + 1;
END
GO

-- Verify Count
SELECT COUNT(*) AS TotalClaims FROM Claims;
GO


	-- STEP 1: Create a Login at the Server Level
-- Run this in a "New Query" window while connected to your 'DOG' server
USE [master];
GO

-- Create the login 'bi_engine_user' with a strong password
-- Replace 'YourStrongPassword123!' with the password you want in your .env file
CREATE LOGIN [bi_engine_user] WITH PASSWORD = N'Baloo100!!ss', 
    CHECK_EXPIRATION = OFF, 
    CHECK_POLICY = OFF;
GO


-- STEP 2: Create a User in the Specific Database
-- This maps the server login to your healthcare database
USE [HealthcareClaims];
GO

CREATE USER [bi_engine_user] FOR LOGIN [bi_engine_user];
GO


-- STEP 3: Grant Permissions
-- We give the user permission to read and write to the Claims table
GRANT SELECT, INSERT, UPDATE TO [bi_engine_user];
GO

-- To be safe, verify the user can see the table
-- EXEC AS USER = 'bi_engine_user';
-- SELECT TOP 5 * FROM Claims;
-- REVERT;

-- --- NEW: PERFORMANCE & DATA SYNCING ---

-- STEP 4: Optimization (Fix the 10-second lag)
-- Creating a non-clustered index on MemberID allows the engine 
-- to find specific employees in milliseconds instead of seconds.
CREATE INDEX IX_Claims_MemberID ON Claims (MemberID);
GO


-- STEP 5: Data Syncing (Fix the $0.00 result)
-- Currently, Postgres uses IDs like '1001' while SQL Server uses 'MEM-xxxx'.
-- Let's force the first 100 claims to match Postgres IDs so the report works.
UPDATE TOP (100) Claims
SET MemberID = CAST((1000 + (ClaimID % 100)) AS VARCHAR(20));
GO

-- Verify the update
SELECT TOP 5 MemberID, BilledAmount FROM Claims WHERE MemberID LIKE '100%';
GO