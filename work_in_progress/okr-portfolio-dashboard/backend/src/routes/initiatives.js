import express from 'express';
import { body, validationResult } from 'express-validator';
import { PrismaClient } from '@prisma/client';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();
const prisma = new PrismaClient();

router.use(authenticateToken);

router.get('/', async (req, res) => {
  try {
    const { status } = req.query;
    const where = { userId: req.user.id };

    if (status) where.status = status;

    const initiatives = await prisma.initiative.findMany({
      where,
      orderBy: { updatedAt: 'desc' }
    });

    res.json(initiatives);
  } catch (error) {
    console.error('Erro ao buscar iniciativas:', error);
    res.status(500).json({ error: 'Erro ao buscar iniciativas' });
  }
});

router.get('/:id', async (req, res) => {
  try {
    const initiative = await prisma.initiative.findFirst({
      where: {
        id: req.params.id,
        userId: req.user.id
      }
    });

    if (!initiative) {
      return res.status(404).json({ error: 'Iniciativa não encontrada' });
    }

    res.json(initiative);
  } catch (error) {
    console.error('Erro ao buscar iniciativa:', error);
    res.status(500).json({ error: 'Erro ao buscar iniciativa' });
  }
});

router.post('/',
  [
    body('title').notEmpty().withMessage('Título é obrigatório'),
    body('description').optional(),
    body('status').isIn(['idea', 'evaluating', 'approved', 'in_progress', 'completed', 'rejected']),
    body('estimatedEffort').optional().isIn(['low', 'medium', 'high']),
    body('potentialImpact').optional().isIn(['low', 'medium', 'high'])
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { title, description, status, estimatedEffort, potentialImpact, notes } = req.body;

      const initiative = await prisma.initiative.create({
        data: {
          title,
          description: description || '',
          status,
          estimatedEffort: estimatedEffort || null,
          potentialImpact: potentialImpact || null,
          notes: notes || null,
          userId: req.user.id
        }
      });

      res.status(201).json(initiative);
    } catch (error) {
      console.error('Erro ao criar iniciativa:', error);
      res.status(500).json({ error: 'Erro ao criar iniciativa' });
    }
  }
);

router.put('/:id',
  [
    body('title').optional().notEmpty(),
    body('status').optional().isIn(['idea', 'evaluating', 'approved', 'in_progress', 'completed', 'rejected']),
    body('estimatedEffort').optional().isIn(['low', 'medium', 'high']),
    body('potentialImpact').optional().isIn(['low', 'medium', 'high'])
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const existing = await prisma.initiative.findFirst({
        where: { id: req.params.id, userId: req.user.id }
      });

      if (!existing) {
        return res.status(404).json({ error: 'Iniciativa não encontrada' });
      }

      const { title, description, status, estimatedEffort, potentialImpact, notes } = req.body;

      const initiative = await prisma.initiative.update({
        where: { id: req.params.id },
        data: {
          ...(title && { title }),
          ...(description !== undefined && { description }),
          ...(status && { status }),
          ...(estimatedEffort !== undefined && { estimatedEffort }),
          ...(potentialImpact !== undefined && { potentialImpact }),
          ...(notes !== undefined && { notes })
        }
      });

      res.json(initiative);
    } catch (error) {
      console.error('Erro ao atualizar iniciativa:', error);
      res.status(500).json({ error: 'Erro ao atualizar iniciativa' });
    }
  }
);

router.delete('/:id', async (req, res) => {
  try {
    const existing = await prisma.initiative.findFirst({
      where: { id: req.params.id, userId: req.user.id }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Iniciativa não encontrada' });
    }

    await prisma.initiative.delete({
      where: { id: req.params.id }
    });

    res.status(204).send();
  } catch (error) {
    console.error('Erro ao deletar iniciativa:', error);
    res.status(500).json({ error: 'Erro ao deletar iniciativa' });
  }
});

export default router;
