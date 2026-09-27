import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { resolveTaskToQuery } from './civicTaskResolver.js';
import { findNearbyOffices } from './placesService.js';

// Load environment variables from .env
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

/**
 * Health check endpoint
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'civic-locator-backend',
    mockMode: process.env.USE_MOCK_DATA !== 'false'
  });
});

/**
 * POST /api/resolve-task
 * Resolves natural language civic/municipal tasks to structured department queries.
 * Calls existing resolveTaskToQuery function unchanged.
 *
 * Body: { task: string } or { query: string }
 */
app.post('/api/resolve-task', (req, res) => {
  try {
    const task =
      req.body?.task ||
      req.body?.query ||
      req.body?.taskInput ||
      req.body?.text ||
      (typeof req.body === 'string' ? req.body : '');

    if (!task || !task.trim()) {
      return res.status(400).json({
        error: 'Task description is required. Please provide a "task" or "query" in the JSON request body.'
      });
    }

    const resolution = resolveTaskToQuery(task);
    return res.json(resolution);
  } catch (err) {
    console.error('Error in POST /api/resolve-task:', err);
    return res.status(500).json({
      error: err.message || 'Internal server error resolving civic task'
    });
  }
});

/**
 * GET /api/nearby-offices
 * Locates nearest government offices and service kendras based on query and coordinates.
 * Calls existing findNearbyOffices function unchanged.
 *
 * Query Params:
 *  - query (string): Search query or resolved target
 *  - userLat (number): Latitude (default: 28.6139)
 *  - userLng (number): Longitude (default: 77.2090)
 *  - radiusMeters (number): Radius in meters (default: 10000)
 */
app.get('/api/nearby-offices', async (req, res) => {
  try {
    const query = req.query.query || req.query.q || req.query.task || '';
    const userLat =
      req.query.userLat !== undefined
        ? parseFloat(req.query.userLat)
        : req.query.lat !== undefined
        ? parseFloat(req.query.lat)
        : undefined;

    const userLng =
      req.query.userLng !== undefined
        ? parseFloat(req.query.userLng)
        : req.query.lng !== undefined
        ? parseFloat(req.query.lng)
        : undefined;

    const radiusMeters =
      req.query.radiusMeters !== undefined
        ? parseInt(req.query.radiusMeters, 10)
        : req.query.radius !== undefined
        ? parseInt(req.query.radius, 10)
        : undefined;

    const result = await findNearbyOffices({
      query,
      userLat: isNaN(userLat) ? undefined : userLat,
      userLng: isNaN(userLng) ? undefined : userLng,
      radiusMeters: isNaN(radiusMeters) ? undefined : radiusMeters
    });

    return res.json(result);
  } catch (err) {
    console.error('Error in GET /api/nearby-offices:', err);
    return res.status(500).json({
      success: false,
      data: [],
      error: err.message || 'Internal server error finding nearby offices',
      isMock: true
    });
  }
});

// Start listening if executed directly
app.listen(PORT, () => {
  console.log(`Civic Locator Backend running on http://localhost:${PORT}`);
  console.log(`  - POST /api/resolve-task`);
  console.log(`  - GET  /api/nearby-offices`);
});

export default app;
