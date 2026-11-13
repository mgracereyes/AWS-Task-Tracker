-- =============================================================================
-- AWS Task Tracker - Database Schema v1.3 (PostgreSQL 16+)
-- Matches Database_Schema_v1.3 (15 tables), Requirements v1.2 (FR-001 to FR-035)
-- and Technical Documentation v1.3.
-- Updated: 2026-11-10
--
-- Run on an empty database:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f AWS_Task_Tracker_Schema_v1.3.sql
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. users - everyone who signs in with Google (@awsys-i.com)    FR-001 to FR-004, FR-015
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    user_id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    google_account  VARCHAR(255) NOT NULL,
    user_name       VARCHAR(150) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'employee'
                    CHECK (role IN ('employee', 'team_lead', 'manager', 'admin')),
    team_lead_id    INT REFERENCES users (user_id) ON DELETE SET NULL,
    active_flag     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_date    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT users_company_domain CHECK (lower(google_account) LIKE '%@awsys-i.com'),
    CONSTRAINT users_not_own_lead   CHECK (team_lead_id IS NULL OR team_lead_id <> user_id)
);
CREATE UNIQUE INDEX users_google_account_uk ON users (lower(google_account));
CREATE INDEX users_team_lead_idx ON users (team_lead_id);

-- -----------------------------------------------------------------------------
-- 2. project_templates - predefined and saved templates           FR-016, FR-030
-- -----------------------------------------------------------------------------
CREATE TABLE project_templates (
    template_id        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_name      VARCHAR(150) NOT NULL,
    category           VARCHAR(100),
    version            INT          NOT NULL DEFAULT 1,
    owner_id           INT REFERENCES users (user_id),              -- saved by (NULL = predefined)
    sharing            VARCHAR(10)  NOT NULL DEFAULT 'only_me'
                       CHECK (sharing IN ('only_me', 'my_team', 'everyone')),
    approval_status    VARCHAR(10)  NOT NULL DEFAULT 'not_needed'
                       CHECK (approval_status IN ('not_needed', 'pending', 'approved', 'rejected')),
    approved_by        INT REFERENCES users (user_id),              -- Manager
    approved_date      TIMESTAMPTZ,
    source_project_id  INT,                                         -- FK added below (NULL = predefined)
    active_flag        BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_by         INT REFERENCES users (user_id),
    updated_date       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT templates_everyone_needs_approval CHECK (
        sharing <> 'everyone' OR approval_status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT templates_approval_complete CHECK (
        approval_status <> 'approved' OR (approved_by IS NOT NULL AND approved_date IS NOT NULL))
);
CREATE INDEX project_templates_owner_idx ON project_templates (owner_id);

-- -----------------------------------------------------------------------------
-- 3. template_tasks - tasks and items inside a template
--    parent_id NULL = task; parent_id set = item of that task
-- -----------------------------------------------------------------------------
CREATE TABLE template_tasks (
    template_task_id  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_id       INT NOT NULL REFERENCES project_templates (template_id) ON DELETE CASCADE,
    parent_id         INT REFERENCES template_tasks (template_task_id) ON DELETE CASCADE,
    name              VARCHAR(150) NOT NULL,
    sort_order        INT NOT NULL DEFAULT 0
);
CREATE INDEX template_tasks_template_idx ON template_tasks (template_id);
CREATE INDEX template_tasks_parent_idx   ON template_tasks (parent_id);

-- -----------------------------------------------------------------------------
-- 4. projects                                                     FR-005, FR-017, FR-029
-- -----------------------------------------------------------------------------
CREATE TABLE projects (
    project_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_name  VARCHAR(150) NOT NULL,
    description   TEXT,
    template_id   INT REFERENCES project_templates (template_id) ON DELETE SET NULL,  -- NULL = blank project
    owner_id      INT REFERENCES users (user_id),
    visibility    VARCHAR(10) NOT NULL DEFAULT 'public'
                  CHECK (visibility IN ('public', 'private')),
    active_flag   BOOLEAN     NOT NULL DEFAULT TRUE,                -- FALSE = archived
    created_by    INT REFERENCES users (user_id),
    created_date  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX projects_name_uk ON projects (lower(project_name));

ALTER TABLE project_templates
    ADD CONSTRAINT project_templates_source_project_fk
    FOREIGN KEY (source_project_id) REFERENCES projects (project_id) ON DELETE SET NULL;

-- -----------------------------------------------------------------------------
-- 5. project_members - membership, role on project and dates      FR-007, FR-031, FR-032
-- -----------------------------------------------------------------------------
CREATE TABLE project_members (
    project_member_id  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id         INT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    user_id            INT NOT NULL REFERENCES users (user_id),
    role_on_project    VARCHAR(50),                                 -- Developer, Designer, QA, Support...
    start_date         DATE,
    end_date           DATE,
    added_by           INT REFERENCES users (user_id),              -- Manager or Team Lead
    active_flag        BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT project_members_uk UNIQUE (project_id, user_id),
    CONSTRAINT project_members_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
CREATE INDEX project_members_user_idx ON project_members (user_id);

-- -----------------------------------------------------------------------------
-- 6. tasks                                                        FR-006, FR-017, FR-034
-- -----------------------------------------------------------------------------
CREATE TABLE tasks (
    task_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id       INT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    task_name        VARCHAR(150) NOT NULL,
    planned_minutes  INT NOT NULL DEFAULT 0 CHECK (planned_minutes >= 0),  -- sum of items
    from_template    BOOLEAN NOT NULL DEFAULT FALSE,
    active_flag      BOOLEAN NOT NULL DEFAULT TRUE,
    created_date     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX tasks_name_uk ON tasks (project_id, lower(task_name));

-- -----------------------------------------------------------------------------
-- 7. items                                                        FR-006, FR-017, FR-034
-- -----------------------------------------------------------------------------
CREATE TABLE items (
    item_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id          INT NOT NULL REFERENCES tasks (task_id) ON DELETE CASCADE,
    item_name        VARCHAR(150) NOT NULL,
    work_type        VARCHAR(10) NOT NULL DEFAULT 'task'
                     CHECK (work_type IN ('task', 'meeting')),      -- blue / orange bars
    planned_minutes  INT NOT NULL DEFAULT 0 CHECK (planned_minutes >= 0),
    from_template    BOOLEAN NOT NULL DEFAULT FALSE,
    active_flag      BOOLEAN NOT NULL DEFAULT TRUE,                 -- FALSE = archived
    created_date     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX items_name_uk ON items (task_id, lower(item_name));

-- -----------------------------------------------------------------------------
-- 8. daily_task_logs - Activity timeline: work entries and breaks FR-018, FR-019, FR-020
-- -----------------------------------------------------------------------------
CREATE TABLE daily_task_logs (
    log_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users (user_id),
    item_id         INT REFERENCES items (item_id),                 -- NULL for a break
    log_date        DATE NOT NULL,
    entry_type      VARCHAR(5) NOT NULL DEFAULT 'work'
                    CHECK (entry_type IN ('work', 'break')),
    start_time      TIME NOT NULL,
    end_time        TIME,                                           -- NULL while running
    effort_minutes  INT CHECK (effort_minutes BETWEEN 0 AND 1440),
    description     TEXT,
    remarks         TEXT,
    start_date      DATE NOT NULL,
    end_date        DATE,
    created_date    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      INT REFERENCES users (user_id),                 -- self, or Admin correction
    updated_date    TIMESTAMPTZ,
    CONSTRAINT logs_item_for_work CHECK (
        (entry_type = 'work' AND item_id IS NOT NULL) OR (entry_type = 'break' AND item_id IS NULL)),
    CONSTRAINT logs_end_after_start CHECK (
        end_date IS NULL OR end_time IS NULL
        OR (end_date + end_time) > (start_date + start_time)),
    CONSTRAINT logs_running_has_no_end CHECK (end_time IS NOT NULL OR end_date IS NULL)
);
CREATE INDEX daily_task_logs_user_date_idx ON daily_task_logs (user_id, log_date);
CREATE INDEX daily_task_logs_item_idx      ON daily_task_logs (item_id);
CREATE INDEX daily_task_logs_date_idx      ON daily_task_logs (log_date);
-- Only one running entry per person
CREATE UNIQUE INDEX daily_task_logs_one_running ON daily_task_logs (user_id) WHERE end_time IS NULL;

-- -----------------------------------------------------------------------------
-- 9. leave_requests - VL / SL, whole or half day                  FR-024
-- -----------------------------------------------------------------------------
CREATE TABLE leave_requests (
    leave_id        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users (user_id),
    leave_type      VARCHAR(2) NOT NULL CHECK (leave_type IN ('VL', 'SL')),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    day_part        VARCHAR(5) NOT NULL DEFAULT 'whole' CHECK (day_part IN ('whole', 'half')),
    hours_credited  NUMERIC(5,2) NOT NULL CHECK (hours_credited >= 0),
    status          VARCHAR(10) NOT NULL DEFAULT 'filed'
                    CHECK (status IN ('filed', 'cancelled')),
    created_date    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT leave_dates CHECK (end_date >= start_date),
    CONSTRAINT leave_half_is_one_day CHECK (day_part = 'whole' OR start_date = end_date)
);
CREATE INDEX leave_requests_user_idx ON leave_requests (user_id, start_date);

-- -----------------------------------------------------------------------------
-- 10. timesheet_locks - locked date ranges                        FR-025
-- -----------------------------------------------------------------------------
CREATE TABLE timesheet_locks (
    lock_id       INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    locked_by     INT NOT NULL REFERENCES users (user_id),
    lock_reason   TEXT,
    created_date  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT locks_dates CHECK (end_date >= start_date)
);
CREATE INDEX timesheet_locks_range_idx ON timesheet_locks (start_date, end_date);

-- -----------------------------------------------------------------------------
-- 11. unlock_requests - request to unlock a day                   FR-026, FR-011
-- -----------------------------------------------------------------------------
CREATE TABLE unlock_requests (
    request_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES users (user_id),
    lock_id       INT NOT NULL REFERENCES timesheet_locks (lock_id) ON DELETE CASCADE,
    request_date  DATE NOT NULL,                                    -- the locked day
    action_type   VARCHAR(6) NOT NULL CHECK (action_type IN ('add', 'edit', 'delete')),
    reason        TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    details       TEXT,
    approver_id   INT REFERENCES users (user_id),                   -- shown in the modal
    status        VARCHAR(10) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'allowed', 'declined', 'expired')),
    created_date  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '72 hours'),
    decided_by    INT REFERENCES users (user_id),
    decided_date  TIMESTAMPTZ,
    CONSTRAINT unlock_decision_complete CHECK (
        status IN ('pending', 'expired') OR (decided_by IS NOT NULL AND decided_date IS NOT NULL))
);
CREATE INDEX unlock_requests_status_idx ON unlock_requests (status, expires_at);
CREATE INDEX unlock_requests_user_idx   ON unlock_requests (user_id, request_date);

-- -----------------------------------------------------------------------------
-- 12. lock_overrides - an allowed request opens one day for 72 hours   FR-026, FR-027
-- -----------------------------------------------------------------------------
CREATE TABLE lock_overrides (
    override_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id     INT NOT NULL UNIQUE REFERENCES unlock_requests (request_id) ON DELETE CASCADE,
    user_id        INT NOT NULL REFERENCES users (user_id),
    unlocked_date  DATE NOT NULL,
    expiry_date    TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '72 hours'),
    approved_by    INT NOT NULL REFERENCES users (user_id),
    revoked_by     INT REFERENCES users (user_id),
    revoked_date   TIMESTAMPTZ
);
CREATE INDEX lock_overrides_user_day_idx ON lock_overrides (user_id, unlocked_date);

-- -----------------------------------------------------------------------------
-- 13. notifications                                               FR-011, FR-022
-- -----------------------------------------------------------------------------
CREATE TABLE notifications (
    notification_id  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          INT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    type             VARCHAR(20) NOT NULL CHECK (type IN (
                         'under_8h', 'locked_day', 'unlock_decision',
                         'lock_verification', 'template_approval')),
    link             VARCHAR(255),                                  -- day record or Locks
    related_date     DATE,
    message          TEXT NOT NULL,
    read_flag        BOOLEAN NOT NULL DEFAULT FALSE,
    created_date     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notifications_unread_idx ON notifications (user_id, read_flag, created_date DESC);

-- -----------------------------------------------------------------------------
-- 14. export_files - XLSX / CSV exports                           FR-013, FR-035
-- -----------------------------------------------------------------------------
CREATE TABLE export_files (
    export_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES users (user_id),
    format        VARCHAR(4) NOT NULL CHECK (format IN ('XLSX', 'CSV')),
    source        VARCHAR(20) NOT NULL DEFAULT 'report'
                  CHECK (source IN ('report', 'dashboard', 'filter_results', 'lock_history')),
    filters       JSONB,
    file_path     VARCHAR(500),
    row_count     INT CHECK (row_count >= 0),
    created_date  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX export_files_user_idx ON export_files (user_id, created_date DESC);

-- -----------------------------------------------------------------------------
-- 15. audit_logs - append-only                                    FR-014, FR-019, NFR-005
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    audit_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id      INT REFERENCES users (user_id),                   -- NULL for system jobs / denied logins
    action        VARCHAR(50) NOT NULL,
    target_table  VARCHAR(50),
    target_id     INT,
    reason        TEXT,                                             -- required for locked-day edits and corrections
    old_value     JSONB,                                            -- change history
    new_value     JSONB,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    details       JSONB
);
CREATE INDEX audit_logs_target_idx ON audit_logs (target_table, target_id);
CREATE INDEX audit_logs_actor_idx  ON audit_logs (actor_id, timestamp DESC);

-- Audit rows can be added but never changed or removed (TC: audit log cannot be changed)
CREATE FUNCTION audit_logs_block_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only';
END;
$$;
CREATE TRIGGER audit_logs_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_block_change();
CREATE TRIGGER audit_logs_no_truncate
    BEFORE TRUNCATE ON audit_logs
    FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_block_change();

-- -----------------------------------------------------------------------------
-- Table comments
-- -----------------------------------------------------------------------------
COMMENT ON TABLE users             IS 'Google-signed-in users, role and team lead (FR-001 to FR-004, FR-015)';
COMMENT ON TABLE project_templates IS 'Predefined and saved templates; sharing Everyone needs Manager approval (FR-016, FR-030)';
COMMENT ON TABLE template_tasks    IS 'Template tasks and items; parent_id NULL = task, set = item';
COMMENT ON TABLE projects          IS 'Projects, blank or from a template; Public or Private (FR-005, FR-029)';
COMMENT ON TABLE project_members   IS 'Project membership with role on project and start/end dates (FR-007, FR-031, FR-032)';
COMMENT ON TABLE tasks             IS 'Tasks of a project (FR-006, FR-017)';
COMMENT ON TABLE items             IS 'Items of a task; task or meeting, planned effort (FR-006, FR-034)';
COMMENT ON TABLE daily_task_logs   IS 'Activity timeline: work entries and breaks (FR-018, FR-019, FR-020)';
COMMENT ON TABLE leave_requests    IS 'VL/SL leave, whole or half day (FR-024)';
COMMENT ON TABLE timesheet_locks   IS 'Locked date ranges (FR-025)';
COMMENT ON TABLE unlock_requests   IS 'Requests to unlock a locked day; expire after 72 hours (FR-026)';
COMMENT ON TABLE lock_overrides    IS 'Allowed request: one day open for one person for 72 hours (FR-026, FR-027)';
COMMENT ON TABLE notifications     IS 'In-app notifications (FR-011, FR-022)';
COMMENT ON TABLE export_files      IS 'XLSX/CSV exports (FR-013, FR-035)';
COMMENT ON TABLE audit_logs        IS 'Append-only audit trail (FR-014, NFR-005)';

COMMIT;
