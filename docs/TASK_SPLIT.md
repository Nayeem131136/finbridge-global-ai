# Task split

## Md. Mahdi Hasan Nayeem (Team Leader): backend, agent, security, evaluation, delivery
- `backend/app/agent.py`, `llm.py`, `tools.py`: agent planners, Groq tool-calling loop, tier enforcement
- `backend/app/security.py`, `session.py`: injection scan, PII masking, audit chain, compliance, confirm flow
- `auth.py`, `db.py`, `store.py`, `userctx.py`, `api_user.py`, `migrations/`: accounts, sessions, database, per-user data
- `fx.py`, `remit.py`, `budget.py`, `tuition.py`, `credit.py`, `invoice.py`: domain logic
- `backend/tests`, `eval/`: tests, 36 scenarios, report
- GitHub repository, deployment, technical documentation, security self-assessment, final submission email

## Rupasha Khan Tandra: frontend, UX, demo and presentation visuals
- `frontend/index.html`, `css/styles.css`, `js/main.js`, `js/cards.js`, `js/globe.js`, `js/account.js`, `js/dash.js`, `js/ui.js`, `js/i18n.js`: 3D globe, chat UI, result cards, PIN modal, security panel, mobile layout
- Improve visual polish (fonts, spacing, empty states, animations), check accessibility and mobile
- Record the demo video (script in the README flow: route compare, sign-up, profile, plans, pay with password, wrong password, invoice fraud, injection)
- Presentation deck design (10 minutes) with screenshots from the live app
- Proofread all English documents

## Both
- Test each other's parts, rehearse the 10-minute presentation, one of you is ready for questions on security and one on user experience
