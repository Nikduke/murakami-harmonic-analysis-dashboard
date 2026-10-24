# Application documentation

Use this index to choose the correct source before changing or operating the dashboard.

| Document | Use it for | Authority |
| --- | --- | --- |
| [Current application reference](APP_REFERENCE.md) | Implemented functionality, workbook rules, UI state, chart calculations, exports, and code responsibilities | Current functional reference |
| [Project README](../../README.md) | Environment setup, local launch, input locations, checks, and Streamlit Community Cloud deployment | Current setup and deployment instructions |
| [Project instructions](../../AGENTS.md) | Rules for coding agents and future development chats | Active development constraints |
| [User guide (PDF)](User_Guide/Harmonic_Analysis_Dashboard_User_Guide.pdf) | User steps with screenshots | Operator guide |
| [Original V1 development prompt](codex_prompt_murakami_harmonics_streamlit_v1_2026-10-02.md) | Initial requirements and design rationale | Historical; not the current implementation specification |
| [Application audit backlog](../../APPLICATION_AUDIT_BACKLOG.md) | Past audit evidence, completed updates, and open or deferred ideas | Historical audit; proposals are not implemented requirements |

For a new development chat, read `AGENTS.md` and `APP_REFERENCE.md` first. Read the README for environment or deployment work. Consult the original V1 prompt for context only. Confirm current behaviour in code and tests when a document and implementation disagree, then update the affected documentation with the code change.
