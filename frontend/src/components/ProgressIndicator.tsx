interface ProgressIndicatorProps {
  currentStep: string;
  percentage: number;
  stepsCompleted: string[];
  stepsRemaining: string[];
}

const formatStepName = (step: string): string => {
  return step
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export function ProgressIndicator({
  currentStep,
  percentage,
  stepsCompleted,
  stepsRemaining,
}: ProgressIndicatorProps) {
  // Ensure arrays are defined
  const completedSteps = stepsCompleted || [];
  const remainingSteps = stepsRemaining || [];
  
  // Determine if we're complete (100% or no remaining steps)
  const isComplete = percentage >= 100 || (remainingSteps.length === 0 && completedSteps.length > 0);

  return (
    <div className="w-full bg-white p-6 rounded-lg shadow-md">
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700">
            Current: {formatStepName(currentStep)}
          </span>
          <span className={`text-sm font-semibold ${isComplete ? 'text-red-600' : 'text-blue-600'}`}>
            {percentage}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className={`h-3 rounded-full transition-all duration-300 ease-in-out ${
              isComplete ? 'bg-red-600' : 'bg-blue-600'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      </div>

      <div className="space-y-3">
        {completedSteps.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
              Completed
            </h4>
            <div className="flex flex-wrap gap-2">
              {completedSteps.map((step) => (
                <span
                  key={step}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"
                >
                  <svg
                    className="w-3 h-3 mr-1"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {formatStepName(step)}
                </span>
              ))}
            </div>
          </div>
        )}

        {remainingSteps.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
              Remaining
            </h4>
            <div className="flex flex-wrap gap-2">
              {remainingSteps.map((step) => (
                <span
                  key={step}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                >
                  {formatStepName(step)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {!isComplete && (
        <div className="mt-4 flex items-center text-xs text-gray-500">
          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600 mr-2"></div>
          Processing...
        </div>
      )}
      {isComplete && (
        <div className="mt-4 flex items-center text-xs text-red-600">
          <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          Complete
        </div>
      )}
    </div>
  );
}
