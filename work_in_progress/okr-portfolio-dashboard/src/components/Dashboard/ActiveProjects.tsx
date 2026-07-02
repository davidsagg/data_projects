import React from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { StatusBadge } from '../common/StatusBadge';
import { CategoryBadge } from '../common/CategoryBadge';
import { ProgressBar } from '../common/ProgressBar';
import type { Project } from '../../types';

export const ActiveProjects: React.FC = () => {
  const { projects } = useApp();

  const activeProjects = projects
    .filter(p => p.status === 'active' || p.status === 'planning')
    .sort((a, b) => {
      // Sort by priority first, then by progress
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
      if (priorityDiff !== 0) return priorityDiff;
      return b.progress - a.progress;
    })
    .slice(0, 6);

  if (activeProjects.length === 0) {
    return (
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Projetos Ativos</h2>
        <p className="text-gray-500 text-center py-8">
          Nenhum projeto ativo no momento
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Projetos Ativos</h2>
      <div className="space-y-4">
        {activeProjects.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </div>
    </div>
  );
};

const ProjectCard: React.FC<{ project: Project }> = ({ project }) => {
  const hasRedFlags = project.redFlags.filter(r => !r.resolved).length > 0;
  const completedMilestones = project.milestones.filter(m => m.completed).length;
  const totalMilestones = project.milestones.length;

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-gray-900">{project.title}</h3>
            {hasRedFlags && (
              <span title="Possui red flags">
                <AlertCircle className="w-4 h-4 text-red-500" />
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600 line-clamp-2">{project.description}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <CategoryBadge category={project.category} size="sm" />
        <StatusBadge status={project.status} size="sm" />
        {project.priority === 'critical' && (
          <span className="text-xs px-2 py-0.5 bg-red-100 text-red-800 border border-red-200 rounded-full font-medium">
            Crítico
          </span>
        )}
        {project.priority === 'high' && (
          <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-800 border border-orange-200 rounded-full font-medium">
            Alta
          </span>
        )}
      </div>

      <div className="mb-2">
        <ProgressBar value={project.progress} size="sm" />
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>
            {completedMilestones}/{totalMilestones} milestones
          </span>
        </div>
        {hasRedFlags && (
          <div className="flex items-center gap-1 text-red-600">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{project.redFlags.filter(r => !r.resolved).length} red flag(s)</span>
          </div>
        )}
      </div>
    </div>
  );
};
