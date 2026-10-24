// Select a model whose configured route supports Responses.
import OpenAI from 'openai';

const apiKey = process.env.API_302API_KEY;
const model = process.env.MODEL_ID;
if (!apiKey?.trim() || !model?.trim()) throw new Error('Set API_302API_KEY and MODEL_ID first.');
const client = new OpenAI({
  apiKey,
  baseURL: process.env.API_302API_BASE_URL || 'https://api.302api.com/v1',
  maxRetries: 0,
});
const result = await client.responses.create({ model, input: '请用一句话解释 API。' });
console.log(result.output_text);
