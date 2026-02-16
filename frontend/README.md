# Background Check Agent - Frontend

React + TypeScript frontend for the AI-powered Fair Chance Hiring compliance analysis system.

## Features

- 📤 **File Upload**: Drag-and-drop PDF upload interface
- 🏛️ **Jurisdiction Selection**: Support for CA, IL, and OH regulations
- 📊 **Real-time Progress**: Live status updates during processing
- 📋 **Detailed Results**: Comprehensive offense analysis with recommendations
- ♿ **Accessible**: Built with accessibility in mind
- 📱 **Responsive**: Mobile-friendly design

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Styling
- **Axios** - HTTP client
- **@tanstack/react-query** - Data fetching and caching
- **react-dropzone** - File upload
- **Vitest** - Testing framework
- **@testing-library/react** - Component testing

## Project Structure

```
src/
├── components/          # React components
│   ├── UploadZone.tsx
│   ├── JurisdictionSelector.tsx
│   ├── ProgressIndicator.tsx
│   ├── OffenseCard.tsx
│   ├── ResultsView.tsx
│   └── ErrorMessage.tsx
├── services/           # API client and types
│   ├── api.ts
│   └── types.ts
├── hooks/              # Custom React hooks
│   └── usePolling.ts
├── __tests__/          # Test files
│   ├── api.test.ts
│   └── components/
├── App.tsx             # Main application component
├── main.tsx            # Entry point
└── index.css           # Global styles
```

## Prerequisites

- **Node.js**: 20.19+ or 22.12+ (recommended)
- **npm**: 10.x+

> **Note**: The project was set up with Node.js 20.16.0, which causes build warnings. For production builds, please upgrade to Node.js 20.19+ or 22.12+.

## Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Edit .env to configure API endpoint
# VITE_API_URL=http://localhost:8000/api/v1
```

## Development

```bash
# Start dev server (http://localhost:5173)
npm run dev

# Run tests
npm run test

# Run tests with coverage
npm run test:coverage

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

## Testing

The project includes comprehensive unit and component tests:

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test -- --watch

# Run tests with coverage report
npm run test:coverage
```

### Test Coverage

- ✅ API client tests (mocked axios)
- ✅ Component tests (ErrorMessage, OffenseCard, ProgressIndicator)
- ✅ Utility function tests

## Components

### UploadZone

Drag-and-drop file upload component for PDF files.

```tsx
<UploadZone onFileSelect={(file) => console.log(file)} />
```

### JurisdictionSelector

Dropdown for selecting jurisdiction (CA, IL, OH).

```tsx
<JurisdictionSelector
  value={jurisdiction}
  onChange={setJurisdiction}
/>
```

### ProgressIndicator

Shows processing progress with step breakdown.

```tsx
<ProgressIndicator
  currentStep="cjars_categorization"
  percentage={45}
  stepsCompleted={['extraction']}
  stepsRemaining={['compliance', 'synthesis']}
/>
```

### OffenseCard

Displays offense details with decision and rationale.

```tsx
<OffenseCard offense={offense} />
```

### ResultsView

Comprehensive results view with summary and offense breakdown.

```tsx
<ResultsView
  results={resultsData}
  onReset={() => console.log('Reset')}
/>
```

### ErrorMessage

Error display component with optional retry button.

```tsx
<ErrorMessage
  title="Processing Error"
  message="Failed to process report"
  onRetry={() => console.log('Retry')}
/>
```

## API Integration

The frontend communicates with the backend API using axios:

- `POST /reports/upload` - Upload PDF and start processing
- `GET /reports/{sessionId}/status` - Poll processing status
- `GET /reports/{sessionId}/results` - Fetch analysis results
- `GET /jurisdictions` - Get available jurisdictions

### Polling Strategy

The app uses a custom `usePolling` hook to poll the status endpoint every 2 seconds until processing completes.

## Deployment

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

### Environment-specific Builds

```bash
# Development build
VITE_API_URL=http://localhost:8000/api/v1 npm run build

# Production build
VITE_API_URL=https://api.background-check-agent.com/api/v1 npm run build
```

## Known Issues

1. **Node.js Version Warning**: Vite 7.x requires Node.js 20.19+ or 22.12+. If using Node.js 20.16.0, you may see warnings but the dev server should still work.

2. **Build Errors**: The `npm run build` command may fail with Node.js 20.16.0 due to rollup dependency issues. Upgrade to Node.js 20.19+ to resolve.

## Contributing

1. Create a feature branch
2. Make your changes
3. Add tests for new features
4. Ensure all tests pass (`npm run test`)
5. Run linting (`npm run lint`)
6. Submit a pull request

## License

MIT

## Support

For issues or questions, please contact the development team.
