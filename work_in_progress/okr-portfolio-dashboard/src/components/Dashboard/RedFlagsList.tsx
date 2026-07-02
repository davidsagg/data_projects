import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

export const RedFlagsList: React.FC = () => {
  const { projects, resolveRedFlag } = useApp();

  const allRedFlags = projects.flatMap(project =>
    project.redFlags
      .filter(r => !r.resolved)
      .map(redFlag => ({
        ...redFlag,
        projectTitle: project.title,
      }))
  ).sort((a, b) => {
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  const severityConfig = {
    critical: { color: 'bg-red-100 border-red-300 text-red-800', icon: '🔴' },
    high: { color: 'bg-orange-100 border-orange-300 text-orange-800', icon: '🟠' },
    medium: { color: 'bg-yellow-100 border-yellow-300 text-yellow-800', icon: '🟡' },
    low: { color: 'bg-blue-100 border-blue-300 text-blue-800', icon: '🔵' },
  };

  if (allRedFlags.length === 0) {
    return (
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <AlertTriangle className="w-6 h-6" />
          Red Flags
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
          <CheckCircle className="w-12 h-12 mb-2 text-green-500" />
          <p>Nenhum red flag ativo!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
        <AlertTriangle className="w-6 h-6" />
        Red Flags ({allRedFlags.length})
      </h2>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {allRedFlags.map((redFlag) => {
          const config = severityConfig[redFlag.severity];
          return (
            <div
              key={redFlag.id}
              className={`border rounded-lg p-4 ${config.color}`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-start gap-2 flex-1">
                  <span className="text-lg">{config.icon}</span>
                  <div className="flex-1">
                    <h4 className="font-semibold">{redFlag.title}</h4>
                    <p className="text-sm mt-1">{redFlag.description}</p>
                  </div>
                </div>
                <button
                  onClick={() => resolveRedFlag(redFlag.projectId, redFlag.id)}
                  className="text-sm px-3 py-1 bg-white rounded-lg hover:bg-gray-50 transition-colors border border-current"
                  title="Marcar como resolvido"
                >
                  Resolver
                </button>
              </div>
              <div className="flex items-center justify-between text-xs mt-2 opacity-75">
                <span>Projeto: {redFlag.projectTitle}</span>
                <span>{format(redFlag.createdAt, "dd MMM yyyy", { locale: ptBR })}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
