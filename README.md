# Aserras Frontend

Static marketing site and chat UI for the Aserras platform served through a FastAPI
application. The project exposes multiple marketing pages, authentication flows,
and a chat workspace rendered with Jinja templates.

## Project structure

```
├── app.py              # FastAPI application factory and routes
├── config.py           # Environment aware settings using pydantic-settings
├── static/             # Compiled assets (CSS, JS, sitemap, robots)
├── templates/          # Jinja templates for every page and error view
└── tests/              # FastAPI smoke tests for the main routes
```

## Requirements

The app depends on FastAPI plus Starlette's optional `aiofiles` package so static
assets can be streamed correctly. All dependencies are listed in
`requirements.txt`:

```
aiofiles
fastapi
jinja2
openai
pydantic-settings
python-dotenv
uvicorn[standard]
```

## Local development

1. Create and activate a virtual environment (optional).
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application with Uvicorn:
   ```bash
   uvicorn app:app --reload
   ```
4. Visit `http://localhost:8000` to browse the marketing pages and chat UI.

## Tests

Basic smoke tests confirm that the most important routes render without errors:

```bash
pytest
```
