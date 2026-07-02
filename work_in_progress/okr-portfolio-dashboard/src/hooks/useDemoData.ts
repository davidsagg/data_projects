import { useEffect } from 'react';
import { useApp } from '../contexts/AppContext';
import { demoProjects, demoObjectives, demoInitiatives } from '../utils/demoData';

const DEMO_DATA_LOADED_KEY = 'okr-portfolio-demo-loaded';

export const useDemoData = () => {
  const { projects, objectives, initiatives, addProject, addObjective, addInitiative } = useApp();

  useEffect(() => {
    // Check if demo data was already loaded
    const demoLoaded = localStorage.getItem(DEMO_DATA_LOADED_KEY);

    // Only load demo data if:
    // 1. It hasn't been loaded before
    // 2. There's no existing data
    if (!demoLoaded && projects.length === 0 && objectives.length === 0 && initiatives.length === 0) {
      console.log('Loading demo data...');

      // Load demo projects
      demoProjects.forEach(project => {
        addProject(project);
      });

      // Load demo objectives
      demoObjectives.forEach(objective => {
        addObjective(objective);
      });

      // Load demo initiatives
      demoInitiatives.forEach(initiative => {
        addInitiative(initiative);
      });

      // Mark demo data as loaded
      localStorage.setItem(DEMO_DATA_LOADED_KEY, 'true');
      console.log('Demo data loaded successfully!');
    }
  }, []); // Empty dependency array to run only once on mount
};
