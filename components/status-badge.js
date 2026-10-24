// MIT: presentation only. The caller supplies a verified state, or unknown.
const STATES = {
  operational: ['#16844b', '运行正常'],
  degraded: ['#a76500', '服务异常'],
  unknown: ['#65738a', '状态未知'],
};

export class ApiStatusBadge extends HTMLElement {
  static observedAttributes = ['state'];
  connectedCallback() {
    if (!this.shadowRoot) {
      const root = this.attachShadow({ mode: 'open' });
      const style = document.createElement('style');
      style.textContent = ':host{display:inline-block;font:inherit}span{display:inline-flex;align-items:center;gap:8px;border:1px solid #dce2eb;border-radius:999px;padding:8px 12px;background:#fff;font-size:.9rem}i{width:8px;height:8px;border-radius:50%;background:currentColor}';
      const span = document.createElement('span');
      span.setAttribute('role', 'status');
      span.append(document.createElement('i'), document.createElement('b'));
      span.firstChild.setAttribute('aria-hidden', 'true');
      root.append(style, span);
    }
    this.#render();
  }
  attributeChangedCallback() { this.#render(); }
  #render() {
    const span = this.shadowRoot?.querySelector('span');
    if (!span) return;
    const state = this.getAttribute('state');
    const [color, text] = Object.hasOwn(STATES, state) ? STATES[state] : STATES.unknown;
    span.style.color = color;
    span.querySelector('b').textContent = text;
  }
}
if (!customElements.get('api-status-badge')) customElements.define('api-status-badge', ApiStatusBadge);
