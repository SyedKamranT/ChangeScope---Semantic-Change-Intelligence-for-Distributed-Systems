import express, { Request, Response } from 'express';
import axios from 'axios';
import { EventEmitter } from 'events';

const app = express();
const eventBus = new EventEmitter();
const PORT = process.env.PORT || 8082;
const ORDER_SERVICE_URL = process.env.ORDER_SERVICE_URL || 'http://order-service.internal';

app.use(express.json());

app.post('/api/v1/auth/tokens', async (req: Request, res: Response) => {
  const { username, password } = req.body;
  // Outbound call to internal authentication service
  const authResponse = await axios.post(`${ORDER_SERVICE_URL}/api/v1/verify`, {
    username,
    token: req.headers.authorization,
  });

  eventBus.emit('user.authenticated', { username, timestamp: Date.now() });
  res.json({ token: 'jwt-mock-token', status: authResponse.data.status });
});

app.get('/api/v1/users/profile', (req: Request, res: Response) => {
  res.json({ id: 'usr-123', role: 'admin' });
});

export default app;
