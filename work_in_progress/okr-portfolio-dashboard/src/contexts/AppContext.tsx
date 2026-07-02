import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { Project, Objective, Initiative, Milestone, RedFlag } from '../types';
import { projectsAPI, objectivesAPI, initiativesAPI } from '../services/api';

interface AppContextType {
  projects: Project[];
  objectives: Objective[];
  initiatives: Initiative[];
  isLoading: boolean;
  refresh: () => Promise<void>;
  addProject: (project: any) => Promise<void>;
  updateProject: (id: string, updates: any) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  addObjective: (objective: any) => Promise<void>;
  updateObjective: (id: string, updates: any) => Promise<void>;
  deleteObjective: (id: string) => Promise<void>;
  addInitiative: (initiative: any) => Promise<void>;
  updateInitiative: (id: string, updates: any) => Promise<void>;
  deleteInitiative: (id: string) => Promise<void>;
  addMilestone: (projectId: string, milestone: any) => Promise<void>;
  toggleMilestone: (projectId: string, milestoneId: string) => Promise<void>;
  addRedFlag: (projectId: string, redFlag: any) => Promise<void>;
  resolveRedFlag: (projectId: string, redFlagId: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [initiatives, setInitiatives] = useState<Initiative[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true);
      const [projectsRes, objectivesRes, initiativesRes] = await Promise.all([
        projectsAPI.getAll(),
        objectivesAPI.getAll(),
        initiativesAPI.getAll(),
      ]);

      setProjects(projectsRes.data);
      setObjectives(objectivesRes.data);
      setInitiatives(initiativesRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load data on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Project operations
  const addProject = async (project: any) => {
    try {
      await projectsAPI.create(project);
      await refresh();
    } catch (error) {
      console.error('Failed to add project:', error);
      throw error;
    }
  };

  const updateProject = async (id: string, updates: any) => {
    try {
      await projectsAPI.update(id, updates);
      await refresh();
    } catch (error) {
      console.error('Failed to update project:', error);
      throw error;
    }
  };

  const deleteProject = async (id: string) => {
    try {
      await projectsAPI.delete(id);
      await refresh();
    } catch (error) {
      console.error('Failed to delete project:', error);
      throw error;
    }
  };

  // Objective operations
  const addObjective = async (objective: any) => {
    try {
      await objectivesAPI.create(objective);
      await refresh();
    } catch (error) {
      console.error('Failed to add objective:', error);
      throw error;
    }
  };

  const updateObjective = async (id: string, updates: any) => {
    try {
      await objectivesAPI.update(id, updates);
      await refresh();
    } catch (error) {
      console.error('Failed to update objective:', error);
      throw error;
    }
  };

  const deleteObjective = async (id: string) => {
    try {
      await objectivesAPI.delete(id);
      await refresh();
    } catch (error) {
      console.error('Failed to delete objective:', error);
      throw error;
    }
  };

  // Initiative operations
  const addInitiative = async (initiative: any) => {
    try {
      await initiativesAPI.create(initiative);
      await refresh();
    } catch (error) {
      console.error('Failed to add initiative:', error);
      throw error;
    }
  };

  const updateInitiative = async (id: string, updates: any) => {
    try {
      await initiativesAPI.update(id, updates);
      await refresh();
    } catch (error) {
      console.error('Failed to update initiative:', error);
      throw error;
    }
  };

  const deleteInitiative = async (id: string) => {
    try {
      await initiativesAPI.delete(id);
      await refresh();
    } catch (error) {
      console.error('Failed to delete initiative:', error);
      throw error;
    }
  };

  // Milestone operations
  const addMilestone = async (projectId: string, milestone: any) => {
    try {
      await projectsAPI.addMilestone(projectId, milestone);
      await refresh();
    } catch (error) {
      console.error('Failed to add milestone:', error);
      throw error;
    }
  };

  const toggleMilestone = async (projectId: string, milestoneId: string) => {
    try {
      await projectsAPI.toggleMilestone(projectId, milestoneId);
      await refresh();
    } catch (error) {
      console.error('Failed to toggle milestone:', error);
      throw error;
    }
  };

  // RedFlag operations
  const addRedFlag = async (projectId: string, redFlag: any) => {
    try {
      await projectsAPI.addRedFlag(projectId, redFlag);
      await refresh();
    } catch (error) {
      console.error('Failed to add red flag:', error);
      throw error;
    }
  };

  const resolveRedFlag = async (projectId: string, redFlagId: string) => {
    try {
      await projectsAPI.resolveRedFlag(projectId, redFlagId);
      await refresh();
    } catch (error) {
      console.error('Failed to resolve red flag:', error);
      throw error;
    }
  };

  return (
    <AppContext.Provider
      value={{
        projects,
        objectives,
        initiatives,
        isLoading,
        refresh,
        addProject,
        updateProject,
        deleteProject,
        addObjective,
        updateObjective,
        deleteObjective,
        addInitiative,
        updateInitiative,
        deleteInitiative,
        addMilestone,
        toggleMilestone,
        addRedFlag,
        resolveRedFlag,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
