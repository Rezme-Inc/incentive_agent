import { useParams, useNavigate } from 'react-router-dom';
import { useDevMode } from '../../context/DevModeContext';
import { useSSE } from '../../hooks/useSSE';
import { Layout } from '../../components/common/Layout';
import { NormalModeView } from './NormalModeView';
import { DevModeView } from './DevModeView';

export const ProcessingPage = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { devMode, toggleDevMode } = useDevMode();

  const { status, graphData, runningNode, error } = useSSE({
    sessionId: sessionId || null,
    enabled: !!sessionId,
  });

  // Handle errors
  if (error) {
    return (
      <Layout>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-800">Discovery Error</h1>
            <p className="text-gray-600">An error occurred while discovering programs</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-start">
              <svg
                className="w-6 h-6 text-red-600 mr-3"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <h3 className="text-lg font-medium text-red-800">Error</h3>
                <p className="mt-1 text-sm text-red-700">{error.message}</p>
              </div>
            </div>
            <div className="mt-4">
              <button
                onClick={() => navigate('/input')}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
              >
                Start Over
              </button>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  const isComplete = status?.status === 'completed';

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">
            {isComplete ? 'Discovery Complete' : 'Discovering Incentive Programs'}
          </h1>
          <p className="text-gray-600">
            {isComplete
              ? `Found ${status?.programs_found || 0} programs`
              : 'Searching for incentive programs at all government levels...'}
          </p>
        </div>

        {/* Dev Mode Toggle */}
        <div className="flex justify-end mb-4">
          <label className="flex items-center cursor-pointer">
            <span className="mr-2 text-sm text-gray-600">Dev Mode</span>
            <div className="relative">
              <input
                type="checkbox"
                className="sr-only"
                checked={devMode}
                onChange={toggleDevMode}
              />
              <div
                className={`w-10 h-6 rounded-full transition-colors ${
                  devMode ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`absolute left-1 top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                    devMode ? 'translate-x-4' : ''
                  }`}
                />
              </div>
            </div>
          </label>
        </div>

        {/* Processing View */}
        {devMode ? (
          <DevModeView status={status} nodes={[]} graphData={graphData} runningNode={runningNode} />
        ) : (
          <NormalModeView status={status} />
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-center gap-4">
          {isComplete && (
            <button
              onClick={() => navigate(`/report/${sessionId}`)}
              className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              View Programs
            </button>
          )}
          <button
            onClick={() => navigate('/input')}
            className="px-6 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            {isComplete ? 'New Discovery' : 'Cancel'}
          </button>
        </div>
      </div>
    </Layout>
  );
};
