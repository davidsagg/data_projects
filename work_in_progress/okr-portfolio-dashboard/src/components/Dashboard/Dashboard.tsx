import React from 'react';
import { DashboardStats } from './DashboardStats';
import { ActiveProjects } from './ActiveProjects';
import { ActiveOKRs } from './ActiveOKRs';
import { RedFlagsList } from './RedFlagsList';

export const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h1>
        <p className="text-gray-600">
          Visão geral das suas iniciativas, OKRs e projetos
        </p>
      </div>

      <DashboardStats />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ActiveProjects />
        <ActiveOKRs />
      </div>

      <RedFlagsList />
    </div>
  );
};
