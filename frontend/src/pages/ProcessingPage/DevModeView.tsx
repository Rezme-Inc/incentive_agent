import { useState } from 'react';
import type { DiscoveryStatus } from '../../services/types';

interface DevModeViewProps {
  status: DiscoveryStatus | null;
  nodes: any[];
  graphData?: { nodes: any[]; edges: any[] };
  runningNode?: string | null;
}

export const DevModeView = ({ status, graphData }: DevModeViewProps) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'running':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const nodes = graphData?.nodes || [];

  return (
    <div className="space-y-6">
      {/* Graph Visualization */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Discovery Workflow Graph
        </h3>
        <div className="space-y-3">
          {nodes.map((node) => {
            const isExpanded = expandedNodes.has(node.id);
            return (
              <div
                key={node.id}
                className={`border rounded-lg p-4 ${getStatusColor(node.status)}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {node.status === 'running' && (
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    )}
                    {node.status === 'completed' && (
                      <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                    {node.status === 'pending' && (
                      <div className="w-4 h-4 bg-gray-300 rounded-full" />
                    )}
                    <div>
                      <h4 className="font-medium text-gray-900">{node.name}</h4>
                      <p className="text-xs text-gray-600 capitalize">{node.status}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleNode(node.id)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg
                      className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-sm text-gray-600">
                      Type: {node.type} | Status: {node.status}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Status Details */}
      {status && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Status Details
          </h3>
          <div className="space-y-2 text-sm">
            <div>
              <span className="font-medium text-gray-700">Current Step:</span>
              <span className="ml-2 text-gray-900">{status.current_step}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Programs Found:</span>
              <span className="ml-2 text-gray-900">{status.programs_found}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Status:</span>
              <span className="ml-2 text-gray-900 capitalize">{status.status}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
