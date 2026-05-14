import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { adminApi } from '../api/client';
import PageHeader from '../components/PageHeader';

export default function PromptPage() {
  const [prompt, setPrompt]     = useState('');
  const [original, setOriginal] = useState('');
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const textareaRef             = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    adminApi
      .getPrompt()
      .then(({ prompt: p }) => {
        setPrompt(p);
        setOriginal(p);
      })
      .catch(() => toast.error('Không thể tải system prompt'))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const { message } = await adminApi.savePrompt(prompt);
      setOriginal(prompt);
      toast.success(message || 'Đã lưu thành công');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Lỗi khi lưu');
    } finally {
      setSaving(false);
    }
  }

  const isDirty    = prompt !== original;
  const charCount  = prompt.length;
  const lineCount  = prompt ? prompt.split('\n').length : 0;

  return (
    <>
      <PageHeader
        title="System Prompt"
        description="Thay đổi áp dụng ngay cho phiên Gemini tiếp theo — không cần restart server."
      />

      {/* Stats row */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <StatCard label="Ký tự"    value={charCount.toLocaleString('vi')} />
        <StatCard label="Dòng"     value={String(lineCount)} />
        <StatCard
          label="Trạng thái"
          value={loading ? '—' : isDirty ? 'Chưa lưu' : 'Đồng bộ'}
          valueClass={
            loading ? 'text-gray-500' : isDirty ? 'text-amber-400' : 'text-emerald-400'
          }
        />
      </div>

      {/* Editor card */}
      <div className="card p-6">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">
            Nội dung prompt
          </span>
          <span className="text-xs text-teal-400">
            {charCount.toLocaleString('vi')} ký tự
          </span>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-7 w-7 animate-spin rounded-full border-2 border-teal-400 border-t-transparent" />
          </div>
        ) : (
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            spellCheck={false}
            rows={14}
            className="input min-h-[260px] resize-y font-mono text-sm leading-relaxed"
            placeholder="Nhập system prompt cho AI..."
          />
        )}

        {/* Actions */}
        <div className="mt-4 flex items-center justify-end gap-2">
          {isDirty && !saving && (
            <button onClick={() => setPrompt(original)} className="btn-ghost">
              Hoàn tác
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !isDirty || loading}
            className="btn-primary"
          >
            {saving ? 'Đang lưu...' : 'Lưu Prompt'}
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Sub-component ────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  valueClass = 'text-teal-400',
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-widest text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}
