// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// a dependency-free copy button. It never receives or stores API keys.
export class ApiCodeCopy extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const root = this.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = `
      :host{display:inline-flex;align-items:center;gap:10px;font:inherit}
      button{font:inherit;border:1px solid #ccd5e4;border-radius:10px;padding:8px 14px;
        background:#fff;color:#2457bf;cursor:pointer}
      button:focus-visible{outline:3px solid #b8ceff;outline-offset:2px}
      span{font-size:.875rem;color:#526075}
    `;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = this.getAttribute('label') || '复制代码';
    const status = document.createElement('span');
    status.setAttribute('role', 'status');
    button.addEventListener('click', async () => {
      const id = this.getAttribute('for');
      const target = id && this.getRootNode().getElementById(id);
      if (!target) { status.textContent = '未找到代码区域'; return; }
      try {
        await navigator.clipboard.writeText(target.textContent);
        status.textContent = '已复制';
      } catch {
        status.textContent = '无法自动复制，请手动选择代码';
      }
    });
    root.append(style, button, status);
  }
}
if (!customElements.get('api-code-copy')) customElements.define('api-code-copy', ApiCodeCopy);
