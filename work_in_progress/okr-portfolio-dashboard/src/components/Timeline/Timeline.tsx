import React, { useState, useMemo } from 'react';
import { Calendar, CheckCircle2, Circle } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { CategoryBadge } from '../common/CategoryBadge';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import type { ProjectCategory } from '../../types';

export const Timeline: React.FC = () => {
  const { projects, toggleMilestone } = useApp();
  const [selectedCategory, setSelectedCategory] = useState<ProjectCategory | 'all'>('all');
  const [viewMode, setViewMode] = useState<'upcoming' | 'all'>('upcoming');

  // Get all milestones with project info
  const allMilestones = useMemo(() => {
    return projects.flatMap(project =>
      project.milestones.map(milestone => ({
        ...milestone,
        projectTitle: project.title,
        projectId: project.id,
      }))
    );
  }, [projects]);

  // Filter milestones
  const filteredMilestones = useMemo(() => {
    let filtered = allMilestones;

    // Filter by category
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(m => m.category === selectedCategory);
    }

    // Filter by view mode
    if (viewMode === 'upcoming') {
      filtered = filtered.filter(m => !m.completed && m.date >= new Date());
    }

    return filtered.sort((a, b) => a.date.getTime() - b.date.getTime());
  }, [allMilestones, selectedCategory, viewMode]);

  // Group milestones by month
  const milestonesByMonth = useMemo(() => {
    const groups = new Map<string, typeof filteredMilestones>();

    filteredMilestones.forEach(milestone => {
      const monthKey = format(milestone.date, 'yyyy-MM');
      if (!groups.has(monthKey)) {
        groups.set(monthKey, []);
      }
      groups.get(monthKey)!.push(milestone);
    });

    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredMilestones]);

  const categories: Array<ProjectCategory | 'all'> = ['all', 'work', 'training', 'music', 'personal', 'learning', 'other'];
  const categoryLabels = {
    all: 'Todos',
    work: 'Trabalho',
    training: 'Treino',
    music: 'Música',
    personal: 'Pessoal',
    learning: 'Aprendizado',
    other: 'Outro',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Timeline</h1>
          <p className="text-gray-600">
            Visualize milestones e eventos principais
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* View Mode */}
          <div className="flex-shrink-0">
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Visualização
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode('upcoming')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  viewMode === 'upcoming'
                    ? 'bg-primary-600 text-white'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Próximos
              </button>
              <button
                onClick={() => setViewMode('all')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  viewMode === 'all'
                    ? 'bg-primary-600 text-white'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Todos
              </button>
            </div>
          </div>

          {/* Category Filter */}
          <div className="flex-1">
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Categoria
            </label>
            <div className="flex items-center gap-2 overflow-x-auto">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                    selectedCategory === cat
                      ? 'bg-primary-600 text-white'
                      : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {categoryLabels[cat]}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      {milestonesByMonth.length === 0 ? (
        <div className="card text-center py-12">
          <Calendar className="w-16 h-16 mx-auto mb-4 text-gray-300" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Nenhum milestone encontrado
          </h3>
          <p className="text-gray-600">
            Adicione milestones aos seus projetos para visualizá-los aqui
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {milestonesByMonth.map(([monthKey, milestones]) => {
            const monthDate = new Date(monthKey + '-01');
            return (
              <div key={monthKey}>
                <div className="flex items-center gap-3 mb-4">
                  <div className="bg-primary-600 text-white px-4 py-2 rounded-lg font-bold">
                    {format(monthDate, 'MMM yyyy', { locale: ptBR }).toUpperCase()}
                  </div>
                  <div className="h-0.5 flex-1 bg-gray-200"></div>
                </div>

                <div className="space-y-3 ml-4">
                  {milestones.map((milestone) => (
                    <div
                      key={milestone.id}
                      className={`relative pl-8 pb-4 border-l-2 ${
                        milestone.completed
                          ? 'border-green-500'
                          : milestone.date < new Date()
                          ? 'border-red-500'
                          : 'border-blue-500'
                      }`}
                    >
                      {/* Timeline dot */}
                      <button
                        onClick={() => toggleMilestone(milestone.projectId, milestone.id)}
                        className="absolute -left-3 top-0 bg-white rounded-full p-1 hover:scale-110 transition-transform"
                      >
                        {milestone.completed ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                        ) : (
                          <Circle
                            className={`w-5 h-5 ${
                              milestone.date < new Date() ? 'text-red-500' : 'text-blue-500'
                            }`}
                          />
                        )}
                      </button>

                      {/* Milestone content */}
                      <div className={`card ${milestone.completed ? 'opacity-60' : ''}`}>
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <h4 className={`font-semibold text-gray-900 mb-1 ${milestone.completed ? 'line-through' : ''}`}>
                              {milestone.title}
                            </h4>
                            <p className="text-sm text-gray-600 mb-2">{milestone.description}</p>
                            <div className="flex items-center gap-2 flex-wrap">
                              <CategoryBadge category={milestone.category} size="sm" />
                              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded-full">
                                {milestone.projectTitle}
                              </span>
                              <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full font-medium">
                                {format(milestone.date, "dd 'de' MMMM", { locale: ptBR })}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
