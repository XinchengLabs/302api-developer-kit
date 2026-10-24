import '../components/index.js';

const picker = document.getElementById('models');
picker.models = [
  { id: 'example-chat-model', name: '示例文本模型' },
  { id: 'example-vision-model', name: '示例视觉模型' },
  { id: 'example-embedding-model', name: '示例向量模型' },
];
picker.addEventListener('model-select', event => {
  document.getElementById('selection').textContent = `已选择：${event.detail.id}`;
});
