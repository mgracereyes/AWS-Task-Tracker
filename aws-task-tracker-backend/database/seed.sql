-- Sample data for development and testing (the same people and projects as the mockups).
-- Run on an empty database after schema.sql and migrations. Never run in production.
BEGIN;

INSERT INTO users (google_account, user_name, role, business_unit) VALUES
  ('fay.ong@awsys-i.com',      'Fay Ong',      'admin',     'Admin'),
  ('eli.park@awsys-i.com',     'Eli Park',     'manager',   'Dev C'),
  ('dana.lopez@awsys-i.com',   'Dana Lopez',   'team_lead', 'Dev C'),
  ('mia.cruz@awsys-i.com',     'Mia Cruz',     'team_lead', 'Dev C'),
  ('sam.reyes@awsys-i.com',    'Sam Reyes',    'team_lead', 'Dev C');

INSERT INTO users (google_account, user_name, role, team_lead_id, business_unit, active_flag)
SELECT v.email, v.name, 'employee', l.user_id, 'Dev C', v.active
FROM (VALUES
  ('aisha.rahman@awsys-i.com', 'Aisha Rahman', 'dana.lopez@awsys-i.com', TRUE),
  ('ben.ortiz@awsys-i.com',    'Ben Ortiz',    'dana.lopez@awsys-i.com', TRUE),
  ('jo.tan@awsys-i.com',       'Jo Tan',       'dana.lopez@awsys-i.com', TRUE),
  ('raf.cruz@awsys-i.com',     'Raf Cruz',     'dana.lopez@awsys-i.com', TRUE),
  ('lea.sison@awsys-i.com',    'Lea Sison',    'mia.cruz@awsys-i.com',   TRUE),
  ('tom.lim@awsys-i.com',      'Tom Lim',      'mia.cruz@awsys-i.com',   TRUE),
  ('paolo.reyes@awsys-i.com',  'Paolo Reyes',  'mia.cruz@awsys-i.com',   TRUE),
  ('omar.diaz@awsys-i.com',    'Omar Diaz',    'sam.reyes@awsys-i.com',  TRUE),
  ('nina.go@awsys-i.com',      'Nina Go',      'sam.reyes@awsys-i.com',  TRUE),
  ('kim.bautista@awsys-i.com', 'Kim Bautista', 'dana.lopez@awsys-i.com', FALSE)
) AS v(email, name, lead, active)
JOIN users l ON l.google_account = v.lead;

UPDATE users SET team_lead_id = (SELECT user_id FROM users WHERE google_account = 'eli.park@awsys-i.com')
WHERE role = 'team_lead';

INSERT INTO projects (project_name, description, visibility, owner_id, created_by)
SELECT v.name, v.descr, v.vis, u.user_id, u.user_id
FROM (VALUES
  ('Alpha', 'Client portal', 'public', 'dana.lopez@awsys-i.com'),
  ('Beta', 'Support desk', 'public', 'dana.lopez@awsys-i.com'),
  ('Gamma', 'Design system', 'private', 'mia.cruz@awsys-i.com'),
  ('Delta', 'Integrations', 'public', 'sam.reyes@awsys-i.com'),
  ('Team management', 'Internal meetings', 'public', 'eli.park@awsys-i.com')
) AS v(name, descr, vis, owner)
JOIN users u ON u.google_account = v.owner;

INSERT INTO tasks (project_id, task_name, planned_minutes)
SELECT p.project_id, v.task, v.planned * 60
FROM (VALUES
  ('Alpha', 'Build', 440), ('Alpha', 'Design', 100), ('Beta', 'Support', 250),
  ('Gamma', 'Design', 450), ('Gamma', 'Build', 260), ('Delta', 'Build', 510), ('Team management', 'Meetings', 190)
) AS v(project, task, planned)
JOIN projects p ON p.project_name = v.project;

INSERT INTO items (task_id, item_name, work_type, planned_minutes)
SELECT t.task_id, v.item, v.kind, v.planned * 60
FROM (VALUES
  ('Alpha', 'Build', 'API', 'task', 160), ('Alpha', 'Build', 'UI', 'task', 150), ('Alpha', 'Build', 'Testing', 'task', 130),
  ('Alpha', 'Design', 'Wireframes', 'task', 60), ('Alpha', 'Design', 'Review', 'meeting', 40),
  ('Beta', 'Support', 'Tickets', 'task', 180), ('Beta', 'Support', 'Escalations', 'meeting', 70),
  ('Gamma', 'Design', 'Review', 'meeting', 200), ('Gamma', 'Design', 'Prototype', 'task', 250), ('Gamma', 'Build', 'Frontend', 'task', 260),
  ('Delta', 'Build', 'API', 'task', 250), ('Delta', 'Build', 'Integration', 'task', 260),
  ('Team management', 'Meetings', 'Stand-up', 'meeting', 110), ('Team management', 'Meetings', 'Planning', 'meeting', 80)
) AS v(project, task, item, kind, planned)
JOIN projects p ON p.project_name = v.project
JOIN tasks t ON t.project_id = p.project_id AND t.task_name = v.task;

