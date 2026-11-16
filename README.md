# Safe Student Productivity Agent

A beginner-friendly Streamlit AI agent for the CS 4680 Prompt Engineering assignment. The user enters a natural-language request, the Gemini model converts it into a structured command, and the Python application validates and executes an approved action.

## Features

- LLM integration through the Gemini API
- Structured JSON command interpretation
- Pydantic validation
- Safe file creation, reading, listing, and folder creation
- SQLite task storage
- LLM text summarization
- Confirmation workflow for commands marked as destructive
- Path traversal protection
- Error handling for invalid actions, API failures, rate limits, database errors, and missing files
- JSON-lines audit log in `action_log.txt`
- Streamlit web interface

## Files

- `app.py`: Streamlit user interface
- `agent.py`: Gemini integration and command interpretation
- `actions.py`: allowlisted action executor and safety checks
- `models.py`: Pydantic models
- `database.py`: SQLite task database
- `agent_workspace/`: permitted file workspace
- `action_log.txt`: audit log created at runtime
- `tasks.db`: SQLite database created at runtime

## Windows setup

Open PowerShell in this folder and run:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace `your_gemini_api_key_here` with your Gemini API key. Never upload `.env` to GitHub.

Start the application:

```powershell
streamlit run app.py
```

If no API key is present, the app runs in demo mode so the interface and non-LLM actions can still be tested.

## Example requests

```text
Create a note named recursion.txt explaining recursion.
List the files in my project.
Read recursion.txt.
Add a task called Study programming paradigms.
Show all of my tasks.
Create a folder named exam_notes.
Summarize this text: Static typing checks types before execution.
```

## Safety design

The model cannot execute arbitrary shell commands. The executor accepts only actions in `ALLOWED_ACTIONS`. File operations are restricted to `agent_workspace`, absolute paths are rejected, and paths containing `..` are rejected. Commands marked as requiring confirmation are not executed until the user confirms them in the interface.

## GitHub

```powershell
git init
git add .
git commit -m "Initial safe student agent"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Confirm that `.env`, `tasks.db`, `action_log.txt`, and `.venv` are not committed.

## Render deployment

Create a Render Web Service connected to the GitHub repository.

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Add `GEMINI_API_KEY` as a Render environment variable. Do not place the real key in the repository.
