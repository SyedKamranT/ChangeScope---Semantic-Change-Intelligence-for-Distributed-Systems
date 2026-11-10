import axios from 'axios';

export interface CheckoutOrderRequest {
  orderId: string;
  itemId: string;
}

export class InventoryClient {
  private baseUrl = 'http://inventory.internal';

  async reserveItem(itemId: string, sku: string): Promise<any> {
    // Outbound call to inventory-service
    const response = await axios.post(`${this.baseUrl}/api/v1/items`, {
      item_id: itemId,
      sku: sku,
      status: 'AVAILABLE'
    });
    return response.data;
  }
}
