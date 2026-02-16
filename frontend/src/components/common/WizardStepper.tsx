interface Step {
  label: string;
  description?: string;
}

interface WizardStepperProps {
  steps: Step[];
  currentStep: number;
  onStepClick?: (step: number) => void;
  isStepComplete: (step: number) => boolean;
}

export const WizardStepper = ({
  steps,
  currentStep,
  onStepClick,
  isStepComplete,
}: WizardStepperProps) => {
  return (
    <nav aria-label="Progress">
      <ol className="flex items-center justify-between w-full">
        {steps.map((step, index) => {
          const isActive = index === currentStep;
          const isComplete = isStepComplete(index);
          const isPast = index < currentStep;
          const isClickable = onStepClick && (isPast || isComplete);
          // Connector line should be red if previous step is complete
          const prevStepComplete = index > 0 ? isStepComplete(index - 1) : false;

          return (
            <li key={step.label} className="flex-1 relative">
              {/* Connector line */}
              {index > 0 && (
                <div
                  className={`absolute top-4 h-0.5 z-0 ${
                    prevStepComplete ? 'bg-red-600' : 'bg-gray-200'
                  }`}
                  style={{ width: 'calc(100% - 2rem)', left: 'calc(-50% + 1rem)' }}
                />
              )}

              <button
                onClick={() => isClickable && onStepClick?.(index)}
                disabled={!isClickable}
                className={`relative z-10 flex flex-col items-center group ${
                  isClickable ? 'cursor-pointer' : 'cursor-default'
                }`}
              >
                {/* Step circle */}
                <span
                  className={`w-8 h-8 flex items-center justify-center rounded-full text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-red-600 text-white ring-2 ring-red-600 ring-offset-2'
                      : isComplete
                      ? 'bg-red-600 text-white'
                      : 'bg-gray-200 text-gray-600'
                  } ${isClickable ? 'group-hover:ring-2 group-hover:ring-red-300' : ''}`}
                >
                  {isComplete && !isActive ? (
                    <svg
                      className="w-4 h-4"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </span>

                {/* Step label */}
                <span
                  className={`mt-2 text-xs font-medium ${
                    isActive ? 'text-red-600' : 'text-gray-500'
                  }`}
                >
                  {step.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
