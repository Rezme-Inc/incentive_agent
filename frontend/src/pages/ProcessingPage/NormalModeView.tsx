import type { DiscoveryStatus } from '../../services/types';

interface NormalModeViewProps {
  status: DiscoveryStatus | null;
}

export const NormalModeView = ({ status }: NormalModeViewProps) => {
  const isComplete = status?.status === 'completed';
  const currentStep = status?.current_step || 'Initializing...';
  const searchProgress = status?.search_progress || {
    city: 'pending',
    county: 'pending',
    state: 'pending',
    federal: 'pending',
  };

  const getStatusIcon = (progress: string) => {
    switch (progress) {
      case 'completed':
        return (
          <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        );
      case 'running':
        return (
          <div className="w-6 h-6 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
        );
      default:
        return (
          <div className="w-6 h-6 rounded-full bg-gray-200" />
        );
    }
  };

  const getStatusText = (progress: string, level: string) => {
    switch (progress) {
      case 'completed':
        return `✓ ${level} search completed`;
      case 'running':
        return `Searching ${level}...`;
      default:
        return `${level} search pending`;
    }
  };

  return (
    <div className="space-y-6">
      {/* Current Step Display */}
      <div className="bg-white rounded-lg shadow-md p-6">
        {!isComplete ? (
          <>
            {/* Animated spinner and message */}
            <div className="flex items-center justify-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-4 border-blue-100" />
                <div className="absolute top-0 left-0 w-12 h-12 rounded-full border-4 border-blue-600 border-t-transparent animate-spin" />
              </div>
              <div>
                <p className="text-lg font-medium text-gray-900">{currentStep}</p>
                <p className="text-sm text-gray-500">
                  {status?.programs_found || 0} programs found so far
                </p>
              </div>
            </div>
          </>
        ) : (
          /* Completion state */
          <div className="flex items-center justify-center gap-4">
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div>
              <p className="text-lg font-medium text-green-700">Discovery Complete</p>
              <p className="text-sm text-gray-500">
                Found {status?.programs_found || 0} unique programs
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Government Levels Discovered */}
      {status?.government_levels && status.government_levels.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Government Levels
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {status.government_levels.map((level, idx) => (
              <div
                key={idx}
                className="p-3 bg-gray-50 rounded-lg border border-gray-200"
              >
                <p className="text-sm font-medium text-gray-900 capitalize">{level}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search Progress */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Search Progress
        </h3>
        <div className="space-y-3">
          {Object.entries(searchProgress).map(([level, progress]) => (
            <div
              key={level}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div className="flex items-center gap-3">
                {getStatusIcon(progress as string)}
                <span className="text-sm font-medium text-gray-900 capitalize">
                  {getStatusText(progress as string, level)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
