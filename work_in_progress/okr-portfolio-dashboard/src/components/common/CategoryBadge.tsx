import React from 'react';
import { Briefcase, Dumbbell, Music, User, BookOpen, MoreHorizontal } from 'lucide-react';
import type { ProjectCategory } from '../../types';

interface CategoryBadgeProps {
  category: ProjectCategory;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const categoryConfig: Record<ProjectCategory, { label: string; color: string; icon: React.FC<{ className?: string }> }> = {
  work: {
    label: 'Trabalho',
    color: 'bg-blue-100 text-blue-800 border-blue-200',
    icon: Briefcase,
  },
  training: {
    label: 'Treino',
    color: 'bg-green-100 text-green-800 border-green-200',
    icon: Dumbbell,
  },
  music: {
    label: 'Música',
    color: 'bg-purple-100 text-purple-800 border-purple-200',
    icon: Music,
  },
  personal: {
    label: 'Pessoal',
    color: 'bg-pink-100 text-pink-800 border-pink-200',
    icon: User,
  },
  learning: {
    label: 'Aprendizado',
    color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    icon: BookOpen,
  },
  other: {
    label: 'Outro',
    color: 'bg-gray-100 text-gray-800 border-gray-200',
    icon: MoreHorizontal,
  },
};

const sizeClasses = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
  lg: 'text-base px-3 py-1.5',
};

const iconSizes = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

export const CategoryBadge: React.FC<CategoryBadgeProps> = ({
  category,
  showIcon = true,
  size = 'md',
}) => {
  const config = categoryConfig[category];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${config.color} ${sizeClasses[size]}`}
    >
      {showIcon && <Icon className={iconSizes[size]} />}
      {config.label}
    </span>
  );
};
