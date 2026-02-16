# Incentive Agent - Setup & Run Guide

## Quick Start

### 1. Install Dependencies

**Backend:**
```bash
cd /Users/rjama/incentive_agent
pip install -r requirements.txt
```

**Frontend:**
```bash
cd /Users/rjama/incentive_agent/frontend/frontend-backup
npm install
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory (`/Users/rjama/incentive_agent/.env`):

```bash
ANTHROPIC_API_KEY=your_anthropic_key_here
TAVILY_API_KEY=your_tavily_key_here
```

### 3. Run the System

**Terminal 1 - Backend API:**
```bash
cd /Users/rjama/incentive_agent
python run_backend.py
```

Or directly with uvicorn:
```bash
uvicorn backend.api.incentives:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd /Users/rjama/incentive_agent/frontend/frontend-backup
npm run dev
```

### 4. Access the Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

## Troubleshooting

### Network Error in Frontend

1. **Check if backend is running:**
   - Visit http://localhost:8000/api/v1/health
   - Should return: `{"status":"healthy","version":"1.0.0",...}`

2. **Check CORS:**
   - CORS middleware is already added to the backend
   - Frontend should be able to connect from `http://localhost:5173`

3. **Check API URL:**
   - Frontend is configured to use `http://localhost:8000/api/v1`
   - Can be overridden with `VITE_API_URL` environment variable

### Node.js Version Issues

- **Required:** Node.js 20.19+ or 22.12+
- **Check version:** `node --version`
- **Upgrade with nvm:**
  ```bash
  nvm install 20
  nvm use 20
  ```
- **Reinstall dependencies after upgrading:**
  ```bash
  cd frontend/frontend-backup
  rm -rf node_modules package-lock.json
  npm install
  ```

### Backend Import Errors

- Make sure you're in the root directory when running the backend
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify `.env` file exists with API keys

## API Endpoints

- `POST /api/v1/incentives/discover` - Start discovery for an address
- `GET /api/v1/incentives/{session_id}/status` - Get discovery status
- `GET /api/v1/incentives/{session_id}/programs` - Get discovered programs
- `POST /api/v1/incentives/{session_id}/shortlist` - Submit shortlist
- `GET /api/v1/incentives/{session_id}/roi-questions` - Get ROI questions
- `POST /api/v1/incentives/{session_id}/roi-answers` - Submit ROI answers
- `GET /api/v1/incentives/{session_id}/roi-spreadsheet` - Download ROI spreadsheet

## Development

The backend uses FastAPI with auto-reload enabled. Changes to Python files will automatically restart the server.

The frontend uses Vite with hot module replacement. Changes to React files will automatically update in the browser.