INSERT INTO project_members (project_id, user_id, role_on_project, start_date, end_date, added_by)
SELECT p.project_id, u.user_id, v.role, DATE '2026-09-01', DATE '2026-12-31', (SELECT user_id FROM users WHERE google_account = 'eli.park@awsys-i.com')
FROM (VALUES
  ('dana.lopez@awsys-i.com', 'Alpha', 'Team lead'), ('dana.lopez@awsys-i.com', 'Beta', 'Team lead'),
  ('aisha.rahman@awsys-i.com', 'Alpha', 'Developer'), ('aisha.rahman@awsys-i.com', 'Beta', 'Developer'),
  ('ben.ortiz@awsys-i.com', 'Alpha', 'QA / Tester'), ('ben.ortiz@awsys-i.com', 'Beta', 'QA / Tester'),
  ('jo.tan@awsys-i.com', 'Alpha', 'Designer'), ('jo.tan@awsys-i.com', 'Beta', 'Support'),
  ('raf.cruz@awsys-i.com', 'Alpha', 'Designer'), ('raf.cruz@awsys-i.com', 'Beta', 'Designer'),
  ('mia.cruz@awsys-i.com', 'Gamma', 'Team lead'), ('lea.sison@awsys-i.com', 'Gamma', 'Designer'),
  ('tom.lim@awsys-i.com', 'Gamma', 'Developer'), ('paolo.reyes@awsys-i.com', 'Gamma', 'Developer'),
  ('sam.reyes@awsys-i.com', 'Delta', 'Team lead'), ('omar.diaz@awsys-i.com', 'Delta', 'Developer'),
  ('nina.go@awsys-i.com', 'Delta', 'Developer')
) AS v(email, project, role)
JOIN users u ON u.google_account = v.email
JOIN projects p ON p.project_name = v.project;

-- Everyone except Manager and Admin attends Team management meetings.
INSERT INTO project_members (project_id, user_id, role_on_project, start_date, end_date)
SELECT p.project_id, u.user_id, 'Member', DATE '2026-09-01', DATE '2026-12-31'
FROM users u CROSS JOIN projects p
WHERE p.project_name = 'Team management' AND u.role IN ('employee', 'team_lead') AND u.active_flag;

INSERT INTO project_templates (template_name, category, sharing, approval_status, approved_by, approved_date)
SELECT v.name, v.cat, 'everyone', 'approved', u.user_id, now()
FROM (VALUES ('Software build', 'Development'), ('Support desk', 'Operations'), ('Internal meetings', 'Management')) AS v(name, cat)
CROSS JOIN (SELECT user_id FROM users WHERE google_account = 'eli.park@awsys-i.com') u;

INSERT INTO template_tasks (template_id, name, sort_order)
SELECT t.template_id, v.task, v.ord
FROM (VALUES ('Software build', 'Design', 0), ('Software build', 'Build', 1), ('Software build', 'Test', 2),
             ('Support desk', 'Support', 0), ('Internal meetings', 'Meetings', 0)) AS v(tpl, task, ord)
JOIN project_templates t ON t.template_name = v.tpl;

INSERT INTO template_tasks (template_id, parent_id, name, sort_order)
SELECT p.template_id, p.template_task_id, v.item, v.ord
FROM (VALUES ('Software build', 'Design', 'Wireframes', 0), ('Software build', 'Design', 'Review', 1),
             ('Software build', 'Build', 'API', 0), ('Software build', 'Build', 'UI', 1),
             ('Software build', 'Test', 'Testing', 0), ('Software build', 'Test', 'Bug fixes', 1),
             ('Support desk', 'Support', 'Tickets', 0), ('Support desk', 'Support', 'Escalations', 1),
             ('Internal meetings', 'Meetings', 'Stand-up', 0), ('Internal meetings', 'Meetings', 'Planning', 1)) AS v(tpl, task, item, ord)
JOIN project_templates t ON t.template_name = v.tpl
JOIN template_tasks p ON p.template_id = t.template_id AND p.parent_id IS NULL AND p.name = v.task;

INSERT INTO timesheet_locks (start_date, end_date, locked_by, lock_reason)
SELECT DATE '2026-09-01', DATE '2026-09-30', user_id, 'September closed' FROM users WHERE google_account = 'eli.park@awsys-i.com';

COMMIT;
