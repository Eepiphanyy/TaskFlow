# TaskFlow - Codex Project Instructions

## Goal and stack
Build TaskFlow, an enterprise ticket and task collaboration system for a Python backend job portfolio.
- Backend: Python 3.11, Django 5.2, Django REST Framework
- Frontend: Vue 3, Vite, Element Plus
- Database: MySQL 8.0
- Later: JWT, Redis, Docker, automated tests
- Local development: Windows 11 + PowerShell

## Working rules
1. Work incrementally; do not generate the whole application in one pass.
2. Inspect the repository before editing and explain intended changes.
3. Preserve the agreed stack unless a concrete compatibility issue requires a change.
4. Use readable, beginner-friendly code and explain key concepts in Chinese.
5. Never invent performance metrics, data volumes, test results or project achievements.
6. Keep secrets in backend/.env; never commit .env.
7. Add/update tests for meaningful backend behavior.
8. Run relevant checks and report exact commands/results. Never claim a command ran if it did not.
9. Update README.md and docs/ when setup, APIs, schema or behavior changes.

## Code and security conventions
- Django apps live under backend/apps/.
- Prefer Django ORM; separate views, serializers, services and permissions as the project grows.
- Validate input on the backend; do not rely only on frontend validation.
- Use transactions for multi-step state changes.
- Use pagination/filtering for list endpoints and avoid N+1 queries.
- Frontend API calls belong in frontend/src/api/.
- Use Django password hashing; never store plaintext passwords.
- Enforce authorization on the backend, including object-level access.
- Validate uploaded file type and size.
- Never expose stack traces or secrets in API responses.
- Production configuration must use DEBUG=False and secure settings.

## Current milestone: Phase 1
Acceptance criteria:
- Django starts successfully.
- MySQL migrations run successfully.
- GET /api/health/ returns JSON.
- Vue frontend starts successfully.
- Vue dashboard calls /api/health/ through the Vite proxy and displays success.

## Next milestones
1. Registration, login, JWT access/refresh.
2. Roles, departments and backend permission enforcement.
3. Ticket CRUD, assignment, filtering, pagination and valid status transitions.
4. Comments, attachments, notifications and dashboard statistics.
5. Tests, Redis where justified, Docker deployment and interview documentation.

## Teaching agreement
For each task: state the goal and files to change; implement one small testable feature; explain code and interview concepts in Chinese; give exact PowerShell commands; ask for local test output before moving on when needed.
