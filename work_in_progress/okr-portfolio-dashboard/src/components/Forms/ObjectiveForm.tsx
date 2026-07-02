import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import type { ProjectCategory, OKRStatus } from '../../types';
import { Modal } from '../common/Modal';

interface KeyResultInput {
  description: string;
  target: number;
  current: number;
  unit: string;
  status: OKRStatus;
}

interface ObjectiveFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
  initialData?: any;
}

export const ObjectiveForm: React.FC<ObjectiveFormProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
}) => {
  const [formData, setFormData] = useState({
    title: initialData?.title || '',
    description: initialData?.description || '',
    category: (initialData?.category || 'work') as ProjectCategory,
    status: (initialData?.status || 'not_started') as OKRStatus,
    quarter: initialData?.quarter || '',
  });

  const [keyResults, setKeyResults] = useState<KeyResultInput[]>(
    initialData?.keyResults || [
      { description: '', target: 100, current: 0, unit: '%', status: 'not_started' as OKRStatus },
    ]
  );

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const addKeyResult = () => {
    setKeyResults([
      ...keyResults,
      { description: '', target: 100, current: 0, unit: '%', status: 'not_started' },
    ]);
  };

  const removeKeyResult = (index: number) => {
    if (keyResults.length > 1) {
      setKeyResults(keyResults.filter((_, i) => i !== index));
    }
  };

  const updateKeyResult = (index: number, field: keyof KeyResultInput, value: any) => {
    const updated = [...keyResults];
    updated[index] = { ...updated[index], [field]: value };
    setKeyResults(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate key results
    const validKeyResults = keyResults.filter(kr => kr.description.trim());
    if (validKeyResults.length === 0) {
      setError('Adicione pelo menos um resultado-chave');
      return;
    }

    setIsLoading(true);

    try {
      // Calculate progress based on key results
      const totalProgress = validKeyResults.reduce((sum, kr) => {
        return sum + (kr.current / kr.target) * 100;
      }, 0);
      const avgProgress = Math.round(totalProgress / validKeyResults.length);

      const submitData = {
        ...formData,
        progress: avgProgress,
        keyResults: validKeyResults.map(kr => ({
          ...kr,
          target: Number(kr.target),
          current: Number(kr.current),
        })),
      };

      await onSubmit(submitData);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Erro ao salvar objetivo');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={initialData ? 'Editar OKR' : 'Novo OKR'}
      size="xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Objetivo *
          </label>
          <input
            type="text"
            required
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            placeholder="Ex: Crescer a base de usuários em 150%"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Descrição *
          </label>
          <textarea
            required
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={2}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
            placeholder="Descreva o objetivo"
          />
        </div>

        {/* Category, Status, Quarter */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Categoria *
            </label>
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value as ProjectCategory })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            >
              <option value="work">Trabalho</option>
              <option value="training">Treino</option>
              <option value="music">Música</option>
              <option value="personal">Pessoal</option>
              <option value="learning">Aprendizado</option>
              <option value="other">Outro</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Status *
            </label>
            <select
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value as OKRStatus })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            >
              <option value="not_started">Não Iniciado</option>
              <option value="in_progress">Em Progresso</option>
              <option value="at_risk">Em Risco</option>
              <option value="completed">Concluído</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Trimestre
            </label>
            <input
              type="text"
              value={formData.quarter}
              onChange={(e) => setFormData({ ...formData, quarter: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
              placeholder="Q1 2024"
            />
          </div>
        </div>

        {/* Key Results */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-gray-700">
              Resultados-Chave * (mínimo 1)
            </label>
            <button
              type="button"
              onClick={addKeyResult}
              className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Adicionar KR
            </button>
          </div>

          <div className="space-y-3">
            {keyResults.map((kr, index) => (
              <div key={index} className="bg-gray-50 rounded-lg p-4 relative">
                {keyResults.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeKeyResult(index)}
                    className="absolute top-2 right-2 p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="md:col-span-2">
                    <input
                      type="text"
                      value={kr.description}
                      onChange={(e) => updateKeyResult(index, 'description', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                      placeholder="Descrição do resultado"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Meta</label>
                    <input
                      type="number"
                      value={kr.target}
                      onChange={(e) => updateKeyResult(index, 'target', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Atual</label>
                    <input
                      type="number"
                      value={kr.current}
                      onChange={(e) => updateKeyResult(index, 'current', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Unidade</label>
                    <input
                      type="text"
                      value={kr.unit}
                      onChange={(e) => updateKeyResult(index, 'unit', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                      placeholder="%, km, usuários..."
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Status</label>
                    <select
                      value={kr.status}
                      onChange={(e) => updateKeyResult(index, 'status', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                    >
                      <option value="not_started">Não Iniciado</option>
                      <option value="in_progress">Em Progresso</option>
                      <option value="at_risk">Em Risco</option>
                      <option value="completed">Concluído</option>
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t">
          <button
            type="button"
            onClick={onClose}
            className="btn-secondary"
            disabled={isLoading}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={isLoading}
          >
            {isLoading ? 'Salvando...' : (initialData ? 'Salvar' : 'Criar OKR')}
          </button>
        </div>
      </form>
    </Modal>
  );
};
