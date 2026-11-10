const express = require('express');
const router = express.Router();

const METRICS_ENDPOINT = process.env.METRICS_ENDPOINT || 'http://metrics.internal/v1/telemetry';

router.get('/health', (req, res) => {
  res.json({ status: 'UP', timestamp: Date.now() });
});

router.post('/metrics/dispatch', async (req, res) => {
  const result = await fetch(METRICS_ENDPOINT, {
    method: 'POST',
    body: JSON.stringify(req.body),
    headers: { 'Content-Type': 'application/json' }
  });
  res.status(result.status).send();
});

module.exports = router;
