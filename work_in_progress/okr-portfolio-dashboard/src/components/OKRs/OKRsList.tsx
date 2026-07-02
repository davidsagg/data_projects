import React, { useState } from 'react';
import { Plus, Target, Edit2, Trash2 } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { StatusBadge } from '../common/StatusBadge';
import { CategoryBadge } from '../common/CategoryBadge';
import { ProgressBar } from '../common/ProgressBar';
import { ObjectiveForm } from '../Forms/ObjectiveForm';
import type { ProjectCategory } from '../../types';

export const OKRsList: React.FC = () => {
  const { objectives, deleteObjective, addObjective } = useApp();
  const [selectedCategory, setSelectedCategory] = useState<ProjectCategory | 'all'>('all');
  const [isFormOpen, setIsFormOpen] = useState(false);

  const filteredObjectives = selectedCategory === 'all'
    ? objectives
    : objectives.filter(o => o.category === selectedCategory);

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

  const handleCreate = async (data: any) => {
    try {
      await addObjective(data);
      setIsFormOpen(false);
    } catch (error) {
      console.error('Failed to create objective:', error);
      alert('Erro ao criar OKR. Por favor, tente novamente.');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Tem certeza que deseja excluir este OKR?')) {
      try {
        await deleteObjective(id);
      } catch (error) {
        console.error('Failed to delete objective:', error);
        alert('Erro ao excluir OKR. Por favor, tente novamente.');
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">OKRs</h1>
          <p className="text-gray-600">
            Gerencie seus objetivos e resultados-chave
          </p>
        </div>
        <button
          onClick={() => setIsFormOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Novo OKR
        </button>
      </div>

      {/* Category Filter */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
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

      {/* OKRs List */}
      {filteredObjectives.length === 0 ? (
        <div className="card text-center py-12">
          <Target className="w-16 h-16 mx-auto mb-4 text-gray-300" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Nenhum OKR encontrado
          </h3>
          <p className="text-gray-600 mb-4">
            Comece criando seu primeiro objetivo
          </p>
          <button
            onClick={() => setIsFormOpen(true)}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-5 h-5" />
            Criar OKR
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredObjectives.map((objective) => (
            <div key={objective.id} className="card hover:border-primary-300 border-2 border-transparent transition-all">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3 flex-1">
                  <div className="bg-primary-50 p-3 rounded-lg">
                    <Target className="w-6 h-6 text-primary-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                      {objective.title}
                    </h3>
                    <p className="text-gray-600 mb-3">{objective.description}</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <CategoryBadge category={objective.category} />
                      <StatusBadge status={objective.status} />
                      {objective.quarter && (
                        <span className="text-sm px-3 py-1 bg-gray-100 text-gray-700 border border-gray-200 rounded-full font-medium">
                          {objective.quarter}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Editar"
                  >
                    <Edit2 className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => handleDelete(objective.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Excluir"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Progress */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">Progresso Geral</span>
                </div>
                <ProgressBar
                  value={objective.progress}
                  color={objective.status === 'at-risk' ? 'danger' : 'primary'}
                />
              </div>

              {/* Key Results */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-3">
                  Resultados-Chave ({objective.keyResults.length})
                </h4>
                <div className="space-y-3">
                  {objective.keyResults.map((kr) => {
                    const krProgress = (kr.current / kr.target) * 100;
                    return (
                      <div key={kr.id} className="bg-gray-50 rounded-lg p-3">
                        <div className="flex items-start justify-between mb-2">
                          <p className="text-sm font-medium text-gray-900 flex-1">
                            {kr.description}
                          </p>
                          <StatusBadge status={kr.status} size="sm" />
                        </div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">
                            {kr.current} / {kr.target} {kr.unit}
                          </span>
                        </div>
                        <ProgressBar value={krProgress} size="sm" showLabel={false} />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <ObjectiveForm
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
};
