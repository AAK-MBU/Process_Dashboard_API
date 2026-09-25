-- Indexes for listing, filtering and sorting runs across processes
-- (GET /api/v1/runs/ and GET /api/v1/runs/overview).
--
-- Not applied at startup on purpose: tables come from SQLModel's create_all,
-- which never adds indexes to a table that already exists, and building these
-- on a large production table takes locks. Run this by hand, off-peak:
--
--   sqlcmd -S <server> -d <database> -U <user> -P <password> -C -i scripts/create_run_indexes.sql
--
-- Idempotent: each index is created only if an index of that name is missing.

-- Newest-first per process: the default sort, with or without a process filter.
IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_run_process_id_created_at'
                 AND object_id = OBJECT_ID('dbo.process_run'))
    CREATE INDEX ix_process_run_process_id_created_at
        ON dbo.process_run (process_id, created_at);

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_run_created_at'
                 AND object_id = OBJECT_ID('dbo.process_run'))
    CREATE INDEX ix_process_run_created_at ON dbo.process_run (created_at);

-- started_after / started_before / finished_after / finished_before, and sorting on them.
IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_run_started_at'
                 AND object_id = OBJECT_ID('dbo.process_run'))
    CREATE INDEX ix_process_run_started_at ON dbo.process_run (started_at);

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_run_finished_at'
                 AND object_id = OBJECT_ID('dbo.process_run'))
    CREATE INDEX ix_process_run_finished_at ON dbo.process_run (finished_at);

-- Loading a page's step runs (the overview's selectinload) and the step list of a run.
IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_step_run_run_id'
                 AND object_id = OBJECT_ID('dbo.process_step_run'))
    CREATE INDEX ix_process_step_run_run_id ON dbo.process_step_run (run_id);

-- failed_at: "runs where this step failed".
IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'ix_process_step_run_step_id_status'
                 AND object_id = OBJECT_ID('dbo.process_step_run'))
    CREATE INDEX ix_process_step_run_step_id_status
        ON dbo.process_step_run (step_id, status) INCLUDE (run_id);
