"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  fetchTaskFields,
  updateTask,
  type EditableField,
  type TaskFieldsResponse,
} from "@/lib/api";

type Props = {
  taskId: number;
  /** Called after a successful save so the caller can refresh its list. */
  onSaved: () => void;
  onCancel: () => void;
};

/**
 * Edit the conditions of an existing request from the dashboard.
 *
 * The field list comes from the server rather than being hardcoded here, so it
 * stays in step with the catalogue that drives the AI prompt and the original
 * missing-fields form.
 */
export default function TaskConditionsForm({ taskId, onSaved, onCancel }: Props) {
  const [meta, setMeta] = useState<TaskFieldsResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const data = await fetchTaskFields(taskId, controller.signal);
        if (controller.signal.aborted) return;
        setMeta(data);
        setValues(
          Object.fromEntries(data.fields.map((f) => [f.field, f.value ?? ""])),
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(
          err instanceof ApiError
            ? `讀取需求內容失敗（${err.status}）：${err.message}`
            : "無法連線至後端 API",
        );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [taskId]);

  /** Only what actually changed, so untouched fields are never rewritten. */
  const changed = useMemo(() => {
    if (!meta) return {} as Record<string, string>;
    const diff: Record<string, string> = {};
    for (const f of meta.fields) {
      const next = (values[f.field] ?? "").trim();
      if (next && next !== (f.value ?? "")) diff[f.field] = next;
    }
    return diff;
  }, [meta, values]);

  const changedCount = Object.keys(changed).length;

  async function save() {
    if (changedCount === 0) return;
    setSaving(true);
    setError(null);
    try {
      await updateTask(taskId, { filled_fields: changed });
      onSaved();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `儲存失敗（${err.status}）：${err.message}`
          : "無法連線至後端 API",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mt-3 animate-pulse space-y-2" aria-busy="true">
        <div className="h-9 rounded-lg bg-slate-200" />
        <div className="h-9 rounded-lg bg-slate-200" />
        <div className="h-9 rounded-lg bg-slate-200" />
      </div>
    );
  }

  if (error && !meta) {
    return (
      <p role="alert" className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800">
        {error}
      </p>
    );
  }

  if (meta && !meta.editable) {
    return (
      <div className="mt-3 space-y-2">
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
          <span aria-hidden="true">🔒 </span>
          {meta.locked_reason}
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          關閉
        </button>
      </div>
    );
  }

  const fields = meta?.fields ?? [];

  return (
    <form
      className="mt-3 space-y-3 rounded-lg border border-sky-200 bg-sky-50/60 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <p className="text-xs font-semibold text-sky-900">修改需求內容</p>

      {fields.length === 0 ? (
        <p className="text-xs text-slate-600">這筆需求目前沒有可修改的欄位。</p>
      ) : (
        <div className="space-y-2.5">
          {fields.map((f) => (
            <FieldInput
              key={f.field}
              field={f}
              taskId={taskId}
              value={values[f.field] ?? ""}
              onChange={(v) => setValues((prev) => ({ ...prev, [f.field]: v }))}
            />
          ))}
        </div>
      )}

      {error ? (
        <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800">
          {error}
        </p>
      ) : null}

      <p className="text-[11px] leading-relaxed text-slate-500">
        清空欄位不會刪除原本的值，只有填了內容才會覆蓋。
      </p>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving || changedCount === 0}
          className="flex-1 rounded-lg bg-sky-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {saving
            ? "儲存中…"
            : changedCount === 0
              ? "尚未有變更"
              : `儲存 ${changedCount} 項變更`}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50"
        >
          取消
        </button>
      </div>
    </form>
  );
}

function FieldInput({
  field,
  taskId,
  value,
  onChange,
}: {
  field: EditableField;
  taskId: number;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = `edit-${taskId}-${field.field}`;
  const shared =
    "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500";

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-700"
      >
        {field.label}
        {field.unit ? (
          <span className="text-slate-400">（{field.unit}）</span>
        ) : null}
        {field.missing ? (
          <span className="rounded bg-amber-100 px-1.5 py-px text-[10px] font-semibold text-amber-900">
            待補
          </span>
        ) : null}
      </label>
      {field.input_type === "textarea" ? (
        <textarea
          id={id}
          rows={2}
          value={value}
          placeholder={field.placeholder ?? undefined}
          onChange={(e) => onChange(e.target.value)}
          className={`${shared} resize-none`}
        />
      ) : (
        <input
          id={id}
          type={field.input_type === "file" ? "text" : field.input_type}
          value={value}
          placeholder={field.placeholder ?? undefined}
          onChange={(e) => onChange(e.target.value)}
          className={shared}
        />
      )}
    </div>
  );
}
