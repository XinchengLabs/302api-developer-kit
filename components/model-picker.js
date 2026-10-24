// SPDX-License-Identifier: LicenseRef-302API-Community-Commercial-1.0
// local ID/name filtering only. No model recommendation or network request.
export class ApiModelPicker extends HTMLElement {
  #models = [];
  #query;
  #select;
  #summary;

  set models(values) {
    if (!Array.isArray(values)) throw new TypeError('models must be an array');
    this.#models = values.map(value => {
      const model = typeof value === 'string' ? { id: value } : value;
      if (!model || typeof model.id !== 'string' || !model.id.trim()) {
        throw new TypeError('Each model needs a nonempty string id');
      }
      return { id: model.id, name: String(model.name || model.id) };
    });
    this.#render();
  }

  get models() { return this.#models.map(model => ({ ...model })); }
  get value() { return this.#select?.value || ''; }

  connectedCallback() {
    if (this.shadowRoot) return;
    const root = this.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = `
      :host{display:block;font:inherit;color:#25334b}
      label{display:grid;gap:8px;margin-bottom:14px;font-size:.95rem}
      input,select{box-sizing:border-box;width:100%;font:inherit;min-height:46px;
        border:1px solid #ccd5e4;border-radius:10px;background:#fff;color:inherit;padding:10px 12px}
      input:focus-visible,select:focus-visible{outline:3px solid #b8ceff;outline-offset:2px}
      p{margin:0;color:#526075;font-size:.875rem}
    `;
    const searchLabel = document.createElement('label');
    searchLabel.append('搜索模型 ID 或展示名称');
    this.#query = document.createElement('input');
    this.#query.type = 'search';
    this.#query.placeholder = '输入部分名称';
    this.#query.addEventListener('input', () => this.#render());
    searchLabel.append(this.#query);
    const selectLabel = document.createElement('label');
    selectLabel.append('选择模型');
    this.#select = document.createElement('select');
    this.#select.addEventListener('change', () => {
      this.dispatchEvent(new CustomEvent('model-select', {
        detail: { id: this.#select.value }, bubbles: true, composed: true,
      }));
    });
    selectLabel.append(this.#select);
    this.#summary = document.createElement('p');
    this.#summary.setAttribute('role', 'status');
    root.append(style, searchLabel, selectLabel, this.#summary);
    this.#render();
  }

  #render() {
    if (!this.#select) return;
    const previous = this.#select.value;
    const query = this.#query.value.trim().toLocaleLowerCase();
    const matches = this.#models.filter(model =>
      `${model.id} ${model.name}`.toLocaleLowerCase().includes(query));
    this.#select.replaceChildren();
    for (const model of matches) {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.name === model.id ? model.id : `${model.name} · ${model.id}`;
      this.#select.append(option);
    }
    if (matches.some(model => model.id === previous)) this.#select.value = previous;
    this.#select.disabled = matches.length === 0;
    this.#summary.textContent = matches.length ? `${matches.length} 个匹配项` : '没有匹配的模型';
  }
}
if (!customElements.get('api-model-picker')) customElements.define('api-model-picker', ApiModelPicker);
