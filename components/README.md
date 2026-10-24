# 前端组件

以 Web Components 独立实现，使用原生 HTML / CSS / JavaScript，不依赖 React、框架构建器、生产接口或远程字体。通过 Shadow DOM 隔离内部样式。

这些是本仓库的可复用示例组件，不是 302API 整站前端开发源码，也不是生产后端的公开副本。

## 引入

通过 HTTP 服务加载项目，引用模块：

```html
<script type="module" src="/components/index.js"></script>
<pre id="example">const model = 'MODEL_ID_HERE';</pre>
<api-code-copy for="example"></api-code-copy>
<api-model-picker id="models"></api-model-picker>
<api-status-badge state="unknown"></api-status-badge>
```

```js
import '/components/index.js';

const picker = document.getElementById('models');
picker.models = [{ id: 'example-model', name: '示例模型' }];
picker.addEventListener('model-select', event => {
  console.log(event.detail.id);
});
```

`/components/` 应替换为项目实际的静态资源路径。

## API

| 组件 | 属性 / 方法 | 行为 |
|---|---|---|
| `api-code-copy` | `for="代码元素ID"`、可选 `label` | 复制同一 Document 或 ShadowRoot 中目标元素的纯文本 |
| `api-model-picker` | `.models = [{id, name}]`，只读 `.value` | 对 ID / 名称做本地部分匹配，使用原生 select 选择 |
| `api-model-picker` | `model-select` 事件 | 用户改变选项时发出 `detail.id` |
| `api-status-badge` | `state` | 支持 `operational`、`degraded`、`unknown`，其他值按未知处理 |

组件不请求网络、不保存 API Key、不推荐模型、不计算价格，也不自动证明服务可用。应用应传入自己取得且有权限使用的数据。

代码复制使用 Clipboard API，需要 HTTPS 或 localhost；不可用时提示手动复制。标签、原生表单控件和状态提示包含基础语义，但本次未进行浏览器、移动设备或辅助技术验收。

## 本地演示

在仓库根目录执行：

```bash
python3 -m http.server 8080 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8080/demo/`。演示不读取 `.env`，不向本站发送请求，也不产生模型费用。
