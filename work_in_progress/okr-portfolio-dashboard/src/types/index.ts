export type ProjectStatus = 'planning' | 'active' | 'on-hold' | 'completed' | 'cancelled';
export type ProjectPriority = 'low' | 'medium' | 'high' | 'critical';
export type ProjectCategory = 'work' | 'training' | 'music' | 'personal' | 'learning' | 'other';
export type OKRStatus = 'not-started' | 'in-progress' | 'at-risk' | 'completed';

export interface KeyResult {
  id: string;
  description: string;
  target: number;
  current: number;
  unit: string; // e.g., '%', 'hours', 'projects', etc.
  status: OKRStatus;
}

export interface Objective {
  id: string;
  title: string;
  description: string;
  category: ProjectCategory;
  quarter?: string; // e.g., 'Q1 2024'
  keyResults: KeyResult[];
  status: OKRStatus;
  progress: number; // 0-100
  createdAt: Date;
  updatedAt: Date;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  date: Date;
  projectId: string;
  completed: boolean;
  category: ProjectCategory;
}

export interface RedFlag {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  projectId: string;
  createdAt: Date;
  resolved: boolean;
}

export interface Project {
  id: string;
  title: string;
  description: string;
  category: ProjectCategory;
  status: ProjectStatus;
  priority: ProjectPriority;
  progress: number; // 0-100
  startDate: Date;
  targetEndDate?: Date;
  actualEndDate?: Date;
  objectiveIds: string[]; // Related OKRs
  milestones: Milestone[];
  redFlags: RedFlag[];
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
}

export interface Initiative {
  id: string;
  title: string;
  description: string;
  category: ProjectCategory;
  status: 'idea' | 'planned' | 'in-progress' | 'completed' | 'abandoned';
  priority: ProjectPriority;
  estimatedEffort?: string; // e.g., 'Small', 'Medium', 'Large'
  potentialImpact?: string; // e.g., 'Low', 'Medium', 'High'
  notes: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface DashboardStats {
  totalProjects: number;
  activeProjects: number;
  completedProjects: number;
  totalObjectives: number;
  activeObjectives: number;
  atRiskObjectives: number;
  totalRedFlags: number;
  upcomingMilestones: number;
}
