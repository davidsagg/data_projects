import React, { useState, useMemo } from 'react';
import { Plus, FolderKanban, Lightbulb, Edit2, Trash2, AlertCircle } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { StatusBadge } from '../common/StatusBadge';
import { CategoryBadge } from '../common/CategoryBadge';
import { ProgressBar } from '../common/ProgressBar';
import { ProjectForm } from '../Forms/ProjectForm';
import { InitiativeForm } from '../Forms/InitiativeForm';
import type { ProjectCategory, ProjectStatus } from '../../types';

type ViewMode = 'projects' | 'initiatives';

export const Portfolio: React.FC = () => {
  const { projects, initiatives, addProject, addInitiative, deleteProject, deleteInitiative } = useApp();
  const [viewMode, setViewMode] = useState<ViewMode>('projects');
  const [selectedCategory, setSelectedCategory] = useState<ProjectCategory | 'all'>('all');
  const [selectedStatus, setSelectedStatus] = useState<ProjectStatus | 'all'>('all');
  const [isProjectFormOpen, setIsProjectFormOpen] = useState(false);
  const [isInitiativeFormOpen, setIsInitiativeFormOpen] = useState(false);

  const filteredProjects = useMemo(() => {
    let filtered = projects;

    if (selectedCategory !== 'all') {
      filtered = filtered.filter(p => p.category === selectedCategory);
    }

    if (selectedStatus !== 'all') {
      filtered = filtered.filter(p => p.status === selectedStatus);
    }

    return filtered.sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
  }, [projects, selectedCategory, selectedStatus]);

  const filteredInitiatives = useMemo(() => {
    let filtered = initiatives;

    if (selectedCategory !== 'all') {
      filtered = filtered.filter(i => i.category === selectedCategory);
    }

    return filtered.sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
  }, [initiatives, selectedCategory]);

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

  const projectStatuses: Array<ProjectStatus | 'all'> = ['all', 'planning', 'active', 'on-hold', 'completed', 'cancelled'];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Portfolio</h1>
          <p className="text-gray-600">
            Gerencie seus projetos e iniciativas
          </p>
        </div>
        <button
          onClick={() => viewMode === 'projects' ? setIsProjectFormOpen(true) : setIsInitiativeFormOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          {viewMode === 'projects' ? 'Novo Projeto' : 'Nova Iniciativa'}
        </button>
      </div>

      {/* View Mode Toggle */}
      <div className="card">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setViewMode('projects')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'projects'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <FolderKanban className="w-5 h-5" />
            Projetos ({projects.length})
          </button>
          <button
            onClick={() => setViewMode('initiatives')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'initiatives'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Lightbulb className="w-5 h-5" />
            Iniciativas ({initiatives.length})
          </button>
        </div>

        {/* Filters */}
        <div className="space-y-4">
          {/* Category Filter */}
          <div>
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

          {/* Status Filter (only for projects) */}
          {viewMode === 'projects' && (
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                Status
              </label>
              <div className="flex items-center gap-2 overflow-x-auto">
                {projectStatuses.map((status) => (
                  <button
                    key={status}
                    onClick={() => setSelectedStatus(status)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                      selectedStatus === status
                        ? 'bg-primary-600 text-white'
                        : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {status === 'all' ? 'Todos' : <StatusBadge status={status} size="sm" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      {viewMode === 'projects' ? (
        <ProjectsGrid projects={filteredProjects} onDelete={deleteProject} />
      ) : (
        <InitiativesGrid initiatives={filteredInitiatives} onDelete={deleteInitiative} />
      )}

      <ProjectForm
        isOpen={isProjectFormOpen}
        onClose={() => setIsProjectFormOpen(false)}
        onSubmit={async (data) => {
          try {
            await addProject(data);
            setIsProjectFormOpen(false);
          } catch (error) {
            console.error('Failed to create project:', error);
            alert('Erro ao criar projeto.');
          }
        }}
      />

      <InitiativeForm
        isOpen={isInitiativeFormOpen}
        onClose={() => setIsInitiativeFormOpen(false)}
        onSubmit={async (data) => {
          try {
            await addInitiative(data);
            setIsInitiativeFormOpen(false);
          } catch (error) {
            console.error('Failed to create initiative:', error);
            alert('Erro ao criar iniciativa.');
          }
        }}
      />
    </div>
  );
};

// Projects Grid Component
const ProjectsGrid: React.FC<{
  projects: ReturnType<typeof useApp>['projects'];
  onDelete: (id: string) => void;
}> = ({ projects, onDelete }) => {
  if (projects.length === 0) {
    return (
      <div className="card text-center py-12">
        <FolderKanban className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Nenhum projeto encontrado
        </h3>
        <p className="text-gray-600 mb-4">
          Comece criando seu primeiro projeto
        </p>
        <button className="btn-primary inline-flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Criar Projeto
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {projects.map((project) => {
        const hasRedFlags = project.redFlags.filter(r => !r.resolved).length > 0;
        const completedMilestones = project.milestones.filter(m => m.completed).length;

        return (
          <div key={project.id} className="card hover:border-primary-300 border-2 border-transparent transition-all">
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-lg font-bold text-gray-900">{project.title}</h3>
                  {hasRedFlags && (
                    <span title="Possui red flags">
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">{project.description}</p>
                <div className="flex items-center gap-2 flex-wrap mb-3">
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
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Editar"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => {
                    if (confirm('Tem certeza que deseja excluir este projeto?')) {
                      onDelete(project.id);
                    }
                  }}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Excluir"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="mb-3">
              <ProgressBar value={project.progress} size="sm" />
            </div>

            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{completedMilestones}/{project.milestones.length} milestones</span>
              {hasRedFlags && (
                <span className="text-red-600 font-medium">
                  {project.redFlags.filter(r => !r.resolved).length} red flag(s)
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// Initiatives Grid Component
const InitiativesGrid: React.FC<{
  initiatives: ReturnType<typeof useApp>['initiatives'];
  onDelete: (id: string) => void;
}> = ({ initiatives, onDelete }) => {
  if (initiatives.length === 0) {
    return (
      <div className="card text-center py-12">
        <Lightbulb className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Nenhuma iniciativa encontrada
        </h3>
        <p className="text-gray-600 mb-4">
          Adicione suas ideias e iniciativas futuras
        </p>
        <button className="btn-primary inline-flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Criar Iniciativa
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {initiatives.map((initiative) => (
        <div key={initiative.id} className="card hover:border-primary-300 border-2 border-transparent transition-all">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <h3 className="text-lg font-bold text-gray-900 mb-2">{initiative.title}</h3>
              <p className="text-sm text-gray-600 mb-3">{initiative.description}</p>
              <div className="flex items-center gap-2 flex-wrap mb-3">
                <CategoryBadge category={initiative.category} size="sm" />
                <StatusBadge status={initiative.status} size="sm" />
                {initiative.priority === 'critical' && (
                  <span className="text-xs px-2 py-0.5 bg-red-100 text-red-800 border border-red-200 rounded-full font-medium">
                    Crítico
                  </span>
                )}
                {initiative.priority === 'high' && (
                  <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-800 border border-orange-200 rounded-full font-medium">
                    Alta
                  </span>
                )}
              </div>

              {(initiative.estimatedEffort || initiative.potentialImpact) && (
                <div className="flex items-center gap-4 text-xs text-gray-600">
                  {initiative.estimatedEffort && (
                    <div>
                      <span className="font-medium">Esforço:</span> {initiative.estimatedEffort}
                    </div>
                  )}
                  {initiative.potentialImpact && (
                    <div>
                      <span className="font-medium">Impacto:</span> {initiative.potentialImpact}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="Editar"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => {
                  if (confirm('Tem certeza que deseja excluir esta iniciativa?')) {
                    onDelete(initiative.id);
                  }
                }}
                className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Excluir"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {initiative.notes && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-xs text-gray-600 italic">{initiative.notes}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
