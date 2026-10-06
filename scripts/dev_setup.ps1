<#
PowerShell helper to initialize a local dev environment on Windows.

Usage: Open PowerShell and run:
    .\scripts\dev_setup.ps1

This script will:
- Create and activate a venv in `.venv` if it doesn't exist
- Install packages from `requirements.txt`
- Create `.env` from `.env.example` if missing
- Run `migrate` and load the demo data (`seed_demo --if-empty`)
#>
param()

Write-Host "Starting dev setup..." -ForegroundColor Cyan

if (-not (Test-Path -Path .venv)) {
    python -m venv .venv
    Write-Host "Created virtualenv at .venv" -ForegroundColor Green
}

Write-Host "Activating virtualenv..."
. .\.venv\Scripts\Activate

Write-Host "Installing requirements (if present)..."
if (Test-Path requirements.txt) {
    pip install -r requirements.txt
} else {
    Write-Host "No requirements.txt found; skipping." -ForegroundColor Yellow
}

if (-not (Test-Path -Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

Write-Host "Running migrations and loading demo data..."
python manage.py migrate --noinput
python manage.py seed_demo --if-empty

Write-Host "Optional: create your own admin with 'python manage.py createsuperuser'."

Write-Host "Dev setup complete. Run: python manage.py runserver" -ForegroundColor Green
