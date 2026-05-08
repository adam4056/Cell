function cellApp() {
  return {
    mode: 'space',
    messages: [],
    chats: [],
    currentChat: null,
    draft: '',
    thinking: false,
    ws: null,
    connected: false,
    toasts: [],

    // Command panel
    panelOpen: false,
    panelView: 'root',
    statusData: null,
    memoryEntries: [],
    memoryQuery: '',
    ambientData: null,
    permissionsData: null,

    async init() {
      await this.loadChats();
      await this.loadSpace();
      this.connect();
      this.$nextTick(() => this.focusInput());
      this.attachCodeCopyHandler();
    },

    attachCodeCopyHandler() {
      document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pre-copy');
        if (!btn) return;
        const wrapper = btn.closest('.code-block');
        const pre = wrapper ? wrapper.querySelector('pre') : btn.closest('pre');
        if (!pre) return;
        const code = pre.querySelector('code');
        const text = code ? code.textContent : pre.textContent;
        this.copyText(text);
        btn.classList.add('copied');
        const orig = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(() => {
          btn.textContent = orig;
          btn.classList.remove('copied');
        }, 1400);
      });
    },

    connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      this.ws = new WebSocket(`${proto}://${location.host}/ws`);
      this.ws.onopen = () => { this.connected = true; };
      this.ws.onmessage = (e) => this.handleEvent(JSON.parse(e.data));
      this.ws.onclose = () => {
        this.connected = false;
        setTimeout(() => this.connect(), 1500);
      };
      this.ws.onerror = () => { this.connected = false; };
    },

    handleEvent(ev) {
      if (ev.type === 'thinking') {
        this.thinking = true;
      } else if (ev.type === 'user_echo') {
        // already pushed locally on send()
      } else if (ev.type === 'assistant') {
        this.thinking = false;
        if (ev.content && ev.content.startsWith('[SYSTEM ERROR]')) {
          this.messages.push({ role: 'system', content: ev.content });
        } else if (ev.content) {
          this.messages.push({ role: 'assistant', content: ev.content });
        }
        this.scrollBottom();
        if (this.mode === 'chat' && this.currentChat) this.loadChats();
      } else if (ev.type === 'inbox') {
        this.toast(`📬 ${ev.content}`);
        if (this.mode === 'space') {
          this.messages.push({ role: 'system', content: `[inbox] ${ev.content}` });
        }
      } else if (ev.type === 'permission_request') {
        this.handlePermissionRequest(ev);
      }
    },

    async loadSpace() {
      try {
        const r = await fetch('/api/space');
        const data = await r.json();
        if (this.mode === 'space') {
          this.messages = (data.history || []).filter(m => m.role !== 'tool');
          this.$nextTick(() => this.scrollBottom());
        }
      } catch (e) { /* ignore */ }
    },

    async loadChats() {
      try {
        const r = await fetch('/api/chats');
        const data = await r.json();
        this.chats = data.chats || [];
      } catch (e) { /* ignore */ }
    },

    renderMd(text) {
      if (typeof marked === 'undefined') return this.escapeHtml(text);
      // Strip noisy backend prefixes — they leak into normal messages
      text = String(text).replace(/^\[(SCHEDULED|AMBIENT|inbox|SYSTEM)\]\s*/i, '');
      let html = marked.parse(text, { breaks: true, gfm: true });
      if (typeof DOMPurify !== 'undefined') {
        html = DOMPurify.sanitize(html, { ADD_ATTR: ['target', 'class'] });
      }
      // Wrap each <pre> in a code-block with header (lang + Copy) and run hljs
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      tmp.querySelectorAll('pre').forEach((pre) => {
        const code = pre.querySelector('code');
        let lang = '';
        if (code) {
          const m = (code.className || '').match(/language-([\w+\-#]+)/i);
          if (m) lang = m[1].toLowerCase();
        }
        // Apply hljs
        if (typeof hljs !== 'undefined' && code) {
          try {
            const raw = code.textContent;
            let result;
            if (lang && hljs.getLanguage(lang)) {
              result = hljs.highlight(raw, { language: lang, ignoreIllegals: true });
            } else {
              result = hljs.highlightAuto(raw);
              if (!lang) lang = result.language || 'text';
            }
            code.innerHTML = result.value;
            code.classList.add('hljs');
          } catch (e) { /* ignore highlight errors */ }
        }
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block';
        const bar = document.createElement('div');
        bar.className = 'code-bar';
        bar.innerHTML = `<span class="code-lang">${this.escapeHtml(lang || 'text')}</span><button type="button" class="pre-copy">Copy</button>`;
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(bar);
        wrapper.appendChild(pre);
      });
      return tmp.innerHTML;
    },

    renderSystem(text) {
      // Compact one-liner: tiny coloured dot + muted text, truncated with ellipsis.
      // Strip the [TAG] prefix entirely — it's noise.
      let cleanBody = String(text);
      let tagClass = '';
      const tagMatch = cleanBody.match(/^\[([A-Za-z_ ]+)\]\s*([\s\S]*)$/);
      if (tagMatch) {
        cleanBody = tagMatch[2];
        tagClass = this.systemTagClass(tagMatch[1]);
      } else {
        const p = cleanBody.match(/^\(([^)]+)\)\s*([\s\S]*)$/);
        if (p) cleanBody = p[2] || `(${p[1]})`;
      }
      let bodyHtml = typeof marked !== 'undefined'
        ? marked.parseInline(cleanBody, { breaks: false })
        : this.escapeHtml(cleanBody);
      if (typeof DOMPurify !== 'undefined') {
        bodyHtml = DOMPurify.sanitize(bodyHtml);
      }
      return `<span class="sys-icon ${tagClass}"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg></span><span class="sys-label">${bodyHtml}</span>`;
    },

    systemTagClass(tag) {
      const t = tag.toUpperCase().trim();
      if (t.includes('ERROR')) return 'sys-error';
      if (t === 'AMBIENT') return 'sys-ambient';
      if (t === 'INBOX') return 'sys-inbox';
      return '';
    },

    escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[c]));
    },

    async setMode(m) {
      // Clicking same Chats pill while in a chat → close chat
      if (m === 'chat' && this.mode === 'chat' && this.currentChat) {
        this.currentChat = null;
        this.messages = [];
        await this.loadChats();
        return;
      }
      this.mode = m;
      if (m === 'space') {
        this.currentChat = null;
        await this.loadSpace();
      } else {
        await this.loadChats();
        if (!this.currentChat) {
          this.messages = [];
        }
      }
      this.$nextTick(() => this.focusInput());
    },

    closeChat() {
      this.currentChat = null;
      this.messages = [];
      this.loadChats();
    },

    async newChat() {
      const r = await fetch('/api/chats', { method: 'POST' });
      const chat = await r.json();
      await this.loadChats();
      await this.openChat(chat.id);
    },

    async openChat(id) {
      const r = await fetch(`/api/chats/${id}`);
      const chat = await r.json();
      if (chat.error) return;
      this.currentChat = { id: chat.id, title: chat.title };
      this.messages = (chat.history || []).filter(m => m.role !== 'tool');
      this.$nextTick(() => {
        this.scrollBottom();
        this.focusInput();
      });
    },

    async deleteChat(id) {
      await fetch(`/api/chats/${id}`, { method: 'DELETE' });
      if (this.currentChat && this.currentChat.id === id) {
        this.currentChat = null;
        this.messages = [];
      }
      await this.loadChats();
    },

    onEnter(ev) {
      if (ev.shiftKey) return; // newline
      ev.preventDefault();
      this.send();
    },

    autoGrow(ev) {
      const t = ev.target;
      t.style.height = 'auto';
      t.style.height = Math.min(t.scrollHeight, 200) + 'px';
    },

    resetTextareaHeight() {
      const t = this.$refs.input;
      if (t) t.style.height = 'auto';
    },

    focusInput() {
      const t = this.$refs.input;
      if (t && !t.disabled) t.focus();
    },

    send() {
      const text = this.draft.trim();
      if (!text || this.thinking) return;
      if (this.mode === 'chat' && !this.currentChat) return;
      if (!this.connected) {
        this.toast('Not connected — retrying…');
        return;
      }

      this.messages.push({ role: 'user', content: text });
      this.draft = '';
      this.resetTextareaHeight();
      this.thinking = true;
      this.scrollBottom();

      const payload = { mode: this.mode, text };
      if (this.mode === 'chat' && this.currentChat) payload.chat_id = this.currentChat.id;
      this.ws.send(JSON.stringify(payload));
    },

    stopThinking() {
      this.thinking = false;
      try {
        this.ws.send(JSON.stringify({ type: 'cancel' }));
      } catch (e) {}
      this.toast('Stopped.');
    },

    scrollBottom() {
      requestAnimationFrame(() => {
        const el = document.getElementById('msgs');
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      });
    },

    toast(text) {
      const id = Math.random().toString(36).slice(2);
      this.toasts.push({ id, text });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 3500);
    },

    handlePermissionRequest(ev) {
      const label = ev.label || ev.detail || 'Permission request';
      const detail = ev.detail || '';
      const id = ev.id;
      const shortDetail = detail.length > 120 ? detail.slice(0, 117) + '...' : detail;
      const choice = confirm(`🔐 ${label}\n\n${shortDetail}\n\nAllow?`);
      const decision = choice ? 'always_allow' : 'always_deny';
      fetch('/api/permissions/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, decision })
      }).catch(() => {});
    },

    async copyText(text) {
      try {
        await navigator.clipboard.writeText(text);
      } catch (e) {
        // fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (_) {}
        document.body.removeChild(ta);
      }
    },

    // ── Command panel ──

    openPanel() {
      this.panelOpen = true;
      this.panelView = 'root';
    },

    closePanel() {
      this.panelOpen = false;
    },

    async openPanelView(view) {
      this.panelView = view;
      if (view === 'status') await this.loadStatus();
      else if (view === 'memory') await this.loadMemory();
      else if (view === 'ambient') await this.loadAmbient();
      else if (view === 'permissions') await this.loadPermissions();
    },

    async loadStatus() {
      try {
        const r = await fetch('/api/commands/status');
        this.statusData = await r.json();
      } catch (e) { this.toast('Failed to load status'); }
    },

    async loadMemory() {
      try {
        const url = this.memoryQuery
          ? `/api/commands/memory?q=${encodeURIComponent(this.memoryQuery)}`
          : '/api/commands/memory';
        const r = await fetch(url);
        const data = await r.json();
        this.memoryEntries = data.results || data.entries || [];
      } catch (e) { this.toast('Failed to load memory'); }
    },

    async searchMemory() {
      await this.loadMemory();
    },

    async loadAmbient() {
      try {
        const r = await fetch('/api/commands/ambient');
        this.ambientData = await r.json();
      } catch (e) { this.toast('Failed to load ambient'); }
    },

    async toggleAmbient() {
      const next = !this.ambientData?.enabled;
      try {
        await fetch('/api/commands/ambient', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: next }),
        });
        await this.loadAmbient();
        this.toast(next ? 'Ambient enabled' : 'Ambient disabled');
      } catch (e) { this.toast('Failed to update ambient'); }
    },

    ambientQuiet() {
      const qh = this.ambientData?.quiet_hours;
      if (!qh) return '—';
      const pad = (n) => String(n).padStart(2, '0');
      return `${pad(qh[0])}:00 – ${pad(qh[1])}:00`;
    },

    async loadPermissions() {
      try {
        const r = await fetch('/api/commands/permissions');
        this.permissionsData = await r.json();
      } catch (e) { this.toast('Failed to load permissions'); }
    },

    async setPermission(type, policy) {
      try {
        const r = await fetch('/api/commands/permissions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ perm_type: type, policy }),
        });
        const data = await r.json();
        if (data.error) {
          this.toast(data.error);
        } else {
          this.toast(`${type} → ${policy.replace('_', ' ')}`);
        }
        await this.loadPermissions();
      } catch (e) { this.toast('Failed to update permission'); }
    },

    async cmdAmbientNow() {
      this.toast('Triggering ambient tick…');
      try {
        const r = await fetch('/api/commands/ambient', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'now' }),
        });
        const data = await r.json();
        this.toast(data.result || 'Done');
      } catch (e) { this.toast('Ambient tick failed'); }
    },

    async confirmClear() {
      if (!confirm('Clear conversation context? This cannot be undone.')) return;
      try {
        await fetch('/api/commands/clear', { method: 'POST' });
        this.messages = [];
        this.toast('Context cleared');
        this.closePanel();
        await this.loadSpace();
      } catch (e) { this.toast('Clear failed'); }
    },

    async confirmReset() {
      if (!confirm('Factory reset? Wipes context, memory, schedule, settings, and brain functions. Cannot be undone.')) return;
      if (!confirm('Are you sure? This is destructive.')) return;
      try {
        await fetch('/api/commands/reset', { method: 'POST' });
        this.messages = [];
        this.chats = [];
        this.currentChat = null;
        this.toast('Factory reset complete');
        this.closePanel();
      } catch (e) { this.toast('Reset failed'); }
    },
  };
}
