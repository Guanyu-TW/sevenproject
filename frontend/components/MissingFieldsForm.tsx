"use client";

import { useEffect, useMemo, useState } from "react";
import type { LifeTask, MissingField } from "@/lib/api";

type Props = {
  task: LifeTask;
  /** True while the PATCH + matching round trip is in flight. */
  submitting: boolean;
  /** Receives the canonical field keys the resident filled in. */
  onConfirm: (filled: Record<string, string>) => void;
};

type TextValues = Record<string, string>;
type FileValues = Record<string, File[]>;

/**
 * Renders one input per entry in `task.missing_fields`.
 *
 * The control type comes from the backend field catalogue (`input_type`), so
 * adding a new askable field is a backend data change with no edit here.
 */
const SUPPORTED = "水電維修、居家清潔、餐飲訂購、代購採買";

export default function MissingFieldsForm({ task, submitting, onConfirm }: Props) {
  const fields = task.missing_fields;
  const intent = task.parsed_data.intent;

  // Matching filters on category first, so an unclassified task can never
  // yield a vendor. Say so up front instead of offering a dead-end form.
  if (task.category === null) {
    return (
      <div className="rounded-xl border border-slate-300 bg-slate-50 px-4 py-4">
        <p className="text-sm font-semibold text-slate-900">
          {intent === "question"
            ? "這看起來是一個問題，不是服務需求"
            : intent === "other"
              ? "我沒有辨識出具體的服務需求"
              : "目前沒有提供這類服務"}
        </p>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">
          平台目前支援 {SUPPORTED}。請在左邊換一種說法描述你需要的服務，
          例如「嘉義市西區水龍頭漏水，預算兩千」。
        </p>
      </div>
    );
  }

  const [values, setValues] = useState<TextValues>({});
  const [files, setFiles] = useState<FileValues>({});

  // A new analysis means a fresh form.
  useEffect(() => {
    setValues({});
    setFiles({});
  }, [task.id]);

  const remaining = useMemo(
    () => fields.filter((f) => f.required && !isFilled(f, values, files)),
    [fields, values, files],
  );

  function handleConfirm() {
    // Only non-empty text values go to the API; the server ignores blanks
    // anyway, but sending less keeps the request honest.
    const filled = Object.fromEntries(
      Object.entries(values)
        .map(([key, value]) => [key, value.trim()] as const)
        .filter(([, value]) => value.length > 0),
    );

    // File uploads are not wired up yet, so log what would be sent.
    const pendingFiles = Object.entries(files).filter(([, list]) => list.length > 0);
    if (pendingFiles.length > 0) {
      console.log(
        "[尚未實作上傳]",
        Object.fromEntries(
          pendingFiles.map(([key, list]) => [key, list.map((f) => f.name)]),
        ),
      );
    }

    onConfirm(filled);
  }

  return (
    <div className="space-y-3">
      {fields.length === 0 ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
          <p className="text-sm font-semibold text-emerald-900">資料已完整</p>
          <p className="text-sm text-emerald-800">
            AI 沒有偵測到缺少的欄位，可以直接尋找廠商。
          </p>
        </div>
      ) : (
        <fieldset className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-4">
          <legend className="flex items-center gap-2 px-1 text-sm font-semibold text-amber-900">
            <span aria-hidden="true">⚠</span>
            請補齊 {fields.length} 項資料
          </legend>

          <p className="mb-4 text-xs text-amber-800">
            這些是 AI 判斷派工前必須知道、但你還沒提到的資訊。
          </p>

          <div className="space-y-4">
            {fields.map((field) => (
              <FieldControl
                key={field.field}
                field={field}
                value={values[field.field] ?? ""}
                selectedFiles={files[field.field] ?? []}
                onTextChange={(next) =>
                  setValues((prev) => ({ ...prev, [field.field]: next }))
                }
                onFilesChange={(next) =>
                  setFiles((prev) => ({ ...prev, [field.field]: next }))
                }
              />
            ))}
          </div>
        </fieldset>
      )}

      <div className="space-y-2">
        <button
          type="button"
          onClick={handleConfirm}
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting ? (
            <>
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
              儲存並尋找廠商中…
            </>
          ) : (
            "確認並尋找廠商"
          )}
        </button>

        <p aria-live="polite" className="text-center text-xs">
          {remaining.length > 0 ? (
            <span className="text-amber-700">
              還有 {remaining.length} 項未填：
              {remaining.map((f) => f.label).join("、")}
              <span className="mt-0.5 block text-slate-500">
                沒填完也可以直接送出，AI 會依現有資料媒合
              </span>
            </span>
          ) : (
            <span className="text-emerald-700">所有欄位都填好了</span>
          )}
        </p>
      </div>
    </div>
  );
}

function isFilled(
  field: MissingField,
  values: TextValues,
  files: FileValues,
): boolean {
  if (field.input_type === "file") {
    return (files[field.field] ?? []).length > 0;
  }
  return (values[field.field] ?? "").trim().length > 0;
}

type ControlProps = {
  field: MissingField;
  value: string;
  selectedFiles: File[];
  onTextChange: (next: string) => void;
  onFilesChange: (next: File[]) => void;
};

function FieldControl({
  field,
  value,
  selectedFiles,
  onTextChange,
  onFilesChange,
}: ControlProps) {
  const inputId = `mf-${field.field}`;
  const hintId = field.reason ? `${inputId}-hint` : undefined;

  const shared =
    "w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500";

  return (
    <div>
      <label
        htmlFor={inputId}
        className="mb-1 block text-sm font-medium text-amber-900"
      >
        {field.label}
        {field.required ? (
          <span aria-hidden="true" className="ml-1 text-rose-600">
            *
          </span>
        ) : null}
        {field.unit ? (
          <span className="ml-1 text-xs font-normal text-amber-700">
            （{field.unit}）
          </span>
        ) : null}
      </label>

      {field.input_type === "textarea" ? (
        <textarea
          id={inputId}
          aria-describedby={hintId}
          required={field.required}
          rows={3}
          value={value}
          placeholder={field.placeholder ?? undefined}
          onChange={(e) => onTextChange(e.target.value)}
          className={`${shared} resize-none`}
        />
      ) : field.input_type === "file" ? (
        <>
          <input
            id={inputId}
            aria-describedby={hintId}
            type="file"
            required={field.required}
            multiple
            accept="image/*"
            onChange={(e) => onFilesChange(Array.from(e.target.files ?? []))}
            className="w-full cursor-pointer rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-amber-100 file:px-3 file:py-1 file:text-xs file:font-semibold file:text-amber-900 hover:file:bg-amber-200"
          />
          {selectedFiles.length > 0 ? (
            <ul className="mt-1 space-y-0.5 text-xs text-amber-800">
              {selectedFiles.map((f) => (
                <li key={f.name}>
                  {f.name}（{Math.round(f.size / 1024)} KB）
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <input
          id={inputId}
          aria-describedby={hintId}
          type={field.input_type}
          required={field.required}
          inputMode={field.input_type === "number" ? "numeric" : undefined}
          value={value}
          placeholder={field.placeholder ?? undefined}
          onChange={(e) => onTextChange(e.target.value)}
          className={shared}
        />
      )}

      {field.reason ? (
        <p id={hintId} className="mt-1 text-xs text-amber-700">
          {field.reason}
        </p>
      ) : null}
    </div>
  );
}
