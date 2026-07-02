import express from 'express';
import { body, validationResult } from 'express-validator';
import { PrismaClient } from '@prisma/client';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();
const prisma = new PrismaClient();

router.use(authenticateToken);

router.get('/', async (req, res) => {
  try {
    const { category, status, priority } = req.query;
    const where = { userId: req.user.id };

    if (category) where.category = category;
    if (status) where.status = status;
    if (priority) where.priority = priority;

    const projects = await prisma.project.findMany({
      where,
      include: {
        milestones: { orderBy: { date: 'asc' } },
        redFlags: { orderBy: { createdAt: 'desc' } }
      },
      orderBy: { updatedAt: 'desc' }
    });

    res.json(projects);
  } catch (error) {
    console.error('Erro ao buscar projetos:', error);
    res.status(500).json({ error: 'Erro ao buscar projetos' });
  }
});

router.get('/:id', async (req, res) => {
  try {
    const project = await prisma.project.findFirst({
      where: {
        id: req.params.id,
        userId: req.user.id
      },
      include: {
        milestones: { orderBy: { date: 'asc' } },
        redFlags: { orderBy: { createdAt: 'desc' } }
      }
    });

    if (!project) {
      return res.status(404).json({ error: 'Projeto não encontrado' });
    }

    res.json(project);
  } catch (error) {
    console.error('Erro ao buscar projeto:', error);
    res.status(500).json({ error: 'Erro ao buscar projeto' });
  }
});

router.post('/',
  [
    body('title').notEmpty().withMessage('Título é obrigatório'),
    body('description').optional(),
    body('category').isIn(['work', 'training', 'music', 'personal', 'learning', 'other']),
    body('status').isIn(['planning', 'active', 'on-hold', 'completed', 'cancelled']),
    body('priority').isIn(['low', 'medium', 'high', 'critical']),
    body('progress').isInt({ min: 0, max: 100 }).withMessage('Progresso deve estar entre 0 e 100')
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { title, description, category, status, priority, progress, startDate, targetEndDate, tags } = req.body;

      const project = await prisma.project.create({
        data: {
          title,
          description: description || '',
          category,
          status,
          priority,
          progress: progress || 0,
          startDate: startDate ? new Date(startDate) : null,
          targetEndDate: targetEndDate ? new Date(targetEndDate) : null,
          tags: tags || [],
          userId: req.user.id
        },
        include: {
          milestones: true,
          redFlags: true
        }
      });

      res.status(201).json(project);
    } catch (error) {
      console.error('Erro ao criar projeto:', error);
      res.status(500).json({ error: 'Erro ao criar projeto' });
    }
  }
);

router.put('/:id',
  [
    body('title').optional().notEmpty(),
    body('category').optional().isIn(['work', 'training', 'music', 'personal', 'learning', 'other']),
    body('status').optional().isIn(['planning', 'active', 'on-hold', 'completed', 'cancelled']),
    body('priority').optional().isIn(['low', 'medium', 'high', 'critical']),
    body('progress').optional().isInt({ min: 0, max: 100 })
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const existing = await prisma.project.findFirst({
        where: { id: req.params.id, userId: req.user.id }
      });

      if (!existing) {
        return res.status(404).json({ error: 'Projeto não encontrado' });
      }

      const { title, description, category, status, priority, progress, startDate, targetEndDate, tags } = req.body;

      const project = await prisma.project.update({
        where: { id: req.params.id },
        data: {
          ...(title && { title }),
          ...(description !== undefined && { description }),
          ...(category && { category }),
          ...(status && { status }),
          ...(priority && { priority }),
          ...(progress !== undefined && { progress }),
          ...(startDate !== undefined && { startDate: startDate ? new Date(startDate) : null }),
          ...(targetEndDate !== undefined && { targetEndDate: targetEndDate ? new Date(targetEndDate) : null }),
          ...(tags !== undefined && { tags })
        },
        include: {
          milestones: true,
          redFlags: true
        }
      });

      res.json(project);
    } catch (error) {
      console.error('Erro ao atualizar projeto:', error);
      res.status(500).json({ error: 'Erro ao atualizar projeto' });
    }
  }
);

