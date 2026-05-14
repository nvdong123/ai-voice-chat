import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { adminApi } from '../api/client';
import PageHeader from '../components/PageHeader';

interface Config {
  model: string;
  voice: string;
  availableVoices: string[];
}

interface GeminiModel {
  name: string;
  displayName: string;
}

// ─── Tiny stat card ──────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  valueClass = 'text-gray-100',
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="card p-4">
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-500">
        {label}
      </p>
      <p className={`truncate text-sm font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

export default function ConfigPage() {
  const [config, setConfig]                   = useState<Config | null>(null);
  const [model, setModel]                     = useState('');
  const [voice, setVoice]                     = useState('');
  const [loading, setLoading]                 = useState(true);
  const [saving, setSaving]                   = useState(false);
  const [availableModels, setAvailableModels] = useState<GeminiModel[] | null>(null);
  const [modelsLoading, setModelsLoading]     = useState(true);

  useEffect(() => {
    // Config and models fetched independently so one failure doesn't block the other
    adminApi
      .getConfig()
      .then((cfg) => {
        setConfig(cfg);
        setModel(cfg.model ?? '');
        setVoice(cfg.voice ?? '');
      })
      .catch(() => toast.error('Không thể tải cấu hình'))
      .finally(() => setLoading(false));

    adminApi
      .getModels()
      .then((res) => setAvailableModels(res.models))
      .catch(() => setAvailableModels(null))   // null = show text input fallback
      .finally(() => setModelsLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const { message } = await adminApi.saveConfig(model.trim(), voice);
      setConfig((prev) => (prev ? { ...prev, model: model.trim(), voice } : prev));
      toast.success(message || 'Đã lưu cấu hình');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Lỗi khi lưu');
    } finally {
      setSaving(false);
    }
  }

  const isDirty =
    config !== null && (model !== config.model || voice !== config.voice);

  // Current model might not be in the fetched list (e.g. custom/new model) — add it so it shows
  const modelOptions: GeminiModel[] = availableModels
    ? availableModels.some((m) => m.name === model)
      ? availableModels
      : [{ name: model, displayName: model + ' (hiện tại)' }, ...availableModels]
    : [];

  return (
    <>
      <PageHeader
        title="Cấu hình AI"
        description="Model và giọng đọc áp dụng ngay cho phiên Gemini tiếp theo — không cần restart server."
      />

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <StatCard label="Model hiện tại" value={config?.model ?? '—'} />
        <StatCard label="Voice hiện tại" value={config?.voice ?? '—'} />
        <StatCard
          label="Trạng thái"
          value={loading ? '—' : isDirty ? 'Chưa lưu' : 'Đồng bộ'}
          valueClass={
            loading ? 'text-gray-500' : isDirty ? 'text-amber-400' : 'text-emerald-400'
          }
        />
      </div>

      {/* Config card */}
      <div className="card p-6">
        <div className="mb-5 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">
            Cài đặt mô hình
          </span>
          {availableModels !== null && (
            <span className="text-xs text-teal-400">
              {availableModels.length} model Live API
            </span>
          )}
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <div className="h-7 w-7 animate-spin rounded-full border-2 border-teal-400 border-t-transparent" />
          </div>
        ) : (
          <div className="space-y-5">
            {/* Model — dropdown if list loaded, text input as fallback */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">
                Gemini Model
              </label>

              {modelsLoading ? (
                <div className="input flex w-full items-center gap-2 text-gray-500">
                  <div className="h-4 w-4 flex-shrink-0 animate-spin rounded-full border-2 border-teal-400 border-t-transparent" />
                  <span className="text-sm">Đang tải danh sách model…</span>
                </div>
              ) : availableModels !== null ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="input w-full"
                >
                  {modelOptions.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.displayName}
                    </option>
                  ))}
                </select>
              ) : (
                <>
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="vd: gemini-2.0-flash-live-001"
                    className="input w-full font-mono text-sm"
                  />
                  <p className="mt-1 text-xs text-amber-500">
                    Không thể tải danh sách model — nhập tên model thủ công (không cần tiền tố{' '}
                    <code>models/</code>).
                  </p>
                </>
              )}
            </div>

            {/* Voice */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">
                Giọng đọc (Voice)
              </label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="input w-full"
              >
                {(config?.availableVoices ?? []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-end gap-2">
          {isDirty && !saving && (
            <button
              onClick={() => {
                if (config) {
                  setModel(config.model);
                  setVoice(config.voice);
                }
              }}
              className="btn-ghost"
            >
              Hoàn tác
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !isDirty || loading || !(model ?? '').trim()}
            className="btn-primary"
          >
            {saving ? 'Đang lưu...' : 'Lưu cấu hình'}
          </button>
        </div>
      </div>
    </>
  );
}
