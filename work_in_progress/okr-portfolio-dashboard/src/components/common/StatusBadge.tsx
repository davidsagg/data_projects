import React from 'react';
import type { ProjectStatus, OKRStatus } from '../../types';

interface StatusBadgeProps {
  status: ProjectStatus | OKRStatus | string;
  size?: 'sm' | 'md' | 'lg';
}

const statusColors: Record<string, string> = {
  // Project statuses
  'planning': 'bg-blue-100 text-blue-800 border-blue-200',
  'active': 'bg-green-100 text-green-800 border-green-200',
  'on-hold': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  'completed': 'bg-gray-100 text-gray-800 border-gray-200',
  'cancelled': 'bg-red-100 text-red-800 border-red-200',

  // OKR statuses
  'not-started': 'bg-gray-100 text-gray-800 border-gray-200',
  'in-progress': 'bg-blue-100 text-blue-800 border-blue-200',
  'at-risk': 'bg-red-100 text-red-800 border-red-200',

  // Initiative statuses
  'idea': 'bg-purple-100 text-purple-800 border-purple-200',
  'planned': 'bg-blue-100 text-blue-800 border-blue-200',
  'abandoned': 'bg-gray-100 text-gray-800 border-gray-200',
};

const statusLabels: Record<string, string> = {
  'planning': 'Planejamento',
  'active': 'Ativo',
  'on-hold': 'Pausado',
  'completed': 'Concluído',
  'cancelled': 'Cancelado',
  'not-started': 'Não Iniciado',
  'in-progress': 'Em Progresso',
  'at-risk': 'Em Risco',
  'idea': 'Ideia',
  'planned': 'Planejado',
  'abandoned': 'Abandonado',
};

const sizeClasses = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
  lg: 'text-base px-3 py-1.5',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const colorClass = statusColors[status] || 'bg-gray-100 text-gray-800 border-gray-200';
  const sizeClass = sizeClasses[size];
  const label = statusLabels[status] || status;

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${colorClass} ${sizeClass}`}
    >
      {label}
    </span>
  );
};