router.delete('/:id', async (req, res) => {
  try {
    const existing = await prisma.project.findFirst({
      where: { id: req.params.id, userId: req.user.id }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Projeto não encontrado' });
    }

    await prisma.project.delete({
      where: { id: req.params.id }
    });

    res.status(204).send();
  } catch (error) {
    console.error('Erro ao deletar projeto:', error);
    res.status(500).json({ error: 'Erro ao deletar projeto' });
  }
});

router.post('/:id/milestones',
  [
    body('title').notEmpty().withMessage('Título é obrigatório'),
    body('date').isISO8601().withMessage('Data inválida')
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const project = await prisma.project.findFirst({
        where: { id: req.params.id, userId: req.user.id }
      });

      if (!project) {
        return res.status(404).json({ error: 'Projeto não encontrado' });
      }

      const { title, description, date } = req.body;

      const milestone = await prisma.milestone.create({
        data: {
          title,
          description: description || '',
          date: new Date(date),
          completed: false,
          projectId: req.params.id
        }
      });

      res.status(201).json(milestone);
    } catch (error) {
      console.error('Erro ao criar milestone:', error);
      res.status(500).json({ error: 'Erro ao criar milestone' });
    }
  }
);

router.patch('/:projectId/milestones/:milestoneId/toggle', async (req, res) => {
  try {
    const project = await prisma.project.findFirst({
      where: { id: req.params.projectId, userId: req.user.id }
    });

    if (!project) {
      return res.status(404).json({ error: 'Projeto não encontrado' });
    }

    const milestone = await prisma.milestone.findFirst({
      where: { id: req.params.milestoneId, projectId: req.params.projectId }
    });

    if (!milestone) {
      return res.status(404).json({ error: 'Milestone não encontrado' });
    }

    const updated = await prisma.milestone.update({
      where: { id: req.params.milestoneId },
      data: { completed: !milestone.completed }
    });

    res.json(updated);
  } catch (error) {
    console.error('Erro ao atualizar milestone:', error);
    res.status(500).json({ error: 'Erro ao atualizar milestone' });
  }
});

router.post('/:id/red-flags',
  [
    body('title').notEmpty().withMessage('Título é obrigatório'),
    body('severity').isIn(['low', 'medium', 'high', 'critical'])
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const project = await prisma.project.findFirst({
        where: { id: req.params.id, userId: req.user.id }
      });

      if (!project) {
        return res.status(404).json({ error: 'Projeto não encontrado' });
      }

      const { title, description, severity } = req.body;

      const redFlag = await prisma.redFlag.create({
        data: {
          title,
          description: description || '',
          severity,
          resolved: false,
          projectId: req.params.id
        }
      });

      res.status(201).json(redFlag);
    } catch (error) {
      console.error('Erro ao criar red flag:', error);
      res.status(500).json({ error: 'Erro ao criar red flag' });
    }
  }
);

router.patch('/:projectId/red-flags/:redFlagId/resolve', async (req, res) => {
  try {
    const project = await prisma.project.findFirst({
      where: { id: req.params.projectId, userId: req.user.id }
    });

    if (!project) {
      return res.status(404).json({ error: 'Projeto não encontrado' });
    }

    const redFlag = await prisma.redFlag.findFirst({
      where: { id: req.params.redFlagId, projectId: req.params.projectId }
    });

    if (!redFlag) {
      return res.status(404).json({ error: 'Red flag não encontrado' });
    }

    const updated = await prisma.redFlag.update({
      where: { id: req.params.redFlagId },
      data: {
        resolved: true,
        resolvedAt: new Date()
      }
    });

    res.json(updated);
  } catch (error) {
    console.error('Erro ao resolver red flag:', error);
    res.status(500).json({ error: 'Erro ao resolver red flag' });
  }
});

export default router;
