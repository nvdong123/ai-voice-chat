import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(password);
      navigate('/prompt', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sai mật khẩu');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface bg-[radial-gradient(ellipse_at_50%_60%,rgba(0,80,60,0.15),transparent_70%)]">
      <div className="w-full max-w-sm px-4">
        <div className="card p-9 shadow-2xl shadow-black/50">
          {/* Logo */}
          <div className="mb-7 text-center">
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-400 to-cyan-400 text-2xl shadow-lg">
              🏔️
            </span>
            <h1 className="mt-4 text-xl font-bold text-gray-100">VR 360 Admin</h1>
            <p className="mt-1 text-sm text-gray-500">Lâm Đồng Tourism Platform</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gray-500"
              >
                Mật khẩu
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="Nhập mật khẩu..."
                required
                className="input"
              />
            </div>

            {error && (
              <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3">
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
