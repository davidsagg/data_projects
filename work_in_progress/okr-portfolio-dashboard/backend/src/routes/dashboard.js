import express from 'express';
import { PrismaClient } from '@prisma/client';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();
const prisma = new PrismaClient();

router.use(authenticateToken);

router.get('/stats', async (req, res) => {
  try {
    const userId = req.user.id;

    const [
      totalProjects,
      activeProjects,
      completedProjects,
      totalObjectives,
      objectivesOnTrack,
      totalInitiatives,
      initiativesInProgress,
      unresolvedRedFlags
    ] = await Promise.all([
      prisma.project.count({ where: { userId } }),
      prisma.project.count({ where: { userId, status: 'active' } }),
      prisma.project.count({ where: { userId, status: 'completed' } }),
      prisma.objective.count({ where: { userId } }),
      prisma.objective.count({ where: { userId, status: 'on_track' } }),
      prisma.initiative.count({ where: { userId } }),
      prisma.initiative.count({ where: { userId, status: 'in_progress' } }),
      prisma.redFlag.count({
        where: {
          project: { userId },
          resolved: false
        }
      })
    ]);

    const projects = await prisma.project.findMany({
      where: { userId, status: { in: ['planning', 'active', 'on-hold'] } },
      select: { progress: true }
    });

    const avgProgress = projects.length > 0
      ? Math.round(projects.reduce((sum, p) => sum + p.progress, 0) / projects.length)
      : 0;

    res.json({
      projects: {
        total: totalProjects,
        active: activeProjects,
        completed: completedProjects,
        avgProgress
      },
      objectives: {
        total: totalObjectives,
        onTrack: objectivesOnTrack
      },
      initiatives: {
        total: totalInitiatives,
        inProgress: initiativesInProgress
      },
      redFlags: {
        unresolved: unresolvedRedFlags
      }
    });
  } catch (error) {
    console.error('Erro ao buscar estatísticas:', error);
    res.status(500).json({ error: 'Erro ao buscar estatísticas' });
  }
});

router.get('/summary', async (req, res) => {
  try {
    const userId = req.user.id;

    const [recentProjects, recentObjectives, recentInitiatives, criticalRedFlags] = await Promise.all([
      prisma.project.findMany({
        where: { userId },
        include: {
          milestones: { orderBy: { date: 'asc' }, take: 3 },
          redFlags: { where: { resolved: false }, take: 3 }
        },
        orderBy: { updatedAt: 'desc' },
        take: 5
      }),
      prisma.objective.findMany({
        where: { userId },
        include: {
          keyResults: true
        },
        orderBy: { updatedAt: 'desc' },
        take: 5
      }),
      prisma.initiative.findMany({
        where: { userId },
        orderBy: { updatedAt: 'desc' },
        take: 5
      }),
      prisma.redFlag.findMany({
        where: {
          project: { userId },
          resolved: false,
          severity: { in: ['high', 'critical'] }
        },
        include: {
          project: { select: { id: true, title: true } }
        },
        orderBy: { createdAt: 'desc' }
      })
    ]);

    res.json({
      recentProjects,
      recentObjectives,
      recentInitiatives,
      criticalRedFlags
    });
  } catch (error) {
    console.error('Erro ao buscar resumo:', error);
    res.status(500).json({ error: 'Erro ao buscar resumo' });
  }
});

export default router;
