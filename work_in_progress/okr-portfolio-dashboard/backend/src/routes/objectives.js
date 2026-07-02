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

    const objectives = await prisma.objective.findMany({
      where,
      include: {
        keyResults: { orderBy: { createdAt: 'asc' } }
      },
      orderBy: { updatedAt: 'desc' }
    });

    res.json(objectives);
  } catch (error) {
    console.error('Erro ao buscar objetivos:', error);
    res.status(500).json({ error: 'Erro ao buscar objetivos' });
  }
});

router.get('/:id', async (req, res) => {
  try {
    const objective = await prisma.objective.findFirst({
      where: {
        id: req.params.id,
        userId: req.user.id
      },
      include: {
        keyResults: { orderBy: { createdAt: 'asc' } }
      }
    });

    if (!objective) {
      return res.status(404).json({ error: 'Objetivo não encontrado' });
    }

    res.json(objective);
  } catch (error) {
    console.error('Erro ao buscar objetivo:', error);
    res.status(500).json({ error: 'Erro ao buscar objetivo' });
  }
});

router.post('/',
  [
    body('title').notEmpty().withMessage('Título é obrigatório'),
    body('description').optional(),
    body('status').isIn(['not_started', 'on_track', 'at_risk', 'off_track', 'completed']),
    body('progress').isInt({ min: 0, max: 100 }).withMessage('Progresso deve estar entre 0 e 100'),
    body('keyResults').isArray().withMessage('Key Results devem ser um array'),
    body('keyResults.*.description').notEmpty().withMessage('Descrição do KR é obrigatória'),
    body('keyResults.*.target').isFloat({ min: 0 }).withMessage('Target deve ser um número positivo'),
    body('keyResults.*.current').isFloat({ min: 0 }).withMessage('Current deve ser um número positivo'),
    body('keyResults.*.unit').notEmpty().withMessage('Unidade é obrigatória')
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { title, description, status, progress, targetDate, keyResults } = req.body;

      const objective = await prisma.objective.create({
        data: {
          title,
          description: description || '',
          status,
          progress: progress || 0,
          targetDate: targetDate ? new Date(targetDate) : null,
          userId: req.user.id,
          keyResults: {
            create: keyResults.map(kr => ({
              description: kr.description,
              target: kr.target,
              current: kr.current || 0,
              unit: kr.unit,
              status: kr.status || 'not_started'
            }))
          }
        },
        include: {
          keyResults: true
        }
      });

      res.status(201).json(objective);
    } catch (error) {
      console.error('Erro ao criar objetivo:', error);
      res.status(500).json({ error: 'Erro ao criar objetivo' });
    }
  }
);

router.put('/:id',
  [
    body('title').optional().notEmpty(),
    body('status').optional().isIn(['not_started', 'on_track', 'at_risk', 'off_track', 'completed']),
    body('progress').optional().isInt({ min: 0, max: 100 })
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const existing = await prisma.objective.findFirst({
        where: { id: req.params.id, userId: req.user.id }
      });

      if (!existing) {
        return res.status(404).json({ error: 'Objetivo não encontrado' });
      }

      const { title, description, status, progress, targetDate } = req.body;

      const objective = await prisma.objective.update({
        where: { id: req.params.id },
        data: {
          ...(title && { title }),
          ...(description !== undefined && { description }),
          ...(status && { status }),
          ...(progress !== undefined && { progress }),
          ...(targetDate !== undefined && { targetDate: targetDate ? new Date(targetDate) : null })
        },
        include: {
          keyResults: true
        }
      });

      res.json(objective);
    } catch (error) {
      console.error('Erro ao atualizar objetivo:', error);
      res.status(500).json({ error: 'Erro ao atualizar objetivo' });
    }
  }
);

router.delete('/:id', async (req, res) => {
  try {
    const existing = await prisma.objective.findFirst({
      where: { id: req.params.id, userId: req.user.id }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Objetivo não encontrado' });
    }

    await prisma.objective.delete({
      where: { id: req.params.id }
    });

    res.status(204).send();
  } catch (error) {
    console.error('Erro ao deletar objetivo:', error);
    res.status(500).json({ error: 'Erro ao deletar objetivo' });
  }
});

router.put('/:objectiveId/key-results/:krId',
  [
    body('current').optional().isFloat({ min: 0 }),
    body('status').optional().isIn(['not_started', 'on_track', 'at_risk', 'off_track', 'completed'])
  ],
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const objective = await prisma.objective.findFirst({
        where: { id: req.params.objectiveId, userId: req.user.id }
      });

      if (!objective) {
        return res.status(404).json({ error: 'Objetivo não encontrado' });
      }

      const kr = await prisma.keyResult.findFirst({
        where: { id: req.params.krId, objectiveId: req.params.objectiveId }
      });

      if (!kr) {
        return res.status(404).json({ error: 'Key Result não encontrado' });
      }

      const { current, status } = req.body;

      const updated = await prisma.keyResult.update({
        where: { id: req.params.krId },
        data: {
          ...(current !== undefined && { current }),
          ...(status && { status })
        }
      });

      res.json(updated);
    } catch (error) {
      console.error('Erro ao atualizar Key Result:', error);
      res.status(500).json({ error: 'Erro ao atualizar Key Result' });
    }
  }
);

export default router;
