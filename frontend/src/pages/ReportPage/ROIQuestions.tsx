import { useState, useEffect } from 'react';
import { getROIQuestions, submitROIAnswers } from '../../services/api';
import type { ROIQuestion } from '../../services/types';

interface ROIQuestionsProps {
  sessionId: string;
  onAnswersSubmitted: (calculations: any[]) => void;
}

export const ROIQuestions = ({ sessionId, onAnswersSubmitted }: ROIQuestionsProps) => {
  const [questions, setQuestions] = useState<ROIQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await getROIQuestions(sessionId);
        setQuestions(response.questions);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load questions');
      } finally {
        setLoading(false);
      }
    };

    fetchQuestions();
  }, [sessionId]);

  const handleAnswerChange = (questionId: string, value: any) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleSubmit = async () => {
    // Validate required fields - check for undefined/null/empty string, but allow 0
    const missingRequired = questions.filter(
      (q) => q.required && (answers[q.id] === undefined || answers[q.id] === null || answers[q.id] === '')
    );
    if (missingRequired.length > 0) {
      setError(`Please answer all required questions: ${missingRequired.map(q => q.question).join(', ')}`);
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await submitROIAnswers(sessionId, answers);
      onAnswersSubmitted(response.calculations);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answers');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-12 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading ROI questions...</p>
      </div>
    );
  }

  if (error && !submitting) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-700">{error}</p>
      </div>
    );
  }

  // Group questions by program
  const questionsByProgram = questions.reduce((acc, q) => {
    if (!acc[q.program_id]) {
      acc[q.program_id] = [];
    }
    acc[q.program_id].push(q);
    return acc;
  }, {} as Record<string, ROIQuestion[]>);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          ROI Calculation Questions
        </h3>
        <p className="text-sm text-gray-600">
          Please provide the following information to calculate ROI for each program.
        </p>
      </div>

      {Object.entries(questionsByProgram).map(([programId, programQuestions]) => (
        <div key={programId} className="bg-white rounded-lg shadow-md p-6">
          <h4 className="text-md font-semibold text-gray-900 mb-4">
            {programQuestions[0]?.program_name || programId}
          </h4>
          <div className="space-y-4">
            {programQuestions.map((question) => (
              <div key={question.id} className="relative">
                <label 
                  htmlFor={`question-${question.id}`}
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  {question.question}
                  {question.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                {question.type === 'number' && (
                  <input
                    id={`question-${question.id}`}
                    type="number"
                    value={answers[question.id] ?? ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      // Allow empty string, only parse if there's a value
                      const numValue = value === '' ? '' : (parseFloat(value) || 0);
                      handleAnswerChange(question.id, numValue);
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    required={question.required}
                  />
                )}
                {question.type === 'text' && (
                  <input
                    id={`question-${question.id}`}
                    type="text"
                    value={answers[question.id] ?? ''}
                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    required={question.required}
                  />
                )}
                {question.type === 'select' && question.options && (
                  <select
                    id={`question-${question.id}`}
                    value={answers[question.id] ?? ''}
                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    required={question.required}
                  >
                    <option value="">Select an option...</option>
                    {question.options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'Calculating ROI...' : 'Calculate ROI'}
        </button>
      </div>
    </div>
  );
};

