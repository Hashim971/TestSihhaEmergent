import { PineconeClient } from '@pinecone-database/pinecone';

class PineconeService {
  private static instance: PineconeService;
  private client: PineconeClient | null = null;
  private initialized = false;

  private constructor() {}

  static getInstance(): PineconeService {
    if (!PineconeService.instance) {
      PineconeService.instance = new PineconeService();
    }
    return PineconeService.instance;
  }

  async initialize() {
    if (!this.initialized) {
      try {
        this.client = new PineconeClient();
        await this.client.init({
          apiKey: import.meta.env.VITE_PINECONE_API_KEY || '',
          environment: import.meta.env.VITE_PINECONE_ENVIRONMENT || ''
        });
        this.initialized = true;
      } catch (error) {
        console.error('Failed to initialize Pinecone:', error);
        throw new Error('Failed to initialize Pinecone client');
      }
    }
    return this.client;
  }

  async getIndex(indexName: string) {
    if (!this.initialized) {
      await this.initialize();
    }
    return this.client?.Index(indexName);
  }
}

export const pineconeService = PineconeService.getInstance();