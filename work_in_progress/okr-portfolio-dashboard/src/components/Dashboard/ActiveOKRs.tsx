import React from 'react';
import { Target } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { StatusBadge } from '../common/StatusBadge';
import { CategoryBadge } from '../common/CategoryBadge';
import { ProgressBar } from '../common/ProgressBar';
import type { Objective } from '../../types';

export const ActiveOKRs: React.FC = () => {
  const { objectives } = useApp();

  const activeOKRs = objectives
    .filter(o => o.status === 'in-progress' || o.status === 'at-risk')
    .sort((a, b) => {
      // Sort at-risk first, then by progress
      if (a.status === 'at-risk' && b.status !== 'at-risk') return -1;
      if (a.status !== 'at-risk' && b.status === 'at-risk') return 1;
      return b.progress - a.progress;
    })
    .slice(0, 4);

  if (activeOKRs.length === 0) {
    return (
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 mb-4">OKRs Ativos</h2>
        <p className="text-gray-500 text-center py-8">
          Nenhum OKR ativo no momento
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-xl font-bold text-gray-900 mb-4">OKRs Ativos</h2>
      <div className="space-y-4">
        {activeOKRs.map((okr) => (
          <OKRCard key={okr.id} objective={okr} />
        ))}
      </div>
    </div>
  );
};

const OKRCard: React.FC<{ objective: Objective }> = ({ objective }) => {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
      <div className="flex items-start gap-3 mb-3">
        <div className="bg-primary-50 p-2 rounded-lg">
          <Target className="w-5 h-5 text-primary-600" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-gray-900">{objective.title}</h3>
          </div>
          <p className="text-sm text-gray-600 mb-2">{objective.description}</p>
          <div className="flex items-center gap-2">
            <CategoryBadge category={objective.category} size="sm" />
            <StatusBadge status={objective.status} size="sm" />
            {objective.quarter && (
              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-700 border border-gray-200 rounded-full font-medium">
                {objective.quarter}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mb-3">
        <ProgressBar
          value={objective.progress}
          size="sm"
          color={objective.status === 'at-risk' ? 'danger' : 'primary'}
        />
      </div>

      <div className="space-y-2">
        {objective.keyResults.map((kr) => (
          <div key={kr.id} className="flex items-center justify-between text-sm">
            <span className="text-gray-700 flex-1">{kr.description}</span>
            <div className="flex items-center gap-2">
              <span className="text-gray-900 font-medium">
                {kr.current} / {kr.target} {kr.unit}
              </span>
              <StatusBadge status={kr.status} size="sm" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
