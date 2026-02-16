import { useState } from 'react';
import { Layout } from '../../components/common/Layout';
import { ProgramCard } from '../../components/ProgramCard';
import { getPrograms, submitShortlist, getROIQuestions, submitROIAnswers } from '../../services/api';
import type { Program, ROIQuestion } from '../../services/types';

export const AdminPage = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [programs, setPrograms] = useState<Program[]>([]);
  const [selectedProgramIds, setSelectedProgramIds] = useState<string[]>([]);
  const [roiQuestions, setRoiQuestions] = useState<ROIQuestion[]>([]);
  const [roiAnswers, setRoiAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoadPrograms = async () => {
    if (!sessionId) {
      setError('Please enter a session ID');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getPrograms(sessionId);
      setPrograms(data.programs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load programs');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleProgram = (programId: string) => {
    setSelectedProgramIds((prev) => {
      if (prev.includes(programId)) {
        return prev.filter((id) => id !== programId);
      } else {
        return [...prev, programId];
      }
    });
  };

  const handleSubmitShortlist = async () => {
    if (!sessionId || selectedProgramIds.length === 0) {
      setError('Please select at least one program');
      return;
    }

    try {
      await submitShortlist(sessionId, selectedProgramIds);
      // Load ROI questions
      const questionsResponse = await getROIQuestions(sessionId);
      setRoiQuestions(questionsResponse.questions);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit shortlist');
    }
  };

  const handleROIAnswerChange = (questionId: string, value: any) => {
    setRoiAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleSubmitROI = async () => {
    try {
      const response = await submitROIAnswers(sessionId, roiAnswers);
      setError(null);
      alert(`ROI calculated! Total ROI: $${response.calculations.reduce((sum, calc) => sum + calc.total_roi, 0).toLocaleString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate ROI');
    }
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Admin Dashboard</h1>
          <p className="text-gray-600">Manage incentive program discovery and ROI calculations</p>
        </div>

        {/* Session ID Input */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex gap-4">
            <input
              type="text"
              placeholder="Enter session ID"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              onClick={handleLoadPrograms}
              disabled={loading}
              className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load Programs'}
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Programs List */}
        {programs.length > 0 && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Programs ({programs.length})
                </h2>
                <button
                  onClick={handleSubmitShortlist}
                  disabled={selectedProgramIds.length === 0}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  Shortlist Selected ({selectedProgramIds.length})
                </button>
              </div>
              <div className="space-y-4">
                {programs.map((program) => (
                  <ProgramCard
                    key={program.id}
                    program={program}
                    selected={selectedProgramIds.includes(program.id)}
                    onSelect={handleToggleProgram}
                  />
                ))}
              </div>
            </div>

            {/* ROI Questions */}
            {roiQuestions.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  ROI Questions
                </h2>
                <div className="space-y-4">
                  {roiQuestions.map((question) => (
                    <div key={question.id}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {question.question}
                        {question.required && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {question.type === 'number' && (
                        <input
                          type="number"
                          value={roiAnswers[question.id] || ''}
                          onChange={(e) => handleROIAnswerChange(question.id, parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        />
                      )}
                      {question.type === 'text' && (
                        <input
                          type="text"
                          value={roiAnswers[question.id] || ''}
                          onChange={(e) => handleROIAnswerChange(question.id, e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        />
                      )}
                      {question.type === 'select' && question.options && (
                        <select
                          value={roiAnswers[question.id] || ''}
                          onChange={(e) => handleROIAnswerChange(question.id, e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="">Select...</option>
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
                <div className="mt-6 flex justify-end">
                  <button
                    onClick={handleSubmitROI}
                    className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    Calculate ROI
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
};

