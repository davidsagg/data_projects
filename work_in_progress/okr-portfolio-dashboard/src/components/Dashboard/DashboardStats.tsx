import React from 'react';
import { Target, FolderKanban, AlertTriangle, Calendar } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

export const DashboardStats: React.FC = () => {
  const { projects, objectives } = useApp();

  const stats = {
    totalProjects: projects.length,
    activeProjects: projects.filter(p => p.status === 'active').length,
    completedProjects: projects.filter(p => p.status === 'completed').length,
    totalObjectives: objectives.length,
    activeObjectives: objectives.filter(o => o.status === 'in-progress').length,
    atRiskObjectives: objectives.filter(o => o.status === 'at-risk').length,
    totalRedFlags: projects.reduce((sum, p) => sum + p.redFlags.filter(r => !r.resolved).length, 0),
    upcomingMilestones: projects.reduce((sum, p) => {
      const upcoming = p.milestones.filter(m => {
        const daysUntil = Math.ceil((m.date.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
        return !m.completed && daysUntil >= 0 && daysUntil <= 30;
      });
      return sum + upcoming.length;
    }, 0),
  };

  const statCards = [
    {
      title: 'Projetos Ativos',
      value: stats.activeProjects,
      total: stats.totalProjects,
      icon: FolderKanban,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'OKRs em Progresso',
      value: stats.activeObjectives,
      total: stats.totalObjectives,
      icon: Target,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Red Flags',
      value: stats.totalRedFlags,
      total: undefined,
      icon: AlertTriangle,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
    },
    {
      title: 'Milestones (30 dias)',
      value: stats.upcomingMilestones,
      total: undefined,
      icon: Calendar,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {statCards.map((stat) => (
        <div key={stat.title} className="card">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-600 mb-1">{stat.title}</p>
              <p className="text-3xl font-bold text-gray-900">
                {stat.value}
                {stat.total !== undefined && (
                  <span className="text-lg font-normal text-gray-500 ml-1">
                    / {stat.total}
                  </span>
                )}
              </p>
            </div>
            <div className={`${stat.bgColor} p-3 rounded-lg`}>
              <stat.icon className={`w-6 h-6 ${stat.color}`} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
