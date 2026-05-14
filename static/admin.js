/**
 * admin.js — Alpine.js app for Lâm Đồng AI Admin Panel
 * Requires: CodeMirror 5 (global), Alpine.js 3 (deferred)
 */

const ADMIN_TOKEN_KEY = 'adminToken';

function adminApp() {
  return {

    // ── State ──────────────────────────────────────────────────────────────
    activeTab:     'prompt',
    config:        {},
    charCount:     0,
    saving:        false,
    toast:         { show: false, message: '', type: 'ok' },
    editor:        null,

    // Auth
    loggedIn:      false,
    loginPassword: '',
    loginError:    '',
    loginLoading:  false,

    // ── Auth helpers ───────────────────────────────────────────────────────

    /** Fetch wrapper that injects X-Admin-Token and handles 401 */
    async authFetch(url, opts = {}) {
      const token = localStorage.getItem(ADMIN_TOKEN_KEY) || '';
      const headers = Object.assign({ 'X-Admin-Token': token }, opts.headers || {});
      const res = await fetch(url, Object.assign({}, opts, { headers }));
      if (res.status === 401) {
        this._logout();
        throw new Error('401');
      }
      return res;
    },

    _logout() {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      this.loggedIn = false;
    },

    async doLogin() {
      this.loginError   = '';
      this.loginLoading = true;
      try {
        const res  = await fetch('/admin/login', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ password: this.loginPassword }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.loginError = data.detail || 'Sai mật khẩu';
          return;
        }
        localStorage.setItem(ADMIN_TOKEN_KEY, data.token);
        this.loginPassword = '';
        this.loggedIn      = true;
        this._afterLogin();
      } catch {
        this.loginError = 'Không kết nối được server';
      } finally {
        this.loginLoading = false;
      }
    },

    // ── Lifecycle ──────────────────────────────────────────────────────────
    async init() {
      // Initialise CodeMirror 5 editor
      this.editor = CodeMirror(document.getElementById('editor-container'), {
        value:        '',
        mode:         'text/plain',
        theme:        'dracula',
        lineNumbers:  true,
        lineWrapping: true,
        indentUnit:   2,
        extraKeys: {
          'Ctrl-S': () => this.savePrompt(),
          'Cmd-S':  () => this.savePrompt(),
        },
      });

      this.editor.on('change', (cm) => {
        this.charCount = cm.getValue().length;
      });

      if (window.lucide) lucide.createIcons();

      // Restore session from localStorage
      const saved = localStorage.getItem(ADMIN_TOKEN_KEY);
      if (saved) {
        // Verify token is still valid
        try {
          const res = await fetch('/admin/api/me', {
            headers: { 'X-Admin-Token': saved },
          });
          if (res.ok) {
            this.loggedIn = true;
            this._afterLogin();
            return;
          }
        } catch { /* fall through to login screen */ }
        localStorage.removeItem(ADMIN_TOKEN_KEY);
      }
      // No valid token — show login overlay (loggedIn stays false)
    },

    _afterLogin() {
      this.loadPrompt();
      this.loadConfig();
    },

    // ── API calls ──────────────────────────────────────────────────────────

    async loadPrompt() {
      try {
        const res  = await this.authFetch('/admin/prompt');
        const data = await res.json();
        const text = data.prompt || '';
        this.editor.setValue(text);
        this.charCount = text.length;
      } catch (e) {
        if (e.message !== '401') this.showToast('Không thể tải prompt', 'err');
      }
    },

    async loadConfig() {
      try {
        const res   = await this.authFetch('/admin/config');
        this.config = await res.json();
      } catch (e) {
        if (e.message !== '401') console.error('[admin] loadConfig:', e);
      }
    },

    async savePrompt() {
      const text = this.editor.getValue().trim();
      if (!text) {
        this.showToast('Prompt không được để trống', 'err');
        return;
      }

      this.saving = true;
      try {
        const res  = await this.authFetch('/admin/prompt', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ prompt: text }),
        });
        const data = await res.json();
        if (res.ok) {
          const hms = new Date().toTimeString().slice(0, 8);
          this.showToast(`Đã lưu lúc ${hms}`, 'ok');
        } else {
          this.showToast(data.detail || data.message || 'Lỗi khi lưu', 'err');
        }
      } catch (e) {
        if (e.message !== '401') this.showToast('Lỗi kết nối server', 'err');
      } finally {
        this.saving = false;
      }
    },

    async resetPrompt() {
      if (!confirm('Reset về prompt mặc định (lúc server khởi động)?')) return;
      try {
        const res = await this.authFetch('/admin/reset', { method: 'POST' });
        if (res.ok) {
          await this.loadPrompt();
          this.showToast('Đã reset về mặc định', 'ok');
        } else {
          this.showToast('Lỗi khi reset', 'err');
        }
      } catch (e) {
        if (e.message !== '401') this.showToast('Lỗi kết nối server', 'err');
      }
    },

    // ── Helpers ────────────────────────────────────────────────────────────

    showToast(message, type = 'ok') {
      this.toast = { show: true, message, type };
      setTimeout(() => { this.toast.show = false; }, 3000);
    },

    charCountClass() {
      if (this.charCount > 2000) return 'danger';
      if (this.charCount > 1500) return 'warn';
      return 'ok';
    },

  };
}
